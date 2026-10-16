"""Metadata protocol, legacy migration and fixed-result recovery."""
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock

from src.gateway import Gateway
from src.matrix_as import AGENT
from src.matrix_http import MatrixError
from src.task_result import encode_outcome, outcome
from src.agent_document_api import render_outcome
from src.gitdocs import GitDocs


class TaskResultTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'gateway.sqlite'
        self.agent = Mock()
        self.agent.api.side_effect = self.api
        self.gateway = Gateway(self.path, self.agent)
        self.event = {'type':'m.room.message','event_id':'$structured','room_id':'!r:local',
                      'sender':'@alice:local','content':{'msgtype':'m.text','body':'save',
                      'm.mentions':{'user_ids':[AGENT]}}}

    def api(self, method, path, data=None):
        if path.endswith('/state/m.room.encryption'):
            raise MatrixError(404, {'errcode':'M_NOT_FOUND'})
        return {'membership':'join','event_id':'$reply'}

    def test_invalid_metadata_rejected_without_fixing_result(self):
        self.gateway.accept('one',[self.event]);task=self.gateway.claim()
        invalid=[{'version':True,'status':'read'},{'version':2,'status':'read'},
                 {'version':1,'status':[]},{'version':1,'status':'saved'},
                 {'version':1,'status':'read','content':'no body allowed'},
                 {'version':1,'status':'rejected','reason':[]},
                 {'version':1,'status':'saved','path':'../x','commit':'a'*40,'blob':'b'*40}]
        for value in invalid:
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.gateway.complete(task['id'],task['lease'],'display',value)
        with self.gateway.db() as db:
            self.assertIsNone(db.execute('SELECT result FROM tasks').fetchone()[0])
        self.assertFalse(any(c.args[0]=='PUT' for c in self.agent.api.call_args_list))

    def test_fixed_pair_survives_failed_delivery_restart_and_replacement_lease(self):
        self.gateway.accept('one',[self.event]);task=self.gateway.claim()
        typed=outcome('saved',path='demo.md',commit='a'*40,blob='b'*40)
        def offline(method,path,data=None):
            if method=='PUT':raise OSError('offline')
            return self.api(method,path,data)
        self.agent.api.side_effect=offline
        with self.assertRaises(OSError):self.gateway.complete(task['id'],task['lease'],'任意显示文本',typed)
        with self.gateway.db() as db:db.execute('UPDATE tasks SET until=0')
        self.agent.api.side_effect=self.api
        restored=Gateway(self.path,self.agent);retry=restored.claim()
        self.assertEqual(retry['outcome'],typed);self.assertEqual(retry['result'],'任意显示文本')
        for changed in (None,outcome('read')):
            with self.assertRaisesRegex(ValueError,'already fixed'):
                restored.complete(retry['id'],retry['lease'],retry['result'],changed)
        restored.complete(retry['id'],retry['lease'],retry['result'],retry['outcome'])
        self.assertEqual(restored.status(task['id'])['outcome'],typed)
        receipt=[c.args[2] for c in self.agent.api.call_args_list if c.args[0]=='PUT'][-1]
        self.assertEqual(receipt['org.didadi.task.result'],typed)
        sends=len([c for c in self.agent.api.call_args_list if c.args[0]=='PUT'])
        restored.complete(retry['id'],retry['lease'],retry['result'],typed)
        with self.assertRaises(ValueError):restored.complete(retry['id'],retry['lease'],retry['result'],None)
        self.assertEqual(len([c for c in self.agent.api.call_args_list if c.args[0]=='PUT']),sends)

    def test_legacy_null_is_fixed_and_old_database_is_not_inferred_from_text(self):
        self.gateway.accept('one',[self.event]);task=self.gateway.claim()
        self.gateway.complete(task['id'],task['lease'],'Saved demo.md\nGit commit: '+'a'*40)
        self.assertIsNone(Gateway(self.path,self.agent).status(task['id'])['outcome'])
        with self.assertRaises(ValueError):self.gateway.complete(task['id'],task['lease'],'Saved demo.md\nGit commit: '+'a'*40,outcome('read'))
        old=Path(self.tmp.name)/'old.sqlite'
        with sqlite3.connect(old) as db:
            db.execute('CREATE TABLE tasks(id TEXT PRIMARY KEY,event TEXT,status TEXT,lease TEXT,until REAL,result TEXT,reply TEXT)')
            db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?)',('$old','{}','done','x',0,'Saved old text','$reply'))
        self.assertIsNone(Gateway(old,self.agent).status('$old')['outcome'])

    def test_worker_returns_structured_saved_read_conflict_and_rejected(self):
        store=GitDocs(Path(self.tmp.name)/'docs.git')
        task={'id':'$write','event':copy.deepcopy(self.event)}
        command={'action':'write','content':'# hello','base_blob':None}
        task['event']['content']['org.didadi.document']=command
        _,item,saved=render_outcome(task,store)
        self.assertEqual(saved,outcome('saved',path='demo.md',commit=item['commit'],blob=item['blob']))
        task['id']='$stale';command['content']='stale'
        self.assertEqual(render_outcome(task,store)[2]['status'],'conflict')
        command['action']='read'
        self.assertEqual(render_outcome(task,store)[2]['status'],'read')
        command['action']='bad'
        self.assertEqual(render_outcome(task,store)[2]['status'],'rejected')
