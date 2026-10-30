"""Offline unit checks for actual Matrix token-backed session policy (no network)."""
import unittest
from types import SimpleNamespace
from src.matrix_as import PREFIX
from src.matrix_http import MatrixError
from src.matrix_sessions import MatrixSessions, SessionError


class MatrixSessionsTests(unittest.TestCase):
    def setUp(self):
        self.clock = [1000]
        self.calls = []
        self.revocation_unavailable = False
        self.invalid = set()
        self.accounts = {
            'alice': ('@alice:localhost', 'secret-a', 'token-alice-0123456789'),
            'bob': ('@bob:localhost', 'secret-b', 'token-bob-0123456789'),
        }
        self.workspaces = []

        def fake_matrix(url, method, path, token=None, data=None):
            self.calls.append((method, path, token, data))
            self.assertEqual(url, 'http://127.0.0.1:8009')
            if path == PREFIX + '/login':
                self.assertEqual(method, 'POST')
                self.assertEqual(data['type'], 'm.login.password')
                account = self.accounts.get(data['identifier']['user'])
                if not account or data['password'] != account[1]:
                    raise MatrixError(403, {'errcode': 'M_FORBIDDEN'})
                return {'user_id': account[0], 'access_token': account[2],
                        'device_id': 'device-' + data['identifier']['user']}
            if path == PREFIX + '/account/whoami':
                if token in self.invalid:
                    raise MatrixError(401, {'errcode': 'M_UNKNOWN_TOKEN'})
                for user, _, secret in self.accounts.values():
                    if token == secret:
                        return {'user_id': user}
                raise MatrixError(401, {'errcode': 'M_UNKNOWN_TOKEN'})
            if path == PREFIX + '/logout':
                self.assertEqual(method, 'POST')
                if self.revocation_unavailable:
                    raise MatrixError(503, {'errcode': 'M_UNKNOWN'})
                self.invalid.add(token)
                return {}
            raise AssertionError('Unexpected Matrix route: ' + path)

        def workspace(token, user_id):
            result = SimpleNamespace(user_id=user_id, csrf='csrf-' + user_id, token=token)
            self.workspaces.append(result)
            return result

        self.sessions = MatrixSessions('http://127.0.0.1:8009', workspace,
                                       fake_matrix, lambda: self.clock[0], lifetime=60)

    def test_two_real_password_logins_and_same_device_refresh(self):
        first, a = self.sessions.login('alice', 'secret-a')
        second, b = self.sessions.login('bob', 'secret-b')
        self.assertNotEqual(first, second)
        self.assertNotEqual(a.user_id, b.user_id)
        self.assertNotIn('token-alice', self.sessions.cookie(first))
        self.assertIn('HttpOnly; SameSite=Strict', self.sessions.cookie(first))
        self.assertEqual(self.sessions.require('didadi_session=' + first).workspace, a.workspace)
        self.assertEqual(self.sessions.require('didadi_session=' + second).workspace, b.workspace)
        self.assertEqual(len(self.workspaces), 2)
        self.assertEqual(len([x for x in self.calls if x[1].endswith('/login')]), 2)

    def test_wrong_password_no_session_and_cookie_overrides_fail_closed(self):
        with self.assertRaises(SessionError) as caught:
            self.sessions.login('alice', 'wrong')
        self.assertEqual(caught.exception.status, 401)
        with self.assertRaises(SessionError):
            self.sessions.login('bob', '')
        key, _ = self.sessions.login('alice', 'secret-a')
        for cookie in ('', 'didadi_session=guess', 'didadi_session=' + key +
                       '; didadi_session=' + key, 'didadi_session=' + key + '; bad=1\r\n'):
            with self.subTest(cookie=cookie), self.assertRaises(SessionError):
                self.sessions.require(cookie)
        self.assertEqual(self.sessions.require('other=x; didadi_session=' + key).user_id,
                         '@alice:localhost')

    def test_revoked_or_expired_matrix_token_cannot_be_reused(self):
        key, session = self.sessions.login('alice', 'secret-a')
        self.invalid.add(session.access_token)
        with self.assertRaises(SessionError) as caught:
            self.sessions.require('didadi_session=' + key)
        self.assertEqual(caught.exception.status, 401)
        with self.assertRaises(SessionError):
            self.sessions.require('didadi_session=' + key)
        key, _ = self.sessions.login('bob', 'secret-b')
        self.clock[0] += 61
        with self.assertRaises(SessionError):
            self.sessions.require('didadi_session=' + key)

    def test_logout_only_invalidates_one_device_and_cannot_be_replayed(self):
        a, _ = self.sessions.login('alice', 'secret-a')
        b, other = self.sessions.login('bob', 'secret-b')
        self.revocation_unavailable = True
        result = self.sessions.logout('didadi_session=' + a)
        self.assertEqual(result, {'status': 'signed_out', 'matrix_revocation': 'unconfirmed'})
        self.assertIn('Max-Age=0', self.sessions.clear_cookie())
        with self.assertRaises(SessionError):
            self.sessions.require('didadi_session=' + a)
        self.assertEqual(self.sessions.require('didadi_session=' + b).user_id,
                         other.user_id)
        with self.assertRaises(SessionError):
            self.sessions.logout('didadi_session=' + a)

    def test_workspace_identity_mismatch_revokes_access_token(self):
        self.sessions.workspace_factory = lambda *_: SimpleNamespace(user_id='@spoof:local')
        with self.assertRaises(SessionError):
            self.sessions.login('alice', 'secret-a')
        self.assertIn('token-alice-0123456789', self.invalid)
        self.assertEqual(len(self.sessions._sessions), 0)


if __name__ == '__main__':
    unittest.main()
