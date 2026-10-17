"""Authoritative task scope and loopback API boundary tests."""
import copy
from http.server import ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock

from src.agent_document_api import AgentDocuments, DocumentClient, handler
from src.gateway import Gateway, TaskError
from src.gitdocs import GitDocs
from src.matrix_as import AGENT
from src.matrix_http import MatrixError, request


class AgentDocumentAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.power=100
        agent=Mock();agent.api.side_effect=self.matrix
        self.gateway=Gateway(self.root/'gateway.sqlite',agent)
        self.store=GitDocs(self.root/'docs.git')
        self.service=AgentDocuments(self.store,self.backend,room='!room')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.service,'test-token'))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.close)
        self.url='http://127.0.0.1:'+str(self.server.server_port)
        self.client=DocumentClient(self.url,'test-token')
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=3)
    def matrix(self,method,path,data=None):
        if path.endswith('/state/m.room.encryption'):raise MatrixError(404,{'errcode':'M_NOT_FOUND'})
        if path.endswith('/state'):return [
            {'type':'m.room.member','state_key':'@human','content':{'membership':'join'}},
            {'type':'m.room.power_levels','content':{'users':{'@human':self.power}}}]
        return {'membership':'join','event_id':'$reply'}
    def backend(self,method,path,data=None,query=None):
        try:
            if path=='/agent/document-scope':return self.gateway.document_scope(data['id'],data['lease'])
            if path=='/agent/status':return {'task':self.gateway.status(query['id'])}
            raise AssertionError(path)
        except TaskError as error:raise MatrixError(403,{'error':error.code,'retryable':error.retryable})
    def claim(self,identifier='$one',base=None,room='!room',command=None):
        event={'type':'m.room.message','event_id':identifier,'sender':'@human','room_id':room,
            'content':{'msgtype':'m.text','body':'test','m.mentions':{'user_ids':[AGENT]},
                'org.didadi.document':command or {'action':'write','content':'# authoritative\r\n','base_blob':base}}}
        self.gateway.accept(identifier,[event]);return self.gateway.claim()
    def execute(self,task):return self.client.execute({'id':task['id'],'lease':task['lease']})
    def test_server_derives_content_and_rejects_every_override_and_bad_auth(self):
        task=self.claim();scope={'id':task['id'],'lease':task['lease']}
        for key,value in [('event',task['event']),('path','escape.md'),('content','forged'),('room','!evil'),('base_blob',None)]:
            with self.subTest(key=key),self.assertRaises(MatrixError):self.client.execute({**scope,key:value})
        with self.assertRaises(MatrixError):DocumentClient(self.url,'wrong').execute(scope)
        self.assertEqual(self.store.history('demo.md'),[])
        response=self.execute(task)
        self.assertEqual(response['outcome']['status'],'saved')
        self.assertEqual(self.store.read('demo.md'),'# authoritative\r\n')
        self.assertEqual(self.execute(task)['outcome'],response['outcome'])
        self.assertEqual(len(self.store.history('demo.md')),1)
    def test_expired_replaced_cancelled_and_revoked_scopes_cannot_write(self):
        task=self.claim()
        with self.gateway.db() as db:db.execute('UPDATE tasks SET until=0')
        with self.assertRaises(MatrixError):self.execute(task)
        replacement=self.gateway.claim()
        with self.assertRaises(MatrixError):self.execute(task)
        self.power=0
        with self.assertRaises(MatrixError):self.execute(replacement)
        self.assertEqual(self.store.history('demo.md'),[])
        other=self.claim('$cancel');self.gateway.cancel(other['id'])
        with self.assertRaises(MatrixError):self.execute(other)
    def test_cancel_during_authorization_is_rechecked(self):
        task=self.claim();original=self.gateway.allowed
        def check(room):
            allowed=original(room);self.gateway.cancel(task['id']);return allowed
        self.gateway.allowed=check
        with self.assertRaises(MatrixError):self.execute(task)
        self.assertEqual(self.store.history('demo.md'),[])
    def test_concurrent_base_conflict_cross_room_and_done_receipt_recovery(self):
        first=self.claim();a=self.execute(first)
        self.gateway.complete(first['id'],first['lease'],a['result'],a['outcome'])
        # Lost client ACK: reconcile only closes an existing Git receipt.
        self.assertEqual(len(self.store.pending()),1);self.client.reconcile()
        self.assertEqual(self.store.pending(),[])
        # Both competitors must change the base; a no-op leaves the blob unchanged.
        left=self.claim('$left',command={'action':'write','content':'different left','base_blob':a['outcome']['blob']});right=self.claim('$right',a['outcome']['blob'],command={'action':'write','content':'different right','base_blob':a['outcome']['blob']})
        results=[]
        threads=[threading.Thread(target=lambda task:results.append(self.execute(task)),args=(task,)) for task in (left,right)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(sorted(r['outcome']['status'] for r in results),['conflict','saved'])
        # Expire outstanding tasks before selecting a new room's task.
        self.gateway.cancel(left['id']);self.gateway.cancel(right['id'])
        other=self.claim('$room',room='!other')
        self.assertEqual(self.execute(other)['outcome']['status'],'rejected')
        self.assertEqual(len(self.store.history('demo.md')),2)
    def test_fixed_result_during_scope_refresh_prevents_new_write(self):
        task=self.claim();original=self.service.gateway;calls=0
        def gateway(method,path,data=None,query=None):
            nonlocal calls
            response=original(method,path,data,query)
            if path=='/agent/document-scope':
                calls+=1
                if calls==2: response['task']['result']='already fixed';response['task']['outcome']=None
            return response
        self.service.gateway=gateway
        self.assertEqual(self.execute(task)['result'],'Document task completed. Inspect the authorized Document API for its current version.')
        self.assertEqual(self.store.history('demo.md'),[])

    def test_unbound_repository_is_not_bound_by_a_task(self):
        unbound=GitDocs(self.root/'unbound.git');self.service.store=unbound;self.service.room=None
        response=self.execute(self.claim())
        self.assertEqual(response['outcome']['status'],'rejected')
        self.assertEqual(unbound._git('config','--get','didadi.documentRoom',check=False),'')
        self.assertEqual(unbound.history('demo.md'),[])

    def test_mixed_commands_and_runtime_selected_report_text_are_denied(self):
        task=self.claim();event=copy.deepcopy(task['event'])
        event['content']['org.didadi.repository']={'action':'report'}
        with self.gateway.db() as db:
            import json
            db.execute('UPDATE tasks SET event=? WHERE id=?',(json.dumps(event),task['id']))
        self.assertEqual(self.execute(task)['outcome']['status'],'rejected')
        with self.assertRaises(MatrixError):self.client.execute({'id':task['id'],'lease':task['lease'],'report':'forged'})
        self.assertEqual(self.store.history('demo.md'),[])

    def test_metadata_task_write_body_over_http_not_matrix_and_idempotency(self):
        task=self.claim('$http-write',command={'action':'write','base_blob':None})
        text='# PRIVATE document body\r\n'+'中'*10000
        data={'id':task['id'],'lease':task['lease'],'content':text}
        response=self.client.write(data)
        self.assertEqual(response['outcome']['status'],'saved');self.assertNotIn(text,response['result'])
        self.assertEqual(self.store.read('demo.md'),text);self.assertNotIn('content',task['event']['content']['org.didadi.document'])
        self.assertEqual(self.client.write(data)['outcome'],response['outcome']);self.assertEqual(len(self.store.history('demo.md')),1)
        changed=self.client.write({**data,'content':'changed'})
        self.assertEqual(changed['outcome']['status'],'conflict');self.assertEqual(self.store.read('demo.md'),text)
        for extra in ({'path':'other.md'},{'base_blob':None},{'room':'!other'}):
            with self.assertRaises(MatrixError):self.client.write({**data,**extra})

    def test_read_resource_is_http_only_and_fixed_version_recovers_after_result_delivery_failure(self):
        seed=self.store.write('demo.md','# HTTP ONLY CONTENT\n')
        task=self.claim('$read',command={'action':'read'})
        response=self.execute(task);self.assertEqual(response['resource']['content'],'# HTTP ONLY CONTENT\n');self.assertNotIn('HTTP ONLY CONTENT',response['result'])
        with self.gateway.db() as db:
            import json
            db.execute('UPDATE tasks SET result=?,outcome=? WHERE id=?',('OLD UNSAFE BODY',json.dumps(response['outcome'],sort_keys=True,separators=(',',':')),task['id']))
        self.store.write('demo.md','# New version',seed['blob'])
        replay=self.execute(task);self.assertEqual(replay['resource']['content'],'# HTTP ONLY CONTENT\n');self.assertEqual(replay['resource']['commit'],seed['commit']);self.assertNotIn('OLD UNSAFE BODY',replay['result'])
        self.assertEqual(self.client.write({'id':task['id'],'lease':task['lease'],'content':'forged'})['outcome']['status'],'rejected')

    def test_read_resource_is_not_returned_after_cancellation_during_git_read(self):
        self.store.write('demo.md','private')
        task=self.claim('$read-cancel',command={'action':'read'});original=self.store.snapshot
        def snapshot(*args,**kw):
            result=original(*args,**kw);self.gateway.cancel(task['id']);return result
        from unittest.mock import patch
        with patch.object(self.store,'snapshot',side_effect=snapshot),self.assertRaises(MatrixError):self.execute(task)

    def test_source_resource_body_and_metadata_reference_use_only_current_grant(self):
        from src.repository_read import RepositoryReader
        import subprocess
        source=self.root/'source';source.mkdir();subprocess.run(['git','init','-q',str(source)],check=True)
        (source/'example.py').write_text('UNTRUSTED SOURCE BODY\n')
        subprocess.run(['git','-C',str(source),'add','.'],check=True)
        subprocess.run(['git','-C',str(source),'-c','user.name=Fixture','-c','user.email=test@local','commit','-qm','fixture'],check=True)
        commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD']).decode().strip()
        self.service.repositories=RepositoryReader({'repositories':{'fixture':{'path':str(source),'commit':commit,'rooms':['!room'],'senders':['@human'],'files':['example.py']}}})
        task=self.claim('$source');event=task['event'];event['content'].pop('org.didadi.document');event['content']['org.didadi.repository']={'action':'read','repository':'fixture','path':'example.py'}
        with self.gateway.db() as db:
            import json
            db.execute('UPDATE tasks SET event=? WHERE id=?',(json.dumps(event),task['id']))
        result=self.execute(task);self.assertEqual(result['resource']['content'],'UNTRUSTED SOURCE BODY\n');self.assertEqual(result['outcome']['resource']['commit'],commit);self.assertNotIn('UNTRUSTED SOURCE BODY',result['result'])
        self.service.repositories=None
        self.assertEqual(self.execute(task)['outcome']['status'],'rejected')

    def test_fixed_write_replay_validates_original_content_after_delivery_failure_and_release(self):
        task=self.claim('$fixed-http-write',command={'action':'write','base_blob':None})
        data={'id':task['id'],'lease':task['lease'],'content':'original private body'}
        saved=self.client.write(data)
        original=self.gateway.agent.api.side_effect
        def offline(method,path,data=None):
            if method=='PUT':raise OSError('offline')
            return original(method,path,data)
        self.gateway.agent.api.side_effect=offline
        with self.assertRaises(OSError):self.gateway.complete(task['id'],task['lease'],saved['result'],saved['outcome'])
        self.gateway.agent.api.side_effect=original
        with self.assertRaises(MatrixError) as error:self.client.write({**data,'content':'changed'})
        self.assertEqual(error.exception.status,409)
        with self.gateway.db() as db:db.execute('UPDATE tasks SET until=0')
        retry=self.gateway.claim();data['lease']=retry['lease']
        self.assertEqual(self.client.write(data)['outcome'],saved['outcome'])
        with self.assertRaises(MatrixError):self.client.write({**data,'content':'changed again'})
        self.assertEqual(self.store.read('demo.md'),'original private body')
        self.assertEqual(len(self.store.history('demo.md')),1)
