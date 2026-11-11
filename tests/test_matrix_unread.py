"""P0 ROOM-03 Matrix counters and read-marker authorization (injected API, not live E2E)."""
import json
import threading
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

from src.client_server import ClientError, Workspace


class MatrixUnreadAuthorization(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.metadata = str(Path(self.folder.name) / 'rooms.sqlite')
        with sqlite3.connect(self.metadata) as db:
            db.execute('CREATE TABLE rooms (id TEXT PRIMARY KEY)')
            db.executemany('INSERT INTO rooms VALUES (?)', [
                ('!shared:localhost',), ('!departed:localhost',)])
        self.workspace = Workspace.__new__(Workspace)
        self.workspace.live = True
        self.workspace.metadata = self.metadata
        self.workspace._unread_lock = threading.Lock()
        self.workspace._unread_cursor = None
        self.workspace._unread_counts = {}
        self.workspace.api = self.matrix
        self.joined = ['!shared:localhost', '!other-users:localhost']
        self.read_writes = []

    def matrix(self, method, path, data=None, query=None):
        if method == 'GET' and path == '/joined_rooms':
            return {'joined_rooms': list(self.joined)}
        if method == 'GET' and path == '/sync':
            self.assertEqual(query['timeout'], '0')
            if self.workspace._unread_cursor is not None:
                self.assertEqual(query.get('since'), self.workspace._unread_cursor)

            self.assertEqual(json.loads(query['filter'])['room']['timeline']['limit'], 0)
            return {'next_batch': 'cursor-1', 'rooms': {'join': {
                '!shared:localhost': {'unread_notifications': {'notification_count': 0, 'unread_count': 3}},
                '!departed:localhost': {'unread_notifications': {'notification_count': 88}},
                '!other-users:localhost': {'unread_notifications': {'notification_count': 99}},
            }}}
        if method == 'GET' and '/event/' in path:
            room = unquote(path.split('/')[2])
            event = unquote(path.split('/event/')[1])
            return {'event_id': event, 'room_id': room,
                    'type': 'm.room.message' if event == '$visible' else 'm.room.member'}
        if method == 'POST' and path.endswith('/read_markers'):
            self.read_writes.append((path, data))
            return {}
        self.fail('Unexpected Matrix call %s %s' % (method, path))

    def test_snapshot_is_only_current_joined_registered_room(self):
        self.assertEqual(self.workspace.unread_rooms(), {'unread': {'!shared:localhost': 3}})
        self.assertEqual(self.workspace._unread_cursor, 'cursor-1')
        self.assertEqual(self.workspace.unread_rooms(), {'unread': {'!shared:localhost': 3}})
        self.joined = []
        self.assertEqual(self.workspace.unread_rooms(), {'unread': {}})
        self.workspace.live = False
        self.assertEqual(self.workspace.unread_rooms(), {'unread': {}})

    def test_receipt_requires_live_membership_and_a_real_room_message(self):
        self.assertEqual(self.workspace.mark_room_read('!shared:localhost', '$visible'),
                         {'room': '!shared:localhost', 'read': True})
        self.assertEqual(len(self.read_writes), 1)
        self.assertEqual(self.read_writes[0][1], {'m.fully_read': '$visible', 'm.read': '$visible'})
        for room, event in [
            ('!departed:localhost', '$visible'),
            ('!other-users:localhost', '$visible'),
            ('!shared:localhost', '$not-message'),
            ('!shared:localhost', 'not-an-event'),
        ]:
            with self.subTest(room=room, event=event), self.assertRaises(ClientError):
                self.workspace.mark_room_read(room, event)
        self.assertEqual(len(self.read_writes), 1, 'Denied reads must never mutate Matrix')
        self.joined = []
        with self.assertRaises(ClientError):
            self.workspace.mark_room_read('!shared:localhost', '$visible')


if __name__ == '__main__':
    unittest.main()
