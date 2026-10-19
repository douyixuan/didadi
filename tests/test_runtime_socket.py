from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect
from scripts.document_worker import once, render
from scripts.websocket_worker import SocketTransport, connect_runtime
from src.gateway import Gateway, TaskError
from src.gitdocs import GitDocs
from src.matrix_as import AGENT
from src.matrix_http import MatrixError
from src.runtime_socket import bridge


class RuntimeSocketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.agent = Mock(); self.agent.api.side_effect = self.api
        self.gateway = Gateway(self.root/'tasks.sqlite', self.agent)
        self.event = {'type':'m.room.message','event_id':'$task','room_id':'!room','sender':'@human',
            'content':{'msgtype':'m.text','body':'fixture','m.mentions':{'user_ids':[AGENT]},
                       'org.didadi.document':{'action':'write','content':'# Socket fixture\n','base_blob':None}}}
        self.store = GitDocs(self.root/'docs.git')
        self.transport_patch = patch('src.runtime_socket.request', side_effect=self.backend)
        self.transport_patch.start(); self.addCleanup(self.transport_patch.stop)
        self.server = bridge('http://127.0.0.1:1', 'fixture-token', 0, wait_seconds=.1)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)
        self.url = 'ws://127.0.0.1:' + str(self.server.socket.getsockname()[1]) + '/runtime'

    def close(self): self.server.shutdown(); self.thread.join(timeout=3)
    def api(self, method, path, data=None):
        if path.endswith('/state/m.room.encryption'): raise MatrixError(404, {'errcode':'M_NOT_FOUND'})
        return {'membership':'join','event_id':'$reply'}
    def backend(self, base, method, path, token, data=None, query=None):
        try:
            if path == '/agent/tasks': return {'task':self.gateway.claim()}
            if path == '/agent/status': return {'task':self.gateway.status(query['id'])}
            if path == '/agent/validate': return self.gateway.validate(data['id'], data['lease'])
            if path == '/agent/complete': return self.gateway.complete(data['id'], data['lease'], data['result'])
            if path == '/agent/fail': return self.gateway.fail(data['id'], data['lease'], data['reason'], retryable=data.get('retryable',False))
            raise AssertionError(path)
        except TaskError as error:
            raise MatrixError(400, {'error':error.code,'retryable':error.retryable})

    def test_auth_origin_and_route_reject_before_claim(self):
        for token, url, origin in [('wrong',self.url,None), ('fixture-token',self.url+'?token=fixture-token',None),
                                   ('fixture-token',self.url,'https://example.invalid')]:
            with self.subTest(token=token,origin=origin), self.assertRaises(InvalidStatus):
                with connect(url, additional_headers={'Authorization':'Bearer '+token}, origin=origin, proxy=None): pass
        self.assertEqual(self.gateway.audit('$task'), [])

    def test_disconnect_after_git_commit_recovers_same_commit_after_lease_expiry(self):
        self.gateway.accept('txn', [self.event])
        with connect_runtime(self.url,'fixture-token') as socket:
            transport = SocketTransport(socket)
            task = transport('', 'GET', '/agent/tasks')['task']
            _, item = render(task, self.store)
        with self.gateway.db() as db: db.execute('UPDATE tasks SET until=0 WHERE id=?', ('$task',))
        with connect_runtime(self.url,'fixture-token') as socket:
            self.assertTrue(once('', '', self.store, transport=SocketTransport(socket)))
        self.assertEqual(self.store.snapshot('demo.md')['commit'], item['commit'])
        self.assertEqual(len(self.store.history('demo.md')), 1)
        self.assertEqual(self.gateway.status('$task')['status'], 'done')
        self.assertEqual(sum(call.args[0]=='PUT' for call in self.agent.api.call_args_list), 1)
        self.assertEqual(self.store.pending(), [])

    def test_completed_delivery_recovers_outbox_after_lost_client_ack(self):
        self.gateway.accept('txn', [self.event])
        with connect_runtime(self.url,'fixture-token') as socket:
            transport=SocketTransport(socket); task=transport('', 'GET', '/agent/tasks')['task']
            result,item=render(task,self.store)
            transport('', 'POST', '/agent/complete', data={'id':task['id'],'lease':task['lease'],'result':result})
            # Runtime stops before acknowledging its Git outbox.
        with connect_runtime(self.url,'fixture-token') as socket:
            self.assertFalse(once('', '', self.store, transport=SocketTransport(socket)))
        self.assertEqual(self.store.pending(), [])
        self.assertEqual(len(self.store.history('demo.md')), 1)
        self.assertEqual(sum(call.args[0]=='PUT' for call in self.agent.api.call_args_list), 1)

    def test_invalid_route_and_cancelled_task_are_typed_without_side_effect(self):
        self.gateway.accept('txn',[self.event])
        with connect_runtime(self.url,'fixture-token') as socket:
            transport=SocketTransport(socket)
            with self.assertRaises(MatrixError): transport('', 'GET', '/health')
            task=transport('', 'GET', '/agent/tasks')['task']; self.gateway.cancel('$task')
            with self.assertRaises(MatrixError) as caught:
                transport('', 'POST', '/agent/validate', data={'id':task['id'],'lease':task['lease']})
            self.assertEqual(caught.exception.body['error'],'task_cancelled')
            self.assertFalse(caught.exception.body['retryable'])
        self.assertEqual(self.store.history('demo.md'), [])

    def test_legal_large_event_is_received_and_completed_in_one_attempt(self):
        self.event['content']['large_fixture_field'] = '界' * 150000
        self.gateway.accept('large', [self.event])
        with connect_runtime(self.url, 'fixture-token') as socket:
            self.assertTrue(once('', '', self.store, transport=SocketTransport(socket)))
        self.assertEqual(self.gateway.status('$task')['status'], 'done')
        self.assertEqual(self.gateway.status('$task')['attempts'], 1)

    def test_idle_disconnect_does_not_claim_subsequent_task(self):
        first_empty_claim = threading.Event()
        original = self.gateway.claim
        def empty():
            result = original(); first_empty_claim.set(); return result
        with patch.object(self.gateway, 'claim', side_effect=empty):
            with connect_runtime(self.url, 'fixture-token') as socket:
                socket.send(json.dumps({'method':'GET','path':'/agent/tasks'}))
                self.assertTrue(first_empty_claim.wait(2))
            self.gateway.accept('after-close', [self.event])
            time.sleep(.35)
        self.assertEqual(self.gateway.status('$task')['attempts'], 0)
        self.assertIsNotNone(self.gateway.claim())
