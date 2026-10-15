import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import unquote

from src.gateway import Gateway, TaskError
from src.matrix_as import AGENT, EchoAgent
from src.matrix_http import MatrixError
from scripts.document_worker import once, reconcile
from src.gitdocs import GitDocs


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.forbidden, self.unavailable = set(), set()
        self.agent = Mock()
        self.agent.api.side_effect = self.api
        self.gateway = Gateway(self.root / 'tasks.sqlite', self.agent, max_attempts=3, retry_seconds=0)

    def event(self, identifier, room):
        return {'type': 'm.room.message', 'event_id': identifier, 'room_id': room, 'sender': '@alice:local',
                'content': {'body': 'hello', 'msgtype': 'm.text', 'm.mentions': {'user_ids': [AGENT]}}}

    def api(self, method, path, data=None):
        path=unquote(path)
        if any(room in path for room in self.forbidden):
            raise MatrixError(403, {'errcode': 'M_FORBIDDEN'})
        if any(room in path for room in self.unavailable):
            raise MatrixError(503, {'errcode': 'M_UNKNOWN'})
        if path.endswith('/state/m.room.encryption'):
            raise MatrixError(404, {'errcode': 'M_NOT_FOUND'})
        return {'membership': 'join', 'event_id': '$reply'}

    def test_mixed_forbidden_and_healthy_batch_is_durably_acked(self):
        self.forbidden.add('!gone')
        self.gateway.accept('mixed', [self.event('$a','!gone'), self.event('$b','!ok')])
        self.assertIsNone(self.gateway.status('$a'))
        self.assertEqual(self.gateway.claim()['id'], '$b')
        with self.gateway.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM transactions').fetchone()[0], 1)

    def test_transient_event_is_unverified_then_rechecks_without_blocking_healthy(self):
        self.unavailable.add('!slow')
        self.gateway.accept('mixed', [self.event('$a','!slow'), self.event('$b','!ok')])
        self.assertEqual(self.gateway.status('$a')['status'], 'unverified')
        self.assertEqual(self.gateway.claim()['id'], '$b')
        self.unavailable.clear()
        self.assertEqual(self.gateway.claim()['id'], '$a')

    def test_forbidden_at_claim_never_reaches_document_write(self):
        event = self.event('$doc','!gone')
        event['content']['org.didadi.document'] = {'action':'write','content':'secret','base_blob':None}
        self.gateway.accept('one', [event])
        self.forbidden.add('!gone')
        store = GitDocs(self.root / 'docs.git')
        with patch('scripts.document_worker.request', return_value={'task':self.gateway.claim()}):
            self.assertFalse(once('unused','token',store))
        self.assertEqual(self.gateway.status('$doc')['status'], 'failed')
        self.assertEqual(store.history('demo.md'), [])
        self.assertIsNone(self.gateway.claim())

    def test_retry_budget_terminal_and_exponential_backoff(self):
        self.gateway.accept('one', [self.event('$a','!ok')])
        for attempt in range(1,4):
            task = self.gateway.claim()
            self.assertEqual(task['attempts'], attempt)
            response = self.gateway.fail(task['id'], task['lease'], retryable=True)
        self.assertEqual(response, {'status':'failed','retryable':False})
        self.assertIsNone(self.gateway.claim())
        self.assertEqual(self.gateway.status('$a')['attempts'], 3)
        other = Gateway(self.root / 'backoff.sqlite', self.agent, retry_seconds=2)
        other.accept('one', [self.event('$b','!ok')])
        task = other.claim()
        other.fail(task['id'],task['lease'],retryable=True)
        self.assertIsNone(other.claim())

    def test_completion_forbidden_is_typed_and_terminal(self):
        self.gateway.accept('one', [self.event('$a','!ok')])
        task = self.gateway.claim(); self.forbidden.add('!ok')
        with self.assertRaises(TaskError) as caught:
            self.gateway.complete('$a',task['lease'],'answer')
        self.assertEqual(caught.exception.code,'room_forbidden')
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.gateway.status('$a')['status'],'failed')
        self.assertIsNone(self.gateway.claim())

    def test_expired_runtime_crashes_eventually_stop_being_claimed(self):
        self.gateway.accept('one', [self.event('$a','!ok')])
        for _ in range(3):
            self.assertIsNotNone(self.gateway.claim())
            with self.gateway.db() as db: db.execute('UPDATE tasks SET until=0')
        self.assertIsNone(self.gateway.claim())
        self.assertEqual(self.gateway.status('$a')['last_error'],'attempts_exhausted')

    def test_existing_database_migrates_without_losing_tasks(self):
        path = self.root / 'old.sqlite'
        with sqlite3.connect(path) as db:
            db.executescript("CREATE TABLE transactions(id TEXT PRIMARY KEY);CREATE TABLE tasks(id TEXT PRIMARY KEY,event TEXT NOT NULL,status TEXT DEFAULT 'pending',lease TEXT,until REAL DEFAULT 0,result TEXT,reply TEXT);")
            db.execute('INSERT INTO tasks(id,event) VALUES (?,?)', ('$old',json.dumps(self.event('$old','!ok'))))
        self.assertEqual(Gateway(path,self.agent).claim()['id'],'$old')

    def test_legacy_errors_are_isolated_per_event(self):
        legacy = EchoAgent('unused','unused');legacy.api = Mock(side_effect=self.api)
        gone, healthy = self.event('$a','!gone'), self.event('$b','!ok')
        for event in [gone,healthy]:event['content']['body']='!echo hello'
        self.forbidden.add('!gone');legacy.process([gone,healthy])
        sends = [call for call in legacy.api.call_args_list if call.args[0]=='PUT']
        self.assertEqual(len(sends),1)
        self.assertIn('!ok',unquote(sends[0].args[1]))

    def test_validate_revocation_after_claim_prevents_git_write(self):
        event = self.event('$doc','!ok')
        event['content']['org.didadi.document'] = {'action':'write','content':'private','base_blob':None}
        self.gateway.accept('doc', [event])
        task = self.gateway.claim()
        self.forbidden.add('!ok')
        store = GitDocs(self.root / 'revoked.git')
        def api(base, method, path, token, data=None, query=None):
            if path == '/agent/tasks': return {'task':task}
            if path == '/agent/validate': return self.gateway.validate(data['id'],data['lease'])
            if path == '/agent/fail': return {'status':'failed'}
            raise AssertionError(path)
        with patch('scripts.document_worker.request',side_effect=api), patch('scripts.agent_worker.request',side_effect=api):
            with self.assertRaises(TaskError): once('unused','token',store)
        self.assertEqual(store.history('demo.md'), [])
        self.assertEqual(self.gateway.status('$doc')['status'],'failed')

    def test_failed_operation_is_abandoned_durably_without_changing_document(self):
        store=GitDocs(self.root / 'abandoned.git')
        item=store.write('demo.md','retained',None,operation='$abandoned',notification={'task_id':'$abandoned'})
        with patch('scripts.document_worker.request',return_value={'task':{'status':'failed','last_error':'room_forbidden'}}):
            reconcile('unused','token',store)
        reopened=GitDocs(store.root)
        self.assertEqual(reopened.pending(),[])
        self.assertEqual(reopened.snapshot('demo.md')['commit'],item['commit'])
        ref=reopened._operation_ref('$abandoned').replace('/operations/','/notified/')
        receipt=json.loads(reopened._git('cat-file','blob',ref))
        self.assertEqual(receipt['reason'],'room_forbidden')
        reopened.abandon('$abandoned','room_forbidden')
        self.assertEqual(reopened.pending(),[])

    def test_invalid_lease_is_typed_retryable(self):
        self.gateway.accept('one',[self.event('$a','!ok')])
        self.gateway.claim()
        with self.assertRaises(TaskError) as caught:
            self.gateway.complete('$a','obsolete','answer')
        self.assertEqual(caught.exception.code,'invalid_lease')
        self.assertTrue(caught.exception.retryable)

    def test_malformed_events_cannot_poison_mixed_batch(self):
        invalid=[]
        for change in [{'m.mentions':None},{'m.mentions':{'user_ids':None}}]:
            event=self.event('$bad'+str(len(invalid)),'!ok');event['content'].update(change);invalid.append(event)
        invalid.extend([None,{'content':None}])
        self.gateway.accept('mixed-invalid',invalid+[self.event('$healthy','!ok')])
        self.assertEqual(self.gateway.claim()['id'],'$healthy')
        legacy=EchoAgent('unused','unused');legacy.api=Mock(side_effect=self.api)
        healthy=self.event('$echo','!ok');healthy['content']['body']='!echo hi'
        legacy.process(invalid+[healthy])
        self.assertEqual(len([call for call in legacy.api.call_args_list if call.args[0]=='PUT']),1)

    def test_claim_and_validate_recheck_lease_after_network_check(self):
        self.gateway.accept('one',[self.event('$a','!ok')])
        original=self.gateway.allowed
        def invalidate(room):
            with self.gateway.db() as db:
                db.execute("UPDATE tasks SET status='failed',lease=NULL WHERE id='$a'")
            return True
        self.gateway.allowed=invalidate
        self.assertIsNone(self.gateway.claim())
        with self.gateway.db() as db: db.execute("UPDATE tasks SET status='pending',until=0 WHERE id='$a'")
        self.gateway.allowed=original
        task=self.gateway.claim()
        self.gateway.allowed=invalidate
        with self.assertRaises(TaskError) as caught:self.gateway.validate(task['id'],task['lease'])
        self.assertEqual(caught.exception.code,'invalid_lease')

    def test_completion_checks_terminal_lease_after_authorization_network_call(self):
        self.gateway.accept('one',[self.event('$a','!ok')])
        task=self.gateway.claim()
        def terminate(room):
            self.gateway.fail(task['id'],task['lease'],'room_forbidden')
            return True
        self.gateway.allowed=terminate
        self.agent.api.reset_mock()
        with self.assertRaises(TaskError) as caught:self.gateway.complete(task['id'],task['lease'],'fixed answer')
        self.assertEqual(caught.exception.code,'invalid_lease')
        self.assertFalse(any(call.args[0]=='PUT' for call in self.agent.api.call_args_list))
        self.assertEqual(self.gateway.status(task['id'])['status'],'failed')
