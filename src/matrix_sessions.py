"""Server-held Matrix password sessions for the opt-in, loopback real-user client.

No Matrix access token or password is ever returned to the browser. Browser cookies
contain only an unpredictable opaque handle. Unlike the fictional contract this
actually verifies tokens with Synapse; unlike production SSO this is deliberately
restricted to a locally bound development workspace.
"""
from dataclasses import dataclass
import re
import secrets
import threading
import time

from src.matrix_as import PREFIX
from src.matrix_http import MatrixError, request


class SessionError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


@dataclass
class ActiveSession:
    user_id: str
    access_token: str
    device_id: str
    workspace: object
    expires_at: float


class MatrixSessions:
    COOKIE = 'didadi_session'
    MAX_SESSIONS = 128

    def __init__(self, matrix_url, workspace_factory, matrix_request=request, now=time.time,
                 lifetime=12 * 60 * 60):
        self.matrix_url = matrix_url
        self.workspace_factory = workspace_factory
        self.matrix_request = matrix_request
        self.now = now
        self.lifetime = lifetime
        self._lock = threading.RLock()
        self._sessions = {}

    def _matrix(self, method, path, token=None, data=None):
        return self.matrix_request(self.matrix_url, method, PREFIX + path, token, data)

    def _revoke_token(self, token):
        # Never retain an expired Matrix device after dropping its local handle.
        # A network outage must not prevent local invalidation.
        try:
            self._matrix('POST', '/logout', token, {})
        except Exception:
            pass

    def login(self, username, password):
        if (not isinstance(username, str) or not 1 <= len(username) <= 255 or
                username.strip() != username or any(ch.isspace() for ch in username) or
                not isinstance(password, str) or not 1 <= len(password) <= 1024):
            raise SessionError(400, 'Enter a Matrix username and password.')
        try:
            result = self._matrix('POST', '/login', data={
                'type': 'm.login.password',
                'identifier': {'type': 'm.id.user', 'user': username},
                'password': password,
                'initial_device_display_name': 'Didadi local web workspace',
            })
        except MatrixError as exc:
            if exc.status in (400, 401, 403):
                raise SessionError(401, 'Matrix rejected the username or password.') from None
            raise
        if not isinstance(result, dict):
            raise SessionError(503, 'Matrix returned an invalid login response.')
        token, user, device = result.get('access_token'), result.get('user_id'), result.get('device_id')
        if (not isinstance(token, str) or len(token) < 12 or not isinstance(user, str) or
                not re.fullmatch(r'@[^\s:]+:[^\s]+', user) or
                not isinstance(device, str) or not device):
            raise SessionError(503, 'Matrix did not issue a valid user/device session.')
        try:
            verified = self._matrix('GET', '/account/whoami', token)
            if not isinstance(verified, dict) or verified.get('user_id') != user:
                raise SessionError(503, 'Matrix identity verification disagrees with login.')
            workspace = self.workspace_factory(token, user)
            if workspace.user_id != user:
                raise SessionError(503, 'Workspace identity does not match Matrix login.')
        except Exception:
            # A token is only useful in the server. Best effort revoke on startup failure.
            try:
                self._matrix('POST', '/logout', token, {})
            except Exception:
                pass
            raise
        with self._lock:
            now = self.now()
            expired = [entry for entry in self._sessions.values()
                       if entry.expires_at <= now]
            self._sessions = {key: entry for key, entry in self._sessions.items()
                              if entry.expires_at > now}
            full = len(self._sessions) >= self.MAX_SESSIONS
            if not full:
                handle = secrets.token_urlsafe(32)
                active = ActiveSession(user, token, device, workspace,
                                       now + self.lifetime)
                self._sessions[handle] = active
        # Remote HTTP is deliberately outside the registry lock.
        for entry in expired:
            self._revoke_token(entry.access_token)
        if full:
            self._revoke_token(token)
            raise SessionError(429, 'Too many local sessions. Try again later.')
        return handle, active

    @classmethod
    def handle_from_cookie(cls, header):
        if (not isinstance(header, str) or len(header) > 4096 or
                '\r' in header or '\n' in header):
            return None
        candidates = []
        for part in header.split(';'):
            name, equal, value = part.strip().partition('=')
            if equal and name == cls.COOKIE:
                candidates.append(value)
        if len(candidates) != 1 or not re.fullmatch(r'[a-zA-Z0-9_-]{32,128}', candidates[0]):
            return None
        return candidates[0]

    def local(self, cookie):
        """Validate the local handle without network IO (only for CSRF-guarded logout).

        A Matrix outage must not trap a user in a locally authenticated session.
        All other workspace routes still use require() for live whoami checks.
        """
        handle = self.handle_from_cookie(cookie)
        with self._lock:
            current = self._sessions.get(handle)
            expired = current is not None and current.expires_at <= self.now()
            if expired:
                self._sessions.pop(handle, None)
        if expired:
            self._revoke_token(current.access_token)
            current = None
        if current is None:
            raise SessionError(401, 'Sign in to your Matrix account.')
        return current

    def require(self, cookie):
        handle = self.handle_from_cookie(cookie)
        current = self.local(cookie)
        try:
            whoami = self._matrix('GET', '/account/whoami', current.access_token)
        except MatrixError as exc:
            if exc.status in (401, 403):
                with self._lock:
                    self._sessions.pop(handle, None)
                raise SessionError(401, 'Matrix session expired. Sign in again.') from None
            raise
        if not isinstance(whoami, dict) or whoami.get('user_id') != current.user_id:
            with self._lock:
                self._sessions.pop(handle, None)
            raise SessionError(401, 'Matrix identity changed. Sign in again.')
        return current

    def logout(self, cookie):
        handle = self.handle_from_cookie(cookie)
        with self._lock:
            session = self._sessions.pop(handle, None)
        if session is None:
            raise SessionError(401, 'This session is already signed out.')
        try:
            self._matrix('POST', '/logout', session.access_token, {})
            revoked = True
        except MatrixError as exc:
            revoked = exc.status in (401, 403)
        except Exception:
            revoked = False
        # Local handle is removed even if upstream revocation could not be confirmed.
        return {'status': 'signed_out', 'matrix_revocation': 'confirmed' if revoked else 'unconfirmed'}

    def cookie(self, handle):
        return (self.COOKIE + '=' + handle +
                '; Path=/; HttpOnly; SameSite=Strict; Max-Age=' + str(int(self.lifetime)))

    def clear_cookie(self):
        return self.COOKIE + '=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'
