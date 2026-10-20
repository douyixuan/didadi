"""Public Git history must not publish private Matrix routing metadata."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from src.gitdocs import GitDocs, Conflict


class CommitMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = GitDocs(self.root / 'docs.git')
        self.operation = '$private-task:local'
        self.notice = {'room_id': '!private-room:local', 'task_id': self.operation}
        self.author = {'name': '@alice:local', 'email': 'alice@matrix.invalid'}

    def legacy_commit(self):
        fields = ['demo.md', 'old', None, self.notice]
        metadata = {'operation': self.operation, 'name': 'demo.md', 'notification': self.notice,
                    'request_hash': hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()}
        blob = self.store._git('hash-object', '-w', '--stdin', input='old').strip()
        tree = self.store._git('mktree', input='100644 blob ' + blob + '\tdemo.md\n').strip()
        commit = self.store._git('commit-tree', tree, input=json.dumps(metadata)).strip()
        self.store._git('update-ref', self.store.branch, commit)
        return commit

    def test_public_main_is_attributed_and_private_refs_are_not_pushed(self):
        remote = GitDocs(self.root / 'remote.git')
        store = GitDocs(self.root / 'writer.git', remote.root)
        item = store.write('demo.md', 'hello', operation=self.operation,
                           notification=self.notice, author=self.author)
        log = remote._git('log', '--format=%an%n%ae%n%cn%n%B', 'main')
        self.assertIn('@alice:local\nalice@matrix.invalid\nDoc Service', log)
        self.assertIn('docs(demo.md): update from workspace', log)
        self.assertNotIn(self.operation, log)
        self.assertNotIn(self.notice['room_id'], log)
        self.assertIn(hashlib.sha256(self.operation.encode()).hexdigest(), log)
        self.assertEqual(remote._git('for-each-ref', '--format=%(refname)', 'refs/didadi/'), '')
        restored = GitDocs(store.root)
        self.assertEqual(restored.pending()[0]['notification'], self.notice)
        restored.acknowledge(self.operation)
        self.assertEqual(restored.pending(), [])
        retry = GitDocs(self.root / 'retry.git', remote.root)
        self.assertEqual(retry.pending(), [])  # A clone has no private routing authority.
        recovered = retry.write('demo.md', 'hello', operation=self.operation,
                                notification=self.notice, author=self.author)
        self.assertEqual(recovered['commit'], item['commit'])
        self.assertEqual(GitDocs(retry.root).pending()[0]['notification'], self.notice)
        with self.assertRaises(Conflict):
            retry.write('demo.md', 'changed', operation=self.operation,
                        notification=self.notice, author=self.author)

    def test_old_json_recovery_and_attributed_retry_preserve_original_commit(self):
        commit = self.legacy_commit()
        restored = GitDocs(self.store.root)
        self.assertEqual(restored.pending()[0]['commit'], commit)
        item = restored.write('demo.md', 'old', operation=self.operation,
                              notification=self.notice, author=self.author)
        self.assertEqual(item['commit'], commit)
        restored.acknowledge(self.operation)
        fresh = restored.write('demo.md', 'new', item['blob'], operation='next',
                               notification=self.notice, author=self.author)
        self.assertEqual([i['commit'] for i in GitDocs(restored.root).pending()], [fresh['commit']])
        self.assertTrue(restored._git('show', '-s', '--format=%B', commit).startswith('{'))

    def test_intent_before_branch_cas_cannot_create_a_phantom_notification(self):
        original = self.store._git
        def fail_commit(*args, **kwargs):
            if args[:2] == ('update-ref', self.store.branch):
                raise RuntimeError('simulated failure before main CAS')
            return original(*args, **kwargs)
        self.store._git = fail_commit
        with self.assertRaisesRegex(RuntimeError, 'before main CAS'):
            self.store.write('demo.md', 'hello', operation=self.operation,
                             notification=self.notice, author=self.author)
        restored = GitDocs(self.store.root)
        self.assertEqual(restored.pending(), [])
        self.assertEqual(restored.history('demo.md'), [])
        item = restored.write('demo.md', 'hello', operation=self.operation,
                              notification=self.notice, author=self.author)
        self.assertEqual([p['commit'] for p in GitDocs(restored.root).pending()], [item['commit']])

    def test_missing_or_corrupt_private_routing_is_not_invented(self):
        self.store.write('demo.md', 'hello', operation=self.operation,
                         notification=self.notice, author=self.author)
        key = hashlib.sha256(self.operation.encode()).hexdigest()
        bad = self.store._git('hash-object', '-w', '--stdin', input='{broken').strip()
        self.store._git('update-ref', 'refs/didadi/intents/' + key, bad)
        with self.assertRaisesRegex(RuntimeError, 'intent is unreadable'):
            self.store.pending()

    def test_valid_json_with_missing_or_wrong_intent_fields_fails_explicitly(self):
        item = self.store.write('demo.md', 'hello', operation=self.operation,
                                notification=self.notice, author=self.author)
        key = hashlib.sha256(self.operation.encode()).hexdigest()
        ref = 'refs/didadi/intents/' + key
        valid = json.loads(self.store._git('cat-file', 'blob', self.store._ref(ref)))
        for damaged in [{k:v for k,v in valid.items() if k != 'operation'},
                        {**valid, 'operation': 123}, {**valid, 'operation': 'other'},
                        {k:v for k,v in valid.items() if k != 'notification'}]:
            with self.subTest(damaged=sorted(damaged)):
                bad = self.store._git('hash-object', '-w', '--stdin', input=json.dumps(damaged)).strip()
                self.store._git('update-ref', ref, bad)
                with self.assertRaisesRegex(RuntimeError, 'private operation intent'):
                    GitDocs(self.store.root).pending()
        self.assertEqual(self.store.read('demo.md', item['commit']), 'hello')

    def test_orphaned_intent_does_not_block_matching_remote_operation(self):
        self.check_orphan_recovery(prune=False)

    def test_pruned_orphan_intent_does_not_block_matching_remote_operation(self):
        self.check_orphan_recovery(prune=True)

    def check_orphan_recovery(self, prune):
        remote = GitDocs(self.root / 'remote.git')
        failed = GitDocs(self.root / 'failed.git', remote.root)
        original = failed._git
        def fail_main(*args, **kwargs):
            if args[0] == 'commit-tree':
                kwargs['env'] = {**kwargs.get('env', {}), 'GIT_AUTHOR_DATE':'2001-01-01T00:00:00Z',
                                 'GIT_COMMITTER_DATE':'2001-01-01T00:00:00Z'}
            if args[:2] == ('update-ref', failed.branch):
                raise RuntimeError('simulated lost main CAS')
            return original(*args, **kwargs)
        failed._git = fail_main
        with self.assertRaisesRegex(RuntimeError, 'lost main CAS'):
            failed.write('demo.md', 'hello', operation=self.operation,
                         notification=self.notice, author=self.author)
        key = hashlib.sha256(self.operation.encode()).hexdigest()
        ref = 'refs/didadi/intents/' + key
        orphan_blob = original('rev-parse', ref).strip()
        if prune:
            old_commit = json.loads(original('cat-file', 'blob', orphan_blob))['commit']
            original('reflog', 'expire', '--expire=now', '--all')
            original('gc', '--prune=now')
            self.assertIsNone(failed._ref(old_commit + '^{commit}'))
        publisher = GitDocs(self.root / 'publisher.git', remote.root)
        published = publisher.write('demo.md', 'hello', operation=self.operation,
                                    notification=self.notice, author=self.author)
        recovered = GitDocs(failed.root)
        self.assertEqual(recovered.pending(), [])
        with self.assertRaises(Conflict):
            recovered.write('demo.md', 'different', operation=self.operation,
                            notification=self.notice, author=self.author)
        self.assertEqual(recovered._ref(ref), orphan_blob)
        retry = recovered.write('demo.md', 'hello', operation=self.operation,
                                notification=self.notice, author=self.author)
        self.assertEqual(retry['commit'], published['commit'])
        self.assertNotEqual(recovered._ref(ref), orphan_blob)
        self.assertEqual([x['commit'] for x in GitDocs(recovered.root).pending()], [published['commit']])
