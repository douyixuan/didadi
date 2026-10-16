"""Real Matrix authority and direct Git saves, with no external document worker."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

from src.client_server import Workspace, handler
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment, MatrixError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--state-file',required=True);parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008');parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();state=json.loads(Path(args.state_file).read_text());token=Path(args.token_file).read_text().strip()
    servers=[]
    def serve(workspace):
        server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        server.RequestHandlerClass=handler(workspace,Path('client/dist'),server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();servers.append((server,thread))
        base='http://127.0.0.1:'+str(server.server_port)
        def api(path,data=None,method='GET',headers=None):
            req=Request(base+path,data=None if data is None else json.dumps(data).encode(),method=method,
                        headers=headers if headers is not None else {'Content-Type':'application/json','X-CSRF-Token':workspace.csrf,'Origin':base})
            try:
                with urlopen(req,timeout=20) as response:return response.status,json.load(response)
            except HTTPError as error:return error.code,json.load(error)
        return api
    with tempfile.TemporaryDirectory(prefix='didadi-direct-e2e-') as folder:
        root=Path(folder);repo=root/'documents.git'
        workspace=Workspace(state,token,repo,root/'alice.sqlite',args.matrix_url,args.gateway_url)
        reader=Workspace({**state,'tokens':[state['tokens'][1]]},token,repo,root/'bob.sqlite',args.matrix_url,args.gateway_url)
        api=serve(workspace);read_api=serve(reader);route='/api/documents/demo.md'
        marker='direct-body-'+secrets.token_hex(10);text='# Direct save\r\n\r\n'+marker+'\r\n'+'中文原文\r\n'*1800
        data={'room':state['room'],'operation':str(uuid.uuid4()),'content':text,'base_blob':None}
        try:
            status,first=api(route,data,'PUT');assert status==200 and first['status']=='saved',first
            assert api(route,data,'PUT')[1]['commit']==first['commit']
            latest=api('/api/document?'+urlencode({'room':state['room']}))[1]
            assert latest['content']==text and len(text.encode())>6000
            assert GitDocs(repo)._git('show','-s','--format=%an',first['commit']).strip()==workspace.user_id
            assert read_api('/api/document?'+urlencode({'room':state['room']}))[1]['writable'] is False
            assert read_api(route,{**data,'operation':str(uuid.uuid4()),'base_blob':first['blob']},'PUT')[0]==403
            assert api(route,{**data,'room':'!unbound:local'},'PUT')[0]==403
            assert api(route,{**data,'author':'@spoof'},'PUT')[0]==400
            assert api(route,data,'PUT',headers={})[0]==403
            assert api(route,data,'PUT',headers={'X-CSRF-Token':workspace.csrf,'Origin':'https://invalid.example'})[0]==403
            base=first['blob']
            def concurrent(index):return api(route,{**data,'operation':str(uuid.uuid4()),'base_blob':base,'content':'# concurrent '+str(index)},'PUT')
            with ThreadPoolExecutor(2) as pool:results=list(pool.map(concurrent,range(2)))
            assert sorted(r[0] for r in results)==[200,409]
            current=workspace.docs.snapshot('demo.md');stable={'room':state['room'],'operation':str(uuid.uuid4()),'base_blob':current['blob'],'content':'# Receipt recovery\r\n'+marker}
            original=workspace.documents.api
            def offline(method,path,data=None):
                if method=='PUT':raise OSError('simulated receipt network loss')
                return original(method,path,data)
            workspace.documents.api=offline
            status,pending=api(route,stable,'PUT');assert status==200 and pending['receipt_pending']
            # Recreate the service after Git commit, before a receipt can be delivered.
            restored=Workspace(state,token,repo,root/'restored.sqlite',args.matrix_url,args.gateway_url);restored_api=serve(restored)
            acknowledge=restored.docs.acknowledge
            restored.docs.acknowledge=lambda operation: (_ for _ in ()).throw(OSError('simulated ACK loss'))
            assert restored_api(route,stable,'PUT')[1]['receipt_pending']
            restored.docs.acknowledge=acknowledge
            replay=restored_api(route,stable,'PUT')[1]
            assert replay['commit']==pending['commit'] and not replay['receipt_pending']
            assert len(restored.docs.history('demo.md'))==3 and restored.docs.pending()==[]
            timeline=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/messages',state['tokens'][0],query={'dir':'b','limit':'100'})['chunk']
            receipts=[e for e in timeline if e.get('content',{}).get('org.didadi.document.commit',{}).get('commit')==pending['commit']]
            assert len(receipts)==1 and marker not in json.dumps(timeline)
            # A raw low-power Matrix command cannot bypass the direct write policy.
            forbidden=request(args.matrix_url,'PUT',PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+secrets.token_hex(12),state['tokens'][1],{
                'msgtype':'m.text','body':'Disposable permission fixture','m.mentions':{'user_ids':[AGENT]},
                'org.didadi.document':{'action':'write','content':'forbidden','base_blob':pending['blob']}})['event_id']
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                claimed=request(args.gateway_url,'GET','/agent/tasks',token)['task']
                if claimed and claimed['id']==forbidden:break
                if claimed:request(args.gateway_url,'POST','/agent/complete',token,{'id':claimed['id'],'lease':claimed['lease'],'result':claimed['result'] or 'Fixture cleanup','outcome':claimed.get('outcome')})
                time.sleep(.2)
            else:raise AssertionError('permission fixture was not dispatched')
            try:request(args.gateway_url,'POST','/agent/validate',token,{'id':claimed['id'],'lease':claimed['lease']})
            except MatrixError as error:assert error.status==403
            else:raise AssertionError('low-power legacy mutation was allowed')
            assert restored.docs.snapshot('demo.md')['commit']==pending['commit']
            print('PASS workerless direct API -> Git -> metadata-only Matrix receipt; UTF-8/CRLF/attribution, duplicate retry, concurrent conflict, reader/room/CSRF denial, receipt failure/restart/ACK loss and raw Matrix privilege bypass denial')
        finally:
            for server,thread in servers:server.shutdown();server.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
