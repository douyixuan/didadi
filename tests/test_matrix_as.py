import copy
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from deploy.init import initialize
from src.matrix_as import AGENT, EchoAgent, make_handler
from src.matrix_http import MatrixError, request


class MatrixSpikeTests(unittest.TestCase):
    def setUp(self):
        self.agent = EchoAgent('http://unused', 'secret')
        self.event = {'type': 'm.room.message', 'event_id': '$one', 'room_id': '!r:local',
                      'sender': '@alice:local', 'content': {'msgtype': 'm.text', 'body': '!echo hello'}}

    def unencrypted(self, method, path, data=None):
        if path.endswith('/state/m.room.encryption'):
            raise MatrixError(404, {'errcode': 'M_NOT_FOUND'})
        return {'membership': 'join'}

    def test_reply_and_replay_use_same_matrix_transaction_id(self):
        self.agent.api = Mock(side_effect=self.unencrypted)
        self.agent.process([self.event, self.event])
        sends = [c for c in self.agent.api.call_args_list if c.args[0] == 'PUT']
        self.assertEqual(len(sends), 2)
        self.assertEqual(sends[0], sends[1])
        self.assertEqual(sends[0].args[2]['body'], 'Echo: hello')

    def test_encrypted_or_unknown_encryption_state_never_replies(self):
        self.agent.api = Mock(return_value={'algorithm': 'm.megolm.v1.aes-sha2'})
        self.agent.process([self.event])
        self.assertEqual(self.agent.api.call_count, 1)
        self.agent.api = Mock(side_effect=MatrixError(500, {'errcode': 'M_UNKNOWN'}))
        self.agent.process([self.event])
        self.assertFalse(any(call.args[0] == 'PUT' for call in self.agent.api.call_args_list))

    def test_ignores_self_noncommand_and_encrypted_events(self):
        variants = []
        for changes in ({'sender': AGENT}, {'type': 'm.room.encrypted'}, {'state_key': ''},
                        {'content': {'msgtype': 'm.text', 'body': 'hello'}}):
            event = copy.deepcopy(self.event)
            event.update(changes)
            variants.append(event)
        self.agent.api = Mock()
        self.agent.process(variants)
        self.agent.api.assert_not_called()

    def test_invite_joins_only_managed_echo_identity(self):
        self.agent.api = Mock()
        self.agent.process([{'type': 'm.room.member', 'room_id': '!r:local', 'state_key': AGENT,
                             'content': {'membership': 'invite'}}])
        self.assertEqual(self.agent.api.call_args.args[0], 'POST')
        self.assertTrue(self.agent.api.call_args.args[1].endswith('/join'))

    def test_http_auth_and_failure_ack(self):
        agent = Mock()
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(agent, 'hs-secret'))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        path = '/_matrix/app/v1/transactions/1'
        try:
            with self.assertRaises(MatrixError) as caught:
                request(base, 'PUT', path, data={'events': []})
            self.assertEqual(caught.exception.status, 403)
            agent.process.assert_not_called()
            self.assertEqual(request(base, 'PUT', path, 'hs-secret', {'events': []}), {})
            agent.process.side_effect = RuntimeError('upstream unavailable')
            with self.assertRaises(MatrixError) as caught:
                request(base, 'PUT', path, 'hs-secret', {'events': []})
            self.assertEqual(caught.exception.status, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_configuration_rerun_keeps_secrets_and_scoped_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initialize(root)
            before = (root / 'secrets.json').read_text()
            initialize(root)
            self.assertEqual(before, (root / 'secrets.json').read_text())
            config = json.loads((root / 'appservice.yaml').read_text())
            self.assertNotEqual(config['as_token'], config['hs_token'])
            self.assertEqual(config['namespaces']['rooms'], [])
            self.assertEqual(config['namespaces']['aliases'], [])
            self.assertRegex(AGENT, config['namespaces']['users'][0]['regex'])
