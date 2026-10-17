"""Two HTTP clients, real Matrix authority, clean merge and overlap rejection."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import tempfile
import threading
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from urllib.parse import urlencode
import uuid

from src.client_server import Workspace,handler
from src.matrix_as import PREFIX
from src.matrix_http import request,segment


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--state-file',required=True);parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008');parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();state=json.loads(Path(args.state_file).read_text());token=Path(args.token_file).read_text().strip();servers=[]
    def serve(workspace):
        server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None);server.RequestHandlerClass=handler(workspace,Path('client/dist'),server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();servers.append((server,thread));base='http://127.0.0.1:'+str(server.server_port)
        def api(data):
            req=Request(base+'/api/documents/demo.md',method='PUT',data=json.dumps(data).encode(),headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':workspace.csrf})
            try:
                with urlopen(req,timeout=30) as response:return response.status,json.load(response)
            except HTTPError as error:return error.code,json.load(error)
        return api
    try:
        with tempfile.TemporaryDirectory(prefix='didadi-merge-smoke-') as temporary:
            root=Path(temporary);repo=root/'documents.git'
            # Same authorized Matrix identity, separate client sessions/process-owned metadata.
            # No room power changes or new permissions are needed to test concurrent writers.
            first=Workspace(state,token,repo,root/'one.sqlite',args.matrix_url,args.gateway_url)
            second=Workspace(state,token,repo,root/'two.sqlite',args.matrix_url,args.gateway_url)
            clients=[serve(first),serve(second)];room=state['room'];marker='merge-body-'+secrets.token_hex(10)
            base='# Shared document\n\nFirst paragraph.\n\n'+marker+'\n\nLast paragraph.\n'
            def payload(content,blob):return {'room':room,'operation':str(uuid.uuid4()),'content':content,'base_blob':blob}
            status,seed=clients[0](payload(base,None));assert status==200,seed
            versions=[payload(base.replace('First paragraph.','第一段 changed by client one.'),seed['blob']),payload(base.replace('Last paragraph.','Last paragraph changed by client two.'),seed['blob'])]
            with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda item:clients[item[0]](item[1]),enumerate(versions)))
            assert all(status==200 for status,_ in results),results;assert sum(bool(result['merged']) for _,result in results)==1
            merged=next(result for _,result in results if result['merged']);expected=base.replace('First paragraph.','第一段 changed by client one.').replace('Last paragraph.','Last paragraph changed by client two.')
            assert merged['content']==expected and first.docs.read('demo.md')==expected
            for index,data in enumerate(versions):assert clients[index](data)[1]['commit']==results[index][1]['commit']
            head=first.docs.snapshot('demo.md')['commit'];status,conflict=clients[0](payload(base.replace('First paragraph.','Overlapping first paragraph.'),seed['blob']))
            assert status==409 and '<<<<<<< submitted' in conflict['conflict_markdown'];assert first.docs.snapshot('demo.md')['commit']==head
            restored=Workspace(state,token,repo,root/'restored.sqlite',args.matrix_url,args.gateway_url);retry=serve(restored)
            merged_index=next(index for index,(_,result) in enumerate(results) if result['merged']);assert retry(versions[merged_index])[1]['commit']==merged['commit']
            assert first.docs.pending()==[]
            timeline=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(room)+'/messages',state['tokens'][0],query={'dir':'b','limit':'100'})['chunk']
            assert marker not in json.dumps(timeline)
            print('PASS two HTTP sessions: non-overlapping edits preserved, overlap409 with details, exact committed content, restart/idempotency, metadata-only Matrix receipts')
    finally:
        for server,thread in servers:server.shutdown();thread.join(timeout=5);server.server_close()


if __name__=='__main__':main()
