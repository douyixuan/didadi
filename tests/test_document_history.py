import base64
import json
import tempfile
import unittest

from src.gitdocs import GitDocs


class DocumentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = GitDocs(self.tmp.name)

    def test_move_history_pages_pin_versions_and_resolve_original_paths(self):
        first = self.store.write('Notes/A.md', 'A0')
        other = self.store.write('B.md', 'independent B')
        latest = first
        for index in range(1, 12):
            latest = self.store.write('Notes/A.md', 'A' + str(index), latest['blob'])
        moved = self.store.write('Archive/设计 A.md', '', latest['blob'], move_from='Notes/A.md')
        page = self.store.history_page('Archive/设计 A.md')
        self.assertEqual(len(page['versions']), 8)
        self.assertEqual(page['versions'][0], {'commit': moved['commit'], 'path': 'Archive/设计 A.md'})
        self.assertEqual(page['versions'][1], {'commit': latest['commit'], 'path': 'Notes/A.md'})
        pinned = page['head']
        added = self.store.write('Archive/设计 A.md', 'newer after pagination', moved['blob'])
        versions = page['versions'][:]
        while page['next_cursor']:
            page = self.store.history_page('Archive/设计 A.md', page['next_cursor'])
            self.assertEqual(page['head'], pinned)
            versions.extend(page['versions'])
        self.assertEqual(len(versions), 13)
        self.assertEqual(len({item['commit'] for item in versions}), len(versions))
        self.assertEqual(versions[-1], {'commit': first['commit'], 'path': 'Notes/A.md'})
        self.assertNotIn(added['commit'], [item['commit'] for item in versions])
        for item in versions:
            self.assertIsNotNone(self.store.snapshot(item['path'], item['commit'])['blob'])
        self.assertEqual(self.store.history_page('Archive/设计 A.md')['head'], added['commit'])
        self.assertEqual(self.store.read('B.md'), 'independent B')
        self.assertEqual(self.store.history('B.md'), [other['commit']])

    def test_path_reuse_does_not_mix_an_older_document_incarnation(self):
        old = self.store.write('A.md', 'old identity')
        self.store.write('Moved.md', '', old['blob'], move_from='A.md')
        replacement = self.store.write('A.md', 'new independent document')
        page = self.store.history_page('A.md')
        self.assertEqual(page['versions'], [{'commit': replacement['commit'], 'path': 'A.md'}])
        self.assertIsNone(page['next_cursor'])
        original = self.store.history_page('Moved.md')
        self.assertEqual(original['versions'][-1], {'commit': old['commit'], 'path': 'A.md'})

    def test_cursor_is_bounded_and_bound_to_path_and_canonical_ancestry(self):
        current = self.store.write('A.md', 'first')
        for index in range(9):
            current = self.store.write('A.md', str(index), current['blob'])
        page = self.store.history_page('A.md')
        with self.assertRaises(ValueError):
            self.store.history_page('B.md', page['next_cursor'])
        for value in ('?', 'a' * 4096):
            with self.assertRaises(ValueError):
                self.store.history_page('A.md', value)
        for fields in ([current['commit'], 'A.md', -1], ['f' * 40, 'A.md', 8], [current['commit'], 'A.md', True]):
            cursor = base64.urlsafe_b64encode(json.dumps(fields).encode()).decode().rstrip('=')
            with self.assertRaises(ValueError):
                self.store.history_page('A.md', cursor)

    def test_cursor_rejects_a_no_longer_canonical_pinned_head(self):
        latest = self.store.write('A.md', 'first')
        for index in range(8):
            latest = self.store.write('A.md', str(index), latest['blob'])
        page = self.store.history_page('A.md')
        tree = self.store._git('rev-parse', latest['commit'] + '^{tree}').strip()
        detached = self.store._git('commit-tree', tree, input='Synthetic disconnected root\n').strip()
        self.store._git('update-ref', self.store.branch, detached)
        with self.assertRaises(ValueError):
            self.store.history_page('A.md', page['next_cursor'])
        self.assertEqual(self.store.read('A.md'), '7')

    def test_empty_or_moved_away_current_path_has_no_versions(self):
        self.assertEqual(self.store.history_page('missing.md')['versions'], [])
        first = self.store.write('A.md', 'a')
        self.store.write('Moved.md', '', first['blob'], move_from='A.md')
        self.assertEqual(self.store.history_page('A.md')['versions'], [])

    def test_cursor_retry_and_restart_expiry_leave_canonical_contents_untouched(self):
        first = self.store.write('A.md', 'first')
        current = first
        for index in range(8):
            current = self.store.write('A.md', str(index), current['blob'])
        page = self.store.history_page('A.md')
        cursor = page['next_cursor']
        expected = self.store.history_page('A.md', cursor)['versions']
        self.assertEqual(self.store.history_page('A.md', cursor)['versions'], expected)
        rebuilt = GitDocs(self.tmp.name)
        with self.assertRaises(ValueError):
            rebuilt.history_page('A.md', cursor)
        self.assertEqual(rebuilt.history_page('A.md')['versions'], page['versions'])
        self.assertEqual(rebuilt.snapshot('A.md')['blob'], current['blob'])

    def test_multiple_moves_across_page_boundaries_do_not_alias_identical_documents(self):
        first = self.store.write('A.md', 'same bytes')
        unrelated = self.store.write('B.md', 'same bytes')
        moved = self.store.write('Deep/A.md', '', first['blob'], move_from='A.md')
        edited = self.store.write('Deep/A.md', 'changed A', moved['blob'])
        final = self.store.write('Final/A.md', '', edited['blob'], move_from='Deep/A.md')
        page = self.store.history_page('Final/A.md', limit=2)
        versions = page['versions'][:]
        while page['next_cursor']:
            page = self.store.history_page('Final/A.md', page['next_cursor'], limit=2)
            versions.extend(page['versions'])
        self.assertEqual(versions, [
            {'commit': final['commit'], 'path': 'Final/A.md'},
            {'commit': edited['commit'], 'path': 'Deep/A.md'},
            {'commit': moved['commit'], 'path': 'Deep/A.md'},
            {'commit': first['commit'], 'path': 'A.md'},
        ])
        self.assertNotIn(unrelated['commit'], [item['commit'] for item in versions])
        self.assertEqual(self.store.read('B.md'), 'same bytes')
