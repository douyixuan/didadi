"""Presentation metadata must reflect leases, retries and observed connections only."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

from src.gateway import Gateway
from src.matrix_as import AGENT
from src.matrix_http import MatrixError


class TaskVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'tasks.sqlite';self.agent=Mock();self.agent.api.side_effect=self.api
        self.gateway=Gateway(self.path,self.agent,lease_seconds=10,retry_seconds=4,runtime_ttl_seconds=15)
        self.event={'type':'m.room.message','event_id':'$visible','sender':'@human','room_id':'!room',
            'content':{'msgtype':'m.text','body':'PRIVATE TASK INPUT','m.mentions':{'user_ids':[AGENT]}}}
        self.clock=patch('src.gateway.time.time',return_value=1000);self.now=self.clock.start();self.addCleanup(self.clock.stop)
        self.gateway.accept('fixture',[self.event])

    def api(self,method,path,data=None):
        if path.endswith('/state/m.room.encryption'):raise MatrixError(404,{'errcode':'M_NOT_FOUND'})
        return {'membership':'join','event_id':'$reply'}

    def state(self):return self.gateway.status('$visible')

    def test_waiting_claimed_expired_backoff_and_completion_metadata(self):
        self.assertEqual(self.state()['phase'],'waiting');self.assertEqual(self.state()['runtime']['state'],'unknown')
        task=self.gateway.claim();active=self.state();self.assertEqual(active['phase'],'running')
        self.assertEqual(active['lease_expires_at'],1010);self.assertNotIn(task['lease'],json.dumps(active));self.assertNotIn('PRIVATE TASK INPUT',json.dumps(active))
        self.assertIsNone(self.gateway.claim())
        self.now.return_value=1011
        expired=self.state();self.assertEqual(expired['phase'],'retry_wait');self.assertEqual(expired['retry_reason'],'lease_expired');self.assertEqual(expired['next_retry_at'],1010)
        retry=self.gateway.claim();self.assertNotEqual(retry['lease'],task['lease'])
        self.gateway.fail(retry['id'],retry['lease'],'runtime_error',retryable=True)
        delayed=self.state();self.assertEqual(delayed['phase'],'retry_wait');self.assertEqual(delayed['next_retry_at'],1019)
        self.assertEqual(delayed['retry_reason'],'runtime_error');self.assertIsNone(self.gateway.claim())
        self.now.return_value=1020;final=self.gateway.claim();self.gateway.complete(final['id'],final['lease'],'done')
        self.assertEqual(self.state()['phase'],'done');self.assertIsNone(self.state()['next_retry_at']);self.assertEqual(self.state()['attempts'],3)

    def test_reserved_lease_is_verifying_until_room_check_finishes(self):
        original=self.gateway.allowed;observed=[]
        def allowed(room):observed.append(self.state()['phase']);return original(room)
        self.gateway.allowed=allowed;self.gateway.claim()
        self.assertEqual(observed,['verifying']);self.assertEqual(self.state()['phase'],'running')

    def test_multiple_connections_tombstone_and_expiry_are_not_progress_proof(self):
        def update(session,connected):self.gateway.runtime_update({'session':session*48,'connected':connected})
        update('a',True);update('b',True);self.assertEqual(self.state()['runtime']['state'],'connected')
        update('a',False);update('a',True);self.assertEqual(self.state()['runtime']['state'],'connected')
        update('b',False);self.assertEqual(self.state()['runtime']['state'],'disconnected')
        update('b',True);self.assertEqual(self.state()['runtime']['state'],'disconnected')
        update('c',True);self.now.return_value=1016
        self.assertEqual(self.state()['runtime']['state'],'unknown');self.assertEqual(self.state()['phase'],'waiting')
        self.assertNotIn('session',self.state()['runtime'])
        update('c',False);self.assertEqual(self.state()['runtime']['state'],'disconnected')
        self.now.return_value=1032;self.assertEqual(self.state()['runtime']['state'],'unknown')

    def test_invalid_observations_and_terminal_cancel_do_not_change_claim_policy(self):
        for data in ({'session':'wrong','connected':True},{'session':'a'*48,'connected':1},{'session':'a'*48,'connected':True,'token':'bad'}):
            with self.assertRaises(ValueError):self.gateway.runtime_update(data)
        self.gateway.cancel('$visible');self.assertEqual(self.state()['phase'],'cancelled');self.assertIsNone(self.gateway.claim())

    def test_old_schema_migrates_without_exposing_or_replacing_a_live_lease(self):
        old=Path(self.tmp.name)/'old.sqlite'
        with sqlite3.connect(old) as db:
            db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,event TEXT,status TEXT,lease TEXT,until REAL,result TEXT,reply TEXT)')
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?)',('$old',json.dumps(self.event),'pending','old-private-lease',1010,None,None))
        restored=Gateway(old,self.agent);state=restored.status('$old')
        self.assertEqual(state['phase'],'verifying');self.assertEqual(state['verification_reason'],'legacy_lease_unconfirmed');self.assertNotIn('old-private-lease',json.dumps(state));self.assertIsNone(restored.claim())

    def test_retry_budget_is_visible_without_creating_another_execution(self):
        self.gateway.max_attempts=1;self.gateway.claim();self.now.return_value=1011
        state=self.state();self.assertEqual(state['phase'],'retry_wait');self.assertTrue(state['retry_limit_reached'])
        self.assertIsNone(self.gateway.claim());self.assertEqual(self.state()['phase'],'failed');self.assertEqual(self.state()['attempts'],1)
