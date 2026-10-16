"""Single-node Git document store. Markdown and pending notifications live in Git.

Use a dedicated, service-owned bare repository, not an arbitrary user checkout.
Working-tree paths are never opened: all content is read/written as Git objects.
"""
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unicodedata


class Conflict(Exception):
    pass


class PublicationPending(Conflict):
    pass


class InvalidPath(Exception):
    pass


class GitDocs:
    branch = 'refs/heads/main'

    def __init__(self, root, remote=None):
        self.root = Path(root).absolute()
        if self.root.is_symlink():
            raise InvalidPath('repository root is a symlink')
        self.root.mkdir(parents=True, exist_ok=True)
        with self._locked():
            if (self.root / '.git').exists():
                raise ValueError('use a dedicated bare repository, not a checkout')
            if not (self.root / 'HEAD').exists():
                self._git('init', '--bare', '--initial-branch=main', '-q')
            if self._git('rev-parse', '--is-bare-repository').strip() != 'true':
                raise ValueError('bare repository required')
            if remote is not None:
                # Development spike: never discover credentials or access a network remote.
                target = Path(remote).absolute()
                if not target.is_dir() or '://' in str(remote):
                    raise ValueError('remote must be an existing trusted local directory')
                existing = self._git('config', '--get', 'remote.origin.url', check=False).strip()
                if existing and existing != str(target):
                    raise ValueError('remote already configured')
                if not existing:
                    self._git('remote', 'add', 'origin', str(target))
            configured = self._git('config', '--get', 'remote.origin.url', check=False).strip()
            if configured and not Path(configured).is_absolute():
                raise ValueError('only absolute local remotes supported')
            self.remote = configured or None
            self._sync()

    @contextmanager
    def _locked(self):
        # One opened descriptor per acquisition also serializes threads and store instances.
        fd = os.open(self.root / '.didadi.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)

    def _git(self, *args, input=None, env=None, check=True):
        process_env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        process_env.update({'GIT_LITERAL_PATHSPECS': '1', 'GIT_NO_REPLACE_OBJECTS': '1', 'GIT_TERMINAL_PROMPT': '0',
                            'GIT_AUTHOR_NAME': 'Doc Service', 'GIT_AUTHOR_EMAIL': 'docs@localhost',
                            'GIT_COMMITTER_NAME': 'Doc Service', 'GIT_COMMITTER_EMAIL': 'docs@localhost'})
        process_env.update(env or {})
        p = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                            '-C', str(self.root), *args], input=input.encode('utf-8') if input is not None else None,
                           capture_output=True, timeout=30, env=process_env)
        if check and p.returncode:
            raise RuntimeError(p.stderr.decode('utf-8', errors='replace').strip())
        return p.stdout.decode('utf-8')  # Do not normalize CRLF in Markdown blobs.

    def _ref(self, ref):
        value = self._git('rev-parse', '--verify', ref, check=False).strip()
        return value if re.fullmatch(r'[0-9a-f]{40}', value) else None

    def _name(self, name):
        if not isinstance(name, str):
            raise InvalidPath(name)
        try:
            size = len(name.encode('utf-8'))
        except UnicodeEncodeError:
            raise InvalidPath(name) from None
        if (not 0 < size <= 240 or not name.endswith('.md') or
                unicodedata.normalize('NFC', name) != name):
            raise InvalidPath(name)
        for part in name.split('/'):
            stem = part.split('.', 1)[0].upper()
            if (not part or part in {'.', '..'} or part.casefold().startswith('.git') or
                    part != part.strip() or part.endswith('.') or
                    any(character in '\\<>:"|?*' or unicodedata.category(character).startswith('C')
                        for character in part) or
                    stem in {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                             'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2',
                             'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}):
                raise InvalidPath(name)
        return name

    def _version(self, name, commit):
        if not commit:
            return None
        # Reject tracked symlinks, submodules and non-file paths. Never dereference disk paths.
        for count in range(1, len(name.split('/'))):
            prefix = '/'.join(name.split('/')[:count])
            parent = self._git('ls-tree', commit, '--', prefix).strip()
            if parent and not parent.startswith('040000 tree '):
                raise InvalidPath('document parent must be a tree')
        entry = self._git('ls-tree', commit, '--', name).strip()
        if not entry:
            return None
        mode, kind, tail = entry.split(' ', 2)
        if mode != '100644' or kind != 'blob':
            raise InvalidPath('only regular Markdown blobs supported')
        return tail.split('\t', 1)[0]

    def _fetch_remote(self):
        upstream = self._git('ls-remote', 'origin', self.branch).split()
        seen = self._ref('refs/didadi/remote-seen')
        if not upstream:
            if seen:
                raise PublicationPending('remote branch deleted; explicit reconciliation required')
            return None
        self._git('fetch', '--no-tags', 'origin', self.branch)
        fetched = self._ref('FETCH_HEAD')
        if seen and self._git('merge-base', seen, fetched, check=False).strip() != seen:
            raise PublicationPending('remote history rewound or rewritten; refusing to overwrite it')
        self._git('update-ref', 'refs/didadi/remote-seen', fetched)
        return fetched

    def _sync(self):
        if not getattr(self, 'remote', None):
            return
        fetched = self._fetch_remote()
        local = self._ref(self.branch)
        if fetched is None:
            if local:
                self._publish()
            return
        if local == fetched:
            return
        if local and self._git('merge-base', local, fetched, check=False).strip() != local:
            self._publish()
            return
        self._git('update-ref', self.branch, fetched, local or '0' * 40)

    def snapshot(self, name, commit=None):
        self._name(name)
        if commit is not None and (not isinstance(commit, str) or not re.fullmatch(r'[0-9a-f]{40}', commit)):
            raise ValueError('fixed commit SHA required')
        with self._locked():
            if commit is None:
                self._sync()
            if commit is not None and self._ref(commit + '^{commit}') != commit:
                raise ValueError('unknown commit')
            revision = commit or self._ref(self.branch)
            blob = self._version(name, revision)
            content = self._git('cat-file', 'blob', blob) if blob else None
            return {'name': name, 'content': content, 'blob': blob, 'commit': revision}

    def history(self, name, limit=8):
        self._name(name)
        with self._locked():
            if not self._ref(self.branch):
                return []
            return self._git('log', '-' + str(min(max(int(limit), 1), 20)), '--format=%H',
                             self.branch, '--', name).splitlines()

    def read(self, name, commit=None):
        return self.snapshot(name, commit)['content']

    def blob_version(self, name):
        return self.snapshot(name)['blob']

    def _operation_ref(self, operation):
        if not isinstance(operation, str) or not 0 < len(operation) <= 1000:
            raise ValueError('operation ID required')
        return 'refs/didadi/operations/' + hashlib.sha256(operation.encode()).hexdigest()

    def _operations(self):
        head = self._ref(self.branch)
        if not head:
            return []
        result = []
        for revision in self._git('rev-list', head).splitlines():
            try:
                metadata = json.loads(self._git('show', '-s', '--format=%B', revision))
                if (not isinstance(metadata, dict) or not isinstance(metadata.get('operation'), str)
                    or not isinstance(metadata.get('request_hash'), str)):
                    continue
                self._name(metadata['name'])
                result.append({**metadata, 'commit': revision,
                               'blob': self._version(metadata['name'], revision)})
            except (ValueError, KeyError, InvalidPath):
                continue  # Ordinary external Git commits need no document-operation metadata.
        return result

    def _operation(self, ref):
        return next((item for item in self._operations()
                     if self._operation_ref(item['operation']) == ref), None)

    def _portable_name(self, name, head):
        """Reject case-folding collisions before they can make a clone lose a file."""
        if not head:
            return
        parts = name.split('/')
        fold = lambda value: unicodedata.normalize('NFC', value.casefold())
        for existing in self._git('ls-tree', '-r', '-z', '--name-only', head).split('\0'):
            if not existing:
                continue
            old = existing.split('/')
            for index, (left, right) in enumerate(zip(parts, old)):
                if fold(left) != fold(right):
                    break
                if left != right:
                    raise InvalidPath('name collides with existing ' + '/'.join(old[:index + 1]) +
                                      ' on case-insensitive file systems')

    def write(self, name, content, base_blob=None, *, operation=None, notification=None, author=None):
        self._name(name)
        if not isinstance(content, str) or len(content.encode()) > 65536:
            raise ValueError('content must be text, at most 64 KiB')
        if base_blob is not None and (not isinstance(base_blob, str) or not re.fullmatch(r'[0-9a-f]{40}', base_blob)):
            raise ValueError('invalid base blob')
        if author is not None and (not isinstance(author, dict) or set(author) != {'name', 'email'} or
                any(not isinstance(v, str) or not 0 < len(v) <= 512 or any(c in v for c in '\r\n\0<>') for v in author.values())):
            raise ValueError('invalid commit author')
        operation = operation or os.urandom(24).hex()
        opref = self._operation_ref(operation)
        request_fields = [name, content, base_blob, notification] + ([author] if author is not None else [])
        request_hash = hashlib.sha256(json.dumps(request_fields,
                                               sort_keys=True).encode()).hexdigest()
        with self._locked():
            previous = self._operation(opref)
            if previous:
                if previous['request_hash'] != request_hash:
                    raise Conflict('operation ID reused with different request')
                self._publish()
                return previous
            self._sync()
            # Synchronization can import an operation completed by another store.
            previous = self._operation(opref)
            if previous:
                if previous['request_hash'] != request_hash:
                    raise Conflict('operation ID reused with different request')
                self._publish()
                return previous
            head = self._ref(self.branch)
            if self._version(name, head) != base_blob:
                raise Conflict('document changed; refresh and merge')
            self._portable_name(name, head)
            blob = self._git('hash-object', '-w', '--stdin', input=content).strip()
            # A private index prevents shared-index corruption; no checkout means no symlink TOCTOU.
            with tempfile.TemporaryDirectory(prefix='didadi-index-') as temporary:
                env = {'GIT_INDEX_FILE': str(Path(temporary) / 'index')}
                self._git('read-tree', head or '--empty', env=env)
                self._git('update-index', '--add', '--cacheinfo', '100644', blob, name, env=env)
                tree = self._git('write-tree', env=env).strip()
            metadata = {'operation': operation, 'name': name, 'request_hash': request_hash,
                        'notification': notification}
            parent = ['-p', head] if head else []
            revision = self._git('commit-tree', tree, *parent, input=json.dumps(metadata, sort_keys=True),
                env={'GIT_AUTHOR_NAME':author['name'], 'GIT_AUTHOR_EMAIL':author['email']} if author is not None else None).strip()
            # One atomic branch ref is the commit point. The commit message contains the
            # outbox intent, so no multi-ref or Git/SQLite dual-write gap can lose a notification.
            self._git('update-ref', self.branch, revision, head or '0' * 40)
            self._publish()
            return {**metadata, 'commit': revision, 'blob': blob}

    def _publish(self):
        if not self.remote:
            return
        # Incorporate a remote fast-forward before publishing; retain divergent local work.
        fetched = self._fetch_remote()
        if fetched:
            local = self._ref(self.branch)
            ancestor = self._git('merge-base', local, fetched, check=False).strip() if local else None
            if ancestor == local and local != fetched:
                self._git('update-ref', self.branch, fetched, local)
            elif ancestor != fetched:
                raise PublicationPending('remote diverged; local commit/outbox retained for reconciliation')
        # Ordinary push refuses a race after fetch. Never force or reset unpublished work.
        try:
            self._git('push', 'origin', self.branch + ':' + self.branch)
            self._git('update-ref', 'refs/didadi/remote-seen', self._ref(self.branch))
        except RuntimeError:
            raise PublicationPending('remote advanced; local commit/outbox retained, reconcile before notification') from None

    def pending(self):
        with self._locked():
            self._publish()
            result = []
            for item in self._operations():
                receipt = self._operation_ref(item['operation']).replace('/operations/', '/notified/')
                if self._ref(receipt) is None and item.get('notification') is not None:
                    result.append(item)
            return result

    def acknowledge(self, operation):
        with self._locked():
            opref = self._operation_ref(operation)
            item = self._operation(opref)
            if item is None:
                raise ValueError('unknown operation')
            self._git('update-ref', opref.replace('/operations/', '/notified/'), item['commit'])

    def abandon(self, operation, reason='task_failed'):
        """Keep the committed version, but durably close its notification outbox item."""
        if reason not in {'task_failed','runtime_error','room_forbidden','room_unavailable',
                          'delivery_forbidden','attempts_exhausted','task_cancelled'}:
            raise ValueError('invalid abandonment reason')
        with self._locked():
            opref = self._operation_ref(operation)
            item = self._operation(opref)
            if item is None:
                raise ValueError('unknown operation')
            receipt = opref.replace('/operations/', '/notified/')
            if self._ref(receipt):
                return
            record = {'status':'abandoned', 'reason':reason, 'operation':operation, 'commit':item['commit']}
            blob = self._git('hash-object', '-w', '--stdin', input=json.dumps(record, sort_keys=True)).strip()
            self._git('update-ref', receipt, blob)

    def flush(self, send):
        """Send pending notifications; callback must use the stable operation ID to deduplicate."""
        for item in self.pending():
            send(item)
            self.acknowledge(item['operation'])
