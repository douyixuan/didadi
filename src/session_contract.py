"""Fictional-only identity contract. No Matrix transport, credentials or disk state."""
import copy
import itertools
import threading
import time

class SessionContractError(Exception):
    def __init__(self,status,message):self.status,self.message=status,message

class FakeIdentityService:
    """Deliberately non-authenticating fixtures; never a real identity provider."""
    instances=itertools.count(1)
    identities={'alice':{'user_id':'@alice:fictional.invalid','name':'Fictional Alice'},'bob':{'user_id':'@bob:fictional.invalid','name':'Fictional Bob'}}
    def __init__(self,clock=time.monotonic,ttl=1800,namespace=None):
        self.clock,self.ttl=clock,ttl;self.namespace=namespace or f'fixture-instance-{next(self.instances)}';self.lock=threading.RLock();self.sessions={};self.counter=0
        self.documents={identity:{'name':'Shared name.md','content':f'# {label["name"]}\n\nOnly {label["name"]} sees this fictional document.\n','version':1} for identity,label in self.identities.items()}
        self.receipts={}
    @staticmethod
    def exact(data,keys):
        if not isinstance(data,dict) or set(data)!=set(keys):raise SessionContractError(400,'Use only the supported fictional contract fields.')
    def login(self,data):
        self.exact(data,{'fixture_identity','fixture_device'});identity,device=data['fixture_identity'],data['fixture_device']
        if not isinstance(identity,str) or identity not in self.identities or device not in ('A','B'):raise SessionContractError(400,'Choose Fictional Alice or Bob and fixture device A or B. No passwords are accepted.')
        with self.lock:
            for sid,session in list(self.sessions.items()):
                if session['identity']==identity and session['device']==device:self.sessions.pop(sid);self.receipts.pop(sid,None)
            self.counter+=1;sid=f'fictional-session-{self.namespace}-{self.counter}';csrf=f'fictional-csrf-{self.namespace}-{self.counter}'
            self.sessions[sid]={'identity':identity,'device':device,'csrf':csrf,'expires':self.clock()+self.ttl};self.receipts[sid]={}
            return {'fictional':True,'session_id':sid,'csrf':csrf,'user_id':self.identities[identity]['user_id'],'name':self.identities[identity]['name'],'device':device}
    def authorize(self,sid,csrf=None,write=False):
        session=self.sessions.get(sid)
        if not session or session['expires']<=self.clock():
            self.sessions.pop(sid,None);self.receipts.pop(sid,None);raise SessionContractError(401,'Fictional session expired. Workspace and drafts must be cleared.')
        if write and csrf!=session['csrf']:raise SessionContractError(403,'Use this fictional session’s request marker.')
        return session
    def workspace(self,sid):
        with self.lock:
            session=self.authorize(sid);identity=session['identity'];label=self.identities[identity]
            return copy.deepcopy({'user_id':label['user_id'],'rooms':[{'id':'room-main','name':label['name']+' room'}],'document':self.documents[identity]})
    def save(self,sid,csrf,data):
        self.exact(data,{'operation','base_version','content'});operation,base,content=data['operation'],data['base_version'],data['content']
        if not isinstance(operation,str) or not 8<=len(operation)<=80 or type(base)!=int or not isinstance(content,str) or len(content)>4000:raise SessionContractError(400,'Use a bounded fictional draft, version and operation.')
        with self.lock:
            session=self.authorize(sid,csrf,write=True);receipt=self.receipts[sid].get(operation)
            if receipt:
                if receipt['input']!=data:raise SessionContractError(409,'This operation belongs to another draft. Keep the original request.')
                return copy.deepcopy(receipt['result'])
            document=self.documents[session['identity']]
            if document['version']!=base:raise SessionContractError(409,'The fictional document changed. Your draft is kept; reload before saving again.')
            document.update(content=content,version=base+1);result=copy.deepcopy(document);self.receipts[sid][operation]={'input':copy.deepcopy(data),'result':result}
            return copy.deepcopy(result)
    def logout(self,sid,csrf,data):
        self.exact(data,{'scope'})
        if data['scope']!='current_device':raise SessionContractError(400,'Only current_device logout is supported. Other devices are unchanged.')
        with self.lock:
            self.authorize(sid,csrf,write=True);self.sessions.pop(sid);self.receipts.pop(sid,None)
            return {'status':'signed_out','scope':'current_device','fictional':True}
