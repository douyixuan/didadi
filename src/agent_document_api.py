"""Scoped development Document API. Only this service owns Agent Git writes."""
import argparse
import hmac
import hashlib
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path

from scripts.agent_worker import render as echo
from src.gitdocs import Conflict, GitDocs, InvalidPath, PublicationPending, RemoteDiverged
from src.matrix_http import request, MatrixError
from src.repository_read import RepositoryDenied, RepositoryReader, report
from src.task_result import outcome, metadata_result
from src.runtime_socket import loopback_url

def document_result(item):
    return 'Saved demo.md\nGit commit: ' + item['commit'] + '\nBlob: ' + item['blob']


def render_outcome(task, store, repositories=None, resource=None):
    content = task['event']['content']
    document, source = content.get('org.didadi.document'), content.get('org.didadi.repository')
    mutation = (isinstance(document, dict) and document.get('action') == 'write' or
                isinstance(source, dict) and source.get('action') == 'report')
    bound = store._git('config', '--get', 'didadi.documentRoom', check=False).strip()
    if bound and (isinstance(document, dict) or mutation) and task['event'].get('room_id') != bound:
        return 'Document request rejected: this repository is bound to another room.', None, outcome('rejected', reason='invalid_request')
    if source is not None:
        try:
            if repositories is None or 'org.didadi.document' in task['event']['content']:
                raise RepositoryDenied('repository_request_rejected')
            snapshot = repositories.read(task['event'], source)
            if source['action'] == 'read':
                if resource is not None:resource.update({'kind':'repository',**snapshot})
                reference={'kind':'repository',**{key:snapshot[key] for key in ('repository','path','commit','blob')}}
                typed=outcome('read',resource=reference)
                return metadata_result(task['event'],typed), None, typed
            item = store.write('demo.md', report(snapshot), source.get('base_blob'), operation=task['id'],
                               notification={'task_id': task['id'], 'room_id': task['event']['room_id']})
            return document_result(item), item, outcome('saved', path='demo.md', commit=item['commit'], blob=item['blob'])
        except PublicationPending:
            raise
        except Conflict:
            return 'Document conflict: refresh the Git version and merge your changes. No remote history was overwritten.', None, outcome('conflict', reason='stale_version')
        except (ValueError, KeyError, TypeError):
            return 'Repository request rejected: no matching read grant, file or supported action.', None, outcome('rejected', reason='source_not_granted')
    command = task['event']['content'].get('org.didadi.document')
    if not isinstance(command, dict):
        return echo(task), None, None
    try:
        if command.get('action') == 'read':
            snapshot = store.snapshot('demo.md', command.get('commit'),max_bytes=65536)
            if resource is not None:resource.update({'kind':'document',**snapshot})
            typed=outcome('read', **({'path':'demo.md','commit':snapshot['commit'],'blob':snapshot['blob']} if snapshot['commit'] else {}))
            return metadata_result(task['event'],typed), None, typed
        if command.get('action') != 'write':
            raise ValueError('unsupported document action')
        content = command['content']
        if not isinstance(content, str) or len(content.encode('utf-8')) > 65536:
            raise ValueError('document too large')
        # The grant is fixed here, not selected by message content. The event ID is the operation ID.
        item = store.write('demo.md', content, command.get('base_blob'), operation=task['id'],
                           notification={'task_id': task['id'], 'room_id': task['event']['room_id']})
        return document_result(item), item, outcome('saved', path='demo.md', commit=item['commit'], blob=item['blob'])
    except PublicationPending:
        raise  # Do not complete/ack a saved but unpublished operation as a stale-write error.
    except Conflict:
        return 'Document conflict: refresh the Git version and merge your changes. No remote history was overwritten.', None, outcome('conflict', reason='stale_version')
    except (ValueError, InvalidPath, KeyError):
        return 'Document request rejected: invalid action, content or version.', None, outcome('rejected', reason='invalid_request')


def render(task, store, repositories=None):
    """Compatibility wrapper for callers that only need display text and commit."""
    text, item, _ = render_outcome(task, store, repositories)
    return text, item


class AgentDocuments:
    """Authority comes from Gateway storage on each call, never a runtime event."""
    def __init__(self, store, gateway, repositories=None, room=None):
        self.store, self.gateway, self.repositories = store, gateway, repositories
        with store._locked():
            bound=store._git('config','--get','didadi.documentRoom',check=False).strip()
            if room:
                if bound and bound != room: raise ValueError('document room binding mismatch')
                if not bound: store._git('config','didadi.documentRoom',room)
            self.room=bound or room

    def reconcile(self):
        for item in self.store.pending():
            notice = item.get('notification', {})
            if notice.get('kind') == 'document_commit':
                continue
            identifier = notice.get('task_id')
            if not identifier or item['operation'] != identifier:
                continue
            task = self.gateway('GET', '/agent/status', query={'id': identifier})['task']
            if task and task['status'] == 'done':
                self.store.acknowledge(identifier)
            elif task and task['status'] in {'failed', 'cancelled'}:
                self.store.abandon(identifier, task.get('last_error') or 'task_failed')
        return {'reconciled': True}

    def fixed_response(self, task, data, write_content=None):
        if write_content is not None:
            typed = task.get('outcome')
            if isinstance(typed, dict) and typed.get('status') == 'saved':
                command = task['event']['content']['org.didadi.document']
                fields = ['demo.md', write_content, command.get('base_blob'),
                          {'task_id':task['id'], 'room_id':task['event']['room_id']}]
                digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
                with self.store._locked():
                    item = self.store._operation(self.store._operation_ref(task['id']))
                if (not item or item['request_hash'] != digest or
                        any(item[key] != typed.get(key) for key in ('commit', 'blob'))):
                    raise MatrixError(409, {'error':'fixed_write_mismatch', 'retryable':False})
        response={'result':metadata_result(task['event'],task.get('outcome')) or task['result'],
                  'outcome':task.get('outcome'),'committed':False}
        typed=task.get('outcome')
        if isinstance(typed,dict) and typed.get('status')=='read':
            fixed=copy.deepcopy(task)
            if typed.get('commit'):
                fixed['event']['content']['org.didadi.document']['commit']=typed['commit']
            resource={}
            _,_,current=render_outcome(fixed,self.store,self.repositories,resource)
            if resource and current==typed:
                self.gateway('POST','/agent/document-scope',data=data)
                response['resource']=resource
        return response

    def write(self, data):
        if not isinstance(data,dict) or set(data)!={'id','lease','content'} or not isinstance(data['content'],str) or len(data['content'].encode('utf-8'))>65536:
            raise ValueError('Expected task id, lease and at most64KiB content')
        return self.execute({'id':data['id'],'lease':data['lease']},write_content=data['content'])

    def execute(self, data, *, write_content=None):
        if (not isinstance(data, dict) or set(data) != {'id', 'lease'} or
                any(not isinstance(data[k], str) or not data[k] for k in data)):
            raise ValueError('Expected only task id and lease')
        task = self.gateway('POST', '/agent/document-scope', data=data)['task']
        # Binding is local configuration, never document content or a caller override.
        event = task['event']; content = event['content']
        document, repository = content.get('org.didadi.document'), content.get('org.didadi.repository')
        if document is not None and repository is not None:
            return {'result':'Document request rejected: mixed commands.', 'outcome':outcome('rejected', reason='invalid_request'), 'committed':False}
        if (document is not None or repository is not None) and (not self.room or event['room_id'] != self.room):
            return {'result':'Document request rejected: configured room mismatch.', 'outcome':outcome('rejected', reason='invalid_request'), 'committed':False}
        if write_content is not None:
            command=task['event']['content'].get('org.didadi.document')
            if not isinstance(command,dict) or set(command)!={'action','base_blob'} or command['action']!='write':
                return {'result':'Document request rejected: write scope required.','outcome':outcome('rejected',reason='invalid_request'),'committed':False}
        if task.get('result') is not None:
            return self.fixed_response(task,data,write_content)
        # Read-only source grants and report rendering stay inside the service.
        # Recheck scope immediately before the operation after configuration I/O.
        task=self.gateway('POST', '/agent/document-scope', data=data)['task']
        if task.get('result') is not None:
            return self.fixed_response(task,data,write_content)
        if write_content is not None:
            command=task['event']['content'].get('org.didadi.document')
            if not isinstance(command,dict) or set(command)!={'action','base_blob'} or command['action']!='write':
                return {'result':'Document request rejected: write scope required.', 'outcome':outcome('rejected',reason='invalid_request'),'committed':False}
            task=copy.deepcopy(task);task['event']['content']['org.didadi.document']['content']=write_content
        resource={}
        result, item, structured = render_outcome(task, self.store, self.repositories, resource)
        response={'result':metadata_result(task['event'],structured) or result, 'outcome':structured, 'committed': item is not None}
        if resource:
            self.gateway('POST','/agent/document-scope',data=data)
            response['resource']=resource
        return response


def handler(service, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def do_POST(self):
            status = 200
            try:
                if (self.headers.get('Origin') is not None or not token or
                        not hmac.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token)):
                    raise MatrixError(403, {'error':'forbidden'})
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= (400000 if self.path=='/documents/write' else 2048): raise ValueError('invalid body size')
                data = json.loads(self.rfile.read(size))
                if self.path == '/documents/write': result = service.write(data)
                elif self.path == '/documents/execute': result = service.execute(data)
                elif self.path == '/documents/reconcile' and data == {}: result = service.reconcile()
                else: raise ValueError('invalid document API request')
            except RemoteDiverged as error:
                status, result = 503, {'error':'remote_diverged', 'retryable':True, 'recovery':error.recovery}
            except MatrixError as error:
                status, result = error.status, error.body
            except (ValueError, KeyError, TypeError):
                status, result = 400, {'error':'invalid_document_request', 'retryable':False}
            except Exception:
                status, result = 503, {'error':'document_service_unavailable', 'retryable':True}
            payload = json.dumps(result).encode()
            self.send_response(status); self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(payload))); self.end_headers(); self.wfile.write(payload)
    return Handler


class DocumentClient:
    def __init__(self, url, token):
        loopback_url(url, 'http')
        self.url, self.token = url, token
    def execute(self, data): return request(self.url, 'POST', '/documents/execute', self.token, data)
    def write(self, data): return request(self.url, 'POST', '/documents/write', self.token, data)
    def reconcile(self): return request(self.url, 'POST', '/documents/reconcile', self.token, {})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True); parser.add_argument('--token-file', required=True)
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9000')
    parser.add_argument('--port', type=int, default=9050); parser.add_argument('--repository-grants')
    parser.add_argument('--document-room', help='explicit fixed Matrix room; existing workspace binding may be reused')
    args = parser.parse_args(); loopback_url(args.gateway_url, 'http')
    token = Path(args.token_file).read_text().strip()
    reader = RepositoryReader.from_file(args.repository_grants) if args.repository_grants else None
    service = AgentDocuments(GitDocs(args.repo), lambda method,path,data=None,query=None:
        request(args.gateway_url,method,path,token,data,query), reader, args.document_room)
    if not service.room: parser.error('set --document-room or use an already bound workspace repository')
    ThreadingHTTPServer(('127.0.0.1',args.port),handler(service,token)).serve_forever()
