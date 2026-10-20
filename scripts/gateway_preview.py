"""Loopback-only development preview; credentials stay on the server."""
import argparse
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import threading
import time
import uuid
from urllib.parse import parse_qs, urlsplit

from scripts.agent_worker import once
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment


def serve(state, worker_token, port=8765, document_repo=None,
          matrix_url='http://127.0.0.1:8008', gateway_url='http://127.0.0.1:9000'):
    room = '/rooms/' + segment(state['room'])
    csrf = secrets.token_urlsafe(32)
    store = None
    if document_repo:
        from src.gitdocs import GitDocs
        store = GitDocs(document_repo)
        from src.agent_document_api import AgentDocuments
        AgentDocuments(store, None, room=state['room'])  # Explicit local preview configuration.

    def api(method, path, data=None, query=None):
        return request(matrix_url, method, PREFIX + path, state['tokens'][0], data, query)

    documents = None
    if store:
        from src.document_service import DocumentService
        documents = DocumentService(store, api, api('GET', '/account/whoami')['user_id'], state['room'])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def valid_host(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{port}', f'localhost:{port}'}:
                self.send_error(403)
                return False
            return True

        def document_failure(self, status, message, form):
            # Keep the exact submitted draft and operation on errors; never send it to Matrix.
            hidden = ''.join('<input type="hidden" name="' + key + '" value="' +
                             escape(form.get(key, [''])[0], quote=True) + '">'
                             for key in ('csrf', 'operation', 'base', 'revision'))
            body = ('<!doctype html><meta charset="utf-8"><title>Document save needs attention</title>' +
                    '<h1>Document save needs attention</h1><p>' + escape(message) + '</p>' +
                    '<form method="post">' + hidden +
                    '<textarea aria-label="Preserved Markdown draft" name="doc-content" rows="16">\n' +
                    escape(form.get('doc-content', [''])[0]) + '</textarea>' +
                    '<button name="action" value="doc-save">Retry the same save</button></form>' +
                    '<p><a href="/">Review latest Git version</a>. Keep a copy of this draft before leaving.</p>')
            self.send_response(status)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body.encode())

        def do_GET(self):
            if not self.valid_host():
                return
            try:
                events = api('GET', room + '/messages', query={'dir': 'b', 'limit': 50})['chunk']
                rows = []
                for event in events:
                    if event['type'] != 'm.room.message':
                        continue
                    content = event['content']
                    label = 'EXTERNAL AGENT' if event['sender'] == AGENT else 'HUMAN'
                    rows.append('<article><small>' + label + '</small><p>' + escape(content.get('body', '')) +
                                '</p><code>' + escape(event['event_id']) + '</code></article>')
                query = parse_qs(urlsplit(self.path).query)
                notice = ''
                if query.get('task'):
                    progress = request(gateway_url, 'GET', '/agent/status', worker_token,
                                       query={'id': query['task'][0]})['task']
                    notice = '<p class="note">' + ('Agent replied; see the timeline for the result.'
                              if progress and progress['status'] == 'done' else
                              'Request queued. Refresh shortly to see the result.') + '</p>'
                editor = ''
                if store:
                    revision = query.get('commit', [None])[0]
                    snapshot = documents.read(state['room'], revision)
                    history = ' · '.join('<a href="/?commit=' + h + '">' + h[:10] + '</a>'
                                         for h in store.history('demo.md'))
                    editor = ('<article><small>GIT DOCUMENT / demo.md</small><p>Version: <code>' +
                              escape(snapshot['commit'] or 'not created') + '</code></p>' +
                              '<p class="note">Save writes directly to Git. Matrix receives a version receipt, never this document body.</p>' +
                              '<form method="post"><textarea aria-label="Markdown document" name="doc-content" rows="10">\n' +
                              escape(snapshot['content'] or '') + '</textarea><input type="hidden" name="base" value="' +
                              (snapshot['blob'] or '') + '"><input type="hidden" name="csrf" value="' + csrf +
                              '"><input type="hidden" name="operation" value="' + str(uuid.uuid4()) +
                              '"><button name="action" value="doc-save">Save directly to Git</button>' +
                              '<input type="hidden" name="revision" value="' + (revision or '') +
                              '"><button name="action" value="doc-read">Ask agent to read Git</button></form>' +
                              '<p>Immutable versions: ' + history + ' · <a href="/">Latest</a></p></article>')
                body = '''<!doctype html><html><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Didadi · Agent gateway</title><style>
body{font:16px system-ui;background:#101722;color:#e1e9f2;max-width:860px;margin:45px auto;padding:0 24px}
h1{font-size:42px;margin-bottom:8px}small{color:#83ddc6;letter-spacing:2px}p{line-height:1.6;white-space:pre-wrap}
article{background:#1b2738;padding:18px 24px;border-radius:14px;margin:14px 0}code{font-size:11px;color:#93a5bb;overflow-wrap:anywhere}
textarea{width:100%;box-sizing:border-box;padding:16px;border-radius:8px;font:14px monospace;background:#101722;color:#e1e9f2;border:1px solid #405570}input{flex:1;min-width:180px;padding:15px;border-radius:8px;border:0}button{padding:15px;border:0;border-radius:8px;background:#83ddc6}
a{color:#83ddc6}.note{color:#a8b8cb}form{margin:30px 0;display:flex;gap:10px;flex-wrap:wrap}</style>
<small>DIDADI / LOCAL DEVELOPMENT</small><h1>A message. A durable task.<br>An external agent reply.</h1>
<p class="note">Live Matrix timeline (newest first) · SQLite task ledger · independent polling runtime<br>Deterministic example agent; no LLM.</p>''' + notice + editor + '''
<form method="post"><input aria-label="Message to external agent" name="body" placeholder="Ask the example agent…" required maxlength="4000">
<input type="hidden" name="csrf" value="''' + csrf + '''"><button>Send to agent</button></form>
<p><a href="/">Refresh timeline ↻</a></p>''' + ''.join(rows) + '</html>'
                self.send_response(200)
                self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(body.encode())
            except ValueError:
                self.send_error(400, 'Invalid document revision')
            except Exception:
                self.send_error(503, 'Matrix or document store unavailable')

        def do_POST(self):
            if not self.valid_host():
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size < 600000:
                self.send_error(400)
                return
            form = parse_qs(self.rfile.read(size).decode())
            if not secrets.compare_digest(form.get('csrf', [''])[0], csrf):
                self.send_error(403)
                return
            action = form.get('action', ['message'])[0]
            document = None
            if action.startswith('doc-'):
                if store is None:
                    self.send_error(400)
                    return
                if action == 'doc-save':
                    from src.document_service import DocumentError
                    try:
                        documents.save({'room':state['room'], 'operation':form.get('operation',[''])[0],
                                        'content':form.get('doc-content',[''])[0],
                                        'base_blob':form.get('base',[''])[0] or None})
                    except DocumentError as error:
                        self.document_failure(error.status, 'Document save rejected. Keep this draft and review the latest Git version before retrying.', form)
                        return
                    except Exception:
                        self.document_failure(503, 'Document save unavailable. Keep this draft and retry the same request.', form)
                        return
                    self.send_response(303)
                    self.send_header('Location', '/')
                    self.end_headers()
                    return
                elif action == 'doc-read':
                    document = {'action': 'read'}
                    if form.get('revision', [''])[0]:
                        document['commit'] = form['revision'][0]
                    body = 'Read demo.md from Git'
                else:
                    self.send_error(400)
                    return
            else:
                body = form.get('body', [''])[0].strip()
            if not 0 < len(body) <= 4000:
                self.send_error(400)
                return
            content = {'msgtype': 'm.text', 'body': body, 'm.mentions': {'user_ids': [AGENT]}}
            if document is not None:
                content['org.didadi.document'] = document
            sent = api('PUT', room + '/send/m.room.message/preview-' + secrets.token_hex(12), content)
            self.send_response(303)
            self.send_header('Location', '/?task=' + segment(sent['event_id']))
            self.end_headers()

    def worker():
        while True:
            try:
                if store:
                    from scripts.document_worker import once as document_once
                    document_once(gateway_url, worker_token, store)
                else:
                    once(gateway_url, worker_token)
            except Exception as error:
                print('worker retry: ' + type(error).__name__, flush=True)
            time.sleep(1)

    threading.Thread(target=worker, daemon=True).start()
    print(f'Preview http://127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--document-repo')
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9000')
    args = parser.parse_args()
    serve(json.loads(Path(args.state_file).read_text()), Path(args.token_file).read_text().strip(),
          args.port, args.document_repo, args.matrix_url, args.gateway_url)
