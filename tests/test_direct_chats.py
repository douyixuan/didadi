import copy
from pathlib import Path
import sqlite3
import tempfile
import unittest
from src.direct_chats import DirectChats,DirectChatError
from src.matrix_http import MatrixError

class DirectChatsTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.db=Path(self.tmp.name)/'state.sqlite';self.user='@alice:local';self.peer='@bob:local';self.room='!direct:local';self.data={self.peer:['!older:local'],'@other:local':['!other:local']};self.calls=[];self.fail_get=False;self.fail_put=False;self.lost_put=False;self.concurrent=None;self.changed_roster=False
  with sqlite3.connect(self.db) as db:db.execute('CREATE TABLE rooms(id TEXT PRIMARY KEY)');db.execute('INSERT INTO rooms VALUES (?)',(self.room,))
  self.service=DirectChats(self.db,self.api,self.user,self.allowed)
 def allowed(self,room):
  if room!=self.room:raise DirectChatError(403,'Not allowed')
 def api(self,method,path,data=None):
  self.calls.append((method,path,copy.deepcopy(data)))
  if path=='/joined_rooms':return {'joined_rooms':[self.room]}
  if path.endswith('/state'):
   return [{'type':'m.room.member','state_key':user,'content':{'membership':'join'}} for user in [self.user,self.peer,*(['@extra:local'] if self.changed_roster else [])]]
  self.assertEqual(path,self.service.path)
  if method=='GET':
   if self.fail_get:raise MatrixError(503,{})
   if self.concurrent:
    action,self.concurrent=self.concurrent,None;action()
   return copy.deepcopy(self.data)
  if self.fail_put:raise MatrixError(503,{})
  self.data=copy.deepcopy(data)
  if self.lost_put:self.lost_put=False;raise MatrixError(503,{})
  return {}
 def result(self):return {'room_id':self.room,'kind':'direct','participants':[self.peer]}
 def test_merge_preserves_all_existing_rooms_and_retry_has_no_duplicate_or_write(self):
  result=self.service.after_create(self.result());self.assertEqual(result['direct_sync'],'synced');self.assertEqual(self.data,{self.peer:['!older:local',self.room],'@other:local':['!other:local']});puts=sum(method=='PUT' for method,_,_ in self.calls)
  self.service.after_create(self.result());self.assertEqual(sum(method=='PUT' for method,_,_ in self.calls),puts)
 def test_failed_read_never_writes_and_survives_new_service_retry_with_remote_updates(self):
  self.fail_get=True;self.assertEqual(self.service.after_create(self.result())['direct_sync'],'pending');self.assertFalse(any(method=='PUT' for method,_,_ in self.calls));self.fail_get=False;self.data['@remote:local']=['!remote:local']
  self.service=DirectChats(self.db,self.api,self.user,self.allowed);self.assertEqual(self.service.snapshot()['pending'],[{'room':self.room,'peer':self.peer}]);self.service.retry(self.room);self.assertEqual(self.data['@remote:local'],['!remote:local']);self.assertEqual(self.service.snapshot()['pending'],[])
 def test_response_lost_after_put_does_not_overwrite_new_remote_map_on_retry(self):
  self.lost_put=True;self.assertEqual(self.service.after_create(self.result())['direct_sync'],'pending');self.data['@remote:local']=['!remote:local'];puts=sum(method=='PUT' for method,_,_ in self.calls);self.service.retry(self.room);self.assertEqual(sum(method=='PUT' for method,_,_ in self.calls),puts);self.assertIn('@remote:local',self.data)
 def test_observed_remote_replacement_between_put_and_verification_is_merged(self):
  original=self.api;interleaved=False
  def api(method,path,data=None):
   nonlocal interleaved
   result=original(method,path,data)
   if method=='PUT' and not interleaved:
    interleaved=True;self.data={self.peer:['!remote-direct:local'],'@remote:local':['!remote:local']}
   return result
  self.service.api=api;self.service.after_create(self.result());self.assertEqual(self.data,{self.peer:['!remote-direct:local',self.room],'@remote:local':['!remote:local']})
 def test_remote_removal_after_success_is_not_resurrected_by_creation_retry(self):
  self.service.after_create(self.result());self.data={self.peer:['!older:local']};self.service.after_create(self.result());self.assertEqual(self.data,{self.peer:['!older:local']});self.assertEqual(self.service.snapshot()['mapped'],{})
 def test_malformed_account_data_is_not_replaced(self):
  self.data={self.peer:'wrong'};self.assertEqual(self.service.after_create(self.result())['direct_sync'],'pending');self.assertFalse(any(method=='PUT' for method,_,_ in self.calls))
  with self.assertRaises(DirectChatError):self.service.retry(self.room)
 def test_missing_data_is_empty_but_other_errors_are_not(self):
  from unittest.mock import patch
  with patch.object(self.service,'api',side_effect=MatrixError(404,{'errcode':'M_NOT_FOUND'})):self.assertEqual(self.service.read(),{})
  with patch.object(self.service,'api',side_effect=MatrixError(403,{})):
   with self.assertRaises(MatrixError):self.service.read()
 def test_retry_cannot_change_peer_room_identity_or_membership(self):
  self.service.remember(self.room,self.peer)
  with self.assertRaises(DirectChatError):self.service.remember(self.room,'@other:local')
  with self.assertRaises(DirectChatError):self.service.retry('!not-allowed:local')
  other=DirectChats(self.db,self.api,'@other:local',self.allowed)
  with self.assertRaises(DirectChatError):other.retry(self.room)
  self.changed_roster=True
  with self.assertRaises(DirectChatError):self.service.retry(self.room)
  self.assertFalse(any(method=='PUT' for method,_,_ in self.calls))
 def test_snapshot_hides_ungranted_rooms_and_other_pending_actors(self):
  self.data={self.peer:[self.room,'!secret:local'],'@secret:local':['!secret:local']};self.service.remember(self.room,self.peer);other=DirectChats(self.db,self.api,'@other:local',self.allowed);other.remember(self.room,'@otherpeer:local')
  self.assertEqual(self.service.snapshot(),{'mapped':{self.room:[self.peer]},'pending':[{'room':self.room,'peer':self.peer}]})
 def test_non_direct_creation_does_not_access_account_data(self):
  value={'room_id':self.room,'kind':'group','participants':[]};self.assertEqual(self.service.after_create(value),value);self.assertEqual(self.calls,[])
