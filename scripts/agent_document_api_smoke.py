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
from urllib.error import HTTPError

from src.client_server import Workspace, handler
from src.agent_document_api import AgentDocuments, DocumentClient, handler as document_handler
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment
from src.runtime_socket import bridge


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--url');parser.add_argument('--document-url')
    parser.add_argument('--state-file');parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args()
    token=Path(args.token_file).read_text().strip()
    if args.worker:
        from scripts.websocket_worker import run
        run(args.url,token,DocumentClient(args.document_url,token))
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
        import src.agent_document_api as document_module
        document_module.document_result=lambda item:'已保存；展示文本无需包含英文或 Git hash。'
        service=AgentDocuments(store,lambda method,path,data=None,query=None:
            request(args.gateway_url,method,path,token,data,query))
        document_server=ThreadingHTTPServer(('127.0.0.1',0),document_handler(service,token))
        document_thread=threading.Thread(target=document_server.serve_forever,daemon=True);document_thread.start()
        document_url='http://127.0.0.1:'+str(document_server.server_port)
        worker=subprocess.Popen([sys.executable,'-m','scripts.agent_document_api_smoke','--worker',
            '--url',url,'--token-file',args.token_file,'--document-url',document_url],stdout=subprocess.DEVNULL)
        base='http://127.0.0.1:'+str(client.server_port)
        def api(path,data=None,method=None):
            headers={'X-CSRF-Token':workspace.csrf,'Content-Type':'application/json','Origin':base}
            req=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
            with urlopen(req,timeout=10) as response:return json.load(response)
        def send(command,txn=None):
            path=PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+(txn or secrets.token_hex(12))
            payload={'msgtype':'m.text','body':'Structured protocol synthetic fixture',
                     'm.mentions':{'user_ids':[AGENT]},'org.didadi.document':command}
            if command.get('action')=='write':
                # Legacy wire compatibility is an external-client fixture, not a
                # built-in human save. The platform proxy must reject it first.
                try:
                    api('/matrix'+path,payload,'PUT')
                except HTTPError as error:
                    assert error.code==400
                else:
                    raise AssertionError('platform proxy accepted a body-bearing document task')
                return request(args.matrix_url,'PUT',path,state['tokens'][0],payload)['event_id']
            return api('/matrix'+path,payload,'PUT')['event_id']
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
            assert task['body'].startswith('Saved demo.md') and snapshot['content']==text and text not in task['body']
            reply=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/event/'+segment(task['reply']),state['tokens'][0])
            assert reply['content']['org.didadi.task.result']==saved
            assert reply['content']['m.relates_to']['event_id']==identifier
            assert len(store.history('demo.md'))==1
            assert finish(send({'action':'write','base_blob':None,'content':'stale'}))['outcome']['status']=='conflict'
            assert finish(send({'action':'read','commit':'invalid'}))['outcome']['status']=='rejected'
            read=finish(send({'action':'read','commit':snapshot['commit']}))['outcome']
            assert read['status']=='read' and read['commit']==snapshot['commit']
            assert store.snapshot('demo.md')['commit']==snapshot['commit'] and store.pending()==[]
            import uuid
            human=api('/api/documents/demo.md',{'room':state['room'],'operation':str(uuid.uuid4()),
                'content':'# Human direct save after Agent API\r\n','base_blob':snapshot['blob']},'PUT')
            assert human['status']=='saved'
            assert finish(send({'action':'write','base_blob':snapshot['blob'],'content':'stale Agent'}))['outcome']['status']=='conflict'
            assert store.snapshot('demo.md')['commit']==human['commit']
            print('PASS real Matrix -> external WebSocket runtime without --repo -> scoped HTTP Document API -> Git; replay/read/conflict/rejected, metadata receipt and human direct save compatibility')
        finally:
            worker.terminate()
            try:worker.wait(timeout=5)
            except subprocess.TimeoutExpired:worker.kill();worker.wait(timeout=5)
            document_server.shutdown();document_server.server_close();document_thread.join(timeout=3)
            socket.shutdown();socket_thread.join(timeout=3)
            client.shutdown();client.server_close();client_thread.join(timeout=3)


if __name__=='__main__':main()
