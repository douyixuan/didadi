import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from src.gateway import Gateway
from src.matrix_as import AGENT
from src.matrix_http import MatrixError


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'tasks.sqlite'
        self.agent = Mock()
        self.agent.api.side_effect = self.api
        self.gateway = Gateway(self.path, self.agent)
        self.event = {'type': 'm.room.message', 'event_id': '$task', 'room_id': '!r:local',
                      'sender': '@alice:local', 'content': {'msgtype': 'm.text', 'body': 'summarize',
                      'm.mentions': {'user_ids': [AGENT]}}}

    def api(self, method, path, data=None):
        if path.endswith('/state/m.room.encryption'):
            raise MatrixError(404, {'errcode': 'M_NOT_FOUND'})
        return {'membership': 'join', 'event_id': '$reply'}

    def test_replay_restart_and_event_deduplication(self):
        for txn in ['one', 'one', 'two']:
            self.gateway.accept(txn, [self.event])
        restored = Gateway(self.path, self.agent)
        task = restored.claim()
        self.assertEqual(task['event'], self.event)
        self.assertIsNone(restored.claim())
        with restored.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 2)

    def test_concurrent_claim_and_expired_lease_recovery(self):
        self.gateway.accept('one', [self.event])
        with ThreadPoolExecutor(2) as pool:
            tasks = list(pool.map(lambda _: Gateway(self.path, self.agent).claim(), range(2)))
        first = next(t for t in tasks if t)
        self.assertEqual(sum(t is not None for t in tasks), 1)
        with self.gateway.db() as db:
            db.execute('UPDATE tasks SET until=0')
        second = self.gateway.claim()
        self.assertNotEqual(first['lease'], second['lease'])
        with self.assertRaises(ValueError):
            self.gateway.complete(first['id'], first['lease'], 'stale')

    def test_completion_retries_and_thread_root(self):
        self.event['content']['m.relates_to'] = {'rel_type': 'm.thread', 'event_id': '$root'}
        self.gateway.accept('one', [self.event])
        task = self.gateway.claim()
        self.assertEqual(self.gateway.complete(task['id'], task['lease'], 'answer')['event_id'], '$reply')
        self.gateway.complete(task['id'], task['lease'], 'answer')
        sends = [c for c in self.agent.api.call_args_list if c.args[0] == 'PUT']
        self.assertEqual(len(sends), 1)
        self.assertEqual(sends[0].args[2]['m.relates_to']['event_id'], '$root')
        self.assertIsNone(self.gateway.claim())

    def test_failed_send_recovers_persisted_result(self):
        self.gateway.accept('one', [self.event])
        task = self.gateway.claim()
        def fail(method, path, data=None):
            if method == 'PUT':
                raise RuntimeError('offline')
            return self.api(method, path, data)
        self.agent.api.side_effect = fail
        with self.assertRaises(RuntimeError):
            self.gateway.complete(task['id'], task['lease'], 'fixed answer')
        with self.gateway.db() as db:
            db.execute('UPDATE tasks SET until=0')
        recovered = Gateway(self.path, self.agent).claim()
        self.assertEqual(recovered['result'], 'fixed answer')
        self.agent.api.side_effect = self.api
        self.gateway.complete(recovered['id'], recovered['lease'], recovered['result'])

    def test_encryption_and_membership_fail_closed(self):
        self.agent.api.side_effect = None
        self.agent.api.return_value = {'algorithm': 'encrypted'}
        self.gateway.accept('encrypted', [self.event])
        self.assertIsNone(self.gateway.claim())
        self.agent.api.side_effect = MatrixError(500, {})
        self.gateway.accept('unavailable', [self.event])
        with self.gateway.db() as db:
            self.assertIsNotNone(db.execute("SELECT * FROM transactions WHERE id='unavailable'").fetchone())
            self.assertEqual(db.execute('SELECT status FROM tasks').fetchone()[0], 'unverified')
        self.agent.api.side_effect = self.api
        self.gateway.accept('valid', [self.event])
        task = self.gateway.claim()
        self.agent.api.side_effect = None
        self.agent.api.return_value = {'algorithm': 'encrypted'}
        with self.assertRaises(ValueError):
            self.gateway.complete(task['id'], task['lease'], 'answer')

    def test_ignores_unmentioned_self_and_encrypted_events(self):
        for changes in ({'sender': AGENT}, {'type': 'm.room.encrypted'}, {'content': {'body': 'hello'}}):
            event = copy.deepcopy(self.event)
            event.update(changes)
            self.gateway.accept(str(changes), [event])
        self.assertIsNone(self.gateway.claim())

    def test_http_credentials_bind_fixed_identity_and_durable_ack(self):
        from http.server import ThreadingHTTPServer
        import threading
        from src.matrix_as import make_handler
        from src.matrix_http import request
        self.agent.process = Mock()
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
            self.agent, 'homeserver-secret', self.gateway, 'worker-secret'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f'http://127.0.0.1:{server.server_port}'
            for token in [None, 'homeserver-secret', 'wrong']:
                with self.assertRaises(MatrixError) as caught:
                    request(base, 'GET', '/agent/tasks', token)
                self.assertEqual(caught.exception.status, 403)
            for token in [None, 'homeserver-secret', 'wrong']:
                with self.assertRaises(MatrixError) as caught:
                    request(base, 'POST', '/agent/runtime', token, {'session':'a'*48,'connected':True})
                self.assertEqual(caught.exception.status,403)
            request(base, 'POST', '/agent/runtime', 'worker-secret', {'session':'a'*48,'connected':True})
            with self.assertRaises(MatrixError):request(base,'POST','/agent/runtime','worker-secret',{'session':'bad','connected':True})
            request(base, 'PUT', '/_matrix/app/v1/transactions/http', 'homeserver-secret', {'events': [self.event]})
            restored = Gateway(self.path, self.agent)
            with restored.db() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM tasks').fetchone()[0], 1)
            task = request(base, 'GET', '/agent/tasks', 'worker-secret')['task']
            self.assertEqual(task['agent'], AGENT)
            with self.assertRaises(MatrixError):
                request(base, 'POST', '/agent/complete', 'worker-secret',
                        {'id': task['id'], 'lease': 'wrong', 'result': 'answer'})
            reply = request(base, 'POST', '/agent/complete', 'worker-secret',
                            {'id': task['id'], 'lease': task['lease'], 'result': 'answer'})
            self.assertEqual(reply['event_id'], '$reply')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
