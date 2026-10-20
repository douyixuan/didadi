"""Direct development document API. Git owns contents, versions and receipt intent."""
import hashlib
import re
import uuid

from src.document_access import document_level, DocumentAccessError
from src.gitdocs import Conflict, MergeConflict, PublicationPending, RemoteDiverged
from src.matrix_http import MatrixError, segment


class DocumentError(Exception):
    def __init__(self, http_status, message, **data):
        self.status, self.data = http_status, {'error': message, **data}
        super().__init__(message)


class DocumentService:
    def __init__(self, store, api, user_id, room):
        self.store, self.api, self.user_id, self.room = store, api, user_id, room
        with store._locked():
            bound = store._git('config', '--get', 'didadi.documentRoom', check=False).strip()
            if bound and bound != room:
                raise ValueError('document repository is already bound to another room')
            if not bound:
                store._git('config', 'didadi.documentRoom', room)

    def authorize(self, room, write=False):
        if room != self.room:
            raise DocumentError(403, 'This document is bound to the workspace room.')
        try:
            return document_level(self.api, room, self.user_id, write)
        except DocumentAccessError as error:
            raise DocumentError(error.status, error.message) from None

    def read(self, room, commit=None, name='demo.md'):
        level = self.authorize(room)
        # Receipt recovery cannot make an already committed document unreadable.
        self.deliver_pending()
        try:
            return {**self.store.snapshot(name, commit), 'writable': level >= 50}
        except RemoteDiverged as error:
            raise DocumentError(503, str(error), status='remote_diverged', recovery=error.recovery) from None

    def documents(self, room):
        level = self.authorize(room)
        self.deliver_pending()
        try:
            return {**self.store.documents(), 'writable': level >= 50}
        except RemoteDiverged as error:
            raise DocumentError(503, str(error), status='remote_diverged', recovery=error.recovery) from None

    def create(self, data):
        if not isinstance(data, dict) or set(data) != {'room', 'operation', 'content', 'name'}:
            raise DocumentError(400, 'Expected room, operation, content and name.')
        return self.save({key: data[key] for key in ('room', 'operation', 'content')} | {'base_blob': None}, data['name'], create=True)

    def move(self, data):
        if not isinstance(data, dict) or set(data) != {'room', 'operation', 'source', 'name', 'base_blob'}:
            raise DocumentError(400, 'Expected room, operation, source, name and base_blob.')
        self.store._name(data['source'])
        if data['source'] == data['name'] or data['base_blob'] is None:
            raise DocumentError(400, 'Move needs a distinct destination and the current source blob.')
        return self.save({key: data[key] for key in ('room', 'operation', 'base_blob')} | {'content': ''},
                         data['name'], move_from=data['source'])

    def save(self, data, name='demo.md', *, create=False, move_from=None):
        if not isinstance(data, dict) or set(data) != {'room', 'operation', 'content', 'base_blob'}:
            raise DocumentError(400, 'Expected room, operation, content and base_blob.')
        self.store._name(name)
        operation, content, base = data['operation'], data['content'], data['base_blob']
        try:
            valid_id = isinstance(operation, str) and str(uuid.UUID(operation)) == operation
            size = len(content.encode('utf-8')) if isinstance(content, str) else -1
        except (ValueError, UnicodeError):
            valid_id, size = False, -1
        if not valid_id or not 0 <= size <= 65536 or (base is not None and
                (not isinstance(base, str) or not re.fullmatch('[0-9a-f]{40}', base))):
            raise DocumentError(400, 'Use a UUID operation, a Git base blob and at most 64 KiB of UTF-8 text.')
        self.authorize(data['room'], write=True)
        key = 'human-save:' + hashlib.sha256((self.user_id + '\0' + self.room + '\0' + operation).encode()).hexdigest()
        notice = {'kind': 'document_commit', 'version': 1, 'room_id': self.room, 'author': self.user_id}
        try:
            item = self.store.write(name, content, base, operation=key, notification=notice,
                merge_non_overlapping=not create and move_from is None, move_from=move_from, author={'name': self.user_id, 'email': hashlib.sha256(self.user_id.encode()).hexdigest()[:24] + '@matrix.invalid'})
        except RemoteDiverged as error:
            raise DocumentError(503, str(error), status='remote_diverged', recovery=error.recovery) from None
        except PublicationPending:
            raise DocumentError(503, 'Git publication is pending. Keep the draft and retry the same operation.', status='publication_pending') from None
        except MergeConflict as error:
            raise DocumentError(409,'Overlapping edits need a manual merge. Keep your draft.',status='conflict',
                                current_blob=self.store.blob_version(name),
                                conflict_markdown=error.conflict_markdown,conflict_truncated=error.truncated) from None
        except Conflict:
            raise DocumentError(409, 'A newer version exists or this operation was used for different text. Keep your draft.',
                                status='conflict', current_blob=self.store.blob_version(name)) from None
        try:
            receipt = self.deliver(item)
        except (DocumentError, MatrixError, OSError, RuntimeError, Conflict):
            receipt = None
        return {'status': 'saved', 'commit': item['commit'], 'blob': item['blob'], 'path': name,
                'author': self.user_id, 'merged':bool(item.get('merged')),
                'content':self.store.read(name,item['commit']), 'receipt': receipt, 'receipt_pending': receipt is None}

    def deliver(self, item):
        notice = {'kind': 'document_commit', 'version': 1, 'room_id': self.room, 'author': self.user_id}
        if item.get('notification') != notice or not item['operation'].startswith('human-save:'):
            raise DocumentError(403, 'This receipt belongs to another operation.')
        self.authorize(self.room, write=True)
        name = self.store._name(item['name'])
        txn = hashlib.sha256(('document-receipt:' + item['operation']).encode()).hexdigest()
        sent = self.api('PUT', '/rooms/' + segment(self.room) + '/send/m.room.message/' + txn, {
            'msgtype': 'm.text', 'body': 'Saved ' + name + ' (' + item['commit'][:10] + ')',
            'org.didadi.document.commit': {'version': 1, 'path': name, 'commit': item['commit'],
                'blob': item['blob'], 'author': self.user_id}})
        self.store.acknowledge(item['operation'])
        return sent

    def deliver_pending(self):
        try:
            notice = {'kind': 'document_commit', 'version': 1, 'room_id': self.room, 'author': self.user_id}
            for item in self.store.pending():
                if item.get('notification') == notice and item['operation'].startswith('human-save:'):
                    self.deliver(item)
        except (DocumentError, MatrixError, OSError, RuntimeError, Conflict):
            # Recovery cannot turn a committed document into a failed save/read.
            return
