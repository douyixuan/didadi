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

            room_filter = json.loads(query['filter'])['room']
            self.assertEqual(room_filter['timeline']['limit'], 0)
            # Incremental sync must surface m.fully_read/m.receipt after the
            # read_markers write, otherwise the previous count stays cached.
            self.assertIn('m.fully_read', room_filter['account_data']['types'])
            self.assertIn('m.receipt', room_filter['ephemeral']['types'])
            return {'next_batch': 'cursor-2' if self.read_writes else 'cursor-1', 'rooms': {'join': {
                '!shared:localhost': {'unread_notifications': {'notification_count': 0,
                    'unread_count': 0 if self.read_writes else 3}},
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

    def test_read_marker_count_stays_server_authoritative(self):
        self.assertEqual(self.workspace.unread_rooms()['unread']['!shared:localhost'], 3)
        self.workspace.mark_room_read('!shared:localhost', '$visible')
        # The next real Matrix /sync updates the observed count; never fake a
        # local zero just because the read_markers POST returned success.
        self.assertEqual(self.workspace.unread_rooms()['unread']['!shared:localhost'], 0)
        self.assertEqual(self.workspace._unread_cursor, 'cursor-2')

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


    def test_summary_top_level_count_and_invalid_value(self):
        original=self.workspace.api
        def summary(method,path,data=None,query=None):
            if path=='/sync':return {'next_batch':'n','rooms':{'join':{'!shared:localhost':{'org.matrix.msc2654.unread_count':3,'unread_notifications':{'notification_count':0}}}}}
            return original(method,path,data,query)
        self.workspace.api=summary
        self.assertEqual(self.workspace.unread_rooms()['unread']['!shared:localhost'],3)

    def test_summary_count_fallbacks_and_invalid_values(self):
        original=self.workspace.api
        for summary,expected in [
            ({'org.matrix.msc2654.unread_count':0,'unread_notifications':{'notification_count':9}},0),
            ({'unread_notifications':{'unread_count':4,'notification_count':1}},4),
            ({'unread_notifications':{'notification_count':2}},2),
            ({'org.matrix.msc2654.unread_count':-1},None),
            ({'org.matrix.msc2654.unread_count':True},None),
            ({'org.matrix.msc2654.unread_count':'3'},None),
        ]:
            def sync(method,path,data=None,query=None):
                if path=='/sync':return {'next_batch':'n','rooms':{'join':{'!shared:localhost':summary}}}
                return original(method,path,data,query)
            self.workspace.api=sync
            with self.subTest(summary=summary):
                if expected is None:
                    with self.assertRaises(ClientError):self.workspace.unread_rooms()
                else:self.assertEqual(self.workspace.unread_rooms()['unread']['!shared:localhost'],expected)

    def test_foreign_event_room_rejected_without_matrix_write(self):
        original=self.workspace.api
        def foreign(method,path,data=None,query=None):
            if '/event/' in path:return {'event_id':'$visible','room_id':'!foreign:localhost','type':'m.room.message'}
            return original(method,path,data,query)
        self.workspace.api=foreign
        with self.assertRaises(ClientError):self.workspace.mark_room_read('!shared:localhost','$visible')
        self.assertEqual(self.read_writes,[])

if __name__ == '__main__':
    unittest.main()
