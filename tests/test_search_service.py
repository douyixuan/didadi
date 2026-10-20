from pathlib import Path
import tempfile
import unittest
from src.gitdocs import GitDocs
from src.document_service import DocumentService,DocumentError
from src.search_service import SearchService


class SearchServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.store=GitDocs(Path(self.tmp.name)/'docs.git');self.calls=[]
        self.documents=DocumentService(self.store,self.api,'@human:local','!doc:local')
        self.search=SearchService(self.documents,self.api,self.allowed)

    def allowed(self,room):
        if room!='!doc:local':raise DocumentError(403,'Room unavailable')

    def api(self,method,path,data=None,query=None):
        self.calls.append((method,path,data,query))
        if method=='GET':return [{'type':'m.room.member','state_key':'@human:local','content':{'membership':'join'}},{'type':'m.room.power_levels','content':{'users':{'@human:local':0}}}]
        return {'search_categories':{'room_events':{'next_batch':'next','results':[
            {'result':{'event_id':'$ok','room_id':'!doc:local','sender':'@human:local','type':'m.room.message','content':{'msgtype':'m.text','body':'Body needle'}}},
            {'result':{'event_id':'$other','room_id':'!other','sender':'@human:local','type':'m.room.message','content':{'body':'Must not leak'}}}]}}}

    def seed(self,files):
        entries=[]
        for name,content in sorted(files.items()):
            blob=self.store._git('hash-object','-w','--stdin',input=content).strip();entries.append('100644 blob '+blob+'\t'+name)
        tree=self.store._git('mktree',input='\n'.join(entries)+'\n').strip();revision=self.store._git('commit-tree',tree,input='Imported documents\n').strip();self.store._git('update-ref',self.store.branch,revision);return revision

    def test_matrix_search_is_fixed_to_authorized_room_and_body_with_opaque_pagination(self):
        result=self.search.messages({'room':'!doc:local','query':'needle','next_batch':'previous'})
        self.assertEqual([item['id'] for item in result['events']],['$ok']);self.assertEqual(result['next_batch'],'next')
        method,path,body,query=self.calls[-1];self.assertEqual((method,path),('POST','/search'));opts=body['search_categories']['room_events']
        self.assertEqual(opts['keys'],['content.body']);self.assertEqual(opts['filter'],{'rooms':['!doc:local'],'limit':20});self.assertEqual(query,{'next_batch':'previous'})
        before=len(self.calls)
        for data in [{'room':'!other','query':'needle','next_batch':None},{'room':'!doc:local','query':'','next_batch':None},{'room':'!doc:local','query':'needle','next_batch':None,'user_id':'@other'},{'room':{},'query':'needle','next_batch':None}]:
            with self.assertRaises(DocumentError):self.search.messages(data)
        self.assertEqual(len(self.calls),before)

    def test_document_search_reads_body_not_only_names_and_returns_fixed_blob_line(self):
        revision=self.seed({'Plain.md':'# Heading\n\nneedle only inside body\n','Needle.md':'# Title without the term\n'})
        result=self.search.files({'room':'!doc:local','query':'NEEDLE','after':None,'commit':None})
        self.assertEqual([item['name'] for item in result['results']],['Plain.md']);match=result['results'][0];self.assertEqual(match['line'],3);self.assertEqual(match['commit'],revision);self.assertIn('needle only inside body',match['excerpt']);self.assertEqual(match['blob'],self.store.blob_version('Plain.md'))
        with self.assertRaises(DocumentError):self.search.files({'room':'!other','query':'needle','after':None,'commit':None})

    def test_document_pages_keep_one_reachable_snapshot_across_new_writes(self):
        revision=self.seed({f'Doc{i:02}.md':'# Title\nneedle in body' for i in range(25)})
        first=self.search.files({'room':'!doc:local','query':'needle','after':None,'commit':None});self.assertEqual(len(first['results']),20);self.assertEqual(first['next_path'],'Doc19.md')
        self.store.write('Doc24.md','# Replaced',self.store.blob_version('Doc24.md'))
        second=self.search.files({'room':'!doc:local','query':'needle','after':first['next_path'],'commit':first['commit']})
        self.assertEqual(len(second['results']),5);self.assertEqual(second['commit'],revision);self.assertIsNone(second['next_path']);self.assertEqual(second['results'][-1]['name'],'Doc24.md')
        orphan=self.store._git('commit-tree',self.store._git('rev-parse',revision+'^{tree}').strip(),input='Not reachable\n').strip()
        with self.assertRaises(ValueError):self.search.files({'room':'!doc:local','query':'needle','after':None,'commit':orphan})

    def test_oversized_imports_are_reported_and_literal_queries_do_not_become_regex(self):
        self.seed({'Large.md':'needle'+'x'*65536,'Literal.md':'# Text\n[.*] is literal'})
        result=self.search.files({'room':'!doc:local','query':'[.*]','after':None,'commit':None});self.assertEqual(result['skipped_documents'],1);self.assertEqual([item['name'] for item in result['results']],['Literal.md'])
