"""Real Matrix requester-scoped cancellation and gateway history persistence."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from scripts.document_worker import once
from src.client_server import Workspace,handler
from src.gitdocs import GitDocs
from src.matrix_as import AGENT,PREFIX
from src.matrix_http import MatrixError,request,segment


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-file',required=True);parser.add_argument('--token-file',required=True)
    parser.add_argument('--record',required=True);parser.add_argument('--check-persistence',action='store_true')
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();state=json.loads(Path(args.state_file).read_text())
    token=Path(args.token_file).read_text().strip();gateway=args.gateway_url
    def status(identifier):return request(gateway,'GET','/agent/status',token,query={'id':identifier})['task']
    def history(identifier):return request(gateway,'GET','/agent/audit',token,query={'id':identifier})['events']
    if args.check_persistence:
        identifier=json.loads(Path(args.record).read_text())['id']
        assert status(identifier)['status']=='cancelled'
        assert [item['action'] for item in history(identifier)]==['accepted','cancelled']
        print('PASS cancelled task and execution history survived Application Service restart')
        return
    def mention(user):
        return request(args.matrix_url,'PUT',PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+secrets.token_hex(12),state['tokens'][user],
                       {'msgtype':'m.text','body':'task control fixture','m.mentions':{'user_ids':[AGENT]},
                        'org.didadi.document':{'action':'write','content':'# A cancelled task must not write this\n','base_blob':None}})['event_id']
    def wait(identifier):
        deadline=time.monotonic()+40
        while time.monotonic()<deadline:
            if status(identifier):return
            time.sleep(.2)
        raise AssertionError('AS did not accept cancellation fixture')
    mine,other=mention(0),mention(1);wait(mine);wait(other)
    with tempfile.TemporaryDirectory(prefix='didadi-task-control-') as directory:
        root=Path(directory);dist=root/'dist';dist.mkdir();(dist/'index.html').write_text('isolated acceptance')
        workspace=Workspace(state,token,root/'documents.git',root/'client.sqlite',args.matrix_url,gateway)
        server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        server.RequestHandlerClass=handler(workspace,dist,server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base='http://127.0.0.1:'+str(server.server_port)
        def cancel(identifier,csrf=workspace.csrf):
            req=Request(base+'/api/task/cancel',method='POST',headers={'Content-Type':'application/json','X-CSRF-Token':csrf},
                        data=json.dumps({'room':state['room'],'id':identifier}).encode())
            with urlopen(req,timeout=20) as response:return json.load(response)
        try:
            for identifier,csrf in [(mine,''),(other,workspace.csrf)]:
                try:cancel(identifier,csrf)
                except HTTPError as error:assert error.code==403
                else:raise AssertionError('unauthorized cancellation succeeded')
            assert status(other)['status']=='pending'
            assert cancel(mine)['status']=='cancelled';assert cancel(mine)['status']=='cancelled'
            audit=request(base,'GET','/api/task/audit',query={'room':state['room'],'id':mine})['events']
            assert [item['action'] for item in audit]==['accepted','cancelled']
            assert 'task control fixture' not in json.dumps(audit)
            request(gateway,'POST','/agent/cancel',token,{'id':other})
            assert not once(gateway,token,GitDocs(workspace.docs.root))
            assert workspace.docs.history('demo.md')==[]
            try:request(gateway,'POST','/agent/complete',token,{'id':mine,'lease':'obsolete','result':'must not deliver'})
            except MatrixError as error:assert error.body['error']=='task_cancelled' and not error.body['retryable']
            else:raise AssertionError('cancelled task completed')
        finally:server.shutdown();server.server_close();thread.join()
    proof=Path(args.record);proof.parent.mkdir(parents=True,exist_ok=True)
    proof.write_text(json.dumps({'id':mine}));proof.chmod(0o600)
    print('PASS real requester/CSRF boundary, idempotent cancellation, no Git write/reply, metadata-only history')


if __name__=='__main__':main()
