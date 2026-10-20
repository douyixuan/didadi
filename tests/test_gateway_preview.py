"""Legacy HTML uses direct Git saves; its worker is disabled in these HTTP tests."""
from html import escape, unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

from scripts import gateway_preview
from src.gitdocs import GitDocs


class GatewayPreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'documents.git'
        self.level = 100; self.sent = []
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), BaseHTTPRequestHandler)
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)
        def capture(address, handler):
            self.server.RequestHandlerClass = handler
            return SimpleNamespace(serve_forever=lambda: None)
        self.request_patch = patch.object(gateway_preview, 'request', side_effect=self.matrix)
        self.request_patch.start(); self.addCleanup(self.request_patch.stop)
        with patch.object(gateway_preview, 'ThreadingHTTPServer', side_effect=capture), \
                patch.object(gateway_preview.threading, 'Thread', return_value=Mock()):
            gateway_preview.serve({'room':'!room:local', 'tokens':['synthetic-token']}, 'worker-token',
                                  port=self.server.server_port, document_repo=self.repo)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True); self.thread.start()
        self.addCleanup(self.close)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=3)

    def matrix(self, base, method, path, token, data=None, query=None):
        if path.endswith('/account/whoami'): return {'user_id':'@alice:local'}
        if path.endswith('/messages'): return {'chunk':[]}
        if path.endswith('/state'): return [
            {'type':'m.room.member','state_key':'@alice:local','content':{'membership':'join'}},
            {'type':'m.room.power_levels','content':{'users':{'@alice:local':self.level}}}]
        if method == 'PUT' and '/send/' in path:
            self.sent.append(data); return {'event_id':'$receipt'}
        raise AssertionError((method, path))

    def form(self, content):
        with urlopen(self.base, timeout=5) as response: page = response.read().decode()
        fields = {name:unescape(value) for name,value in re.findall(r'name="(csrf|operation|base|revision)" value="([^"]*)"', page)}
        return {**fields, 'action':'doc-save', 'doc-content':content}

    def post(self, data):
        request = Request(self.base, data=urlencode(data).encode(), method='POST')
        with urlopen(request, timeout=10) as response: return response.read().decode()

    def test_direct_save_large_utf8_and_same_form_retry_without_worker_or_body_message(self):
        content = '# Synthetic\n\n中文' * 1500
        form = self.form(content)
        self.post(form); self.post(form)
        store = GitDocs(self.repo)
        self.assertEqual(store.read('demo.md'), content)
        self.assertEqual(len(store.history('demo.md')), 1)
        self.assertEqual(store._git('show','-s','--format=%an','main').strip(), '@alice:local')
        self.assertEqual(store.pending(), [])
        self.assertTrue(self.sent)
        self.assertTrue(all('org.didadi.document.commit' in sent for sent in self.sent))
        self.assertNotIn('中文', json.dumps(self.sent, ensure_ascii=False))
        self.assertTrue(all('org.didadi.document' not in sent for sent in self.sent))

    def test_conflict_and_denied_save_keep_exact_escaped_draft_without_matrix_write(self):
        initial = self.form('first'); self.post(initial)
        content = '\n\n</textarea><script>untrusted</script>\r\n保留原文'
        stale = {**initial, 'operation':str(uuid.uuid4()), 'doc-content':content}
        sent = len(self.sent)
        with self.assertRaises(HTTPError) as caught: self.post(stale)
        self.assertEqual(caught.exception.code, 409)
        page = caught.exception.read().decode()
        self.assertIn(escape(content), page); self.assertNotIn('<script>', page)
        self.assertIn(stale['operation'], page)
        self.assertEqual(len(self.sent), sent)
        self.level = 0
        with self.assertRaises(HTTPError) as denied: self.post(stale)
        self.assertEqual(denied.exception.code, 403)
        self.assertIn(escape(content), denied.exception.read().decode())
        self.assertEqual(GitDocs(self.repo).read('demo.md'), 'first')

    def test_csrf_failure_never_writes_and_oversize_draft_is_retained(self):
        form = self.form('not saved')
        with self.assertRaises(HTTPError) as caught: self.post({**form, 'csrf':'wrong'})
        self.assertEqual(caught.exception.code, 403)
        self.assertEqual(GitDocs(self.repo).history('demo.md'), [])
        self.assertEqual(self.sent, [])
        content = 'x' * 65537
        with self.assertRaises(HTTPError) as oversize: self.post({**form, 'doc-content':content})
        self.assertEqual(oversize.exception.code, 400)
        self.assertIn(content, oversize.exception.read().decode())
        self.assertEqual(GitDocs(self.repo).history('demo.md'), [])
        self.assertEqual(self.sent, [])
