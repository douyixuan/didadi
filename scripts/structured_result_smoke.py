"""Real client/Matrix/outbound-runtime/Git test with translated display text."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.client_server import Workspace, handler
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment
from src.runtime_socket import bridge


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--url');parser.add_argument('--repo')
    parser.add_argument('--state-file');parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args()
    token=Path(args.token_file).read_text().strip()
    if args.worker:
        import src.agent_document_api as worker
        from scripts.websocket_worker import run
        worker.document_result=lambda item:'已保存；展示文本无需包含英文或 Git hash。'
        run(args.url,token,GitDocs(args.repo))
        return
    state=json.loads(Path(args.state_file).read_text())
    with tempfile.TemporaryDirectory(prefix='didadi-structured-e2e-') as directory:
        root=Path(directory);store=GitDocs(root/'docs.git')
        workspace=Workspace(state,token,store.root,root/'client.sqlite',args.matrix_url,args.gateway_url)
        client=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        client.RequestHandlerClass=handler(workspace,Path('client/dist'),client.server_port)
        client_thread=threading.Thread(target=client.serve_forever,daemon=True);client_thread.start()
        socket=bridge(args.gateway_url,token,0,wait_seconds=1)
        socket_thread=threading.Thread(target=socket.serve_forever,daemon=True);socket_thread.start()
        url='ws://127.0.0.1:'+str(socket.socket.getsockname()[1])+'/runtime'
        worker=subprocess.Popen([sys.executable,'-m','scripts.structured_result_smoke','--worker',
            '--url',url,'--token-file',args.token_file,'--repo',str(store.root)],stdout=subprocess.DEVNULL)
        base='http://127.0.0.1:'+str(client.server_port)
        def api(path,data=None,method=None):
            headers={'X-CSRF-Token':workspace.csrf,'Content-Type':'application/json','Origin':base}
            req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
            with urlopen(req,timeout=10) as response:return json.load(response)
        def send(command,txn=None):
            return api('/matrix'+PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+(txn or secrets.token_hex(12)),
                {'msgtype':'m.text','body':'Structured protocol synthetic fixture','m.mentions':{'user_ids':[AGENT]},
                 'org.didadi.document':command},'PUT')['event_id']
        def finish(identifier):
            deadline=time.monotonic()+60
            while time.monotonic()<deadline:
                task=api('/api/task?'+urlencode({'room':state['room'],'id':identifier}))['task']
                if task and task['status']=='done':return task
                if task and task['status'] in {'failed','cancelled'}:raise AssertionError('task stopped')
                time.sleep(.2)
            raise AssertionError('structured task timeout')
        try:
            assert api('/api/session')['userId']==workspace.user_id
            text='# Structured protocol\n\nSynthetic file. No LLM.\n'
            command={'action':'write','base_blob':None,'content':text};txn=secrets.token_hex(12)
            identifier=send(command,txn);assert send(command,txn)==identifier
            task=finish(identifier);saved=task['outcome'];snapshot=store.snapshot('demo.md')
            assert saved=={'version':1,'status':'saved','path':'demo.md','commit':snapshot['commit'],'blob':snapshot['blob']}
            assert task['body'].startswith('已保存') and snapshot['content']==text
            reply=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/event/'+segment(task['reply']),state['tokens'][0])
            assert reply['content']['org.didadi.task.result']==saved
            assert reply['content']['m.relates_to']['event_id']==identifier
            assert len(store.history('demo.md'))==1
            assert finish(send({'action':'write','base_blob':None,'content':'stale'}))['outcome']['status']=='conflict'
            assert finish(send({'action':'read','commit':'invalid'}))['outcome']['status']=='rejected'
            read=finish(send({'action':'read','commit':snapshot['commit']}))['outcome']
            assert read['status']=='read' and read['commit']==snapshot['commit']
            assert store.snapshot('demo.md')['commit']==snapshot['commit'] and store.pending()==[]
            print('PASS client CSRF -> real Matrix -> external WebSocket runtime -> Git -> structured API/receipt; translated reply, idempotency, saved/read/conflict/rejected')
        finally:
            worker.terminate()
            try:worker.wait(timeout=5)
            except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=5)
            socket.shutdown();socket_thread.join(timeout=3)
            client.shutdown();client.server_close();client_thread.join(timeout=3)


if __name__=='__main__':main()
