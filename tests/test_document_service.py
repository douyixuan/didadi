from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from src.document_service import DocumentService, DocumentError
from src.gitdocs import GitDocs, PublicationPending
from src.matrix_http import MatrixError
from scripts.document_worker import reconcile


class DocumentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'docs.git';self.store=GitDocs(self.root)
        self.level=100;self.joined=True;self.encrypted=False;self.offline=False;self.events={}
        self.service=DocumentService(self.store,self.api,'@alice:local','!doc:local')

    def api(self,method,path,data=None):
        if method=='GET':
            return ([{'type':'m.room.encryption','content':{}}] if self.encrypted else [])+[
                {'type':'m.room.member','state_key':'@alice:local','content':{'membership':'join' if self.joined else 'leave'}},
                {'type':'m.room.power_levels','content':{'users':{'@alice:local':self.level}}}]
        if self.offline:raise OSError('receipt offline')
        if path not in self.events:self.events[path]={'event_id':'$receipt-'+str(len(self.events)),'content':data}
        return {'event_id':self.events[path]['event_id']}

    def payload(self,**changes):
        return {'room':'!doc:local','operation':str(uuid.uuid4()),'content':'# Test 原文\r\n','base_blob':None,**changes}

    def test_direct_save_and_retry_no_body_in_receipt(self):
        data=self.payload();first=self.service.save(data);again=self.service.save(data)
        self.assertEqual(first,again);self.assertFalse(again['receipt_pending'])
        self.assertEqual(len(self.events),1);self.assertEqual(len(self.store.history('demo.md')),1)
        self.assertEqual(self.store._git('show','-s','--format=%an',first['commit']).strip(),'@alice:local')
        content=next(iter(self.events.values()))['content']
        self.assertNotIn(data['content'],str(content));self.assertEqual(content['org.didadi.document.commit']['author'],'@alice:local')
        self.assertEqual(self.store.snapshot('demo.md')['content'],data['content'])
        with self.assertRaises(DocumentError) as caught:self.service.save({**data,'content':'changed'})
        self.assertEqual(caught.exception.status,409)

    def test_concurrent_same_base_allows_only_one_commit(self):
        def save(i):
            try:return self.service.save(self.payload(content=str(i)))['status']
            except DocumentError as error:return error.status
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(save,range(2)))
        self.assertCountEqual(results,['saved',409]);self.assertEqual(len(self.store.history('demo.md')),1)

    def test_permission_boundaries_and_unicode_size(self):
        for level,join,encrypted in [(0,True,False),(True,True,False),(100,False,False),(100,True,True)]:
            self.level,self.joined,self.encrypted=level,join,encrypted
            with self.assertRaises(DocumentError):self.service.save(self.payload())
            self.assertIsNone(self.store.snapshot('demo.md')['commit'])
        self.level,self.joined,self.encrypted=100,True,False
        for change in ({'room':'!other:local'},{'content':'中'*22000},{'content':'\ud800'},{'operation':'not-uuid'},
                       {'base_blob':'wrong'},{'author':'@spoof:local'},{'path':'../private.md'}):
            with self.assertRaises(DocumentError):self.service.save(self.payload(**change))
        self.service.save(self.payload(content=''))
        self.assertEqual(self.store.snapshot('demo.md')['content'],'')

    def test_receipt_failure_restart_and_ack_loss_keep_one_commit_and_event(self):
        data=self.payload();self.offline=True;result=self.service.save(data)
        self.assertEqual(result['status'],'saved');self.assertTrue(result['receipt_pending'])
        self.assertEqual(len(self.store.pending()),1)
        self.offline=False
        with patch.object(self.store,'acknowledge',side_effect=OSError('ACK lost')):
            self.assertTrue(self.service.save(data)['receipt_pending'])
        self.assertEqual(len(self.events),1)
        restored=DocumentService(GitDocs(self.root),self.api,'@alice:local','!doc:local')
        restored.read('!doc:local')
        self.assertEqual(restored.store.pending(),[]);self.assertEqual(len(self.events),1)
        self.assertEqual(len(restored.store.history('demo.md')),1)
        self.assertFalse(restored.save(data)['receipt_pending'])

    def test_recovery_never_sends_or_acknowledges_agent_or_foreign_outbox(self):
        original=self.store.write('demo.md','agent',None,operation='$agent',notification={'task_id':'$agent','room_id':'!doc:local'})
        self.offline=True;self.service.save(self.payload(base_blob=original['blob']))
        self.offline=False;self.service.read('!doc:local')
        self.assertEqual([i['operation'] for i in self.store.pending()],['$agent'])
        calls=[]
        reconcile('', '', self.store, lambda *args,**kw: calls.append(kw['query']['id']) or {'task':None})
        self.assertEqual(calls,['$agent'])

    def test_publication_pending_preserves_operation_for_retry(self):
        with patch.object(self.store,'_publish',side_effect=PublicationPending('remote race')):
            with self.assertRaises(DocumentError) as caught:self.service.save(self.payload())
        self.assertEqual(caught.exception.status,503)
        self.assertEqual(caught.exception.data['status'],'publication_pending')
        self.assertEqual(len(self.store.history('demo.md')),1)

    def test_binding_and_gateway_mutation_authority_are_not_bypassed(self):
        from src.gateway import Gateway, TaskError
        from src.matrix_as import AGENT
        from src.agent_document_api import render_outcome
        from unittest.mock import Mock
        with self.assertRaises(ValueError):DocumentService(GitDocs(self.root),self.api,'@alice:local','!different:local')
        task={'id':'$cross-room','event':{'room_id':'!different:local','sender':'@alice:local','content':{
            'org.didadi.document':{'action':'write','content':'no','base_blob':None}}}}
        self.assertEqual(render_outcome(task,self.store)[2]['status'],'rejected')
        task['event']['content']['org.didadi.document']={'action':'read'}
        self.assertEqual(render_outcome(task,self.store)[2]['status'],'rejected')
        event={'type':'m.room.message','event_id':'$low','room_id':'!doc:local','sender':'@alice:local','content':{
            'msgtype':'m.text','body':'legacy write','m.mentions':{'user_ids':[AGENT]},
            'org.didadi.document':{'action':'write','content':'no','base_blob':None}}}
        agent=Mock();agent.api.side_effect=lambda method,path,data=None: (_ for _ in ()).throw(MatrixError(404,{'errcode':'M_NOT_FOUND'})) if path.endswith('/state/m.room.encryption') else ({'membership':'join'} if '/state/m.room.member/' in path else self.api(method,path,data))
        gateway=Gateway(Path(self.tmp.name)/'gateway.sqlite',agent)
        gateway.accept('one',[event]);claimed=gateway.claim();self.level=0
        with self.assertRaises(TaskError):gateway.validate(claimed['id'],claimed['lease'])
        self.assertIsNone(self.store.snapshot('demo.md')['commit'])
