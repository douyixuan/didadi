from http.server import ThreadingHTTPServer
import json
import sqlite3
from pathlib import Path
import tempfile
import threading
import uuid
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen

from src.client_server import ClientError,Workspace,handler
from src.matrix_as import AGENT
from src.matrix_http import MatrixError


class ClientServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.calls=[];self.encrypted=False;self.alias_exists=False
        self.api_patch=patch.object(Workspace,'api',side_effect=self.api)
        self.api_patch.start();self.addCleanup(self.api_patch.stop)
        self.workspace=Workspace({'room':'!seed:local','tokens':['private-human-token']},'private-worker-token',
                                 self.root/'docs.git',self.root/'rooms.sqlite','http://127.0.0.1:8009','http://127.0.0.1:9001')

    def api(self,method,path,data=None,query=None):
        self.calls.append((method,path,data,query))
        if path=='/account/whoami':return {'user_id':'@human:local'}
        if path=='/joined_rooms':return {'joined_rooms':['!seed:local','!ungranted:local','!created:local']}
        if path=='/createRoom':
            if self.alias_exists:raise MatrixError(400,{'errcode':'M_ROOM_IN_USE'})
            return {'room_id':'!created:local'}
        if path.startswith('/directory/room/'):return {'room_id':'!created:local'}
        if '/state/m.room.member/' in path:return {'membership':'join'}
        if path.endswith('/state'):
            return ([{'type':'m.room.encryption','content':{}}] if self.encrypted else [])+[
                {'type':'m.room.member','state_key':AGENT,'content':{'membership':'join'}}]
        if '/send/' in path:return {'event_id':'$one'}
        return {'chunk':[]}

    def test_only_explicit_rooms_routes_and_identity_are_proxied(self):
        self.assertEqual(self.workspace.proxy('GET','/joined_rooms',{})['joined_rooms'],['!seed:local'])
        for method,path,query in [('GET','/account/whoami',{}),('GET','/rooms/!ungranted:local/state',{}),
                                  ('POST','/rooms/!seed:local/state',{}),('GET','/joined_rooms',{'user_id':['@other']})]:
            with self.assertRaises(ClientError):self.workspace.proxy(method,path,query)

    def test_repository_choices_hide_local_locations_and_ungranted_identity_or_room(self):
        grant={'path':'/private/synthetic/location','commit':'a'*40,'files':['main.py'],
               'rooms':['!seed:local','!hidden:local'],'senders':['@human:local']}
        repositories=SimpleNamespace(grants={'fixture':grant,'other-user':{**grant,'senders':['@other']}})
        workspace=Workspace({'room':'!seed:local','tokens':['private-human-token']},'private-worker-token',
            self.root/'sources-docs.git',self.root/'sources-rooms.sqlite','http://127.0.0.1:8009',
            'http://127.0.0.1:9001',repositories)
        self.assertEqual(workspace.repository_choices(),[{'repository':'fixture','path':'main.py','commit':'a'*40,'room':'!seed:local'}])
        self.assertNotIn('/private',json.dumps(workspace.repository_choices()))

    def test_encryption_and_invalid_agent_grants_fail_before_send(self):
        content={'msgtype':'m.text','body':'hello','m.mentions':{'user_ids':[AGENT]}}
        self.encrypted=True
        with self.assertRaises(ClientError) as error:self.workspace.proxy('PUT','/rooms/!seed:local/send/m.room.message/one',{},content)
        self.assertEqual(error.exception.status,409)
        self.assertFalse(any('/send/' in call[1] for call in self.calls))
        self.encrypted=False
        content['org.didadi.document']={'action':'write','content':'safe','name':'../escape.md'}
        with self.assertRaises(ClientError):self.workspace.proxy('PUT','/rooms/!seed:local/send/m.room.message/one',{},content)

    def test_platform_matrix_proxy_rejects_document_bodies_before_send(self):
        for command in ({'action':'write','content':'private draft','base_blob':None},
                        {'action':'write','base_blob':None},
                        {'action':'read','content':'private draft'}):
            self.calls.clear()
            content={'msgtype':'m.text','body':'request','m.mentions':{'user_ids':[AGENT]},
                     'org.didadi.document':command}
            with self.subTest(command=command),self.assertRaises(ClientError) as error:
                self.workspace.proxy('PUT','/rooms/!seed:local/send/m.room.message/task',{},content)
            self.assertEqual(error.exception.status,400)
            self.assertFalse(any('/send/' in call[1] for call in self.calls))
        self.calls.clear()
        content['org.didadi.document']={'action':'read'}
        self.assertEqual(self.workspace.proxy('PUT','/rooms/!seed:local/send/m.room.message/read',{},content),{'event_id':'$one'})

    def test_quote_and_thread_references_are_validated_before_send(self):
        path='/rooms/!seed:local/send/m.room.message/quote'
        for relation in ({'m.in_reply_to':{'event_id':'$source'}},
                         {'rel_type':'m.thread','event_id':'$root','m.in_reply_to':{'event_id':'$source'}}):
            self.calls.clear()
            result=self.workspace.proxy('PUT',path,{}, {'msgtype':'m.text','body':'reply','m.relates_to':relation})
            self.assertEqual(result,{'event_id':'$one'})
            sent=next(call[2] for call in self.calls if '/send/' in call[1])
            self.assertEqual(sent['m.relates_to'],relation)
            self.assertTrue(any('/event/%24source' in call[1] for call in self.calls))
        for relation in ({'m.in_reply_to':{'event_id':'bad'}},{'m.in_reply_to':{'event_id':'$one','body':'spoof'}},
                         {'rel_type':'m.replace','event_id':'$one'}, {'m.in_reply_to':{'event_id':'$one'},'user_id':'@other'},
                         {'rel_type':'m.thread','event_id':'$'+'a'*513}):
            self.calls.clear()
            with self.assertRaises(ClientError):
                self.workspace.proxy('PUT',path,{}, {'msgtype':'m.text','body':'reply','m.relates_to':relation})
            self.assertFalse(any('/send/' in call[1] for call in self.calls))

    def test_room_creation_is_idempotent_and_recovers_after_lost_record(self):
        first=self.workspace.create_room('stable-request-id','Client room')
        second=self.workspace.create_room('stable-request-id','Client room')
        self.assertEqual(first,second)
        self.assertEqual(sum(path=='/createRoom' for _,path,_,_ in self.calls),1)
        with sqlite3.connect(self.workspace.metadata) as db:
            db.execute("DELETE FROM rooms WHERE operation='stable-request-id'")
        self.alias_exists=True
        self.assertEqual(self.workspace.create_room('stable-request-id','Recovered room')['room_id'],'!created:local')
        self.workspace.allowed('!created:local')

    def test_named_document_http_creation_errors_and_room_boundary(self):
        def document_api(method, path, data=None):
            if method=='GET' and '/event/' in path:
                return {'event_id':'$source','room_id':'!seed:local','type':'m.room.message','sender':'@human:local','origin_server_ts':1,'content':{'msgtype':'m.text','body':'Canonical HTTP source'}}
            if method == 'GET':
                return [{'type': 'm.room.member', 'state_key': '@human:local', 'content': {'membership': 'join'}},
                        {'type': 'm.room.power_levels', 'content': {'users': {'@human:local': 100}}}]
            return {'event_id': '$document-receipt'}
        self.workspace.documents.api = document_api
        dist = self.root / 'document-dist'
        dist.mkdir()
        server = ThreadingHTTPServer(('127.0.0.1', 0), lambda *args: None)
        server.RequestHandlerClass = handler(self.workspace, dist, server.server_port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        def fetch(path, method='GET', data=None):
            req = Request(base + path, method=method, headers={'X-CSRF-Token': self.workspace.csrf},
                          data=json.dumps(data).encode() if data is not None else None)
            with urlopen(req, timeout=5) as response:
                return json.load(response)
        payload = {'room': '!seed:local', 'name': 'Good.md', 'content': '# Good', 'operation': str(uuid.uuid4())}
        try:
            first = fetch('/api/documents', 'POST', payload)
            self.assertEqual(fetch('/api/documents', 'POST', payload)['commit'], first['commit'])
            self.assertEqual(fetch('/api/documents?room=!seed:local')['documents'][0]['name'], 'Good.md')
            self.assertEqual(fetch('/api/document?room=!seed:local&path=Good.md')['content'], '# Good')
            for name, status in [('../outside.md', 400), ('.git/secret.md', 400), ('good.md', 409), ('Good.md', 409)]:
                with self.subTest(name=name), self.assertRaises(HTTPError) as caught:
                    fetch('/api/documents', 'POST', {**payload, 'name': name, 'operation': str(uuid.uuid4())})
                self.assertEqual(caught.exception.code, status)
            with self.assertRaises(HTTPError) as caught:
                fetch('/api/documents', 'POST', {**payload, 'room': '!other:local', 'name': 'Other.md'})
            self.assertEqual(caught.exception.code, 403)
            self.assertEqual(self.workspace.docs.read('Good.md'), '# Good')
            self.assertIsNone(self.workspace.docs.read('Other.md'))
            move={'room':'!seed:local','source':'Good.md','name':'Archive/Moved.md','base_blob':first['blob'],'operation':str(uuid.uuid4())}
            moved=fetch('/api/documents/move','POST',move)
            self.assertEqual(moved['blob'],first['blob'])
            self.assertEqual(fetch('/api/documents/move','POST',move)['commit'],moved['commit'])
            self.assertIsNone(self.workspace.docs.read('Good.md'))
            self.assertEqual(self.workspace.docs.read('Archive/Moved.md'),'# Good')
            with self.assertRaises(HTTPError) as forbidden_move:
                fetch('/api/documents/move','POST',{**move,'source':'Archive/Moved.md','name':'Other.md','room':'!other:local','operation':str(uuid.uuid4())})
            self.assertEqual(forbidden_move.exception.code,403)
            selection={'room':'!seed:local','name':'Selected.md','events':['$source'],'operation':str(uuid.uuid4())}
            selected=fetch('/api/documents/from-messages','POST',selection)
            self.assertIn('Canonical HTTP source',self.workspace.docs.read('Selected.md'))
            self.assertEqual(fetch('/api/documents/from-messages','POST',selection)['commit'],selected['commit'])
            with self.assertRaises(HTTPError) as spoofed:
                fetch('/api/documents/from-messages','POST',{**selection,'content':'Spoofed'})
            self.assertEqual(spoofed.exception.code,400)
            self.workspace.search.api=lambda method,path,data=None,query=None:{'search_categories':{'room_events':{'results':[{'result':{'event_id':'$search','room_id':'!seed:local','type':'m.room.message','sender':'@human:local','content':{'body':'Canonical HTTP source'}}}]}}}
            searched=fetch('/api/search/messages','POST',{'room':'!seed:local','query':'Canonical','next_batch':None})
            self.assertEqual(searched['events'][0]['id'],'$search')
            files=fetch('/api/search/documents','POST',{'room':'!seed:local','query':'Canonical HTTP source','after':None,'commit':None})
            self.assertEqual([item['name'] for item in files['results']],['Selected.md'])
            for path,search in [('/api/search/messages',{'room':'!other:local','query':'Canonical','next_batch':None}),('/api/search/documents',{'room':'!other:local','query':'Canonical','after':None,'commit':None})]:
                with self.assertRaises(HTTPError) as denied_search:fetch(path,'POST',search)
                self.assertEqual(denied_search.exception.code,403)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_http_csrf_host_and_static_path_boundaries_without_token_disclosure(self):
        dist=self.root/'dist';dist.mkdir();(dist/'index.html').write_text('<html>workspace</html>')
        server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None)
        server.RequestHandlerClass=handler(self.workspace,dist,server.server_port)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        def fetch(path,method='GET',data=None,headers=None):
            req=Request(base+path,method=method,headers=headers or {},data=json.dumps(data).encode() if data is not None else None)
            with urlopen(req,timeout=3) as response:return response.read().decode()
        try:
            session=fetch('/api/session');self.assertNotIn('private-human-token',session);self.assertNotIn('private-worker-token',session)
            for path,method,data,headers in [('/api/session','GET',None,{'Host':'evil.invalid'}),
                ('/api/rooms','POST',{'name':'room','operation':'operation-id'},{}),
                ('/api/task/cancel','POST',{'room':'!seed:local','id':'$task'},{}),
                ('/api/task/cancel','POST',{'room':'!seed:local','id':'$task'},{'X-CSRF-Token':self.workspace.csrf,'Origin':'https://evil.invalid'}),
                ('/api/rooms','POST',{'name':'room','operation':'operation-id'},{'X-CSRF-Token':self.workspace.csrf,'Origin':'https://evil.invalid'}),
                ('/%2e%2e/secret','GET',None,{})]:
                with self.assertRaises(HTTPError) as caught:fetch(path,method,data,headers)
                self.assertEqual(caught.exception.code,403)
            result=json.loads(fetch('/api/rooms','POST',{'name':'room','operation':'operation-id'},{'X-CSRF-Token':self.workspace.csrf}))
            self.assertEqual(result['room_id'],'!created:local')
        finally:server.shutdown();server.server_close();thread.join()

    def test_external_backends_are_rejected(self):
        with self.assertRaises(ValueError):Workspace({'room':'!seed','tokens':['x']},'x',self.root/'unused.git',self.root/'db','https://matrix.example','http://127.0.0.1:9001')

    def test_only_requester_in_granted_room_can_cancel(self):
        with patch.object(self.workspace,'api',return_value={'sender':'@human:local'}), patch('src.client_server.request',return_value={'status':'cancelled'}) as gateway:
            self.assertEqual(self.workspace.cancel_task('!seed:local','$mine')['status'],'cancelled')
            gateway.assert_called_once()
        with patch.object(self.workspace,'api',return_value={'sender':'@other:local'}), patch('src.client_server.request') as gateway:
            with self.assertRaises(ClientError):self.workspace.cancel_task('!seed:local','$other')
            gateway.assert_not_called()
        with patch('src.client_server.request') as gateway:
            with self.assertRaises(ClientError):self.workspace.cancel_task('!ungranted:local','$mine')
            gateway.assert_not_called()

    def test_thread_relations_are_room_scoped_and_never_allow_identity_or_limit_overrides(self):
        path='/rooms/%21seed%3Alocal/relations/%24root/m.thread/m.room.message'
        with patch('src.client_server.request',return_value={'chunk':[]}) as request:
            self.assertEqual(self.workspace.thread_relations('GET',path,{'from':['cursor'],'limit':['999'],'dir':['f']}),{'chunk':[]})
            args,kwargs=request.call_args
            self.assertEqual(args[:3],('http://127.0.0.1:8009','GET','/_matrix/client/v1'+path))
            self.assertEqual(kwargs['query'],{'from':'cursor','limit':'50','dir':'b'})
            for method,other,query in [('POST',path,{}),('GET',path,{'user_id':['@other']}),('GET',path.replace('seed','ungranted'),{}),('GET',path.replace('m.thread','m.replace'),{})]:
                with self.assertRaises(ClientError):self.workspace.thread_relations(method,other,query)
            self.assertEqual(request.call_count,1)

    def test_raw_attachment_upload_and_authenticated_forced_download(self):
        payload=b'<script>literal bytes</script>\r\n';events={};uploads=[]
        def attachment_api(method,path,data=None):
            if path.endswith('/state'):return [{'type':'m.room.member','state_key':'@human:local','content':{'membership':'join'}},{'type':'m.room.power_levels','content':{'users':{'@human:local':0}}}]
            if '/event/' in path:return events[path.rsplit('/',1)[1].replace('%24','$')]
            events['$attachment']={'event_id':'$attachment','room_id':'!seed:local','type':'m.room.message','content':data};return {'event_id':'$attachment'}
        def media(base,method,path,token,content=None,kind=None):
            if method=='POST':uploads.append(content);return {'content_uri':'mxc://local/media123'}
            return payload
        self.workspace.attachments.api=attachment_api;self.workspace.attachments.media=media
        dist=self.root/'attachment-dist';dist.mkdir();server=ThreadingHTTPServer(('127.0.0.1',0),lambda *args:None);server.RequestHandlerClass=handler(self.workspace,dist,server.server_port);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();base=f'http://127.0.0.1:{server.server_port}'
        operation=str(uuid.uuid4());path='/api/attachments?room=!seed:local&name=page.html&type=text%2Fhtml&operation='+operation;headers={'X-CSRF-Token':self.workspace.csrf,'Content-Type':'text/html'}
        try:
            for _ in range(2):
                with urlopen(Request(base+path,method='POST',headers=headers,data=payload),timeout=5) as response:self.assertEqual(json.load(response)['event_id'],'$attachment')
            self.assertEqual(uploads,[payload])
            download=base+'/api/attachments/download?room=!seed:local&event=$attachment'
            with self.assertRaises(HTTPError) as missing_csrf:urlopen(download,timeout=5)
            self.assertEqual(missing_csrf.exception.code,403)
            with urlopen(Request(download,headers={'X-CSRF-Token':self.workspace.csrf}),timeout=5) as response:
                self.assertEqual(response.read(),payload);self.assertEqual(response.headers['Content-Type'],'application/octet-stream');self.assertTrue(response.headers['Content-Disposition'].startswith('attachment;'));self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff')
            with self.assertRaises(HTTPError) as forbidden:urlopen(Request(download.replace('!seed:local','!other'),headers={'X-CSRF-Token':self.workspace.csrf}),timeout=5)
            self.assertEqual(forbidden.exception.code,403)
        finally:server.shutdown();server.server_close();thread.join(timeout=2)
