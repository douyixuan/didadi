"""Real Synapse room revocation and healthy-room progress. Run in isolated Compose."""
import json
from pathlib import Path
import secrets
import time

from scripts.agent_worker import once
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment, MatrixError


def main():
    state=json.loads(Path('/config/smoke-state.json').read_text())
    token=Path('/config/agent-token').read_text().strip()
    hs=json.loads(Path('/config/secrets.json').read_text())['hs_token']
    matrix='http://synapse:8008';gateway='http://appservice:9000'
    def api(method,path,data=None):
        return request(matrix,method,PREFIX+path,state['tokens'][0],data)
    def wait(predicate):
        end=time.monotonic()+40
        while time.monotonic()<end:
            result=predicate()
            if result:return result
            time.sleep(.2)
        raise AssertionError('lifecycle condition timed out')
    while once(gateway,token):pass
    gone=api('POST','/createRoom',{'preset':'private_chat','invite':[AGENT]})['room_id']
    def joined():
        try:return api('GET','/rooms/'+segment(gone)+'/state/m.room.member/'+segment(AGENT)).get('membership')=='join'
        except MatrixError:return False
    wait(joined)
    def mention(room):
        return api('PUT','/rooms/'+segment(room)+'/send/m.room.message/'+secrets.token_hex(12),
                   {'msgtype':'m.text','body':'lifecycle fixture','m.mentions':{'user_ids':[AGENT]}})['event_id']
    blocked=mention(gone)
    wait(lambda:request(gateway,'GET','/agent/status',token,query={'id':blocked})['task'])
    api('POST','/rooms/'+segment(gone)+'/kick',{'user_id':AGENT,'reason':'isolated lifecycle validation'})
    healthy=mention(state['room'])
    wait(lambda:request(gateway,'GET','/agent/status',token,query={'id':healthy})['task'])
    # A mixed AS delivery after revocation exercises real Synapse forbidden lookups.
    sender=api('GET','/account/whoami')['user_id']
    events=[]
    for room,identifier in [(gone,'$denied-'+secrets.token_hex(8)),(state['room'],healthy)]:
        events.append({'type':'m.room.message','event_id':identifier,'room_id':room,'sender':sender,
                       'content':{'msgtype':'m.text','body':'mixed fixture','m.mentions':{'user_ids':[AGENT]}}})
    request(gateway,'PUT','/_matrix/app/v1/transactions/lifecycle-'+secrets.token_hex(8),hs,{'events':events})
    assert request(gateway,'GET','/agent/status',token,query={'id':events[0]['event_id']})['task'] is None
    assert request(gateway,'GET','/agent/status',token,query={'id':events[1]['event_id']})['task']
    while once(gateway,token):pass
    assert request(gateway,'GET','/agent/status',token,query={'id':blocked})['task']['status']=='failed'
    assert request(gateway,'GET','/agent/status',token,query={'id':healthy})['task']['status']=='done'
    print('PASS real kicked room terminates its pending task; healthy room progresses; mixed transaction ACKed')


if __name__=='__main__':main()
