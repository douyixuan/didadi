"""Server-held Matrix password sessions for the opt-in, loopback real-user client.

No Matrix access token or password is ever returned to the browser. Browser cookies
contain only an unpredictable opaque handle. Unlike the fictional contract this
actually verifies tokens with Synapse; unlike production SSO this is deliberately
restricted to a locally bound development workspace.
"""
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os
import queue
import re
import secrets
import sqlite3
import stat
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
    csrf: str = ''


class MatrixSessions:
    COOKIE = 'didadi_session'
    MAX_SESSIONS = 128

    def __init__(self, matrix_url, workspace_factory, matrix_request=request, now=time.time,
                 lifetime=12 * 60 * 60, store_path=None):
        self.matrix_url = matrix_url
        self.workspace_factory = workspace_factory
        self.matrix_request = matrix_request
        self.now = now
        self.lifetime = lifetime
        self._lock = threading.RLock()
        self._sessions = {}
        # Expired devices are revoked outside HTTP requests. A single daemon
        # worker bounds concurrent upstream /logout calls; revocation is best
        # effort and local handles are already invalid before being enqueued.
        self._revoke_queue = queue.Queue()
        self._revoke_thread = None
        self.store_path = Path(store_path) if store_path is not None else None
        if self.store_path is not None:
            self.store_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
            fd = os.open(self.store_path, flags, 0o600)
            try:
                info = os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077:
                    raise ValueError('Matrix session store must be a private regular file (mode 0600).')
            finally:
                os.close(fd)
            with closing(sqlite3.connect(self.store_path)) as db:
                with db:
                    db.execute('''CREATE TABLE IF NOT EXISTS matrix_sessions (
                        handle_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL,
                        token TEXT NOT NULL, device_id TEXT NOT NULL,
                        csrf TEXT NOT NULL, expires_at REAL NOT NULL)''')

    @staticmethod
    def _digest(handle):
        # A stolen DB row must not by itself be a valid browser cookie.
        return hashlib.sha256(handle.encode('ascii')).hexdigest()

    def _store_add(self, handle, session):
        if self.store_path is None:
            return
        with closing(sqlite3.connect(self.store_path)) as db:
            with db:
                db.execute('''INSERT INTO matrix_sessions
                    (handle_hash, user_id, token, device_id, csrf, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                    (self._digest(handle), session.user_id, session.access_token,
                     session.device_id, session.csrf, session.expires_at))

    def _store_find(self, handle):
        if self.store_path is None or handle is None:
            return None
        with closing(sqlite3.connect(self.store_path)) as db:
            row = db.execute('''SELECT user_id, token, device_id, csrf, expires_at
                FROM matrix_sessions WHERE handle_hash=?''', (self._digest(handle),)).fetchone()
        return ActiveSession(row[0], row[1], row[2], None, row[4], row[3]) if row else None

    def _store_delete(self, handle):
        if self.store_path is None or handle is None:
            return
        with closing(sqlite3.connect(self.store_path)) as db:
            with db:
                db.execute('DELETE FROM matrix_sessions WHERE handle_hash=?',
                           (self._digest(handle),))

    def _store_prune(self, now):
        if self.store_path is None:
            return [], len(self._sessions)
        with closing(sqlite3.connect(self.store_path)) as db:
            with db:
                expired = [row[0] for row in db.execute(
                    'SELECT token FROM matrix_sessions WHERE expires_at<=?', (now,))]
                db.execute('DELETE FROM matrix_sessions WHERE expires_at<=?', (now,))
                count = db.execute('SELECT COUNT(*) FROM matrix_sessions').fetchone()[0]
        return expired, count

    def _forget(self, handle):
        # Caller holds the registry lock. Commit the deletion before allowing
        # logout to report success; stale cookies must not revive after restart.
        self._store_delete(handle)
        return self._sessions.pop(handle, None)

    def _matrix(self, method, path, token=None, data=None):
        return self.matrix_request(self.matrix_url, method, PREFIX + path, token, data)

    def _revoke_token(self, token):
        # Never retain an expired Matrix device after dropping its local handle.
        # A network outage must not prevent local invalidation.
        try:
            self._matrix('POST', '/logout', token, {})
        except Exception:
            pass

    def _revoke_worker(self):
        while True:
            token = self._revoke_queue.get()
            try:
                self._revoke_token(token)
            finally:
                self._revoke_queue.task_done()

    def _schedule_revocation(self, tokens):
        tokens = tuple(tokens)
        if not tokens:
            return
        # put_nowait keeps login independent of a slow/unavailable homeserver.
        with self._lock:
            for token in tokens:
                self._revoke_queue.put_nowait(token)
            if self._revoke_thread is None or not self._revoke_thread.is_alive():
                self._revoke_thread = threading.Thread(
                    target=self._revoke_worker, name='matrix-session-revocation',
                    daemon=True)
                self._revoke_thread.start()

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
        expired_tokens = set()
        try:
            with self._lock:
                now = self.now()
                expired_tokens.update(entry.access_token for entry in self._sessions.values()
                                      if entry.expires_at <= now)
                self._sessions = {key: entry for key, entry in self._sessions.items()
                                  if entry.expires_at > now}
                persisted_expired, count = self._store_prune(now)
                expired_tokens.update(persisted_expired)
                full = count >= self.MAX_SESSIONS
                if not full:
                    handle = secrets.token_urlsafe(32)
                    active = ActiveSession(user, token, device, workspace,
                                           now + self.lifetime, workspace.csrf)
                    # Publish the local handle only after durable storage commits.
                    self._store_add(handle, active)
                    self._sessions[handle] = active
        except (sqlite3.Error, OSError) as exc:
            self._revoke_token(token)
            raise SessionError(503, 'Private session storage is unavailable.') from exc
        # Never block the login response on a slow Matrix logout endpoint.
        # These handles are already deleted; remote revocation is best effort.
        self._schedule_revocation(expired_tokens)
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
            if current is None:
                current = self._store_find(handle)
                if current is not None:
                    self._sessions[handle] = current
            expired = current is not None and current.expires_at <= self.now()
            if expired:
                self._forget(handle)
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
                    self._forget(handle)
                raise SessionError(401, 'Matrix session expired. Sign in again.') from None
            raise
        if not isinstance(whoami, dict) or whoami.get('user_id') != current.user_id:
            with self._lock:
                self._forget(handle)
            self._revoke_token(current.access_token)
            raise SessionError(401, 'Matrix identity changed. Sign in again.')
        if current.workspace is None:
            # After a server restart, rebuild the workspace only after whoami.
            # Reuse the original CSRF so already-open browser tabs can recover.
            try:
                workspace = self.workspace_factory(current.access_token, current.user_id)
                if workspace.user_id != current.user_id:
                    raise SessionError(401, 'Matrix workspace identity changed.')
            except MatrixError as exc:
                if exc.status in (401, 403):
                    with self._lock:
                        self._forget(handle)
                    raise SessionError(401, 'Matrix session expired. Sign in again.') from None
                raise
            with self._lock:
                if self._sessions.get(handle) is not current:
                    raise SessionError(401, 'Matrix session expired. Sign in again.')
                workspace.csrf = current.csrf
                current.workspace = workspace
        return current

    def logout(self, cookie):
        # Do not contact whoami: a user must be able to sign out while offline.
        session = self.local(cookie)
        handle = self.handle_from_cookie(cookie)
        with self._lock:
            removed = self._forget(handle)
        if removed is None:
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
