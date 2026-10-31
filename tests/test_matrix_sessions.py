"""Offline unit checks for actual Matrix token-backed session policy (no network)."""
import unittest
from types import SimpleNamespace
from pathlib import Path
import os
import tempfile
import threading
import time
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
        self.sessions._revoke_queue.join()
        self.assertIn('token-bob-0123456789', self.invalid)

    def test_expired_sessions_are_revoked_on_next_login(self):
        alice, session = self.sessions.login('alice', 'secret-a')
        self.clock[0] += 61
        bob, active = self.sessions.login('bob', 'secret-b')
        self.sessions._revoke_queue.join()
        self.assertIn(session.access_token, self.invalid)
        self.assertEqual(self.sessions.require('didadi_session=' + bob), active)
        with self.assertRaises(SessionError):
            self.sessions.require('didadi_session=' + alice)

    def test_slow_upstream_expiry_cleanup_does_not_block_new_login(self):
        first, _ = self.sessions.login('alice', 'secret-a')
        upstream_entered = threading.Event()
        allow_finish = threading.Event()
        original = self.sessions.matrix_request

        def slow_matrix(url, method, path, token=None, data=None):
            if path.endswith('/logout'):
                upstream_entered.set()
                allow_finish.wait(3)
            return original(url, method, path, token, data)

        self.sessions.matrix_request = slow_matrix
        self.clock[0] += 61
        try:
            started = time.monotonic()
            bob, _ = self.sessions.login('bob', 'secret-b')
            elapsed = time.monotonic() - started
            self.assertLess(elapsed, 1, 'Login must not wait for upstream token revocation')
            self.assertTrue(upstream_entered.wait(1))
            self.assertEqual(self.sessions.local('didadi_session=' + bob).user_id,
                             '@bob:localhost')
        finally:
            allow_finish.set()
        self.sessions._revoke_queue.join()
        with self.assertRaises(SessionError):
            self.sessions.local('didadi_session=' + first)

    def test_local_logout_validation_does_not_require_matrix_whoami(self):
        handle, active = self.sessions.login('alice', 'secret-a')
        cookie = 'didadi_session=' + handle
        before = len([call for call in self.calls if call[1].endswith('/account/whoami')])
        self.assertEqual(self.sessions.local(cookie), active)
        self.assertEqual(before, len([call for call in self.calls if call[1].endswith('/account/whoami')]))
        self.revocation_unavailable = True
        self.assertEqual(self.sessions.logout(cookie)['matrix_revocation'], 'unconfirmed')
        with self.assertRaises(SessionError):
            self.sessions.local(cookie)

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

    def test_private_disk_sessions_survive_server_restart_without_new_login(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'matrix-sessions.sqlite'
            factory = self.sessions.workspace_factory
            transport = self.sessions.matrix_request
            clock = self.sessions.now
            def registry():
                return MatrixSessions('http://127.0.0.1:8009', factory, transport, clock,
                                      lifetime=60, store_path=path)
            first = registry()
            cookie, issued = first.login('alice', 'secret-a')
            browser_cookie = 'didadi_session=' + cookie
            self.assertEqual(os.stat(path).st_mode & 0o077, 0)
            self.assertNotIn(cookie, path.read_bytes().decode(errors='ignore'))
            restarted = registry()
            local = restarted.local(browser_cookie)
            self.assertIsNone(local.workspace)
            self.assertEqual(local.csrf, issued.workspace.csrf)
            recovered = restarted.require(browser_cookie)
            self.assertEqual(recovered.user_id, issued.user_id)
            self.assertEqual(recovered.workspace.csrf, issued.workspace.csrf)
            self.assertEqual(len([x for x in self.calls if x[1].endswith('/login')]), 1)
            self.revocation_unavailable = True
            self.assertEqual(restarted.logout(browser_cookie)['matrix_revocation'], 'unconfirmed')
            third = registry()
            with self.assertRaises(SessionError):
                third.local(browser_cookie)

    def test_expired_persisted_sessions_revoke_orphaned_matrix_devices(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'sessions.sqlite'
            make = lambda: MatrixSessions('http://127.0.0.1:8009',
                self.sessions.workspace_factory, self.sessions.matrix_request,
                self.sessions.now, lifetime=60, store_path=path)
            first = make()
            alice, active = first.login('alice', 'secret-a')
            self.clock[0] += 61
            another = make()
            another.login('bob', 'secret-b')
            another._revoke_queue.join()
            self.assertIn(active.access_token, self.invalid)
            with self.assertRaises(SessionError):
                another.require('didadi_session=' + alice)

    def test_store_rejects_unsafe_file_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'sessions.sqlite'
            path.touch(mode=0o600)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                MatrixSessions('http://127.0.0.1:8009',
                    self.sessions.workspace_factory, self.sessions.matrix_request,
                    self.sessions.now, store_path=path)

    def test_workspace_identity_mismatch_revokes_access_token(self):
        self.sessions.workspace_factory = lambda *_: SimpleNamespace(user_id='@spoof:local')
        with self.assertRaises(SessionError):
            self.sessions.login('alice', 'secret-a')
        self.assertIn('token-alice-0123456789', self.invalid)
        self.assertEqual(len(self.sessions._sessions), 0)


if __name__ == '__main__':
    unittest.main()
