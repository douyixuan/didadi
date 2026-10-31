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
from src.matrix_sessions import MatrixSessions, SessionError


class ClientError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


from src.room_service import RoomService,RoomError
from src.direct_chats import DirectChats,DirectChatError
from src.source_references import SourceReferences
from src.search_service import SearchService
from src.attachment_service import AttachmentService,MAX_ATTACHMENT_BYTES


class Workspace:
    def __init__(self, state, token, repo, metadata, matrix_url, gateway_url, repositories=None, fixture_contacts=(), live=False):
        for base in [matrix_url, gateway_url]:
            url = urlsplit(base)
            if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost'}:
                raise ValueError('only existing loopback development backends are supported')
        self.state, self.token, self.live = state, token, live
        self.matrix_url, self.gateway_url = matrix_url, gateway_url
        self.docs, self.metadata = GitDocs(repo), str(metadata)
        self.csrf = secrets.token_urlsafe(32)
        self.user_id = self.api('GET', '/account/whoami')['user_id']
        self.documents = DocumentService(self.docs, self.api, self.user_id, state['room'])
        self.search = SearchService(self.documents,self.api,self.allowed)
        self.attachments=AttachmentService(self.metadata,self.api,self.allowed,self.matrix_url,self.user_id,self.state['tokens'][0])
        self.sources=SourceReferences(repositories,self.api,self.allowed,self.user_id)
        self.repository_reads = []
        if repositories is not None:
            for alias, grant in repositories.grants.items():
                if self.user_id in grant['senders']:
                    self.repository_reads.extend({'repository': alias, 'path': name, 'commit': grant['commit'], 'room': room}
                        for name in sorted(grant['files']) for room in sorted(grant['rooms']))
        with sqlite3.connect(self.metadata) as db:
            db.execute('CREATE TABLE IF NOT EXISTS rooms (id TEXT PRIMARY KEY, operation TEXT UNIQUE)')
            db.execute('INSERT OR IGNORE INTO rooms VALUES (?,?)', (state['room'], 'seed'))
        self.room_service=RoomService(self.metadata,self.api,self.user_id,fixture_contacts)
        self.direct_chats=DirectChats(self.metadata,self.api,self.user_id,self.allowed)

    def api(self, method, path, data=None, query=None):
        return request(self.matrix_url, method, PREFIX + path, self.state['tokens'][0], data, query)

    def allowed(self, room):
        with sqlite3.connect(self.metadata) as db:
            if db.execute('SELECT 1 FROM rooms WHERE id=?', (room,)).fetchone() is None:
                raise ClientError(403, 'This room is not part of this workspace.')
        if self.live and room not in self.api('GET', '/joined_rooms')['joined_rooms']:
            raise ClientError(403, 'You are not joined to this room.')

    def repository_choices(self):
        with sqlite3.connect(self.metadata) as db:
            rooms = {row[0] for row in db.execute('SELECT id FROM rooms')}
        if self.live:
            rooms &= set(self.api('GET', '/joined_rooms')['joined_rooms'])
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

    def create_room(self,operation,name,**options):
        try:return self.direct_chats.after_create(self.room_service.create({'operation':operation,'name':name,**options}))
        except RoomError as error:raise ClientError(error.status,error.message) from None

    def thread_relations(self, method, path, query):
        match=re.fullmatch(r'/rooms/([^/]+)/relations/([^/]+)/m\.thread/m\.room\.message',path)
        if method!='GET' or not match or any(key in query for key in ['access_token','user_id']):
            raise ClientError(403,'Unsupported thread route.')
        self.allowed(unquote(match[1]))
        filtered={key:values[0] for key,values in query.items() if key in {'from','to'}}
        filtered.update({'limit':'50','dir':'b'})
        return request(self.matrix_url,'GET','/_matrix/client/v1'+path,self.state['tokens'][0],query=filtered)

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
            raise ClientError(409, 'The example Agent is not joined to this room. It must be explicitly invited before it can receive messages.')
        content = {'msgtype': 'm.text', 'body': data['body'], 'm.mentions': {'user_ids': mentions}}
        if command:
            content['org.didadi.document'] = command
        if repository is not None:
            content['org.didadi.repository'] = repository
        source=data.get('org.didadi.source_ref')
        if source is not None:
            try:expected=self.sources.reference(room,source)
            except ValueError:raise ClientError(403,'Source reference is not available through the current grants.') from None
            if data['body']!=expected or mentions or command is not None or repository is not None:
                raise ClientError(400,'Send the canonical source excerpt without Agent commands or mentions.')
            content['org.didadi.source_ref']=source
        relation = data.get('m.relates_to')
        if relation:
            if not isinstance(relation, dict) or set(relation)-{'rel_type','event_id','m.in_reply_to'}:
                raise ClientError(400, 'Invalid message reference.')
            targets=[]
            if 'rel_type' in relation or 'event_id' in relation:
                if relation.get('rel_type')!='m.thread':
                    raise ClientError(400, 'Invalid thread reference.')
                targets.append(relation.get('event_id'))
            if 'm.in_reply_to' in relation:
                reply=relation['m.in_reply_to']
                if not isinstance(reply,dict) or set(reply)!={'event_id'}:
                    raise ClientError(400, 'Invalid quoted message reference.')
                targets.append(reply['event_id'])
            if not targets or any(not isinstance(target,str) or not target.startswith('$') or len(target)>512 for target in targets):
                raise ClientError(400, 'Invalid message reference.')
            for target in dict.fromkeys(targets):
                self.api('GET', '/rooms/' + segment(room) + '/event/' + segment(target))
            content['m.relates_to'] = relation
        return self.api('PUT', path, content)


def handler(workspace, dist, port, sessions=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, data, kind='application/json', headers=None):
            payload = json.dumps(data).encode() if kind == 'application/json' else data
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; frame-ancestors 'none'")
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers()
            self.wfile.write(payload)

        def handle_request(self, method):
            try:
                if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                    raise ClientError(403, 'Loopback Host required.')
                parsed = urlsplit(self.path)
                origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
                if sessions is not None and parsed.path == '/api/auth/login':
                    if (method != 'POST' or self.headers.get('Origin') not in origins or
                            self.headers.get('X-Didadi-Login') != '1' or
                            self.headers.get_content_type() != 'application/json'):
                        raise ClientError(403, 'Same-origin Matrix password sign-in required.')
                    size = int(self.headers.get('Content-Length', '0'))
                    if not 1 <= size <= 4096:
                        raise ClientError(400, 'Invalid login request size.')
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict) or set(data) != {'username', 'password'}:
                        raise ClientError(400, 'Expected username and password.')
                    handle, authenticated = sessions.login(data['username'], data['password'])
                    self.respond(200, {'userId': authenticated.user_id}, headers={
                        'Set-Cookie': sessions.cookie(handle)})
                    return
                current_workspace = workspace
                if sessions is not None and parsed.path.startswith(('/api/', '/matrix/')):
                    # Sign-out must work offline: validate the local cookie+CSRF+origin,
                    # then invalidate it even when Matrix /whoami is unreachable.
                    signed_out = parsed.path == '/api/auth/logout' and method == 'POST'
                    current_session = (sessions.local(self.headers.get('Cookie')) if signed_out
                                       else sessions.require(self.headers.get('Cookie')))
                    current_workspace = current_session.workspace
                if method != 'GET':
                    if current_workspace is None or not hmac.compare_digest(
                            self.headers.get('X-CSRF-Token', ''), current_workspace.csrf):
                        raise ClientError(403, 'Refresh this session before retrying.')
                    origin = self.headers.get('Origin')
                    if origin and origin not in origins:
                        raise ClientError(403, 'Same-origin requests required.')
                    if sessions is not None and origin not in origins:
                        raise ClientError(403, 'Same-origin requests required.')
                query = parse_qs(parsed.query)
                body = None
                if method != 'GET':
                    size = int(self.headers.get('Content-Length', '0'))
                    if parsed.path=='/api/attachments' and method=='POST':
                        if not 0<=size<=MAX_ATTACHMENT_BYTES:raise ClientError(413,'Attachments must be at most 5 MiB.')
                        body=self.rfile.read(size)
                    else:
                        if not 0 < size < 500000:
                            raise ClientError(400, 'Invalid request size.')
                        body = json.loads(self.rfile.read(size))
                if sessions is not None and parsed.path == '/api/auth/logout' and method == 'POST':
                    if body != {}:
                        raise ClientError(400, 'Logout accepts no request parameters.')
                    result = sessions.logout(self.headers.get('Cookie'))
                    self.respond(200, result, headers={'Set-Cookie': sessions.clear_cookie()})
                    return
                if parsed.path == '/api/session' and method == 'GET':
                    result = {'csrf': current_workspace.csrf, 'userId': current_workspace.user_id, 'agentId': AGENT,
                              'initialRoom': current_workspace.state['room'], 'documentRoom': current_workspace.state['room'], 'documentSave': 'direct-v1', 'qa': getattr(workspace, 'qa', None), 'agentLabel': 'Example echo agent · no LLM',
                              'directChats':True, 'liveMatrix': sessions is not None, 'repositoryReads': current_workspace.repository_choices(), 'roomCreation':{'version':1,'visibility':'private','kinds':['direct','group','channel'],'contacts':list(current_workspace.room_service.contacts)}}
                elif parsed.path=='/api/attachments' and method=='POST':
                    if set(query)-{'room','name','operation','type','root'} or any(len(values)!=1 for values in query.values()):raise ClientError(400,'Unknown attachment parameter.')
                    result=current_workspace.attachments.upload(query.get('room',[''])[0],query.get('name',[''])[0],query.get('operation',[''])[0],query.get('type',['application/octet-stream'])[0],body,query.get('root',[None])[0])
                elif parsed.path=='/api/attachments/download' and method=='GET':
                    if set(query)!={'room','event'} or any(len(values)!=1 for values in query.values()):raise ClientError(400,'Use one room and one attachment event.')
                    if not hmac.compare_digest(self.headers.get('X-CSRF-Token',''),current_workspace.csrf):raise ClientError(403,'Use the current local session to download attachments.')
                    name,payload=current_workspace.attachments.download(query.get('room',[''])[0],query.get('event',[''])[0])
                    from urllib.parse import quote
                    self.respond(200,payload,'application/octet-stream',{'Content-Disposition':"attachment; filename*=UTF-8''"+quote(name,safe='')})
                    return
                elif parsed.path == '/api/repositories/read' and method == 'POST':
                    try:result=current_workspace.sources.read(body)
                    except ValueError:raise ClientError(403,'Source is not available through the current grants.') from None
                elif parsed.path == '/api/search/messages' and method == 'POST':
                    result = current_workspace.search.messages(body)
                elif parsed.path == '/api/search/documents' and method == 'POST':
                    result = current_workspace.search.files(body)
                elif parsed.path == '/api/documents' and method == 'GET':
                    result = current_workspace.documents.documents(query.get('room', [''])[0])
                elif parsed.path == '/api/documents' and method == 'POST':
                    result = current_workspace.documents.create(body)
                elif parsed.path == '/api/documents/from-messages' and method == 'POST':
                    result = current_workspace.documents.from_messages(body)
                elif parsed.path == '/api/documents/move' and method == 'POST':
                    result = current_workspace.documents.move(body)
                elif parsed.path.startswith('/api/documents/') and method == 'PUT':
                    name = unquote(parsed.path[len('/api/documents/'):], errors='strict')
                    result = current_workspace.documents.save(body, name)
                elif parsed.path == '/api/task/cancel' and method == 'POST':
                    result = current_workspace.cancel_task(body['room'],body['id'])
                elif parsed.path == '/api/task/audit' and method == 'GET':
                    room=query.get('room',[''])[0];task_id=query.get('id',[''])[0]
                    current_workspace.task_event(room,task_id)
                    result=request(current_workspace.gateway_url,'GET','/agent/audit',current_workspace.token,query={'id':task_id})
                elif parsed.path=='/api/direct-chats' and method=='GET':
                    if query:raise ClientError(400,'Direct-chat preferences use the current identity only.')
                    result=current_workspace.direct_chats.snapshot()
                elif parsed.path=='/api/direct-chats/retry' and method=='POST':
                    if query or not isinstance(body,dict) or set(body)!={'room'} or not isinstance(body['room'],str):raise ClientError(400,'Use only the existing room for synchronization retry.')
                    result=current_workspace.direct_chats.retry(body['room'])
                elif parsed.path == '/api/rooms' and method == 'POST':
                    try:result=current_workspace.direct_chats.after_create(current_workspace.room_service.create(body))
                    except RoomError as error:raise ClientError(error.status,error.message) from None
                elif parsed.path == '/matrix/_matrix/client/versions' and method == 'GET':
                    result = request(current_workspace.matrix_url, 'GET', '/_matrix/client/versions')
                elif parsed.path.startswith('/matrix/_matrix/client/v1/'):
                    result = current_workspace.thread_relations(method, parsed.path[len('/matrix/_matrix/client/v1'):], query)
                elif parsed.path.startswith('/matrix' + PREFIX):
                    result = current_workspace.proxy(method, parsed.path[len('/matrix' + PREFIX):], query, body)
                elif parsed.path in {'/api/document', '/api/history', '/api/task'} and method == 'GET':
                    room = query.get('room', [''])[0]
                    current_workspace.allowed(room)
                    if parsed.path == '/api/document':
                        result = current_workspace.documents.read(room, query.get('commit', [None])[0], query.get('path', ['demo.md'])[0])
                    elif parsed.path == '/api/history':
                        current_workspace.documents.authorize(room)
                        result = {'commits': current_workspace.docs.history(query.get('path', ['demo.md'])[0])}
                    else:
                        event_id = query.get('id', [''])[0]
                        current_workspace.api('GET', '/rooms/' + segment(room) + '/event/' + segment(event_id))
                        result = request(current_workspace.gateway_url, 'GET', '/agent/status', current_workspace.token, query={'id': event_id})
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
            except SessionError as error:
                self.respond(error.status, {'error': error.message}, headers={
                    'Set-Cookie': sessions.clear_cookie()} if sessions is not None and
                    error.status == 401 and parsed.path != '/api/auth/login' else None)
            except DirectChatError as error:
                self.respond(error.status, {'error':error.message})
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
                data={'error':'Matrix request failed. Keep your draft and retry.','errcode':error.body.get('errcode','M_UNKNOWN')}
                wait=error.body.get('retry_after_ms')
                if error.status==429 and type(wait) in {int,float} and 0<=wait<=86400000:
                    data['retry_after_ms']=wait
                self.respond(error.status if error.status < 500 else 503,data)
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
    parser.add_argument('--fixture-contacts',help='JSON list of explicitly configured local test identity IDs; contains no tokens')
    parser.add_argument('--fixture-contact',action='append',default=[],help='explicit local test identities available for room invitations; no credentials')
    parser.add_argument('--metadata', required=True)
    parser.add_argument('--dist', default='client/dist')
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8009')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9001')
    parser.add_argument('--port', type=int, default=8767)
    parser.add_argument('--auth-mode', choices=('fixture', 'matrix'), default='fixture',
                        help='matrix requires actual Matrix password login; no implicit fixture login')
    args = parser.parse_args()
    from src.repository_read import RepositoryReader
    repositories = RepositoryReader.from_file(args.repository_grants) if args.repository_grants else None
    fixture_contacts=json.loads(Path(args.fixture_contacts).read_text()) if args.fixture_contacts else []
    if not isinstance(fixture_contacts,list):parser.error('--fixture-contacts must contain a JSON list of identity IDs')
    state = json.loads(Path(args.state_file).read_text())
    agent_token = Path(args.token_file).read_text().strip()
    if args.auth_mode == 'matrix':
        # Do not send submitted passwords to an operator-controlled non-loopback URL.
        for base in (args.matrix_url, args.gateway_url):
            url = urlsplit(base)
            if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost'}:
                parser.error('real Matrix login is restricted to loopback backends')
        if not isinstance(state, dict) or not isinstance(state.get('room'), str):
            parser.error('a trusted document room ID is required in --state-file')
        def create_workspace(matrix_token, user_id):
            # Fixture tokens, if present, are deliberately not used for real-user sessions.
            workspace = Workspace({'room': state['room'], 'tokens': [matrix_token]}, agent_token,
                                  args.repo, args.metadata, args.matrix_url, args.gateway_url,
                                  repositories, [peer for peer in args.fixture_contact + fixture_contacts
                                                 if peer != user_id], live=True)
            if workspace.user_id != user_id:
                raise ClientError(401, 'Matrix account identity mismatch.')
            return workspace
        sessions = MatrixSessions(args.matrix_url, create_workspace)
        workspace = None
    else:
        sessions = None
        workspace = Workspace(state, agent_token, args.repo, args.metadata,
                              args.matrix_url, args.gateway_url, repositories,
                              args.fixture_contact + fixture_contacts)
    print(f'React workspace http://127.0.0.1:{args.port} ({args.auth_mode})', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), handler(
        workspace, Path(args.dist), args.port, sessions)).serve_forever()
