from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from src.session_contract import FakeIdentityService,SessionContractError
from src.session_contract_server import handler

class SessionContractTests(unittest.TestCase):
 def setUp(self):self.now=0;self.service=FakeIdentityService(clock=lambda:self.now,ttl=60)
 def login(self,user='alice',device='A'):return self.service.login({'fixture_identity':user,'fixture_device':device})
 def test_fixed_fictional_values_only_and_no_auth_transport(self):
  with patch('urllib.request.urlopen',side_effect=AssertionError('Real transport forbidden')):
   session=self.login();self.assertTrue(session['fictional']);self.assertTrue(session['session_id'].startswith('fictional-'));self.assertNotIn('access_token',session);self.assertIn('Alice',self.service.workspace(session['session_id'])['document']['content'])
  for data in [{'fixture_identity':'real-user','fixture_device':'A'},{'fixture_identity':'alice','fixture_device':'A','password':'never-read'},{'fixture_identity':'alice','fixture_device':'real-device'}]:
   with self.assertRaises(SessionContractError):self.service.login(data)
 def test_identical_room_ids_and_document_names_do_not_cross_identities(self):
  alice,bob=self.login(),self.login('bob');a=self.service.workspace(alice['session_id']);b=self.service.workspace(bob['session_id']);self.assertEqual(a['rooms'][0]['id'],b['rooms'][0]['id']);self.assertEqual(a['document']['name'],b['document']['name']);self.assertNotEqual(a['document']['content'],b['document']['content'])
  self.service.save(alice['session_id'],alice['csrf'],{'operation':'alice-save-0001','base_version':1,'content':'Private fictional Alice draft'});self.assertNotIn('Private fictional Alice draft',json.dumps(self.service.workspace(bob['session_id'])))
 def test_save_response_loss_retry_is_idempotent_and_request_bound(self):
  a=self.login();body={'operation':'operation-0001','base_version':1,'content':'Saved once'};one=self.service.save(a['session_id'],a['csrf'],body);self.assertEqual(self.service.save(a['session_id'],a['csrf'],body),one);self.assertEqual(one['version'],2)
  with self.assertRaises(SessionContractError):self.service.save(a['session_id'],a['csrf'],{**body,'content':'Different'})
  with self.assertRaises(SessionContractError):self.service.save(a['session_id'],a['csrf'],{**body,'operation':'operation-0002'})
  with self.assertRaises(SessionContractError):self.service.save(a['session_id'],'wrong',body)
 def test_only_current_device_logout_and_other_device_is_valid(self):
  a,b=self.login(),self.login(device='B')
  with self.assertRaises(SessionContractError):self.service.logout(a['session_id'],a['csrf'],{'scope':'all_devices'})
  self.assertEqual(self.service.logout(a['session_id'],a['csrf'],{'scope':'current_device'})['scope'],'current_device');self.assertIn('Alice',self.service.workspace(b['session_id'])['document']['content'])
  with self.assertRaises(SessionContractError) as error:self.service.workspace(a['session_id'])
  self.assertEqual(error.exception.status,401)
 def test_new_same_device_session_and_expiration_do_not_affect_other_devices(self):
  old=self.login();other=self.login(device='B');current=self.login()
  with self.assertRaises(SessionContractError):self.service.workspace(old['session_id'])
  self.service.workspace(current['session_id']);self.service.workspace(other['session_id']);self.now=61
  with self.assertRaises(SessionContractError) as error:self.service.workspace(current['session_id'])
  self.assertEqual(error.exception.status,401);self.assertNotIn(current['session_id'],self.service.receipts)
 def test_service_restart_has_no_persisted_session_or_document_mutation(self):
  a=self.login();self.service.save(a['session_id'],a['csrf'],{'operation':'restart-save','base_version':1,'content':'Memory only'});new=FakeIdentityService();new.login({'fixture_identity':'bob','fixture_device':'A'})
  with self.assertRaises(SessionContractError):new.workspace(a['session_id'])
  self.assertNotIn('Memory only',new.workspace(new.login({'fixture_identity':'alice','fixture_device':'A'})['session_id'])['document']['content'])

class SessionContractHTTPTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.dist=Path(self.tmp.name);(self.dist/'session-contract.html').write_text('<h1>Fictional only</h1>');self.service=FakeIdentityService();self.server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None);self.server.RequestHandlerClass=handler(self.service,self.dist,self.server.server_port);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();self.addCleanup(self.close);self.base=f'http://127.0.0.1:{self.server.server_port}'
 def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
 def api(self,route,session=None,body=None,headers=None):
  req=Request(self.base+route,method='POST' if body is not None else 'GET',headers={'Content-Type':'application/json',**({'X-Fictional-Session':session['session_id'],'X-Fictional-CSRF':session['csrf']} if session else {}),**(headers or {})},data=json.dumps(body).encode() if body is not None else None)
  try:
   with urlopen(req,timeout=5) as response:return response.status,json.load(response)
  except HTTPError as error:return error.code,json.load(error)
 def test_http_contract_is_separate_from_matrix_and_has_no_identity_overrides(self):
  status,a=self.api('/api/session-contract/login',body={'fixture_identity':'alice','fixture_device':'A'});self.assertEqual(status,200);self.assertEqual(self.api('/api/session-contract/workspace',a)[0],200)
  for route in ['/matrix/_matrix/client/v3/login','/api/session','/api/session-contract/workspace?user_id=@bob']:
   self.assertIn(self.api(route,a)[0],{400,404})
  self.assertEqual(self.api('/api/session-contract/document',a,{'user_id':'bob','operation':'operation','base_version':1,'content':'invalid'})[0],400)
  self.assertEqual(self.api('/api/session-contract/logout',a,{'scope':'current_device'},headers={'Origin':'https://external.invalid'})[0],403);self.assertEqual(self.api('/api/session-contract/logout',a,{'scope':'current_device'},headers={'X-Fictional-CSRF':'wrong'})[0],403)
  _,b=self.api('/api/session-contract/login',body={'fixture_identity':'alice','fixture_device':'B'});self.assertEqual(self.api('/api/session-contract/logout',a,{'scope':'current_device'})[0],200);self.assertEqual(self.api('/api/session-contract/workspace',a)[0],401);self.assertEqual(self.api('/api/session-contract/workspace',b)[0],200)
 def test_static_preview_is_no_store_and_cannot_read_parent_files(self):
  with urlopen(self.base,timeout=5) as response:self.assertIn(b'Fictional only',response.read());self.assertEqual(response.headers['Cache-Control'],'no-store');self.assertEqual(response.headers['X-Frame-Options'],'DENY')
  self.assertEqual(self.api('/../outside.json')[0],404)
