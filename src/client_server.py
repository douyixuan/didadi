"""Loopback development adapter for the React client, using only existing test credentials."""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, unquote, urlsplit

from src.gitdocs import GitDocs, Conflict, InvalidPath, NameCollision
from src.document_service import DocumentService, DocumentError
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import MatrixError, request, segment


class ClientError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class Workspace:
    def __init__(self, state, token, repo, metadata, matrix_url, gateway_url, repositories=None):
        for base in [matrix_url, gateway_url]:
            url = urlsplit(base)
            if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost'}:
                raise ValueError('only existing loopback development backends are supported')
        self.state, self.token = state, token
        self.matrix_url, self.gateway_url = matrix_url, gateway_url
        self.docs, self.metadata = GitDocs(repo), str(metadata)
        self.csrf = secrets.token_urlsafe(32)
        self.user_id = self.api('GET', '/account/whoami')['user_id']
        self.documents = DocumentService(self.docs, self.api, self.user_id, state['room'])
        self.repository_reads = []
        if repositories is not None:
            for alias, grant in repositories.grants.items():
                if self.user_id in grant['senders']:
                    self.repository_reads.extend({'repository': alias, 'path': name, 'commit': grant['commit'], 'room': room}
                        for name in sorted(grant['files']) for room in sorted(grant['rooms']))
        with sqlite3.connect(self.metadata) as db:
            db.execute('CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, operation TEXT UNIQUE)')
            db.execute('INSERT OR IGNORE INTO rooms VALUES (?,?)', (state['room'], 'seed'))

    def api(self, method, path, data=None, query=None):
        return request(self.matrix_url, method, PREFIX + path, self.state['tokens'][0], data, query)

    def allowed(self, room):
        with sqlite3.connect(self.metadata) as db:
            if db.execute('SELECT 1 FROM rooms WHERE id=?', (room,)).fetchone() is None:
                raise ClientError(403, 'This room is not part of the local demo.')

    def repository_choices(self):
        with sqlite3.connect(self.metadata) as db:
            rooms = {row[0] for row in db.execute('SELECT id FROM rooms')}
        return [source for source in self.repository_reads if source['room'] in rooms]

    def task_event(self, room, task_id):
        self.allowed(room)
        if not isinstance(task_id,str) or not 0<len(task_id)<=1000:
            raise ClientError(400,'Invalid task reference.')
        return self.api('GET','/rooms/'+segment(room)+'/event/'+segment(task_id))

    def cancel_task(self, room, task_id):
        event=self.task_event(room,task_id)
        if event.get('sender')!=self.user_id:
            raise ClientError(403,'Only the original requester can cancel this task.')
        return request(self.gateway_url,'POST','/agent/cancel',self.token,{'id':task_id})

    def create_room(self, operation, name):
        if (not isinstance(operation, str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', operation) or
            not isinstance(name, str) or not 1 <= len(name.strip()) <= 60):
            raise ClientError(400, 'Enter a room name of 1–60 characters.')
        alias = 'didadi-client-' + hashlib.sha256(operation.encode()).hexdigest()[:32]
        with sqlite3.connect(self.metadata, timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT id FROM rooms WHERE operation=?', (operation,)).fetchone()
            if old:
                return {'room_id': old[0]}
            try:
                room = self.api('POST', '/createRoom', {'preset': 'private_chat', 'name': name.strip(),
                                'room_alias_name': alias, 'invite': [AGENT]})['room_id']
            except MatrixError as error:
                if error.body.get('errcode') != 'M_ROOM_IN_USE':
                    raise
                server = self.user_id.split(':', 1)[1]
                room = self.api('GET', '/directory/room/' + segment('#' + alias + ':' + server))['room_id']
                membership = self.api('GET', '/rooms/' + segment(room) + '/state/m.room.member/' + segment(self.user_id))
                if membership.get('membership') != 'join':
                    raise ClientError(403, 'Recovered room is not joined by this demo identity.')
            db.execute('INSERT INTO rooms VALUES (?,?)', (room, operation))
            return {'room_id': room}

    def proxy(self, method, path, query, data=None):
        if any(key in query for key in ['access_token', 'user_id']):
            raise ClientError(403, 'Identity overrides are not permitted.')
        if method == 'GET' and path == '/joined_rooms':
            joined = self.api('GET', path)['joined_rooms']
            with sqlite3.connect(self.metadata) as db:
                allowed = {row[0] for row in db.execute('SELECT id FROM rooms')}
            return {'joined_rooms': [room for room in joined if room in allowed]}
        match = re.fullmatch(r'/rooms/([^/]+)/(messages|state|event/[^/]+|send/m\.room\.message/[^/]+)', path)
        if not match:
            raise ClientError(403, 'Unsupported development client route.')
        room, route = unquote(match[1]), match[2]
        self.allowed(room)
        if method == 'GET' and (route in {'messages', 'state'} or route.startswith('event/')):
            filtered = {key: values[0] for key, values in query.items()
                        if key in {'from', 'to', 'dir', 'filter'}}
            if route == 'messages':
                filtered['limit'] = '50'
            return self.api('GET', path, query=filtered)
        if method != 'PUT' or not route.startswith('send/m.room.message/'):
            raise ClientError(403, 'Unsupported development client method.')
        if (not isinstance(data, dict) or data.get('msgtype') != 'm.text' or
            not isinstance(data.get('body'), str) or not 1 <= len(data['body'].strip()) <= 4000):
            raise ClientError(400, 'Enter a text message of 1–4000 characters.')
        # Fail closed before accepting agent context; the gateway independently rechecks permissions.
        state = self.api('GET', '/rooms/' + segment(room) + '/state')
        if any(event['type'] == 'm.room.encryption' for event in state):
            raise ClientError(409, 'Encrypted rooms are not supported by this demo. No message was sent.')
        mentions = data.get('m.mentions', {}).get('user_ids', [])
        if mentions and mentions != [AGENT]:
            raise ClientError(400, 'Only the explicitly labeled example agent is available.')
        command = data.get('org.didadi.document')
        repository = data.get('org.didadi.repository')
        if repository is not None:
            if (command is not None or not isinstance(repository, dict) or mentions != [AGENT] or
                repository.get('action') not in {'read', 'report'} or
                not isinstance(repository.get('repository'), str) or not isinstance(repository.get('path'), str) or
                set(repository) - {'action', 'repository', 'path', 'base_blob'}):
                raise ClientError(400, 'Invalid repository request. Runtime read grants are required.')
        if isinstance(repository, dict) and repository.get('action') == 'report':
            self.documents.authorize(room, write=True)
        if command is not None:
            if (not isinstance(command, dict) or command.get('action') != 'read' or
                    mentions != [AGENT] or set(command) - {'action', 'commit'}):
                raise ClientError(400, 'Use the direct document API to save. Matrix document requests contain read metadata only.')
        if mentions and not any(event['type'] == 'm.room.member' and event.get('state_key') == AGENT and
                                event['content'].get('membership') == 'join' for event in state):
            raise ClientError(409, 'The example agent is still joining. Refresh and retry.')
        content = {'msgtype': 'm.text', 'body': data['body'], 'm.mentions': {'user_ids': mentions}}
        if command:
            content['org.didadi.document'] = command
        if repository is not None:
            content['org.didadi.repository'] = repository
        relation = data.get('m.relates_to')
        if relation:
            if not isinstance(relation, dict) or relation.get('rel_type') != 'm.thread' or not isinstance(relation.get('event_id'), str):
                raise ClientError(400, 'Invalid thread reference.')
            self.api('GET', '/rooms/' + segment(room) + '/event/' + segment(relation['event_id']))
            content['m.relates_to'] = relation
        return self.api('PUT', path, content)


def handler(workspace, dist, port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, kind='application/json'):
            payload = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(payload)

        def handle_request(self, method):
            try:
                if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                    raise ClientError(403, 'Loopback Host required.')
                if method != 'GET':
                    if not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), workspace.csrf):
                        raise ClientError(403, 'Refresh this local session before retrying.')
                    origin = self.headers.get('Origin')
                    if origin and origin not in {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}:
                        raise ClientError(403, 'Same-origin requests required.')
                parsed = urlsplit(self.path)
                query = parse_qs(parsed.query)
                body = None
                if method != 'GET':
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 0 < size < 500000:
                        raise ClientError(400, 'Invalid request size.')
                    body = json.loads(self.rfile.read(size))
                if parsed.path == '/api/session' and method == 'GET':
                    result = {'csrf': workspace.csrf, 'userId': workspace.user_id, 'agentId': AGENT,
                              'initialRoom': workspace.state['room'], 'documentRoom': workspace.state['room'], 'documentSave': 'direct-v1', 'qa': getattr(workspace, 'qa', None), 'agentLabel': 'Example echo agent · no LLM',
                              'repositoryReads': workspace.repository_choices()}
                elif parsed.path == '/api/documents' and method == 'GET':
                    result = workspace.documents.documents(query.get('room', [''])[0])
                elif parsed.path == '/api/documents' and method == 'POST':
                    result = workspace.documents.create(body)
                elif parsed.path.startswith('/api/documents/') and method == 'PUT':
                    name = unquote(parsed.path[len('/api/documents/'):], errors='strict')
                    result = workspace.documents.save(body, name)
                elif parsed.path == '/api/task/cancel' and method == 'POST':
                    result = workspace.cancel_task(body['room'],body['id'])
                elif parsed.path == '/api/task/audit' and method == 'GET':
                    room=query.get('room',[''])[0];task_id=query.get('id',[''])[0]
                    workspace.task_event(room,task_id)
                    result=request(workspace.gateway_url,'GET','/agent/audit',workspace.token,query={'id':task_id})
                elif parsed.path == '/api/rooms' and method == 'POST':
                    result = workspace.create_room(body['operation'], body['name'])
                elif parsed.path == '/matrix/_matrix/client/versions' and method == 'GET':
                    result = request(workspace.matrix_url, 'GET', '/_matrix/client/versions')
                elif parsed.path.startswith('/matrix' + PREFIX):
                    result = workspace.proxy(method, parsed.path[len('/matrix' + PREFIX):], query, body)
                elif parsed.path in {'/api/document', '/api/history', '/api/task'} and method == 'GET':
                    room = query.get('room', [''])[0]
                    workspace.allowed(room)
                    if parsed.path == '/api/document':
                        result = workspace.documents.read(room, query.get('commit', [None])[0], query.get('path', ['demo.md'])[0])
                    elif parsed.path == '/api/history':
                        workspace.documents.authorize(room)
                        result = {'commits': workspace.docs.history(query.get('path', ['demo.md'])[0])}
                    else:
                        event_id = query.get('id', [''])[0]
                        workspace.api('GET', '/rooms/' + segment(room) + '/event/' + segment(event_id))
                        result = request(workspace.gateway_url, 'GET', '/agent/status', workspace.token, query={'id': event_id})
                        task = result['task']
                elif method == 'GET' and not parsed.path.startswith(('/api/', '/matrix/')):
                    path = (dist / unquote(parsed.path).lstrip('/')).resolve()
                    if not path.is_relative_to(dist.resolve()):
                        raise ClientError(403, 'Invalid asset path.')
                    if not path.is_file():
                        path = dist / 'index.html'
                    self.respond(200, path.read_bytes(), mimetypes.guess_type(str(path))[0] or 'application/octet-stream')
                    return
                else:
                    raise ClientError(404, 'Unknown client route.')
                self.respond(200, result)
            except DocumentError as error:
                self.respond(error.status, error.data)
            except ClientError as error:
                self.respond(error.status, {'error': error.message})
            except NameCollision:
                self.respond(409, {'error': 'This document name collides with an existing path. Choose another name.', 'status': 'name_conflict'})
            except InvalidPath:
                self.respond(400, {'error': 'Use a safe, portable Markdown path ending in .md.'})
            except (ValueError, KeyError, TypeError):
                self.respond(400, {'error': 'Invalid request or document revision.'})
            except Conflict:
                self.respond(409, {'error': 'Git publication requires reconciliation; your draft is preserved.'})
            except MatrixError as error:
                self.respond(error.status if error.status < 500 else 503,
                             {'error': 'Matrix request failed. Keep your draft and retry.', 'errcode': error.body.get('errcode', 'M_UNKNOWN')})
            except Exception:
                self.respond(503, {'error': 'Local backend unavailable. Keep your draft and retry.'})

        def do_GET(self):
            self.handle_request('GET')

        def do_POST(self):
            self.handle_request('POST')

        def do_PUT(self):
            self.handle_request('PUT')
    return Handler


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--repository-grants', help='advertise explicitly configured read choices; runtime independently enforces grants')
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--dist', default='client/dist')
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8009')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9001')
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    from src.repository_read import RepositoryReader
    repositories = RepositoryReader.from_file(args.repository_grants) if args.repository_grants else None
    workspace = Workspace(json.loads(Path(args.state_file).read_text()), Path(args.token_file).read_text().strip(),
                          args.repo, args.metadata, args.matrix_url, args.gateway_url, repositories)
    print(f'React workspace http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), handler(workspace, Path(args.dist), args.port)).serve_forever()
