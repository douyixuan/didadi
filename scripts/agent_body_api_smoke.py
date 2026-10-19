"""Real metadata-only Matrix tasks, external runtime and scoped HTTP body IO.

The runtime is a separate process and receives no Git path or source grant.
"""
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

from src.agent_document_api import AgentDocuments, DocumentClient, handler
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment
from src.repository_read import RepositoryReader
from src.runtime_socket import bridge


def runtime(args, token):
    from scripts.websocket_worker import connect_runtime, SocketTransport
    payload=json.loads(Path(args.payload_file).read_text())
    client=DocumentClient(args.document_url,token)
    with connect_runtime(args.url,token) as socket:
        send=SocketTransport(socket)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            task=send('', 'GET','/agent/tasks')['task']
            if not task:continue
            if task['id']==payload['id']:break
            # The baseline Matrix smoke intentionally leaves one chat recovery task.
            assert not any(key in task['event']['content'] for key in ('org.didadi.document','org.didadi.repository'))
            send('', 'POST','/agent/complete',data={'id':task['id'],'lease':task['lease'],'result':'Synthetic chat recovery completed'})
        else:raise AssertionError('requested task not claimable')
        scope={'id':task['id'],'lease':task['lease']}
        if payload['action']=='write':
            assert 'content' not in task['event']['content']['org.didadi.document']
            data={**scope,'content':payload['content']}
            result=client.write(data)
            assert result['outcome']['status']=='saved'
            assert client.write(data)['outcome']==result['outcome']
            assert client.write({**data,'content':'different'})['outcome']['status']=='conflict'
        else:
            result=client.execute(scope)
            assert result['resource']['content']==payload['content']
            assert result['outcome']['status']=='read'
        assert payload['content'] not in result['result']
        # An old/custom runtime must not be able to echo resource bodies back.
        send('', 'POST','/agent/complete',data={**scope,'result':payload['content'],'outcome':result['outcome']})
        client.reconcile()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',action='store_true')
    parser.add_argument('--url');parser.add_argument('--document-url');parser.add_argument('--payload-file')
    parser.add_argument('--state-file');parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();token=Path(args.token_file).read_text().strip()
    if args.worker:
        runtime(args,token);return
    state=json.loads(Path(args.state_file).read_text())
    with tempfile.TemporaryDirectory(prefix='didadi-body-api-') as directory:
        root=Path(directory);store=GitDocs(root/'docs.git');source=root/'source';source.mkdir()
        source_text='SYNTHETIC_SOURCE_BODY_'+secrets.token_hex(12)+'\n'
        (source/'example.py').write_text(source_text)
        subprocess.run(['git','init','-q',str(source)],check=True)
        subprocess.run(['git','-C',str(source),'add','.'],check=True)
        subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=fixture@local','commit','-qm','synthetic'],check=True)
        commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()
        user=request(args.matrix_url,'GET',PREFIX+'/account/whoami',state['tokens'][0])['user_id']
        reader=RepositoryReader({'repositories':{'fixture':{'path':str(source),'commit':commit,
            'rooms':[state['room']],'senders':[user],'files':['example.py']}}})
        service=AgentDocuments(store,lambda method,path,data=None,query=None:
            request(args.gateway_url,method,path,token,data,query),reader,state['room'])
        http=ThreadingHTTPServer(('127.0.0.1',0),handler(service,token))
        ws=bridge(args.gateway_url,token,0,wait_seconds=1)
        threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (http,ws)]
        for thread in threads:thread.start()
        body='SYNTHETIC_DOCUMENT_BODY_'+secrets.token_hex(12)+'\n'+'x'*7000
        try:
            receipts=[]
            commands=[('write',{'org.didadi.document':{'action':'write','base_blob':None}},body),
                      ('read',{'org.didadi.document':{'action':'read'}},body),
                      ('source',{'org.didadi.repository':{'action':'read','repository':'fixture','path':'example.py'}},source_text)]
            for action,command,text in commands:
                event=request(args.matrix_url,'PUT',PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+secrets.token_hex(12),
                    state['tokens'][0],{'msgtype':'m.text','body':'Synthetic metadata-only resource task',
                    'm.mentions':{'user_ids':[AGENT]},**command})['event_id']
                deadline=time.monotonic()+30
                while time.monotonic()<deadline:
                    task=request(args.gateway_url,'GET','/agent/status',token,query={'id':event})['task']
                    if task:break
                    time.sleep(.1)
                else:raise AssertionError('task not delivered')
                payload=root/'runtime-payload.json';payload.write_text(json.dumps({'id':event,'action':action,'content':text}));payload.chmod(0o600)
                subprocess.run([sys.executable,'-m','scripts.agent_body_api_smoke','--worker',
                    '--url','ws://127.0.0.1:'+str(ws.socket.getsockname()[1])+'/runtime',
                    '--document-url','http://127.0.0.1:'+str(http.server_port),
                    '--token-file',args.token_file,'--payload-file',str(payload)],check=True,timeout=90)
                task=request(args.gateway_url,'GET','/agent/status',token,query={'id':event})['task']
                assert task['status']=='done' and text not in task['body']
                receipt=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/event/'+segment(task['reply']),state['tokens'][0])
                assert text.splitlines()[0] not in json.dumps(receipt)
                assert receipt['content']['org.didadi.task.result']==task['outcome']
                receipts.append(task['outcome'])
            assert store.read('demo.md')==body and len(store.history('demo.md'))==1 and store.pending()==[]
            assert receipts[0]['commit']==receipts[1]['commit']
            assert receipts[2]['resource']['commit']==commit
            messages=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/messages',state['tokens'][0],query={'dir':'b','limit':100})
            assert body.splitlines()[0] not in json.dumps(messages) and source_text.splitlines()[0] not in json.dumps(messages)
            print('PASS real Matrix metadata-only write/read/source tasks -> separate WebSocket runtime without Git grants -> scoped HTTP body API -> Git; metadata-only Matrix receipts, idempotency, stale-content conflict and outbox reconciliation')
        finally:
            http.shutdown();http.server_close();ws.shutdown()
            for thread in threads:thread.join(timeout=3)


if __name__=='__main__':main()
