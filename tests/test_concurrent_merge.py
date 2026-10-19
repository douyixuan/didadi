from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
import uuid

from src.gitdocs import GitDocs, Conflict, MergeConflict
from src.document_service import DocumentService, DocumentError

BASE='# Team\n\nFirst paragraph.\n\nMiddle paragraph.\n\nLast paragraph.\n'
LEFT=BASE.replace('First paragraph.','First paragraph changed by Alice.')
RIGHT=BASE.replace('Last paragraph.','Last paragraph changed by Bob.')

class ConcurrentMergeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'docs.git';self.store=GitDocs(self.root)
        self.base=self.store.write('demo.md',BASE)

    def test_two_independent_stores_merge_nonoverlapping_edits_and_replay_after_restart(self):
        stores=[GitDocs(self.root),GitDocs(self.root)]
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda item:stores[item[0]].write('demo.md',item[1],self.base['blob'],operation='save'+str(item[0]),merge_non_overlapping=True),enumerate((LEFT,RIGHT))))
        self.assertEqual(sum(bool(result.get('merged')) for result in results),1)
        expected=LEFT.replace('Last paragraph.','Last paragraph changed by Bob.')
        self.assertEqual(self.store.read('demo.md'),expected)
        restored=GitDocs(self.root)
        for index,content in enumerate((LEFT,RIGHT)):
            self.assertEqual(restored.write('demo.md',content,self.base['blob'],operation='save'+str(index),merge_non_overlapping=True)['commit'],results[index]['commit'])
        self.assertEqual(len(restored.history('demo.md')),3)

    def test_overlap_keeps_head_and_returns_bounded_diff3_text(self):
        current=self.store.write('demo.md',LEFT,self.base['blob'])
        with self.assertRaises(MergeConflict) as caught:self.store.write('demo.md',BASE.replace('First paragraph.','Different first paragraph.'),self.base['blob'],merge_non_overlapping=True)
        self.assertIn('<<<<<<< submitted',caught.exception.conflict_markdown)
        self.assertIn('||||||| base',caught.exception.conflict_markdown)
        self.assertIn('>>>>>>> latest',caught.exception.conflict_markdown)
        self.assertEqual(self.store.snapshot('demo.md')['commit'],current['commit'])
        self.assertLessEqual(len(caught.exception.conflict_markdown.encode()),65536)

    def test_default_cas_stays_strict_and_other_document_blob_cannot_be_merged(self):
        secret=self.store.write('private.md','PRIVATE OTHER FILE',None)
        current=self.store.write('demo.md',LEFT,self.base['blob'])
        for base,options in [(self.base['blob'],{}),(secret['blob'],{'merge_non_overlapping':True}),('f'*40,{'merge_non_overlapping':True}),(None,{'merge_non_overlapping':True})]:
            with self.assertRaises(Conflict) as caught:self.store.write('demo.md',RIGHT,base,**options)
            self.assertNotIn('PRIVATE OTHER FILE',str(caught.exception));self.assertFalse(hasattr(caught.exception,'conflict_markdown'))
        self.assertEqual(self.store.snapshot('demo.md')['commit'],current['commit'])

    def test_merged_utf8_size_and_binary_fail_closed(self):
        large='a'*25000+'\n\n'+'m'*100+'\n\n'+'b'*25000+'\n'
        seed=self.store.write('demo.md',large,self.base['blob'])
        first=self.store.write('demo.md',large.replace('a'*25000,'a'*35000),seed['blob'])
        with self.assertRaises(Conflict):self.store.write('demo.md',large.replace('b'*25000,'b'*35000),seed['blob'],merge_non_overlapping=True)
        self.assertEqual(self.store.snapshot('demo.md')['commit'],first['commit'])
        with self.assertRaises(Conflict):self.store.write('demo.md','\0binary',seed['blob'],merge_non_overlapping=True)

    def test_crlf_merge_preserves_unicode_and_line_endings(self):
        text=BASE.replace('\n','\r\n');seed=self.store.write('demo.md',text,self.base['blob'])
        self.store.write('demo.md',text.replace('First paragraph.','第一段。'),seed['blob'])
        self.store.write('demo.md',text.replace('Last paragraph.','最后一段。'),seed['blob'],merge_non_overlapping=True)
        self.assertEqual(self.store.read('demo.md'),text.replace('First paragraph.','第一段。').replace('Last paragraph.','最后一段。'))

    def test_service_merge_author_receipt_and_conflict_contract(self):
        events=[]
        def api(method,path,data=None):
            if method=='GET':return [{'type':'m.room.member','state_key':'@alice:local','content':{'membership':'join'}},{'type':'m.room.power_levels','content':{'users':{'@alice:local':100}}}]
            events.append(data);return {'event_id':'$'+str(len(events))}
        service=DocumentService(self.store,api,'@alice:local','!room:local')
        def payload(content):return {'room':'!room:local','operation':str(uuid.uuid4()),'content':content,'base_blob':self.base['blob']}
        service.save(payload(LEFT));data=payload(RIGHT);merged=service.save(data)
        self.assertTrue(merged['merged']);self.assertEqual(service.save(data)['commit'],merged['commit'])
        self.assertNotIn('paragraph',str(events));self.assertEqual(self.store.pending(),[])
        self.assertEqual(self.store._git('show','-s','--format=%an',merged['commit']).strip(),'@alice:local')
        with self.assertRaises(DocumentError) as caught:service.save(payload(BASE.replace('Last paragraph.','Overlapping last.')))
        self.assertEqual(caught.exception.status,409);self.assertIn('<<<<<<< submitted',caught.exception.data['conflict_markdown'])
        self.assertEqual(self.store.snapshot('demo.md')['commit'],merged['commit'])

    def external_blob(self, data, mode='100644'):
        import subprocess
        result=subprocess.run(['git','--git-dir',str(self.root),'hash-object','-w','--stdin'],input=data,capture_output=True,check=True)
        blob=result.stdout.decode().strip();head=self.store._ref(self.store.branch)
        with tempfile.TemporaryDirectory() as folder:
            env={'GIT_INDEX_FILE':str(Path(folder)/'index')}
            self.store._git('read-tree',head,env=env)
            self.store._git('update-index','--add','--cacheinfo',mode,blob,'demo.md',env=env)
            tree=self.store._git('write-tree',env=env).strip()
        commit=self.store._git('commit-tree',tree,'-p',head,input='External test fixture').strip()
        self.store._git('update-ref',self.store.branch,commit,head)
        return blob,commit

    def test_historical_symlink_base_and_large_or_invalid_utf8_inputs_are_rejected(self):
        link,_=self.external_blob(b'SECRET LINK TARGET','120000')
        self.external_blob(LEFT.encode())
        with self.assertRaises(Conflict) as caught:self.store.write('demo.md',RIGHT,link,merge_non_overlapping=True)
        self.assertFalse(hasattr(caught.exception,'conflict_markdown'))
        for raw in (b'x'*65537,b'\xffnot utf8'):
            base,_=self.external_blob(raw);_,head=self.external_blob(LEFT.encode())
            with self.assertRaises(Conflict):self.store.write('demo.md',RIGHT,base,merge_non_overlapping=True)
            self.assertEqual(self.store._ref(self.store.branch),head)
        self.external_blob(b'\xfflatest')
        with self.assertRaises(Conflict):self.store.write('demo.md',RIGHT,self.base['blob'],merge_non_overlapping=True)

    def test_conflict_preview_is_utf8_bounded_without_a_commit(self):
        base='# A\n\n'+'x'*30000+'\n';seed=self.store.write('demo.md',base,self.base['blob'])
        current=self.store.write('demo.md',base.replace('x'*30000,'中'*21000),seed['blob'])
        with self.assertRaises(MergeConflict) as caught:self.store.write('demo.md',base.replace('x'*30000,'文'*21000),seed['blob'],merge_non_overlapping=True)
        self.assertTrue(caught.exception.truncated);self.assertLessEqual(len(caught.exception.conflict_markdown.encode()),65536)
        self.assertEqual(self.store._ref(self.store.branch),current['commit'])

    def test_separate_processes_do_not_drop_cleanly_mergeable_updates(self):
        import subprocess,sys,json
        code="""import sys,json,time
from pathlib import Path
from src.gitdocs import GitDocs
root,base,content,operation,gate=sys.argv[1:]
while not Path(gate).exists():time.sleep(.01)
print(json.dumps(GitDocs(root).write('demo.md',content,base,operation=operation,merge_non_overlapping=True)))
"""
        gate=Path(self.tmp.name)/'go';children=[]
        try:
            for index,content in enumerate((LEFT,RIGHT)):
                children.append(subprocess.Popen([sys.executable,'-c',code,str(self.root),self.base['blob'],content,'process'+str(index),str(gate)],stdout=subprocess.PIPE,stderr=subprocess.PIPE))
            gate.touch()
            results=[]
            for child in children:
                output,error=child.communicate(timeout=40);self.assertEqual(child.returncode,0,error.decode());results.append(json.loads(output))
            self.assertEqual(sum(bool(result.get('merged')) for result in results),1)
            self.assertIn('Alice',self.store.read('demo.md'));self.assertIn('Bob',self.store.read('demo.md'))
        finally:
            for child in children:
                if child.poll() is None:child.terminate();child.wait(timeout=5)

    def test_service_invalid_or_oversize_latest_keeps_typed_conflict_without_rereading_body(self):
        from unittest.mock import patch
        def api(method,path,data=None):return [{'type':'m.room.member','state_key':'@alice:local','content':{'membership':'join'}},{'type':'m.room.power_levels','content':{'users':{'@alice:local':100}}}]
        service=DocumentService(self.store,api,'@alice:local','!room:local')
        for raw,expected_reads in [(b'x'*65537,0),(b'\xfflatest',1)]:
            blob,head=self.external_blob(raw)
            with patch.object(self.store,'_git',wraps=self.store._git) as calls:
                with self.assertRaises(DocumentError) as caught:service.save({'room':'!room:local','operation':str(uuid.uuid4()),'content':RIGHT,'base_blob':self.base['blob']})
                self.assertEqual(caught.exception.status,409);self.assertEqual(caught.exception.data['current_blob'],blob)
                body_reads=[call for call in calls.call_args_list if call.args==('cat-file','blob',blob)]
                self.assertEqual(len(body_reads),expected_reads)
            self.assertEqual(self.store._ref(self.store.branch),head)
