"""Exercise the documented local workspace through its HTTP routes, without GUI claims."""
import argparse
import json
import secrets
import time
from urllib.parse import urlencode
from urllib.request import Request,urlopen

from src.matrix_as import PREFIX
from src.matrix_http import segment
from src.runtime_socket import loopback_url


def verify(base):
    loopback_url(base,'http')
    with urlopen(base+'/api/session',timeout=15) as response:session=json.load(response)
    assert session['documentSave']=='direct-v1'
    assert 'access_token' not in json.dumps(session)
    choices=session['repositoryReads'];assert choices,'Configure the synthetic source fixture first.'
    source=choices[0];room=session['documentRoom'];assert source['room']==room
    def api(path,data=None,method='GET'):
        headers={'Content-Type':'application/json','X-CSRF-Token':session['csrf'],'Origin':base}
        request=Request(base+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
        with urlopen(request,timeout=20) as response:return json.load(response)
    def document():return api('/api/document?'+urlencode({'room':room}))
    def send(command):
        return api('/matrix'+PREFIX+'/rooms/'+segment(room)+'/send/m.room.message/'+secrets.token_hex(12),{
            'msgtype':'m.text','body':'Synthetic workspace acceptance; deterministic report, no LLM.',
            'm.mentions':{'user_ids':[session['agentId']]},'org.didadi.repository':command},'PUT')['event_id']
    def finish(identifier):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            task=api('/api/task?'+urlencode({'room':room,'id':identifier}))['task']
            if task and task['status']=='done':return task
            if task and task['status'] in {'failed','cancelled'}:raise AssertionError('Workspace task stopped')
            time.sleep(.25)
        raise AssertionError('Workspace task did not finish')
    command={'repository':source['repository'],'path':source['path']}
    read=finish(send({**command,'action':'read'}))
    assert read['outcome']['status']=='read' and source['commit'] in read['body']
    before=document();saved=finish(send({**command,'action':'report','base_blob':before['blob']}))
    assert saved['outcome']['status']=='saved'
    latest=document();assert latest['commit']==saved['outcome']['commit'] and source['commit'] in latest['content']
    denied=finish(send({**command,'path':'not-granted.txt','action':'report','base_blob':latest['blob']}))
    assert denied['outcome']['status']=='rejected' and document()['commit']==latest['commit']
    print('PASS workspace HTTP source choice -> read -> scoped API report -> Git; denied source cannot change document')
    return {'document_commit':latest['commit'],'source_commit':source['commit'],'browser_ui_verified':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',default='http://127.0.0.1:8790')
    args=parser.parse_args();print(json.dumps(verify(args.url)))
