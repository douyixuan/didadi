"""Loopback HTTP routing tests with injected Matrix responses. NOT real Synapse/browser E2E."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from src.client_server import handler
from src.matrix_as import PREFIX
from src.matrix_http import MatrixError
from src.matrix_sessions import MatrixSessions


class TestLiveMatrixClientServer(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.tokens = {'alice': ('@alice:localhost', 'session-token-alice-012345'),
                       'bob': ('@bob:localhost', 'session-token-bob-012345')}
        self.revoked = set()
        self.workspaces = []

        def matrix(base, method, path, token=None, data=None):
            self.assertEqual(base, 'http://127.0.0.1:8009')
            if path == PREFIX + '/login':
                name = data['identifier']['user']
                if name not in self.tokens or data['password'] != 'pass-' + name:
                    raise MatrixError(403, {'errcode': 'M_FORBIDDEN'})
                user, value = self.tokens[name]
                return {'user_id': user, 'access_token': value, 'device_id': name + '-device'}
            if path == PREFIX + '/account/whoami':
                if token in self.revoked:
                    raise MatrixError(401, {'errcode': 'M_UNKNOWN_TOKEN'})
                for user, value in self.tokens.values():
                    if token == value:
                        return {'user_id': user}
                raise MatrixError(401, {'errcode': 'M_UNKNOWN_TOKEN'})
            if path == PREFIX + '/logout':
                self.revoked.add(token)
                return {}
            raise AssertionError('Unexpected route ' + path)

        def factory(token, user):
            class Documents:
                def documents(self, room):
                    if room != '!shared:localhost':
                        raise AssertionError('Room escape')
                    return {'documents': [{'name': user + '.md'}]}
            result = SimpleNamespace(
                user_id=user, csrf='csrf-' + user, state={'room': '!shared:localhost'},
                room_service=SimpleNamespace(contacts=[]), qa=None, documents=Documents(),
                repository_choices=lambda: [], direct_chats=None,
                proxy=lambda method, path, query, body=None: {
                    'joined_rooms': ['!shared:localhost'], 'user': user},
            )
            self.workspaces.append((user, token, result))
            return result

        self.registry = MatrixSessions('http://127.0.0.1:8009', factory, matrix)
        self.dist = Path(self.folder.name)
        (self.dist / 'index.html').write_text('HTML app shell')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.server.RequestHandlerClass = handler(
            None, self.dist, self.server.server_port, self.registry)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def fetch(self, route, method='GET', data=None, cookie=None, csrf=None, origin=True, flag=False):
        headers = {}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-CSRF-Token'] = csrf
        if origin:
            headers['Origin'] = self.base
        if flag:
            headers['X-Didadi-Login'] = '1'
        if data is not None:
            headers['Content-Type'] = 'application/json'
        req = Request(self.base + route, data=json.dumps(data).encode() if data is not None
                      else None, headers=headers, method=method)
        with urlopen(req, timeout=5) as result:
            return json.load(result), result.headers.get('Set-Cookie')

    def login(self, user):
        body, cookie = self.fetch('/api/auth/login', 'POST',
                                  {'username': user, 'password': 'pass-' + user}, flag=True)
        self.assertEqual(body['userId'], '@' + user + ':localhost')
        self.assertIn('HttpOnly', cookie)
        return cookie

    def test_login_routes_are_cookie_scoped_and_logout_revokes_only_current_device(self):
        with self.assertRaises(HTTPError) as unauthenticated:
            self.fetch('/api/session')
        self.assertEqual(unauthenticated.exception.code, 401)
        alice = self.login('alice')
        bob = self.login('bob')
        a, _ = self.fetch('/api/session', cookie=alice)
        b, _ = self.fetch('/api/session', cookie=bob)
        self.assertEqual((a['userId'], b['userId']), ('@alice:localhost', '@bob:localhost'))
        self.assertNotEqual(a['csrf'], b['csrf'])
        self.assertNotIn('access_token', json.dumps(a) + json.dumps(b))
        docs_a, _ = self.fetch('/api/documents?room=!shared:localhost', cookie=alice)
        docs_b, _ = self.fetch('/api/documents?room=!shared:localhost', cookie=bob)
        self.assertEqual(docs_a['documents'][0]['name'], '@alice:localhost.md')
        self.assertEqual(docs_b['documents'][0]['name'], '@bob:localhost.md')
        with self.assertRaises(HTTPError) as cross:
            self.fetch('/api/auth/logout', 'POST', {}, cookie=bob, csrf=a['csrf'])
        self.assertEqual(cross.exception.code, 403)
        result, cleared = self.fetch('/api/auth/logout', 'POST', {}, cookie=alice, csrf=a['csrf'])
        self.assertEqual(result['matrix_revocation'], 'confirmed')
        self.assertIn('Max-Age=0', cleared)
        with self.assertRaises(HTTPError) as signed_out:
            self.fetch('/api/session', cookie=alice)
        self.assertEqual(signed_out.exception.code, 401)
        self.assertEqual(self.fetch('/api/session', cookie=bob)[0]['userId'], '@bob:localhost')

    def test_login_requires_origin_and_custom_header_and_rejects_wrong_password(self):
        for options in [{'origin': False, 'flag': True}, {'flag': False}]:
            with self.subTest(options=options), self.assertRaises(HTTPError) as rejected:
                self.fetch('/api/auth/login', 'POST', {'username': 'alice',
                    'password': 'pass-alice'}, **options)
            self.assertEqual(rejected.exception.code, 403)
        with self.assertRaises(HTTPError) as invalid:
            self.fetch('/api/auth/login', 'POST', {'username': 'alice',
                'password': 'wrong'}, flag=True)
        self.assertEqual(invalid.exception.code, 401)
        alice = self.login('alice')
        with self.assertRaises(HTTPError) as duplicate:
            self.fetch('/api/session', cookie=alice + '; ' + alice)
        self.assertEqual(duplicate.exception.code, 401)


if __name__ == '__main__':
    unittest.main()
