"""Fixed-revision reads from explicitly granted Git files. No worktree execution."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess


class RepositoryDenied(ValueError):
    pass


def safe_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value or
        any(part in {'', '.', '..'} for part in value.split('/')) or
        PurePosixPath(value).is_absolute()):
        raise RepositoryDenied('repository_request_rejected')
    return value


class RepositoryReader:
    def __init__(self, config):
        self.grants = {}
        if not isinstance(config, dict) or set(config) != {'repositories'} or not isinstance(config['repositories'], dict):
            raise ValueError('invalid repository grant configuration')
        for alias, grant in config['repositories'].items():
            if (not isinstance(alias, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,60}', alias) or
                not isinstance(grant, dict) or set(grant) != {'path', 'commit', 'files', 'rooms', 'senders'} or
                not isinstance(grant['path'], str) or not Path(grant['path']).is_absolute() or
                not isinstance(grant['commit'], str) or not re.fullmatch(r'[0-9a-f]{40}', grant['commit'])):
                raise ValueError('invalid repository grant configuration')
            for field in ['files', 'rooms', 'senders']:
                if (not isinstance(grant[field], list) or not grant[field] or
                    not all(isinstance(item, str) and item for item in grant[field])):
                    raise ValueError('invalid repository grant configuration')
            self.grants[alias] = {**grant, 'files': frozenset(safe_path(p) for p in grant['files']),
                                  'rooms': frozenset(grant['rooms']), 'senders': frozenset(grant['senders'])}

    @classmethod
    def from_file(cls, path):
        return cls(json.loads(Path(path).read_text()))

    def _git(self, grant, *args):
        # Only object reads; no checkout, filters, hooks, fetch, shell or message-selected refs.
        try:
            environment = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
            environment.update(GIT_NO_LAZY_FETCH='1', GIT_CONFIG_NOSYSTEM='1',
                               GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0')
            return subprocess.check_output(['git', '--no-lazy-fetch', '--no-replace-objects', '--literal-pathspecs',
                '-c', 'protocol.allow=never', '-c', 'core.fsmonitor=false',
                '-C', grant['path'], *args], stderr=subprocess.DEVNULL, timeout=10, env=environment)
        except (OSError, subprocess.SubprocessError):
            raise RepositoryDenied('repository_request_rejected') from None

    def read(self, event, command):
        if (not isinstance(command, dict) or set(command) - {'action', 'repository', 'path', 'base_blob'} or
            command.get('action') not in {'read', 'report'}):
            raise RepositoryDenied('repository_request_rejected')
        alias, name = command.get('repository'), safe_path(command.get('path'))
        if not isinstance(alias, str):
            raise RepositoryDenied('repository_request_rejected')
        grant = self.grants.get(alias)
        if (grant is None or event.get('room_id') not in grant['rooms'] or
            event.get('sender') not in grant['senders'] or name not in grant['files']):
            raise RepositoryDenied('repository_request_rejected')
        tree = self._git(grant, 'ls-tree', '-z', grant['commit'], '--', name)
        entries = tree.rstrip(b'\0').split(b'\0')
        if len(entries) != 1 or b'\t' not in entries[0]:
            raise RepositoryDenied('repository_request_rejected')
        metadata, actual = entries[0].split(b'\t', 1)
        parts = metadata.split()
        if actual != name.encode() or len(parts) != 3 or parts[0] not in {b'100644', b'100755'} or parts[1] != b'blob':
            raise RepositoryDenied('repository_request_rejected')
        oid = parts[2].decode('ascii')
        size = int(self._git(grant, 'cat-file', '-s', oid))
        if size > 8000:
            raise RepositoryDenied('repository_request_rejected')
        raw = self._git(grant, 'cat-file', 'blob', oid)
        try:
            content = raw.decode('utf-8')
        except UnicodeDecodeError:
            raise RepositoryDenied('repository_request_rejected') from None
        if '\x00' in content:
            raise RepositoryDenied('repository_request_rejected')
        return {'repository': alias, 'path': name, 'commit': grant['commit'], 'blob': oid,
                'content': content, 'bytes': len(raw), 'lines': len(content.splitlines()),
                'sha256': hashlib.sha256(raw).hexdigest()}


def report(snapshot):
    # Deterministic inventory, not semantic or LLM analysis. Source is untrusted text.
    return ('# Repository file report\n\nDeterministic file inventory · no LLM analysis.\n\n' +
            '\n'.join(f'- {key}: {json.dumps(snapshot[key], ensure_ascii=False)}'
                      for key in ['repository', 'path', 'commit', 'blob', 'bytes', 'lines', 'sha256']) + '\n')
