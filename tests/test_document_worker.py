import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.document_worker import once, reconcile, render
from src.gitdocs import GitDocs


class DocumentWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = GitDocs(Path(self.tmp.name) / 'docs.git')
        self.task = {'id': '$write', 'lease': 'first', 'result': None, 'event': {
            'room_id': '!room', 'content': {'org.didadi.document': {
                'action': 'write', 'content': '# demo\n', 'base_blob': None}}}}

    def test_reclaimed_task_reuses_git_commit_with_new_lease(self):
        result, first = render(self.task, self.store)
        repeat = copy.deepcopy(self.task)
        repeat['lease'] = 'replacement'
        repeated_result, second = render(repeat, self.store)
        self.assertEqual(result, repeated_result)
        self.assertEqual(first['commit'], second['commit'])
        self.assertEqual(len(self.store.history('demo.md')), 1)

    def test_crash_after_completion_ack_reconciles_receipt_without_resending(self):
        sent = []
        done = False
        def api(base, method, path, token, data=None, query=None):
            nonlocal done
            if path == '/agent/tasks':
                return {'task': self.task}
            if path == '/agent/status':
                return {'task': {'status': 'done' if done else 'pending'}}
            if path == '/agent/validate':
                return {'allowed': True}
            if path == '/agent/fail':
                return {'status': 'pending'}
            if path == '/agent/complete':
                done = True
                sent.append(data)
                return {'event_id': '$reply'}
            raise AssertionError(path)
        with patch('scripts.document_worker.request', side_effect=api), patch('scripts.agent_worker.request', side_effect=api):
            with patch.object(self.store, 'acknowledge', side_effect=RuntimeError('crash')):
                with self.assertRaises(RuntimeError):
                    once('unused', 'token', self.store)
            self.assertEqual(len(self.store.pending()), 1)
            reconcile('unused', 'token', GitDocs(self.store.root))
        self.assertEqual(len(sent), 1)
        self.assertEqual(self.store.pending(), [])

    def test_read_fixed_version_and_ignore_message_selected_path(self):
        self.task['event']['content']['org.didadi.document']['name'] = '../escape.md'
        _, first = render(self.task, self.store)
        self.store.write('demo.md', 'new', first['blob'])
        read = copy.deepcopy(self.task)
        read['event']['content']['org.didadi.document'] = {'action': 'read', 'commit': first['commit']}
        result, _ = render(read, self.store)
        self.assertIn('# demo\n', result)
        self.assertIsNone(self.store.read('escape.md'))
        self.assertFalse((Path(self.tmp.name) / 'escape.md').exists())

    def test_malformed_versions_and_stale_updates_have_clear_reply(self):
        command = self.task['event']['content']['org.didadi.document']
        command['base_blob'] = 123
        self.assertIn('rejected', render(self.task, self.store)[0])
        command['base_blob'] = None
        render(self.task, self.store)
        self.task['id'] = '$another'
        command['content'] = 'stale'
        self.assertIn('conflict', render(self.task, self.store)[0])
