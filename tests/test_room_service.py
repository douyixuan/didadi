import concurrent.futures
from pathlib import Path
import sqlite3
import tempfile
import unittest
from src.room_service import RoomService,RoomError,ROOM_KIND
from src.matrix_as import AGENT
from src.matrix_http import MatrixError

class RoomServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.db=Path(self.tmp.name)/'rooms.sqlite'
        with sqlite3.connect(self.db) as db:db.execute('CREATE TABLE rooms(id TEXT PRIMARY KEY,operation TEXT UNIQUE)')
        self.user='@human:didadi.localhost';self.peer='@bob_fixture:didadi.localhost';self.payload=None;self.calls=[];self.lose=False;self.mutate=lambda state:state;self.visibility='private'
        self.service=RoomService(self.db,self.api,self.user,[self.peer])
        self.data={'operation':'stable-operation','name':'A private group'}
    def api(self,method,path,data=None):
        self.calls.append((method,path,data))
        if path=='/createRoom':
            if self.payload:raise MatrixError(400,{'errcode':'M_ROOM_IN_USE'})
            self.payload=data
            if self.lose:raise MatrixError(503,{'errcode':'M_UNKNOWN'})
            return {'room_id':'!created:didadi.localhost'}
        if path.startswith('/directory/room/'):return {'room_id':'!created:didadi.localhost'}
        if path.startswith('/directory/list/room/'):return {'visibility':self.visibility}
        if path.endswith('/state'):
            state=[{'type':'m.room.create','sender':self.user,'content':{'m.federate':False}},{'type':'m.room.join_rules','state_key':'','content':{'join_rule':'invite'}},{'type':'m.room.member','state_key':self.user,'content':{'membership':'join'}},*self.payload['initial_state']]
            state.extend({'type':'m.room.member','state_key':peer,'content':{'membership':'invite','is_direct':self.payload['is_direct']}} for peer in self.payload['invite'])
            return self.mutate(state)
        raise AssertionError(path)
    def test_default_group_and_channel_are_private_without_agent(self):
        result=self.service.create(self.data);self.assertEqual(result['kind'],'group');self.assertFalse(result['invite_agent']);self.assertEqual(self.payload['invite'],[]);self.assertEqual(self.payload['visibility'],'private');self.assertEqual(self.payload['creation_content'],{'m.federate':False});self.assertEqual(self.payload['preset'],'private_chat');self.assertFalse(self.payload['is_direct']);self.assertEqual(self.service.create(self.data),result)
        for change in ({'name':'different'},{'kind':'channel'},{'invite_agent':True},{'participants':[self.peer]}):
            with self.subTest(change=change),self.assertRaises(RoomError) as error:self.service.create({**self.data,**change})
            self.assertEqual(error.exception.status,409)
        self.payload=None;self.service.create({**self.data,'operation':'channel-operation','kind':'channel'});self.assertEqual(next(item['content']['kind'] for item in self.payload['initial_state'] if item['type']==ROOM_KIND),'channel');self.assertEqual(self.payload['invite'],[])
    def test_direct_and_explicit_agent_invitation_have_distinct_rosters(self):
        self.service.create({**self.data,'kind':'direct','participants':[self.peer]});self.assertEqual(self.payload['invite'],[self.peer]);self.assertTrue(self.payload['is_direct'])
        self.payload=None;self.service.create({**self.data,'operation':'agent-group','invite_agent':True,'participants':[self.peer]});self.assertEqual(self.payload['invite'],[self.peer,AGENT]);self.assertFalse(self.payload['is_direct'])
    def test_unsupported_visibility_contacts_and_direct_options_fail_before_create(self):
        for change in ({'visibility':'public'},{'participants':['@third:external.invalid']},{'kind':'direct'},{'kind':'direct','participants':[self.peer],'invite_agent':True},{'kind':[]},{'invite_agent':'yes'},{'participants':[self.peer,self.peer]}):
            with self.subTest(change=change),self.assertRaises(RoomError):self.service.create({**self.data,**change})
        self.assertEqual(self.calls,[])
    def test_lost_create_response_recovers_only_same_verified_intent(self):
        self.lose=True
        with self.assertRaises(RoomError) as error:self.service.create(self.data)
        self.assertEqual(error.exception.status,503)
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM rooms').fetchone()[0],0)
        with self.assertRaises(RoomError):self.service.create({**self.data,'name':'changed'})
        result=self.service.create(self.data);self.assertEqual(result['room_id'],'!created:didadi.localhost');self.assertEqual(sum(path=='/createRoom' for _,path,_ in self.calls),2)
    def test_recovered_foreign_or_changed_room_is_never_added(self):
        self.lose=True
        with self.assertRaises(RoomError):self.service.create(self.data)
        self.mutate=lambda state:[{**event,'sender':'@other:didadi.localhost'} if event['type']=='m.room.create' else event for event in state]
        with self.assertRaises(RoomError):self.service.create(self.data)
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM rooms').fetchone()[0],0)
        self.mutate=lambda state:state;self.visibility='public'
        with self.assertRaises(RoomError):self.service.create(self.data)
        self.visibility='private';self.mutate=lambda state:[event for event in state if event['type']!=ROOM_KIND]
        with self.assertRaises(RoomError):self.service.create(self.data)
    def test_group_and_channel_recovery_reject_unrequested_members(self):
        self.lose=True
        for kind in ['group','channel']:
            self.payload=None;self.mutate=lambda state:state;data={**self.data,'operation':kind+'-changed-roster','kind':kind}
            with self.assertRaises(RoomError):self.service.create(data)
            self.mutate=lambda state:state+[{'type':'m.room.member','state_key':'@unrequested:didadi.localhost','content':{'membership':'invite'}}]
            with self.assertRaises(RoomError) as error:self.service.create(data)
            self.assertEqual(error.exception.status,409)
        with sqlite3.connect(self.db) as db:self.assertEqual(db.execute('SELECT count(*) FROM rooms').fetchone()[0],0)

    def test_concurrent_retries_create_only_one_room_and_preserve_legacy_rows(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(lambda _:self.service.create(self.data),range(6)))
        self.assertTrue(all(result==results[0] for result in results));self.assertEqual(sum(path=='/createRoom' for _,path,_ in self.calls),1)
        with sqlite3.connect(self.db) as db:db.execute('INSERT INTO rooms VALUES (?,?)',('!legacy:didadi.localhost','legacy-operation'))
        with self.assertRaises(RoomError):self.service.create({**self.data,'operation':'legacy-operation'})
