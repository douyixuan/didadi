"""Ordinary divergence stays blocked until an operator preserves both histories."""
from pathlib import Path
import subprocess
import tempfile
import unittest
import uuid
from unittest.mock import patch

from src.document_service import DocumentError, DocumentService
from src.gitdocs import GitDocs, PublicationPending


class RemoteRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.remote=GitDocs(self.root/'remote.git')
        self.store=GitDocs(self.root/'local.git',self.remote.root)
        self.seed=self.store.write('demo.md','# Base\n\nOne\n\nTwo\n')
        self.peer=GitDocs(self.root/'peer.git',self.remote.root);self.events={}
        self.service=DocumentService(self.store,self.api,'@human:local','!room:local')
        self.data={'room':'!room:local','operation':str(uuid.uuid4()),'base_blob':self.seed['blob'],
                   'content':'# Base\n\nLOCAL change\n\nTwo\n'}

    def api(self,method,path,data=None):
        if method=='GET':return [
            {'type':'m.room.member','state_key':'@human:local','content':{'membership':'join'}},
            {'type':'m.room.power_levels','content':{'users':{'@human:local':100}}}]
        self.events[path]=data
        return {'event_id':'$receipt'}

    def diverge(self):
        publish=self.store._publish
        def race():
            self.other=self.peer.write('demo.md','# Base\n\nOne\n\nREMOTE change\n',self.seed['blob'])
            return publish()
        with patch.object(self.store,'_publish',side_effect=race),self.assertRaises(DocumentError) as caught:
            self.service.save(self.data)
        self.local=self.store._ref(self.store.branch)
        return caught.exception

    def merge_as_operator(self):
        review=self.root/'operator-review'
        def git(*args,check=True):
            return subprocess.run(['git','-c','core.hooksPath=/dev/null','-c','commit.gpgsign=false',
                '-c','user.name=Recovery fixture','-c','user.email=recovery@local',*args],
                check=check,capture_output=True,text=True)
        git('clone','--no-hardlinks',str(self.store.root),str(review))
        git('-C',str(review),'remote','add','upstream',str(self.remote.root))
        git('-C',str(review),'fetch','upstream','main')
        git('-C',str(review),'merge','--no-ff','--no-commit',self.other['commit'])
        git('-C',str(review),'commit','-m','Operator reviewed both histories')
        merged=git('-C',str(review),'rev-parse','HEAD').stdout.strip()
        self.assertEqual(git('-C',str(review),'show','-s','--format=%P','HEAD').stdout.split(),[self.local,self.other['commit']])
        self.assertEqual(self.store._ref(self.store.branch),self.local)
        self.assertEqual(self.remote._ref(self.remote.branch),self.other['commit'])
        git('-C',str(review),'push','origin','HEAD:refs/heads/main')
        return merged

    def test_divergence_is_actionable_metadata_and_reopen_keeps_both_heads(self):
        error=self.diverge()
        self.assertEqual(error.status,503);self.assertEqual(error.data['status'],'remote_diverged')
        self.assertEqual(error.data['recovery'],{'local_commit':self.local,'remote_commit':self.other['commit'],'merge_base':self.seed['commit']})
        restored=GitDocs(self.store.root)
        service=DocumentService(restored,self.api,'@human:local','!room:local')
        for action in (lambda:service.read('!room:local'),lambda:service.save(self.data)):
            with self.assertRaises(DocumentError) as caught:action()
            self.assertEqual(caught.exception.data['status'],'remote_diverged')
        self.assertEqual(service.read('!room:local',self.local)['content'],self.data['content'])
        self.assertEqual(restored._ref(restored.branch),self.local)
        self.assertEqual(self.remote._ref(self.remote.branch),self.other['commit'])
        self.assertEqual(self.events,{})

    def test_operator_merge_then_same_save_recovers_original_commit_and_one_receipt(self):
        self.diverge();merged=self.merge_as_operator()
        restored=GitDocs(self.store.root);service=DocumentService(restored,self.api,'@human:local','!room:local')
        self.assertEqual(self.remote._ref(self.remote.branch),merged)
        result=service.save(self.data)
        self.assertEqual(result['commit'],self.local)
        self.assertEqual(service.save(self.data)['commit'],self.local)
        self.assertEqual(len(self.events),1);self.assertEqual(restored.pending(),[])
        snapshot=service.read('!room:local')
        self.assertEqual(snapshot['commit'],merged)
        self.assertIn('LOCAL change',snapshot['content']);self.assertIn('REMOTE change',snapshot['content'])
        self.assertEqual(len(restored.history('demo.md')),4)
        self.assertEqual(restored._git('merge-base',self.local,merged).strip(),self.local)
        self.assertEqual(restored._git('merge-base',self.other['commit'],merged).strip(),self.other['commit'])
        self.assertNotIn(self.data['content'],str(self.events))

    def test_known_rewind_still_requires_separate_reconciliation(self):
        second=self.store.write('demo.md','next',self.seed['blob'])
        self.remote._git('update-ref',self.remote.branch,self.seed['commit'],second['commit'])
        with self.assertRaises(PublicationPending):GitDocs(self.store.root)
        self.assertEqual(self.store._ref(self.store.branch),second['commit'])
        self.assertEqual(self.remote._ref(self.remote.branch),self.seed['commit'])

    def test_overlapping_operator_merge_leaves_service_and_remote_refs_untouched(self):
        self.data['content']='# Base\n\nOne\n\nLOCAL competing change\n'
        self.diverge()
        with self.assertRaises(subprocess.CalledProcessError):self.merge_as_operator()
        self.assertEqual(self.store._ref(self.store.branch),self.local)
        self.assertEqual(self.remote._ref(self.remote.branch),self.other['commit'])
        self.assertEqual(self.store.read('demo.md',self.local),self.data['content'])
        self.assertEqual(self.events,{})
        with self.assertRaises(PublicationPending):self.store.pending()

    def test_remote_advances_during_operator_review_keeps_both_histories_blocked(self):
        self.diverge();merged=self.merge_as_operator()
        newer=self.peer.write('demo.md','# Further remote work\n',self.other['blob'])
        restored=GitDocs(self.store.root)
        with self.assertRaises(PublicationPending):restored.snapshot('demo.md')
        self.assertEqual(restored._ref(restored.branch),merged)
        self.assertEqual(self.remote._ref(self.remote.branch),newer['commit'])
        self.assertEqual(restored._git('merge-base',self.local,merged).strip(),self.local)
        self.assertEqual(restored._git('merge-base',self.other['commit'],newer['commit']).strip(),self.other['commit'])
        self.assertEqual(self.events,{})
