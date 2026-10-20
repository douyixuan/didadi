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

    def test_document_creation_list_isolation_and_named_receipts(self):
        first = {'room': '!doc:local', 'operation': str(uuid.uuid4()), 'name': '设计/First doc.md', 'content': '# First\n'}
        saved = self.service.create(first)
        self.assertEqual(self.service.create(first), saved)
        second = self.service.create({**first, 'operation': str(uuid.uuid4()), 'name': 'Second.md', 'content': '# Second\n'})
        self.assertEqual([item['name'] for item in self.service.documents('!doc:local')['documents']], ['Second.md', '设计/First doc.md'])
        self.assertEqual(self.service.read('!doc:local', name=first['name'])['content'], first['content'])
        changed = self.service.save(self.payload(content='# First changed\n', base_blob=saved['blob']), first['name'])
        self.assertEqual(self.store.read('Second.md'), '# Second\n')
        self.assertEqual(self.service.read('!doc:local', saved['commit'], first['name'])['content'], first['content'])
        paths = [item['content']['org.didadi.document.commit']['path'] for item in self.events.values()]
        self.assertEqual(paths, [first['name'], 'Second.md', first['name']])
        self.assertEqual(len(self.store.history(first['name'])), 2)
        self.assertEqual(len(self.store.history('Second.md')), 1)
        with self.assertRaises(DocumentError) as caught:
            self.service.create({**first, 'operation': str(uuid.uuid4()), 'content': '# Must not overwrite'})
        self.assertEqual(caught.exception.status, 409)
        self.assertEqual(self.store.read(first['name']), '# First changed\n')
        with self.assertRaises(DocumentError):
            self.service.documents('!other:local')
        self.level = 0
        self.assertFalse(self.service.documents('!doc:local')['writable'])
        with self.assertRaises(DocumentError):
            self.service.create({**first, 'operation': str(uuid.uuid4()), 'name': 'Denied.md'})

    def test_named_document_paths_and_operation_binding_fail_closed(self):
        from src.gitdocs import InvalidPath
        payload = {'room': '!doc:local', 'operation': str(uuid.uuid4()), 'name': 'Good.md', 'content': '# Good'}
        self.service.create(payload)
        for name in ['../outside.md', '.git/secret.md', 'good.md']:
            with self.assertRaises(InvalidPath):
                self.service.create({**payload, 'operation': str(uuid.uuid4()), 'name': name})
        with self.assertRaises(DocumentError):
            self.service.create({**payload, 'name': 'Other.md'})
        self.assertIsNone(self.store.read('Other.md'))

    def test_listing_filters_imported_executable_and_symlink_entries(self):
        regular = self.store.write('Regular.md', '# Regular')
        executable = self.store.write('Executable.md', '# Executable')
        head = executable['commit']
        with tempfile.TemporaryDirectory() as index:
            env = {'GIT_INDEX_FILE': str(Path(index) / 'index')}
            self.store._git('read-tree', head, env=env)
            self.store._git('update-index', '--cacheinfo', '100755', executable['blob'], 'Executable.md', env=env)
            self.store._git('update-index', '--add', '--cacheinfo', '120000', regular['blob'], 'Link.md', env=env)
            tree = self.store._git('write-tree', env=env).strip()
        commit = self.store._git('commit-tree', tree, '-p', head, input='Imported non-regular Markdown fixture').strip()
        self.store._git('update-ref', self.store.branch, commit, head)
        imported = GitDocs(Path(self.tmp.name) / 'imported.git', self.root)
        self.assertEqual([item['name'] for item in imported.documents()['documents']], ['Regular.md'])
        self.assertEqual(imported.read('Regular.md'), '# Regular')

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
    def test_move_is_atomic_byte_exact_and_idempotent(self):
        content='---\r\ntitle: Preserve\r\n---\r\n\r\n# 原文\r\n'
        created=self.service.create({'room':'!doc:local','name':'Original.md','content':content,'operation':str(uuid.uuid4())})
        payload={'room':'!doc:local','source':'Original.md','name':'Archive/Renamed.md','base_blob':created['blob'],'operation':str(uuid.uuid4())}
        moved=self.service.move(payload)
        self.assertEqual(moved['blob'],created['blob'])
        self.assertEqual(self.store.read(payload['name']),content)
        self.assertIsNone(self.store.blob_version('Original.md'))
        head=self.store._ref(self.store.branch)
        self.assertEqual(self.service.move(payload)['commit'],moved['commit'])
        self.assertEqual(self.store._ref(self.store.branch),head)
        self.assertEqual(self.store.read('Original.md',created['commit']),content)
        self.assertEqual(list(self.events.values())[-1]['content']['org.didadi.document.commit']['path'],payload['name'])
        reloaded=DocumentService(GitDocs(self.root),self.api,'@alice:local','!doc:local')
        self.assertEqual(reloaded.move(payload)['commit'],moved['commit'])

    def test_move_rejects_stale_source_existing_destination_and_cross_room(self):
        created=self.service.create({'room':'!doc:local','name':'A.md','content':'# A','operation':str(uuid.uuid4())})
        other=self.service.create({'room':'!doc:local','name':'B.md','content':'# B','operation':str(uuid.uuid4())})
        payload={'room':'!doc:local','source':'A.md','name':'B.md','base_blob':created['blob'],'operation':str(uuid.uuid4())}
        with self.assertRaises(DocumentError) as conflict:self.service.move(payload)
        self.assertEqual(conflict.exception.status,409)
        self.assertEqual(self.store.read('A.md'),'# A');self.assertEqual(self.store.read('B.md'),'# B')
        newer=self.service.save(self.payload(content='# Updated',base_blob=created['blob']),'A.md')
        with self.assertRaises(DocumentError):self.service.move({**payload,'name':'C.md','operation':str(uuid.uuid4())})
        with self.assertRaises(DocumentError) as forbidden:self.service.move({**payload,'room':'!other','name':'C.md','base_blob':newer['blob']})
        self.assertEqual(forbidden.exception.status,403)
        with self.assertRaises(DocumentError) as missing:self.service.move({**payload,'name':'C.md','base_blob':None})
        self.assertEqual(missing.exception.status,400)
        self.assertEqual(self.store.read('A.md'),'# Updated')
        self.assertIsNone(self.store.blob_version('C.md'))

    def test_competing_moves_have_one_winner_and_preserve_source_blob(self):
        made=self.service.create({'room':'!doc:local','name':'Source.md','content':'# Original','operation':str(uuid.uuid4())})
        def attempt(name):
            try:return self.service.move({'room':'!doc:local','source':'Source.md','name':name,'base_blob':made['blob'],'operation':str(uuid.uuid4())})
            except DocumentError as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(attempt,['One.md','Two.md']))
        self.assertEqual(sum(isinstance(result,dict) for result in results),1)
        self.assertEqual(results.count(409),1)
        files=self.service.documents('!doc:local')['documents']
        self.assertEqual(len(files),1);self.assertEqual(files[0]['blob'],made['blob'])

    def test_move_publication_retry_does_not_create_a_second_commit(self):
        made=self.service.create({'room':'!doc:local','name':'Source.md','content':'# Source','operation':str(uuid.uuid4())})
        payload={'room':'!doc:local','source':'Source.md','name':'Moved.md','base_blob':made['blob'],'operation':str(uuid.uuid4())}
        with patch.object(self.store,'_publish',side_effect=PublicationPending('offline')):
            with self.assertRaises(DocumentError) as pending:self.service.move(payload)
        self.assertEqual(pending.exception.status,503)
        committed=self.store._ref(self.store.branch)
        self.assertIsNone(self.store.blob_version('Source.md'))
        result=self.service.move(payload)
        self.assertEqual(result['commit'],committed)
        self.assertEqual(result['blob'],made['blob'])
