import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.document_worker import render
from src.gitdocs import GitDocs
from src.repository_read import RepositoryDenied, RepositoryReader


class RepositoryReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.repo = self.root / 'source'; self.repo.mkdir()
        self.git('init', '-q'); self.git('config', 'user.name', 'Fixture'); self.git('config', 'user.email', 'fixture@example.invalid')
        (self.repo / 'main.py').write_text('print("synthetic fixture")\n')
        (self.repo / 'secret.txt').write_text('not granted')
        (self.repo / 'link').symlink_to('secret.txt')
        (self.repo / 'large').write_bytes(b'x' * 8001)
        (self.repo / 'binary').write_bytes(b'\x00secret')
        self.git('add', '.'); self.git('commit', '-qm', 'synthetic fixture')
        self.commit = self.git('rev-parse', 'HEAD').decode().strip()
        self.config = {'repositories': {'fixture': {'path': str(self.repo), 'commit': self.commit,
            'files': ['main.py', 'link', 'large', 'binary'], 'rooms': ['!allowed'], 'senders': ['@alice']}}}
        self.reader = RepositoryReader(self.config)
        self.command = {'action': 'read', 'repository': 'fixture', 'path': 'main.py'}
        self.event = {'room_id': '!allowed', 'sender': '@alice', 'content': {'org.didadi.repository': self.command}}
        self.task = {'id': '$fixture', 'event': self.event}
        self.docs = GitDocs(self.root / 'docs.git')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL)

    def test_fixed_commit_ignores_worktree_and_moved_head(self):
        (self.repo / 'main.py').write_text('new untrusted worktree')
        self.git('add', '.'); self.git('commit', '-qm', 'new revision')
        snapshot = self.reader.read(self.event, self.command)
        self.assertEqual(snapshot['content'], 'print("synthetic fixture")\n')
        self.assertEqual(snapshot['commit'], self.commit)
        self.assertEqual(snapshot['lines'], 1)

    def test_denies_room_sender_alias_path_revision_and_unknown_fields(self):
        for field, value in [('room_id', '!other'), ('sender', '@bob')]:
            event = {**self.event, field: value}
            with self.subTest(field=field), self.assertRaises(RepositoryDenied): self.reader.read(event, self.command)
        for change in [{'repository':'unknown'}, {'path':'secret.txt'}, {'path':'../secret.txt'},
                       {'path':'/etc/passwd'}, {'path':'main.py/../secret.txt'}, {'path':'main.py\\x'},
                       {'path':':(glob)*'}, {'commit':self.commit}, {'action':'execute'}, {'repository':[]}]:
            with self.subTest(change=change), self.assertRaises(RepositoryDenied):
                self.reader.read(self.event, {**self.command, **change})

    def test_denies_links_large_and_binary_objects(self):
        for name in ['link', 'large', 'binary']:
            with self.subTest(name=name), self.assertRaises(RepositoryDenied):
                self.reader.read(self.event, {**self.command, 'path': name})

    def test_deny_default_and_report_write_preserves_source_and_stale_guard(self):
        self.assertIn('rejected', render(self.task, self.docs)[0])
        before = self.git('show-ref'); status = self.git('status', '--porcelain')
        self.command.update(action='report', base_blob=None)
        reply, item = render(self.task, self.docs, self.reader)
        self.assertIn('Saved demo.md', reply)
        document = self.docs.snapshot('demo.md')['content']
        self.assertIn(self.commit, document); self.assertIn('no LLM analysis', document)
        self.assertNotIn(str(self.repo), document)
        self.assertEqual(before, self.git('show-ref')); self.assertEqual(status, self.git('status', '--porcelain'))
        repeated = render(self.task, self.docs, self.reader)[1]
        self.assertEqual(item['commit'], repeated['commit'])
        stale = copy.deepcopy(self.task); stale['id'] = '$stale'
        self.assertIn('conflict', render(stale, self.docs, self.reader)[0])
        self.event['content']['org.didadi.document'] = {'action': 'write'}
        self.assertIn('rejected', render(self.task, self.docs, self.reader)[0])

    def test_invalid_config_fails_closed(self):
        for value in [None, {}, {'repositories': []}]:
            with self.assertRaises(ValueError): RepositoryReader(value)

    def test_missing_promisor_blob_is_denied_without_fetch_or_source_object_write(self):
        remote = self.root / 'synthetic-remote.git'
        subprocess.check_call(['git', 'clone', '-q', '--bare', '--no-hardlinks', str(self.repo), str(remote)])
        oid = self.git('rev-parse', self.commit + ':main.py').decode().strip()
        missing = self.repo / '.git' / 'objects' / oid[:2] / oid[2:]
        missing.unlink()
        self.git('config', 'remote.origin.url', str(remote))
        self.git('config', 'remote.origin.promisor', 'true')
        self.git('config', 'remote.origin.partialclonefilter', 'blob:none')
        before = sorted(str(item.relative_to(self.repo)) for item in (self.repo / '.git' / 'objects').rglob('*'))
        with self.assertRaises(RepositoryDenied): self.reader.read(self.event, self.command)
        self.assertFalse(missing.exists())
        after = sorted(str(item.relative_to(self.repo)) for item in (self.repo / '.git' / 'objects').rglob('*'))
        self.assertEqual(before, after)

    def test_inherited_git_environment_cannot_redirect_read(self):
        with patch.dict(os.environ, {'GIT_DIR': str(self.root / 'not-the-granted-repository'),
                                     'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'protocol.allow',
                                     'GIT_CONFIG_VALUE_0': 'always'}):
            self.assertEqual(self.reader.read(self.event, self.command)['commit'], self.commit)
