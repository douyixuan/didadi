"""Stop/restart only owned runtimes; real Matrix/WS/HTTP lease and Git recovery."""
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
from src.matrix_http import request, segment, MatrixError
from src.runtime_socket import bridge


def worker(args, token):
    from scripts.websocket_worker import SocketTransport, connect_runtime
    payload=json.loads(Path(args.payload_file).read_text());client=DocumentClient(args.document_url,token)
    def ready(value):
        path=Path(args.ready_file);pending=path.with_suffix('.pending');pending.write_text(json.dumps(value));pending.chmod(0o600);pending.replace(path)
    with connect_runtime(args.url,token) as socket:
        send=SocketTransport(socket)
        if args.mode=='probe':
            assert send('','GET','/agent/tasks')['task'] is None
            ready({'no_duplicate_claim':True});return
        deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            task=send('','GET','/agent/tasks')['task']
            if not task:continue
            if task['id']==payload['id']:break
            assert not any(key in task['event']['content'] for key in ('org.didadi.document','org.didadi.repository'))
            send('','POST','/agent/complete',data={'id':task['id'],'lease':task['lease'],'result':'Synthetic baseline chat recovered'})
        else:raise AssertionError('target task not claimable')
        scope={'id':task['id'],'lease':task['lease']}
        result=client.write({**scope,'content':payload['content']})
        assert result['outcome']['status']=='saved'
        if 'outcome' in payload:assert result['outcome']==payload['outcome']
        if args.mode=='hold':
            ready({'scope':scope,'result':result,'attempts':task['attempts']})
            while True:time.sleep(.2)
        elif args.mode=='fail':
            send('','POST','/agent/fail',data={**scope,'reason':'runtime_error','retryable':True})
            ready({'attempts':task['attempts'],'retry_scheduled':True})
        else:
            observed=send('','GET','/agent/status',query={'id':task['id']})['task']['observed_at']
            if 'retry_at' in payload:assert observed>=payload['retry_at']
            data={**scope,'result':result['result'],'outcome':result['outcome']}
            first=send('','POST','/agent/complete',data=data)
            assert send('','POST','/agent/complete',data=data)==first
            client.reconcile();ready({'attempts':task['attempts'],'completed':True})


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['hold','probe','fail','finish'])
    parser.add_argument('--url');parser.add_argument('--document-url');parser.add_argument('--payload-file');parser.add_argument('--ready-file')
    parser.add_argument('--state-file');parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008');parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();token=Path(args.token_file).read_text().strip()
    if args.mode:worker(args,token);return
    state=json.loads(Path(args.state_file).read_text());process=None
    with tempfile.TemporaryDirectory(prefix='didadi-task-visibility-') as temporary:
        root=Path(temporary);store=GitDocs(root/'documents.git')
        service=AgentDocuments(store,lambda method,path,data=None,query=None:
            request(args.gateway_url,method,path,token,data,query),room=state['room'])
        http=ThreadingHTTPServer(('127.0.0.1',0),handler(service,token));ws=bridge(args.gateway_url,token,0,wait_seconds=1)
        threads=[threading.Thread(target=server.serve_forever,daemon=True) for server in (http,ws)]
        for thread in threads:thread.start()
        try:
            for auth in (None,'wrong'):
                try:request(args.gateway_url,'POST','/agent/runtime',auth,{'session':'a'*48,'connected':True})
                except MatrixError as error:assert error.status==403
                else:raise AssertionError('runtime observation accepted without auth')
            marker='task-body-'+secrets.token_hex(12);text='# Runtime recovery\n\n'+marker+'\n'
            identifier=request(args.matrix_url,'PUT',PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+secrets.token_hex(12),state['tokens'][0],
                {'msgtype':'m.text','body':'Synthetic runtime visibility task','m.mentions':{'user_ids':[AGENT]},
                 'org.didadi.document':{'action':'write','base_blob':None}})['event_id']
            def status():return request(args.gateway_url,'GET','/agent/status',token,query={'id':identifier})['task']
            def wait(predicate,timeout=100):
                deadline=time.monotonic()+timeout
                while time.monotonic()<deadline:
                    value=predicate()
                    if value:return value
                    time.sleep(.15)
                raise AssertionError('visibility transition timeout')
            wait(lambda:status());assert status()['phase']=='waiting'
            payload=root/'payload.json';payload.write_text(json.dumps({'id':identifier,'content':text}));payload.chmod(0o600)
            def command(mode):
                return [sys.executable,'-m','scripts.task_visibility_smoke','--mode',mode,
                    '--url','ws://127.0.0.1:'+str(ws.socket.getsockname()[1])+'/runtime',
                    '--document-url','http://127.0.0.1:'+str(http.server_port),'--token-file',args.token_file,
                    '--payload-file',str(payload),'--ready-file',str(root/(mode+'.json'))]
            process=subprocess.Popen(command('hold'))
            wait(lambda:(root/'hold.json').exists())
            original=json.loads((root/'hold.json').read_text());active=status()
            assert active['phase']=='running' and active['runtime']['state']=='connected' and active['attempts']==1
            assert original['scope']['lease'] not in json.dumps(active) and marker not in json.dumps(active)
            assert store.read('demo.md')==text and len(store.history('demo.md'))==1
            # A live connection heartbeats while execution holds the task; this
            # must not renew the task lease or assert model progress.
            wait(lambda:status()['runtime']['last_observed_at']>active['runtime']['last_observed_at'],timeout=15)
            assert status()['lease_expires_at']==active['lease_expires_at']
            data={'id':identifier,'content':text,'outcome':original['result']['outcome']};payload.write_text(json.dumps(data))
            # Stop only the child created above. Disconnect must not release its lease.
            process.terminate();process.wait(timeout=5);process=None
            wait(lambda:status()['runtime']['state']=='disconnected',timeout=10)
            assert status()['phase']=='running'
            subprocess.run(command('probe'),check=True,timeout=15)
            assert status()['phase']=='running' and status()['attempts']==1
            print('PASS owned runtime stopped; no duplicate claim or early lease release; waiting for original lease expiry',flush=True)
            expired=wait(lambda:status() if status()['phase']=='retry_wait' else None)
            assert expired['retry_reason']=='lease_expired' and expired['runtime']['state']!='connected'
            before_fail=status()['observed_at']
            subprocess.run(command('fail'),check=True,timeout=30)
            delayed=status();assert delayed['phase']=='retry_wait' and delayed['retry_reason']=='runtime_error' and delayed['attempts']==2
            # The configured attempt2 delay is4s. Do not assume process startup
            # or this status response completed before that short deadline.
            assert delayed['next_retry_at']>=before_fail+4
            data['retry_at']=delayed['next_retry_at'];payload.write_text(json.dumps(data))
            assert len(store.history('demo.md'))==1
            subprocess.run(command('finish'),check=True,timeout=100)
            done=status();assert done['phase']=='done' and done['attempts']==3
            assert store.pending()==[] and len(store.history('demo.md'))==1 and store.read('demo.md')==text
            try:request(args.gateway_url,'POST','/agent/complete',token,{**original['scope'],'result':original['result']['result'],'outcome':original['result']['outcome']})
            except MatrixError as error:assert error.body.get('error')=='invalid_lease'
            else:raise AssertionError('obsolete lease completed')
            events=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/messages',state['tokens'][0],query={'dir':'b','limit':100})['chunk']
            receipts=[event for event in events if event.get('content',{}).get('org.didadi.task',{}).get('id')==identifier]
            assert len(receipts)==1 and marker not in json.dumps(events)
            print('PASS real Matrix/WS/HTTP: waiting -> active lease -> owned process stopped/disconnected -> lease expiry/retry -> explicit backoff -> runtime restart/completion; duplicate claim blocked, stale lease rejected, original Git commit and Matrix receipt exactly one, outbox recovered',flush=True)
        finally:
            if process is not None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            http.shutdown();http.server_close();ws.shutdown()
            for thread in threads:thread.join(timeout=3)


if __name__=='__main__':main()
