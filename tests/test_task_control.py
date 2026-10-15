import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from src.gateway import Gateway,TaskError
from src.gitdocs import GitDocs
from src.matrix_as import AGENT
from src.matrix_http import MatrixError
from scripts.document_worker import reconcile


class TaskControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.agent=Mock();self.agent.api.side_effect=self.api
        self.gateway=Gateway(self.root/'tasks.sqlite',self.agent)
        self.event={'type':'m.room.message','event_id':'$task','room_id':'!room','sender':'@human:local',
                    'content':{'msgtype':'m.text','body':'private fixture body','m.mentions':{'user_ids':[AGENT]}}}
    def api(self,method,path,data=None):
        if path.endswith('/state/m.room.encryption'):raise MatrixError(404,{'errcode':'M_NOT_FOUND'})
        return {'membership':'join','event_id':'$reply'}
    def accept(self):self.gateway.accept('txn',[self.event])

    def test_pending_cancel_survives_restart_and_does_not_duplicate_history(self):
        self.accept();self.gateway.accept('txn',[self.event])
        self.assertTrue(self.gateway.cancel('$task')['cancelled'])
        self.gateway.cancel('$task')
        restored=Gateway(self.root/'tasks.sqlite',self.agent)
        self.assertIsNone(restored.claim());self.assertEqual(restored.status('$task')['status'],'cancelled')
        events=restored.audit('$task');self.assertEqual([e['action'] for e in events],['accepted','cancelled'])
        self.assertNotIn('private fixture body',json.dumps(events))
        self.assertNotIn('lease',json.dumps(events))

    def test_leased_cancel_prevents_validation_and_outbound_reply(self):
        self.accept();task=self.gateway.claim();self.gateway.cancel('$task');self.agent.api.reset_mock()
        for action in [lambda:self.gateway.validate('$task',task['lease']),lambda:self.gateway.complete('$task',task['lease'],'private result')]:
            with self.assertRaises(TaskError) as caught:action()
            self.assertEqual(caught.exception.code,'task_cancelled');self.assertFalse(caught.exception.retryable)
        self.assertFalse(any(call.args[0]=='PUT' for call in self.agent.api.call_args_list))
        self.assertEqual([e['action'] for e in self.gateway.audit('$task')],['accepted','leased','cancelled'])

    def test_cancel_during_authorization_check_does_not_send(self):
        self.accept();task=self.gateway.claim()
        def cancel(room):self.gateway.cancel('$task');return True
        self.gateway.allowed=cancel;self.agent.api.reset_mock()
        with self.assertRaises(TaskError):self.gateway.complete('$task',task['lease'],'answer')
        self.assertFalse(any(call.args[0]=='PUT' for call in self.agent.api.call_args_list))
        self.assertEqual(self.gateway.status('$task')['status'],'cancelled')

    def test_completed_task_stays_completed_and_history_is_idempotent(self):
        self.accept();task=self.gateway.claim()
        self.gateway.complete('$task',task['lease'],'private result')
        self.gateway.complete('$task',task['lease'],'private result')
        self.assertEqual(self.gateway.cancel('$task'),{'status':'done','cancelled':False})
        events=self.gateway.audit('$task');self.assertEqual([e['action'] for e in events],['accepted','leased','result_ready','completed'])
        self.assertNotIn('private result',json.dumps(events))
        self.assertNotIn(task['lease'],json.dumps(events))
        self.assertTrue(all(set(event)=={'sequence','action','at','attempt','reason'} for event in events))

    def test_cancelled_operation_closes_outbox_but_retains_committed_version(self):
        self.accept();store=GitDocs(self.root/'docs.git')
        item=store.write('demo.md','retain me',operation='$task',notification={'task_id':'$task'})
        self.gateway.cancel('$task')
        with patch('scripts.document_worker.request',return_value={'task':self.gateway.status('$task')}):
            reconcile('unused','token',store)
        self.assertEqual(store.pending(),[]);self.assertEqual(store.snapshot('demo.md')['commit'],item['commit'])
        self.assertEqual(store.read('demo.md'),'retain me')
