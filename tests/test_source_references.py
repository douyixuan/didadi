import unittest
from types import SimpleNamespace
from src.source_references import SourceReferences
from src.repository_read import RepositoryDenied

class SourceReferenceTests(unittest.TestCase):
    def setUp(self):
        self.state=[{'type':'m.room.member','state_key':'@me:local','content':{'membership':'join'}}]
        self.snapshot={'repository':'repo','path':'src/a.py','commit':'a'*40,'blob':'b'*40,'content':'one\r\n<script>literal</script>\r\nthree\r\n'}
        self.calls=[]
        def read(event,command):
            self.calls.append((event,command))
            if event!={'room_id':'!room','sender':'@me:local'} or command!={'action':'read','repository':'repo','path':'src/a.py'}:raise RepositoryDenied('denied')
            return self.snapshot
        def allowed(room):
            if room!='!room':raise RepositoryDenied('room')
        self.service=SourceReferences(SimpleNamespace(read=read),lambda *args:self.state,allowed,'@me:local')
        self.ref={'repository':'repo','path':'src/a.py','commit':'a'*40,'blob':'b'*40,'start':2,'end':3}
    def test_canonical_fixed_source_and_lines(self):
        self.assertEqual(self.service.read({'room':'!room','repository':'repo','path':'src/a.py'}),self.snapshot)
        body=self.service.reference('!room',self.ref)
        self.assertEqual(body,'Source: repo / src/a.py\nCommit: '+'a'*40+'\nLines: 2–3\n\n<script>literal</script>\nthree')
        self.assertEqual(self.calls[-1][0]['sender'],'@me:local')
    def test_grants_membership_encryption_and_parameter_boundary(self):
        for data in ({'room':'!other','repository':'repo','path':'src/a.py'}, {'room':'!room','repository':'repo','path':'../a'}, {'room':'!room','repository':'repo','path':'src/a.py','commit':'c'*40}):
            with self.assertRaises(RepositoryDenied):self.service.read(data)
        for state in ([],[{'type':'m.room.encryption','content':{}},*self.state]):
            self.state=state
            with self.assertRaises(RepositoryDenied):self.service.reference('!room',self.ref)
    def test_invalid_or_changed_reference_is_rejected(self):
        for change in ({'commit':'c'*40},{'blob':'c'*40},{'start':True},{'start':0},{'end':4},{'start':3,'end':2},{'extra':'value'}):
            with self.subTest(change=change),self.assertRaises(RepositoryDenied):self.service.reference('!room',{**self.ref,**change})
        self.snapshot['content']='x'*3600
        with self.assertRaises(RepositoryDenied):self.service.reference('!room',{**self.ref,'start':1,'end':1})
