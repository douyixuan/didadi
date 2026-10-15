import multiprocessing
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

from src.gitdocs import Conflict, GitDocs, InvalidPath


def process_write(root, blob, barrier, queue, value):
    store = GitDocs(root)
    barrier.wait()
    try:
        store.write('demo.md', value, blob)
        queue.put('saved')
    except Conflict:
        queue.put('conflict')


def commit_then_crash(root):
    store = GitDocs(root)
    store.write('demo.md', 'committed before crash\n', operation='matrix-event',
                notification={'task_id': 'matrix-event'})
    os._exit(73)


class GitDocsHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.store = GitDocs(self.root / 'store.git')

    def test_two_independent_processes_only_one_same_base_wins(self):
        blob = self.store.write('demo.md', 'initial')['blob']
        ctx = multiprocessing.get_context('spawn')
        barrier, queue = ctx.Barrier(2), ctx.Queue()
        processes = [ctx.Process(target=process_write, args=(str(self.store.root), blob, barrier, queue, value))
                     for value in ['first', 'second']]
        for process in processes:
            process.start()
        for process in processes:
            process.join(20)
            self.assertFalse(process.is_alive())
            self.assertEqual(process.exitcode, 0)
        self.assertEqual(sorted(queue.get(timeout=2) for _ in processes), ['conflict', 'saved'])
        self.assertEqual(len(self.store.history('demo.md')), 2)

    def test_fixed_commit_preserves_whitespace_and_same_content_operation(self):
        first = self.store.write('demo.md', '\nfirst\n\n')
        second = self.store.write('demo.md', 'second\n', first['blob'])
        same = self.store.write('demo.md', 'second\n', second['blob'])
        self.assertEqual(self.store.read('demo.md', first['commit']), '\nfirst\n\n')
        self.assertEqual(self.store.read('demo.md', second['commit']), 'second\n')
        self.assertNotEqual(same['commit'], second['commit'])
        with self.assertRaises(ValueError):
            self.store.read('demo.md', 'f' * 40)

    def test_process_crash_has_atomic_commit_and_recoverable_outbox(self):
        ctx = multiprocessing.get_context('spawn')
        process = ctx.Process(target=commit_then_crash, args=(str(self.store.root),))
        process.start()
        process.join(20)
        self.assertEqual(process.exitcode, 73)
        restored = GitDocs(self.store.root)
        item = restored.pending()[0]
        self.assertEqual(restored.read('demo.md', item['commit']), 'committed before crash\n')
        repeat = restored.write('demo.md', 'committed before crash\n', operation='matrix-event',
                                notification={'task_id': 'matrix-event'})
        self.assertEqual(item['commit'], repeat['commit'])
        with self.assertRaises(Conflict):
            restored.write('demo.md', 'different', operation='matrix-event')
        with self.assertRaises(RuntimeError):
            restored.flush(lambda _: (_ for _ in ()).throw(RuntimeError('Matrix offline')))
        self.assertEqual(len(restored.pending()), 1)
        sent = []
        restored.flush(lambda item: sent.append(item['operation']))
        self.assertEqual(sent, ['matrix-event'])
        self.assertEqual(restored.pending(), [])

    def test_remote_sync_recovers_identical_operation_and_rejects_changed_request(self):
        remote = self.root / 'remote.git'
        GitDocs(remote)
        first = GitDocs(self.root / 'first.git', remote)
        retrying = GitDocs(self.root / 'retrying.git', remote)
        changed = GitDocs(self.root / 'changed.git', remote)
        notification = {'task_id': 'same-event'}
        original = first.write('demo.md', 'saved', operation='same-event',
                               notification=notification)
        recovered = retrying.write('demo.md', 'saved', operation='same-event',
                                   notification=notification)
        self.assertEqual(recovered['commit'], original['commit'])
        self.assertEqual(len(retrying.history('demo.md')), 1)
        with self.assertRaisesRegex(Conflict, 'operation ID reused with different request'):
            changed.write('demo.md', 'changed', operation='same-event',
                          notification=notification)
        self.assertEqual(changed.read('demo.md'), 'saved')

    def test_unicode_dots_spaces_and_normalized_names_round_trip(self):
        for name in ['设计/编辑器选型.md', 'README.zh.md', 'Meeting notes.md', 'v1.2-release.md', 'café.md', '中' * 79 + '.md']:
            with self.subTest(name=name):
                item = self.store.write(name, 'first')
                self.assertEqual(self.store.read(name), 'first')
                self.store.write(name, 'second', item['blob'])
                self.assertEqual(self.store.read(name, item['commit']), 'first')
                self.assertEqual(len(self.store.history(name)), 2)

    def test_names_use_literal_git_pathspecs(self):
        first = self.store.write('[draft].md', 'literal')
        self.store.write('d.md', 'different')
        self.assertEqual(self.store.read('[draft].md'), 'literal')
        self.assertEqual(self.store.history('[draft].md'), [first['commit']])

    def test_names_reject_unsafe_nonportable_and_noncanonical_paths(self):
        names = ['../x.md', '.git/x.md', 'a/./b.md', 'a/../b.md', '/a.md',
                 'a\\b.md', 'a\x00.md', 'a\n.md', 'a\t.md', 'cafe\u0301.md',
                 '.GITmodules.md', 'a/ b.md', 'a /b.md', 'a.md ', 'CON.md',
                 'LPT1.notes.md', 'a./b.md', 'a:b.md', 'a?.md', '\ud800.md',
                 '中' * 80 + '.md']
        for name in names:
            with self.subTest(name=repr(name)), self.assertRaises(InvalidPath):
                self.store.write(name, 'unsafe')
        self.assertIsNone(self.store.snapshot('demo.md')['commit'])

    def test_remote_fast_forward_and_stale_blob_rejection(self):
        remote = self.root / 'remote.git'
        GitDocs(remote)
        first = GitDocs(self.root / 'first.git', remote)
        one = first.write('demo.md', 'one')
        second = GitDocs(self.root / 'second.git', remote)
        two = second.write('demo.md', 'external update', one['blob'])
        with self.assertRaises(Conflict):
            first.write('demo.md', 'stale write', one['blob'])
        self.assertEqual(first.read('demo.md'), 'external update')
        self.assertEqual(first.read('demo.md', one['commit']), 'one')
        self.assertEqual(GitDocs(remote).snapshot('demo.md')['commit'], two['commit'])

    def test_remote_push_race_retains_commit_and_outbox_without_overwrite(self):
        remote = self.root / 'remote.git'
        GitDocs(remote)
        first = GitDocs(self.root / 'first.git', remote)
        one = first.write('demo.md', 'one')
        second = GitDocs(self.root / 'second.git', remote)
        publish = first._publish
        raced = False
        def race():
            nonlocal raced
            if not raced:
                raced = True
                second.write('demo.md', 'remote wins', one['blob'])
            publish()
        with patch.object(first, '_publish', side_effect=race):
            with self.assertRaises(Conflict):
                first.write('demo.md', 'local retained', one['blob'], operation='raced',
                            notification={'task_id': 'raced'})
        self.assertEqual(GitDocs(remote).read('demo.md'), 'remote wins')
        local_commit = first._ref(first.branch)
        self.assertEqual(first.read('demo.md', local_commit), 'local retained')
        self.assertIsNotNone(first._operation(first._operation_ref('raced')))
        with self.assertRaises(Conflict):
            first.pending()  # Never notify a divergent unpublished version.

    def test_crash_before_push_can_publish_on_reopen(self):
        remote = self.root / 'remote.git'
        GitDocs(remote)
        store = GitDocs(self.root / 'local.git', remote)
        with patch.object(store, '_publish', side_effect=RuntimeError('crash before push')):
            with self.assertRaises(RuntimeError):
                store.write('demo.md', 'recover', operation='recovery', notification={'task_id': 'recovery'})
        restored = GitDocs(store.root)
        self.assertEqual(GitDocs(remote).read('demo.md'), 'recover')
        self.assertEqual(len(restored.pending()), 1)

    def test_traversal_and_disk_symlink_race_never_open_document_paths(self):
        for name in ['../outside.md', '/tmp/outside.md', 'docs/../../x.md', 'docs//x.md', '.git/x.md']:
            with self.assertRaises(InvalidPath):
                self.store.write(name, 'unsafe')
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'note.md'
        sentinel.write_text('do not touch')
        stop = threading.Event()
        link = self.store.root / 'docs'
        def replace_link():
            while not stop.is_set():
                try:
                    link.symlink_to(outside, target_is_directory=True)
                    link.unlink()
                except FileExistsError:
                    pass
        thread = threading.Thread(target=replace_link)
        thread.start()
        try:
            version = None
            for i in range(8):
                version = self.store.write('docs/note.md', str(i), version)['blob']
        finally:
            stop.set()
            thread.join()
        self.assertEqual(sentinel.read_text(), 'do not touch')
        self.assertEqual(self.store.read('docs/note.md'), '7')

    def test_tracked_symlink_and_symlink_parent_are_rejected(self):
        # Simulate an external branch containing a symlink blob.
        blob = self.store._git('hash-object', '-w', '--stdin', input='/tmp/secret').strip()
        tree = self.store._git('mktree', input=f'120000 blob {blob}\tdocs\n').strip()
        commit = self.store._git('commit-tree', tree, input='external symlink').strip()
        self.store._git('update-ref', self.store.branch, commit)
        with self.assertRaises(InvalidPath):
            self.store.write('docs/note.md', 'unsafe')

    def test_network_remote_and_checkout_are_rejected(self):
        with self.assertRaises(ValueError):
            GitDocs(self.root / 'network.git', 'https://example.invalid/repo.git')
        checkout = self.root / 'checkout'
        checkout.mkdir()
        (checkout / '.git').mkdir()
        with self.assertRaises(ValueError):
            GitDocs(checkout)

    def test_remote_rewind_is_not_silently_pushed_back(self):
        remote = self.root / 'remote.git'
        origin = GitDocs(remote)
        store = GitDocs(self.root / 'local.git', remote)
        first = store.write('demo.md', 'first')
        second = store.write('demo.md', 'second', first['blob'])
        origin._git('update-ref', origin.branch, first['commit'], second['commit'])
        with self.assertRaises(Conflict):
            store.read('demo.md')
        self.assertEqual(origin.read('demo.md'), 'first')

    def test_casefold_file_directory_and_unicode_collisions_reject_without_changes(self):
        first=self.store.write('Design.md','first')
        for name in ['design.md','DESIGN.md']:
            with self.assertRaises(InvalidPath):self.store.write(name,'colliding')
        self.assertEqual(self.store.snapshot('Design.md')['commit'],first['commit'])
        second=self.store.write('Design.md','updated',first['blob'])
        self.assertEqual(self.store.read('Design.md'),'updated')
        self.store.write('Docs/a.md','nested')
        with self.assertRaises(InvalidPath):self.store.write('docs/b.md','collision')
        with self.assertRaises(InvalidPath):self.store.write('docs/a.md','collision')
        self.store.write('Straße.md','unicode')
        with self.assertRaises(InvalidPath):self.store.write('STRASSE.md','collision')
        self.store.write('Docs/b.md','allowed')
        self.assertEqual(self.store.read('Docs/b.md'),'allowed')

    def test_remote_synced_path_collision_is_checked_before_commit(self):
        remote=self.root/'portable-remote.git';origin=GitDocs(remote)
        local=GitDocs(self.root/'portable-local.git',remote)
        first=origin.write('Remote.md','remote')
        with self.assertRaises(InvalidPath):local.write('remote.md','collision')
        self.assertEqual(local.snapshot('Remote.md')['commit'],first['commit'])
        self.assertEqual(origin.snapshot('Remote.md')['commit'],first['commit'])
