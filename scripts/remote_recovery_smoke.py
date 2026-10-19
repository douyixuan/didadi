"""Real HTTP/Matrix recovery of ordinary divergence; trusted local bare fixtures only."""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid
from unittest.mock import patch

from src.client_server import Workspace, handler
from src.gitdocs import GitDocs
from src.matrix_as import PREFIX
from src.matrix_http import request, segment


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--state-file',required=True);parser.add_argument('--token-file',required=True)
    parser.add_argument('--matrix-url',default='http://127.0.0.1:8008');parser.add_argument('--gateway-url',default='http://127.0.0.1:9000')
    args=parser.parse_args();state=json.loads(Path(args.state_file).read_text());token=Path(args.token_file).read_text().strip();servers=[]
    def serve(workspace):
        http=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None);http.RequestHandlerClass=handler(workspace,Path('client/dist'),http.server_port)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start();servers.append((http,thread));base='http://127.0.0.1:'+str(http.server_port)
        def api(path,data=None):
            req=Request(base+path,method='GET' if data is None else 'PUT',data=None if data is None else json.dumps(data).encode(),
                headers={'Content-Type':'application/json','Origin':base,'X-CSRF-Token':workspace.csrf})
            try:
                with urlopen(req,timeout=30) as response:return response.status,json.load(response)
            except HTTPError as error:return error.code,json.load(error)
        return api
    try:
        with tempfile.TemporaryDirectory(prefix='didadi-remote-recovery-') as temporary:
            root=Path(temporary);remote=GitDocs(root/'upstream.git');GitDocs(root/'documents.git',remote.root)
            first=Workspace(state,token,root/'documents.git',root/'one.sqlite',args.matrix_url,args.gateway_url);api=serve(first);room=state['room']
            marker='recovery-private-body-'+secrets.token_hex(12);base='# Shared\n\nLOCAL base\n\n'+marker+'\n\nREMOTE base\n'
            def payload(content,blob):return {'room':room,'operation':str(uuid.uuid4()),'content':content,'base_blob':blob}
            status,seed=api('/api/documents/demo.md',payload(base,None));assert status==200
            peer=GitDocs(root/'peer.git',remote.root);data=payload(base.replace('LOCAL base','LOCAL reviewed change'),seed['blob'])
            publish=first.docs._publish;other={}
            def race():
                other.update(peer.write('demo.md',base.replace('REMOTE base','REMOTE reviewed change'),seed['blob']))
                return publish()
            with patch.object(first.docs,'_publish',side_effect=race):
                status,blocked=api('/api/documents/demo.md',data)
            assert status==503 and blocked['status']=='remote_diverged'
            local=first.docs._ref(first.docs.branch)
            expected={'local_commit':local,'remote_commit':other['commit'],'merge_base':seed['commit']}
            assert blocked['recovery']==expected and marker not in json.dumps(blocked) and str(root) not in json.dumps(blocked)
            latest='/api/document?'+urlencode({'room':room})
            assert api(latest)[0]==503
            fixed=api(latest+'&'+urlencode({'commit':local}));assert fixed[0]==200 and fixed[1]['content']==data['content']
            restored=Workspace(state,token,first.docs.root,root/'restart.sqlite',args.matrix_url,args.gateway_url);retry=serve(restored)
            assert retry(latest)[1]['status']=='remote_diverged' and retry('/api/documents/demo.md',data)[0]==503
            def timeline():return request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(room)+'/messages',state['tokens'][0],query={'dir':'b','limit':100})['chunk']
            assert not any(e.get('content',{}).get('org.didadi.document.commit',{}).get('commit')==local for e in timeline())
            assert remote._ref(remote.branch)==other['commit'] and restored.docs._ref(restored.docs.branch)==local
            review=root/'review'
            def git(*arguments):return subprocess.check_output(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
                '-c','user.name=Recovery fixture','-c','user.email=recovery@local',*arguments],stderr=subprocess.STDOUT).decode().strip()
            # An operator uses a new working copy, reviews a merge and ordinary-pushes
            # it into the service repository. No forced update, reset or rebase.
            git('clone','--no-hardlinks',str(first.docs.root),str(review))
            git('-C',str(review),'remote','add','upstream',str(remote.root));git('-C',str(review),'fetch','upstream','main')
            git('-C',str(review),'merge','--no-ff','--no-commit',other['commit'])
            expected_text=base.replace('LOCAL base','LOCAL reviewed change').replace('REMOTE base','REMOTE reviewed change')
            assert (review/'demo.md').read_text()==expected_text
            git('-C',str(review),'commit','-m','Operator reviewed both retained histories');merged=git('-C',str(review),'rev-parse','HEAD')
            assert git('-C',str(review),'show','-s','--format=%P','HEAD').split()==[local,other['commit']]
            assert first.docs._ref(first.docs.branch)==local and remote._ref(remote.branch)==other['commit']
            git('-C',str(review),'push','origin','HEAD:refs/heads/main')
            final=Workspace(state,token,first.docs.root,root/'final.sqlite',args.matrix_url,args.gateway_url);done=serve(final)
            for _ in range(2):
                status,saved=done('/api/documents/demo.md',data);assert status==200 and saved['commit']==local
            current=done(latest)[1];assert current['commit']==merged and current['content']==expected_text
            assert remote._ref(remote.branch)==merged and final.docs.pending()==[]
            events=timeline();receipts=[e for e in events if e.get('content',{}).get('org.didadi.document.commit',{}).get('commit')==local]
            assert len(receipts)==1 and marker not in json.dumps(events)
            assert final.docs._git('merge-base',local,merged).strip()==local
            assert final.docs._git('merge-base',other['commit'],merged).strip()==other['commit']
            assert len(final.docs.history('demo.md'))==4
            print('PASS real HTTP/Matrix + isolated local bare remote: divergence503 metadata, blocked latest/restart, fixed reads, no unpublished receipt; operator non-force two-parent merge retains both histories; original save replay one commit/receipt, latest merged content and reconciled outbox')
    finally:
        for http,thread in servers:http.shutdown();http.server_close();thread.join(timeout=3)


if __name__=='__main__':main()
