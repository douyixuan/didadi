"""Fictional-only loopback HTTP contract; never contacts a homeserver."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from src.session_contract import FakeIdentityService,SessionContractError
from src.session_contract_server import handler

def run(dist):
 class LostLogout(FakeIdentityService):
  lose=True
  def logout(self,*args):
   result=super().logout(*args)
   if self.lose:self.lose=False;raise SessionContractError(503,'Fictional logout response lost after completion.')
   return result
 service=LostLogout(namespace='fixed-smoke-generation');server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None);server.RequestHandlerClass=handler(service,Path(dist),server.server_port);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}';routes=[]
 def api(route,session=None,body=None):
  routes.append(route);req=Request(base+'/api/session-contract/'+route,method='GET' if body is None else 'POST',headers={'Content-Type':'application/json',**({'X-Fictional-Session':session['session_id'],'X-Fictional-CSRF':session['csrf']} if session else {})},data=None if body is None else json.dumps(body).encode())
  try:
   with urlopen(req,timeout=5) as response:return response.status,json.load(response)
  except HTTPError as error:return error.code,json.load(error)
 try:
  with urlopen(base,timeout=5) as response:assert response.status==200 and b'Fictional session contract' in response.read()
  _,alice=api('login',body={'fixture_identity':'alice','fixture_device':'A'});_,other=api('login',body={'fixture_identity':'alice','fixture_device':'B'});_,bob=api('login',body={'fixture_identity':'bob','fixture_device':'A'})
  body={'operation':'fixed-fictional-save','base_version':1,'content':'Only fictional Alice may see this saved fixture.'};status,saved=api('document',alice,body);assert status==200;assert api('document',alice,body)==(200,saved);assert saved['version']==2
  status,data=api('workspace',bob);assert status==200 and body['content'] not in json.dumps(data);assert data['rooms'][0]['id']=='room-main';assert data['document']['name']=='Shared name.md'
  assert api('logout',alice,{'scope':'all_devices'})[0]==400;assert api('logout',alice,{'scope':'current_device'})[0]==503;assert api('workspace',alice)[0]==401;assert api('logout',alice,{'scope':'current_device'})[0]==401;assert api('workspace',other)[0]==200;assert api('workspace',bob)[0]==200
  assert api('login',body={'fixture_identity':'alice','fixture_device':'A','password':'not-accepted'})[0]==400
  assert not any('/matrix' in route or route.startswith('http') for route in routes)
  proof={'fictionalOnly':True,'builtEntryServed':True,'httpContract':True,'fixedFictionalInputs':True,'sameRoomAndPathIdentityIsolation':True,'idempotentSave':True,'lostLogoutResponseThen401':True,'currentDeviceOnly':True,'otherDeviceStillActive':True,'passwordFieldRejected':True,'realMatrixLoginOrLogoutCalls':0,'realTokensCreated':0,'persistentAccessConfigured':False};print(json.dumps(proof));return proof
 finally:server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--dist',default='client/dist');args=parser.parse_args();run(args.dist)
