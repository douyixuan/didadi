"""Real Matrix and Git acceptance across a WebSocket bridge restart."""
import argparse
import json
from pathlib import Path
import secrets
import tempfile
import threading
import time

from scripts.websocket_worker import run
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment
from src.runtime_socket import bridge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', required=True); parser.add_argument('--token-file', required=True)
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9000')
    args = parser.parse_args(); state=json.loads(Path(args.state_file).read_text())
    token=Path(args.token_file).read_text().strip(); stop=threading.Event()
    server=bridge(args.gateway_url,token,0,wait_seconds=1)
    port=server.socket.getsockname()[1]
    serving=threading.Thread(target=server.serve_forever,daemon=True);serving.start()
    with tempfile.TemporaryDirectory(prefix='didadi-websocket-acceptance-') as directory:
        store=GitDocs(Path(directory)/'documents.git')
        worker=threading.Thread(target=run,args=('ws://127.0.0.1:'+str(port)+'/runtime',token,store),
                                kwargs={'stop':stop},daemon=True);worker.start()
        def send(text,base_blob):
            return request(args.matrix_url,'PUT',PREFIX+'/rooms/'+segment(state['room'])+'/send/m.room.message/'+secrets.token_hex(12),
                           state['tokens'][0],{'msgtype':'m.text','body':'WebSocket deterministic fixture',
                            'm.mentions':{'user_ids':[AGENT]},'org.didadi.document':{
                            'action':'write','content':text,'base_blob':base_blob}})['event_id']
        def finish(identifier,text):
            deadline=time.monotonic()+50
            while time.monotonic()<deadline:
                task=request(args.gateway_url,'GET','/agent/status',token,query={'id':identifier})['task']
                if task and task['status']=='done':
                    reply=request(args.matrix_url,'GET',PREFIX+'/rooms/'+segment(state['room'])+'/event/'+segment(task['reply']),state['tokens'][0])
                    snapshot=store.snapshot('demo.md')
                    assert snapshot['content']==text and snapshot['commit'] in reply['content']['body']
                    assert reply['content']['m.relates_to']['event_id']==identifier
                    return snapshot
                if task and task['status'] in {'failed','cancelled'}:raise AssertionError('socket task terminated')
                time.sleep(.2)
            raise AssertionError('socket task timed out')
        try:
            first_text='# Outbound WebSocket\n\nReal Matrix fixture; no LLM.\n'
            first=finish(send(first_text,None),first_text)
            server.shutdown();serving.join(timeout=3)
            server=bridge(args.gateway_url,token,port,wait_seconds=1)
            serving=threading.Thread(target=server.serve_forever,daemon=True);serving.start()
            second_text=first_text+'\nRecovered after bridge restart.\n'
            second=finish(send(second_text,first['blob']),second_text)
            assert first['commit']!=second['commit'] and len(store.history('demo.md'))==2
            assert store.pending()==[]
        finally:
            stop.set();server.shutdown();serving.join(timeout=3);worker.join(timeout=5)
            assert not worker.is_alive(),'runtime did not stop'
    print('PASS outbound persistent WebSocket -> real Matrix/Git thread receipt; bridge restart -> automatic reconnect -> second version; exactly two document versions')


if __name__=='__main__':main()
