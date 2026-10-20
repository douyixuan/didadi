from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
import uuid
from src.attachment_service import AttachmentService,MAX_ATTACHMENT_BYTES
from src.document_service import DocumentError

class AttachmentServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.uploads=[];self.sends={};self.joined=True;self.level=0;self.required=0;self.encrypted=False;self.fail_send=False;self.events={}
        self.service=AttachmentService(Path(self.tmp.name)/'state.sqlite',self.api,self.allowed,'http://127.0.0.1:8008','@human:local','private-test-token',self.media)

    def allowed(self,room):
        if room!='!room:local':raise DocumentError(403,'Room not allowed')

    def api(self,method,path,data=None):
        if path.endswith('/state'):return ([{'type':'m.room.encryption','content':{}}] if self.encrypted else [])+[
            {'type':'m.room.member','state_key':'@human:local','content':{'membership':'join' if self.joined else 'leave'}},
            {'type':'m.room.power_levels','content':{'users':{'@human:local':self.level},'events':{'m.room.message':self.required}}}]
        if '/event/' in path:
            from urllib.parse import unquote
            return self.events[unquote(path.rsplit('/',1)[1])]
        if self.fail_send:self.fail_send=False;raise OSError('Matrix response unavailable')
        if path not in self.sends:self.sends[path]={'event_id':'$file'+str(len(self.sends)),'content':data}
        sent=self.sends[path];self.events[sent['event_id']]={'event_id':sent['event_id'],'room_id':'!room:local','type':'m.room.message','sender':'@human:local','content':data}
        return {'event_id':sent['event_id']}

    def media(self,base,method,path,token,content=None,kind=None):
        if method=='POST':self.uploads.append((content,kind));return {'content_uri':'mxc://local/media123'}
        return self.uploads[0][0]

    def upload(self,operation=None,**changes):
        data={'room':'!room:local','name':'原文.html','operation':operation or str(uuid.uuid4()),'kind':'text/html','content':b'<script>literal</script>\r\n'};data.update(changes);return self.service.upload(**data)

    def test_retry_recovers_uploaded_media_and_only_one_file_message(self):
        operation=str(uuid.uuid4());self.fail_send=True
        with self.assertRaises(OSError):self.upload(operation)
        result=self.upload(operation);self.assertEqual(self.upload(operation),result)
        self.assertEqual(len(self.uploads),1);self.assertEqual(len(self.sends),1)
        name,content=self.service.download('!room:local',result['event_id']);self.assertEqual(name,'原文.html');self.assertEqual(content,b'<script>literal</script>\r\n')
        self.assertNotIn('private-test-token',str(result));self.assertEqual(next(iter(self.sends.values()))['content']['msgtype'],'m.file')

    def test_concurrent_same_operation_does_not_reupload_or_duplicate(self):
        operation=str(uuid.uuid4())
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.upload(operation),range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(len(self.uploads),1);self.assertEqual(len(self.sends),1)
        with self.assertRaises(DocumentError) as conflict:self.upload(operation,content=b'different')
        self.assertEqual(conflict.exception.status,409)

    def test_room_membership_power_encryption_and_size_fail_before_upload(self):
        for changes in [{'room':'!other'},{'name':'../secret.txt'},{'content':b'x'*(MAX_ATTACHMENT_BYTES+1)},{'kind':'text/plain\r\nX: injected'}]:
            with self.subTest(changes=list(changes)),self.assertRaises(DocumentError):self.upload(**changes)
        self.joined=False
        with self.assertRaises(DocumentError):self.upload()
        self.joined=True;self.required=10
        with self.assertRaises(DocumentError):self.upload()
        self.required=0;self.encrypted=True
        with self.assertRaises(DocumentError):self.upload()
        self.assertEqual(self.uploads,[]);self.assertEqual(self.sends,{})

    def test_download_requires_a_visible_file_event_and_local_media(self):
        self.events['$forged']={'event_id':'$forged','type':'m.room.message','content':{'msgtype':'m.file','body':'file.txt','url':'mxc://external.example/media123'}}
        with self.assertRaises(DocumentError):self.service.download('!room:local','$forged')
        with self.assertRaises(DocumentError):self.service.download('!other','$forged')
        self.events['$forged']['content']['url']='mxc://local/media123';self.events['$forged']['room_id']='!other'
        with self.assertRaises(DocumentError):self.service.download('!room:local','$forged')
        self.assertEqual(self.uploads,[])

    def test_upload_rechecks_authority_before_sending_and_can_retry_after_restore(self):
        original=self.media
        def revoke(*args,**kwargs):result=original(*args,**kwargs);self.required=10;return result
        self.service.media=revoke;operation=str(uuid.uuid4())
        with self.assertRaises(DocumentError):self.upload(operation)
        self.assertEqual(len(self.uploads),1);self.assertEqual(self.sends,{})
        self.required=0;self.service.media=self.media;self.upload(operation);self.assertEqual(len(self.uploads),1);self.assertEqual(len(self.sends),1)
