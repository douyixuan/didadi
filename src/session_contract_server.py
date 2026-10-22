"""Opt-in loopback fictional contract server. Does not import any Matrix runtime."""
import argparse
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import time
from pathlib import Path
from urllib.parse import urlsplit,unquote
from src.session_contract import FakeIdentityService,SessionContractError

def handler(service,dist,port):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value,kind='application/json'):
            body=value if isinstance(value,bytes) else json.dumps(value).encode()
            self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(body)
        def run_request(self,method):
            try:
                origins={f'http://127.0.0.1:{port}',f'http://localhost:{port}'}
                if self.headers.get('Host') not in {f'127.0.0.1:{port}',f'localhost:{port}'}:raise SessionContractError(403,'Loopback fixture host required.')
                if self.headers.get('Origin') and self.headers['Origin'] not in origins:raise SessionContractError(403,'Same-origin fixture requests required.')
                parsed=urlsplit(self.path)
                if parsed.query:raise SessionContractError(400,'The fictional contract accepts no query overrides.')
                sid=self.headers.get('X-Fictional-Session','');csrf=self.headers.get('X-Fictional-CSRF','');body=None
                if method=='POST':
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<size<=20000:raise SessionContractError(400,'Invalid fictional request size.')
                    body=json.loads(self.rfile.read(size))
                if parsed.path=='/api/session-contract/login' and method=='POST':value=service.login(body)
                elif parsed.path=='/api/session-contract/workspace' and method=='GET':value=service.workspace(sid)
                elif parsed.path=='/api/session-contract/document' and method=='POST':value=service.save(sid,csrf,body)
                elif parsed.path=='/api/session-contract/logout' and method=='POST':value=service.logout(sid,csrf,body)
                elif method=='GET' and not parsed.path.startswith(('/api/','/matrix')):
                    relative='session-contract.html' if parsed.path=='/' else unquote(parsed.path).lstrip('/')
                    path=(dist/relative).resolve()
                    if not path.is_relative_to(dist.resolve()) or not path.is_file() or any(part.startswith('.') for part in Path(relative).parts):raise SessionContractError(404,'Unknown fixture asset.')
                    import mimetypes
                    self.reply(200,path.read_bytes(),mimetypes.guess_type(path.name)[0] or 'application/octet-stream');return
                else:raise SessionContractError(404,'Unknown fictional route. Real authentication is unavailable.')
                self.reply(200,value)
            except SessionContractError as error:self.reply(error.status,{'error':error.message,'fictional':True})
            except (ValueError,TypeError,KeyError):self.reply(400,{'error':'Invalid fictional request.','fictional':True})
            except Exception:self.reply(503,{'error':'Fictional service unavailable.','fictional':True})
        def do_GET(self):self.run_request('GET')
        def do_POST(self):self.run_request('POST')
    return Handler
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--port',type=int,default=8860);parser.add_argument('--dist',default='client/dist');args=parser.parse_args()
    service=FakeIdentityService(namespace=f'fixture-boot-{time.monotonic_ns()}');server=ThreadingHTTPServer(('127.0.0.1',args.port),handler(service,Path(args.dist),args.port));print(f'Fictional-only session preview http://127.0.0.1:{args.port}',flush=True);server.serve_forever()
