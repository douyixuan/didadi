"""Room-authorized file messages with local intent recovery and authenticated media IO."""
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import unicodedata
import uuid
from urllib.error import HTTPError
from urllib.parse import quote,urlsplit
from urllib.request import Request,HTTPRedirectHandler,build_opener
from src.document_access import document_level,DocumentAccessError
from src.document_service import DocumentError
from src.matrix_http import MatrixError,segment

MAX_ATTACHMENT_BYTES=5*1024*1024

class NoMediaRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):return None


def media_request(base,method,path,token,content=None,kind='application/octet-stream'):
    request=Request(base+path,method=method,data=content,headers={'Authorization':'Bearer '+token,'Content-Type':kind})
    try:
        with build_opener(NoMediaRedirects).open(request,timeout=20) as response:
            limit=65536 if method=='POST' else MAX_ATTACHMENT_BYTES
            length=response.headers.get('Content-Length')
            if length is not None and int(length)>limit:raise DocumentError(413,'Attachment exceeds the supported size.')
            payload=response.read(limit+1)
            if len(payload)>limit:raise DocumentError(413,'Attachment exceeds the supported size.')
            return json.loads(payload) if method=='POST' else payload
    except HTTPError as error:
        raise MatrixError(error.code if error.code>=400 else 503,{'errcode':'M_MEDIA_ERROR'}) from None


class AttachmentService:
    def __init__(self,metadata,api,allowed,matrix_url,user_id,token,media=media_request):
        self.metadata=str(Path(str(metadata)+'.attachments.sqlite'));self.api=api;self.allowed=allowed
        self.matrix_url,self.user_id,self.token,self.media=matrix_url,user_id,token,media
        with sqlite3.connect(self.metadata) as db:
            db.execute('CREATE TABLE IF NOT EXISTS attachments (operation TEXT PRIMARY KEY, request_hash TEXT NOT NULL, media_uri TEXT, event_id TEXT)')

    def name(self,value):
        try:valid=isinstance(value,str) and 0<len(value.encode('utf-8'))<=240
        except UnicodeError:valid=False
        if not valid or any(character in '/\\' or unicodedata.category(character).startswith('C') for character in value):
            raise DocumentError(400,'Use a file name without paths or control characters.')
        return value

    def authorize(self,room,send=False):
        if not isinstance(room,str) or not 0<len(room)<=512:raise DocumentError(400,'Invalid attachment room.')
        self.allowed(room)
        state=self.api('GET','/rooms/'+segment(room)+'/state')
        try:level=document_level(lambda *args:state,room,self.user_id)
        except DocumentAccessError as error:raise DocumentError(error.status,'Attachment access could not be verified. Use a joined, unencrypted room.') from None
        if send:
            power=next((event.get('content',{}) for event in state if event.get('type')=='m.room.power_levels'),{})
            events=power.get('events',{})
            required=events.get('m.room.message',power.get('events_default',0)) if isinstance(events,dict) else None
            if type(required) is not int or level<required:raise DocumentError(403,'This room does not permit sending attachments.')

    def local_media(self,uri):
        if not isinstance(uri,str):raise DocumentError(400,'Attachment media is unavailable.')
        value=urlsplit(uri)
        if (value.scheme!='mxc' or value.netloc!=self.user_id.split(':',1)[1] or value.query or value.fragment or
                not re.fullmatch('/[A-Za-z0-9_-]{1,255}',value.path)):
            raise DocumentError(403,'Only media on this local homeserver is supported.')
        return value.netloc,value.path[1:]

    def upload(self,room,name,operation,kind,content,root=None):
        name=self.name(name)
        try:valid=isinstance(operation,str) and str(uuid.UUID(operation))==operation
        except ValueError:valid=False
        if not valid or not isinstance(kind,str) or not re.fullmatch(r'[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+',kind):
            raise DocumentError(400,'Use a UUID operation and a valid file media type.')
        if not isinstance(content,bytes) or len(content)>MAX_ATTACHMENT_BYTES:raise DocumentError(413,'Attachments must be at most 5 MiB.')
        if root is not None and (not isinstance(root,str) or not root.startswith('$') or not 0<len(root)<=512):raise DocumentError(400,'Invalid attachment thread.')
        self.authorize(room,True)
        if root is not None:
            event=self.api('GET','/rooms/'+segment(room)+'/event/'+segment(root))
            if event.get('event_id')!=root or event.get('room_id',room)!=room:raise DocumentError(403,'Thread root is unavailable in this room.')
        key=hashlib.sha256((self.user_id+'\0'+operation).encode()).hexdigest()
        digest=hashlib.sha256(json.dumps([room,name,kind,root,hashlib.sha256(content).hexdigest()],ensure_ascii=True).encode()).hexdigest()
        with sqlite3.connect(self.metadata,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT request_hash,media_uri,event_id FROM attachments WHERE operation=?',(key,)).fetchone()
            if row and row[0]!=digest:raise DocumentError(409,'This attachment operation was already used for another file.')
            if not row:db.execute('INSERT INTO attachments(operation,request_hash) VALUES (?,?)',(key,digest))
            uri=row[1] if row else None;event_id=row[2] if row else None
            if not uri:
                result=self.media(self.matrix_url,'POST','/_matrix/media/v3/upload?filename='+quote(name,safe=''),self.token,content,kind)
                uri=result.get('content_uri');self.local_media(uri)
                db.execute('UPDATE attachments SET media_uri=? WHERE operation=?',(uri,key))
        if event_id:return {'status':'sent','event_id':event_id}
        self.authorize(room,True)
        body={'msgtype':'m.file','body':name,'filename':name,'url':uri,'info':{'size':len(content),'mimetype':kind}}
        if root is not None:body['m.relates_to']={'rel_type':'m.thread','event_id':root}
        sent=self.api('PUT','/rooms/'+segment(room)+'/send/m.room.message/attachment-'+key,body)
        with sqlite3.connect(self.metadata,timeout=30) as db:db.execute('UPDATE attachments SET event_id=? WHERE operation=?',(sent['event_id'],key))
        return {'status':'sent','event_id':sent['event_id']}

    def download(self,room,event_id):
        self.authorize(room)
        if not isinstance(event_id,str) or not event_id.startswith('$') or not 0<len(event_id)<=512:raise DocumentError(400,'Invalid attachment event.')
        event=self.api('GET','/rooms/'+segment(room)+'/event/'+segment(event_id));content=event.get('content',{})
        if (event.get('event_id')!=event_id or event.get('room_id',room)!=room or event.get('type')!='m.room.message' or
                not isinstance(content,dict) or content.get('msgtype')!='m.file'):
            raise DocumentError(400,'The selected message has no supported file attachment.')
        name=self.name(content.get('filename',content.get('body')));server,media_id=self.local_media(content.get('url'))
        payload=self.media(self.matrix_url,'GET','/_matrix/client/v1/media/download/'+segment(server)+'/'+segment(media_id),self.token)
        if not isinstance(payload,bytes) or len(payload)>MAX_ATTACHMENT_BYTES:raise DocumentError(413,'Attachment exceeds the supported size.')
        return name,payload
