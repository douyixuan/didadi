"""Private ordinary communication on the existing isolated Alice/Bob Matrix fixture."""
import argparse
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.request import Request,urlopen
import uuid
from src.matrix_as import AGENT,PREFIX
from src.matrix_http import request,segment
from src.runtime_socket import loopback_url

def run(base,matrix_url,state_file):
    loopback_url(base,'http');loopback_url(matrix_url,'http');state=json.loads(Path(state_file).read_text())
    session=json.load(urlopen(base+'/api/session',timeout=10));csrf=session['csrf'];actor=session['userId']
    bob=request(matrix_url,'GET',PREFIX+'/account/whoami',state['tokens'][1])['user_id']
    assert bob in session['roomCreation']['contacts'];rooms=[]
    def api(path,body=None,method=None):
        req=Request(base+path,method=method or ('POST' if body is not None else 'GET'),headers={'X-CSRF-Token':csrf,'Content-Type':'application/json'},data=json.dumps(body).encode() if body is not None else None)
        started=time.monotonic()
        for attempt in range(8):
            try:
                with urlopen(req,timeout=20) as response:return response.status,json.load(response)
            except HTTPError as error:
                status,value=error.code,json.load(error)
                if status!=429 or attempt==7:return status,value
                hint=value.get('retry_after_ms',2000)
                wait=max(.1,hint/1000) if type(hint) in {int,float} and hint>=0 else 2
                if time.monotonic()-started+wait>60:return status,value
                time.sleep(wait)
    def room_state(room):
        status,events=api('/matrix'+PREFIX+'/rooms/'+segment(room)+'/state');assert status==200;return events
    def roster(room):return {event['state_key']:event['content']['membership'] for event in room_state(room) if event['type']=='m.room.member'}
    def create(kind,peers=None,agent=False):
        body={'name':'Private '+kind+' '+uuid.uuid4().hex[:6],'kind':kind,'participants':peers or [],'invite_agent':agent,'operation':str(uuid.uuid4())}
        status,result=api('/api/rooms',body);assert status==200,(status,result);room=result['room_id'];rooms.append(room)
        assert api('/api/rooms',body)==(200,result);assert api('/api/rooms',{**body,'name':'changed'})[0]==409
        events=room_state(room);content=lambda kind:next(event['content'] for event in events if event['type']==kind)
        assert content('m.room.create')['m.federate'] is False;assert content('m.room.join_rules')['join_rule']=='invite';assert content('m.room.guest_access')['guest_access']=='forbidden';assert content('m.room.history_visibility')['history_visibility']=='invited'
        assert request(matrix_url,'GET',PREFIX+'/directory/list/room/'+segment(room),state['tokens'][0])['visibility']=='private'
        assert content('org.didadi.room')['kind']==kind;assert (AGENT in roster(room))==agent
        return room
    group=create('group');assert roster(group)=={actor:'join'}
    direct=create('direct',[bob]);assert roster(direct)[bob]=='invite'
    invite=next(event for event in room_state(direct) if event['type']=='m.room.member' and event['state_key']==bob);assert invite['content']['is_direct'] is True
    request(matrix_url,'POST',PREFIX+'/rooms/'+segment(direct)+'/join',state['tokens'][1],{})
    assert roster(direct)=={actor:'join',bob:'join'}
    status,sent=api('/matrix'+PREFIX+'/rooms/'+segment(direct)+'/send/m.room.message/'+str(uuid.uuid4()),{'msgtype':'m.text','body':'Synthetic private conversation','m.mentions':{'user_ids':[]}},'PUT');assert status==200
    received=request(matrix_url,'GET',PREFIX+'/rooms/'+segment(direct)+'/event/'+segment(sent['event_id']),state['tokens'][1]);assert received['content']['body']=='Synthetic private conversation'
    reply=request(matrix_url,'PUT',PREFIX+'/rooms/'+segment(direct)+'/send/m.room.message/'+str(uuid.uuid4()),state['tokens'][1],{'msgtype':'m.text','body':'Synthetic Bob reply'})
    assert api('/matrix'+PREFIX+'/rooms/'+segment(direct)+'/event/'+segment(reply['event_id']))[1]['sender']==bob
    invited_group=create('group',[bob]);request(matrix_url,'POST',PREFIX+'/rooms/'+segment(invited_group)+'/join',state['tokens'][1],{});assert roster(invited_group)=={actor:'join',bob:'join'}
    blocked='Agent must not receive this';assert api('/matrix'+PREFIX+'/rooms/'+segment(invited_group)+'/send/m.room.message/'+str(uuid.uuid4()),{'msgtype':'m.text','body':blocked,'m.mentions':{'user_ids':[AGENT]}},'PUT')[0]==409
    assert not any(event.get('content',{}).get('body')==blocked for event in api('/matrix'+PREFIX+'/rooms/'+segment(invited_group)+'/messages?dir=b')[1]['chunk'])
    channel=create('channel',agent=True)
    for _ in range(60):
        if roster(channel).get(AGENT)=='join':break
        time.sleep(.25)
    assert roster(channel)[AGENT]=='join'
    assert api('/api/rooms',{'name':'No external invitation','kind':'group','participants':['@third:external.invalid'],'operation':str(uuid.uuid4())})[0]==403
    assert api('/api/rooms',{'name':'No public room','visibility':'public','operation':str(uuid.uuid4())})[0]==400
    result={'base':base,'rooms':rooms,'actor':actor,'peer':bob,'realMatrix':True,'privateVisibility':True,'nonFederated':True,'defaultNoAgent':True,'directExactlyTwoJoined':True,'bobReplyReadable':True,'explicitAgentOnly':True,'sameOperationSameRoom':True,'changedOptionsRejected':True,'externalContactsRejected':True,'publicVisibilityRejected':True,'direct':direct,'channel':channel,'group':invited_group};print(json.dumps(result));return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--url',required=True);parser.add_argument('--matrix-url',required=True);parser.add_argument('--state-file',required=True);args=parser.parse_args();run(args.url,args.matrix_url,args.state_file)
