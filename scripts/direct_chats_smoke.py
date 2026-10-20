"""m.direct on existing isolated test identities; preferences never add room access."""
import argparse
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
from urllib.request import Request,urlopen
import uuid
from src.direct_chats import DirectChats
from src.matrix_as import PREFIX
from src.matrix_http import request,segment,MatrixError
from src.runtime_socket import loopback_url

def run(base,matrix_url,state_file,other_room):
 loopback_url(base,'http');loopback_url(matrix_url,'http');state=json.loads(Path(state_file).read_text());session=json.load(urlopen(base+'/api/session',timeout=20));actor=session['userId'];peer=session['roomCreation']['contacts'][0];path='/user/'+segment(actor)+'/account_data/m.direct'
 def native(method,route,data=None):return request(matrix_url,method,PREFIX+route,state['tokens'][0],data)
 def mapping():
  try:return native('GET',path)
  except MatrixError as error:
   if error.status==404 and error.body.get('errcode')=='M_NOT_FOUND':return {}
   raise
 def api(route,data=None):
  req=Request(base+route,method='POST' if data is not None else 'GET',headers={'X-CSRF-Token':session['csrf'],'Content-Type':'application/json'},data=json.dumps(data).encode() if data is not None else None)
  return json.load(urlopen(req,timeout=20))
 def peer_mapping():
  try:return request(matrix_url,'GET',PREFIX+'/user/'+segment(peer)+'/account_data/m.direct',state['tokens'][1])
  except MatrixError as error:
   if error.status==404 and error.body.get('errcode')=='M_NOT_FOUND':return {}
   raise
 peer_before=copy.deepcopy(peer_mapping())
 before=copy.deepcopy(mapping());operation={'name':'Direct account data '+uuid.uuid4().hex[:6],'operation':str(uuid.uuid4()),'kind':'direct','participants':[peer],'invite_agent':False}
 created=api('/api/rooms',operation);room=created['room_id'];assert created['direct_sync']=='synced',created;after=mapping();assert room in after[peer]
 for user,rooms in before.items():assert all(item in after[user] for item in rooms)
 assert api('/api/rooms',operation)['room_id']==room;assert mapping()[peer].count(room)==1
 # Independent native client adds another existing synthetic room, preserving current data.
 remote=mapping();remote.setdefault(peer,[])
 if other_room not in remote[peer]:remote[peer].append(other_room)
 native('PUT',path,remote);assert mapping()[peer].count(other_room)==1
 # External removal is authoritative for a completed local receipt.
 remote=mapping();remote[peer]=[item for item in remote[peer] if item!=room];native('PUT',path,remote)
 assert room not in api('/api/direct-chats')['mapped'];assert api('/api/rooms',operation)['direct_sync']=='synced';assert room not in mapping()[peer]
 def allowed(value):assert value==room
 with tempfile.TemporaryDirectory() as root:
  db=Path(root)/'pending.sqlite'
  with sqlite3.connect(db) as connection:connection.execute('CREATE TABLE rooms(id TEXT PRIMARY KEY)');connection.execute('INSERT INTO rooms VALUES (?)',(room,))
  failed=False;put_count=0
  def lose_response(method,route,data=None):
   nonlocal failed,put_count
   result=native(method,route,data)
   if method=='PUT':
    put_count+=1
    if not failed:failed=True;raise MatrixError(503,{})
   return result
  service=DirectChats(db,lose_response,actor,allowed);value={**created,'participants':[peer],'kind':'direct'};assert service.after_create(value)['direct_sync']=='pending';assert room in mapping()[peer]
  # The remote client updates while this local durable receipt is pending.
  remote=mapping();remote.setdefault(actor,[])
  if other_room not in remote[actor]:remote[actor].append(other_room)
  native('PUT',path,remote)
  recovered=DirectChats(db,native,actor,allowed);assert recovered.snapshot()['pending']==[{'room':room,'peer':peer}];assert recovered.retry(room)['status']=='synced';assert recovered.snapshot()['pending']==[];assert put_count==1;assert other_room in mapping()[actor];assert mapping()[peer].count(room)==1
 current=mapping();assert other_room in current[peer] and other_room in current[actor]
 sync=native('GET','/sync',None)  # existing synthetic identity, standard account_data transport
 direct=[event for event in sync.get('account_data',{}).get('events',[]) if event['type']=='m.direct'];assert direct and direct[-1]['content']==current
 snapshot=api('/api/direct-chats');assert peer in snapshot['mapped'][room]
 # No unrestricted account-data route is exposed to the browser.
 from urllib.error import HTTPError
 try:urlopen(base+'/matrix'+PREFIX+path,timeout=10);raise AssertionError('Raw account data unexpectedly proxied')
 except HTTPError as error:assert error.code==403
 assert peer_mapping()==peer_before
 proof={'peerAccountDataUnchanged':True,'base':base,'room':room,'peer':peer,'actor':actor,'realMatrix':True,'newPrivateRooms':1,'otherExistingRoom':other_room,'createdDirectMapping':True,'preservedPriorMappings':True,'idempotentSameRoom':True,'remoteUpdateObserved':True,'remoteRemovalRespected':True,'lostPutResponseDurableRetry':True,'serviceRestartRecovered':True,'pendingRetryDidNotRepeatPut':True,'standardSyncAccountDataObserved':True,'rawAccountDataRouteRejected':True,'noNewIdentityOrCredential':True,'concurrentWholeEventCAS':False};print(json.dumps(proof));return proof
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--matrix-url',required=True);parser.add_argument('--state-file',required=True);parser.add_argument('--other-room',required=True);args=parser.parse_args();run(args.url,args.matrix_url,args.state_file,args.other_room)
