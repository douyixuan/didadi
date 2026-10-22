"""Private room creation using existing local identities and explicit invitations."""
import hashlib
import json
import re
import sqlite3
from src.matrix_as import AGENT
from src.matrix_http import MatrixError,segment

ROOM_KIND='org.didadi.room'
class RoomError(Exception):
    def __init__(self,status,message):self.status,self.message=status,message

class RoomService:
    def __init__(self,metadata,api,user_id,contacts=()):
        self.metadata,self.api,self.user_id=str(metadata),api,user_id
        server=user_id.split(':',1)[1]
        if len(contacts)>32 or any(not isinstance(user,str) or not re.fullmatch(r'@[^\s:]+:'+re.escape(server),user) or user in {user_id,AGENT} for user in contacts):
            raise ValueError('fixture contacts must be other explicitly configured local identities')
        self.contacts=tuple(sorted(set(contacts)))
        with sqlite3.connect(self.metadata) as db:db.execute('CREATE TABLE IF NOT EXISTS room_intents(operation TEXT PRIMARY KEY, request_hash TEXT NOT NULL, room_id TEXT)')

    def create(self,data):
        if not isinstance(data,dict) or set(data)-{'operation','name','kind','participants','invite_agent'} or not {'operation','name'}<=set(data):
            raise RoomError(400,'Use name, operation and the supported private room options.')
        operation,name=data['operation'],data['name'];kind=data.get('kind','group');peers=data.get('participants',[]);invite_agent=data.get('invite_agent',False)
        if (not isinstance(operation,str) or not re.fullmatch(r'[a-zA-Z0-9-]{8,80}',operation) or not isinstance(name,str) or not 1<=len(name.strip())<=60 or not isinstance(kind,str) or kind not in {'direct','group','channel'} or type(invite_agent)!=bool or not isinstance(peers,list) or len(peers)>32 or any(not isinstance(peer,str) for peer in peers) or len(set(peers))!=len(peers)):
            raise RoomError(400,'Choose a private room type, a name of 1–60 characters and valid participants.')
        if not set(peers)<=set(self.contacts):raise RoomError(403,'Only explicitly configured local fixture contacts can be invited here.')
        if kind=='direct' and (len(peers)!=1 or invite_agent):raise RoomError(400,'A private conversation needs exactly one person and no Agent.')
        name=name.strip();peers=sorted(peers)
        spec={'actor':self.user_id,'name':name,'kind':kind,'participants':peers,'invite_agent':invite_agent,'visibility':'private'}
        digest=hashlib.sha256(json.dumps(spec,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        alias='didadi-client-'+hashlib.sha256((self.user_id+'\0'+operation).encode()).hexdigest()[:32]
        marker={'version':1,'kind':kind,'visibility':'private','request_hash':digest}
        # Persist the binding before outbound I/O. A later process can only resume the same intent.
        with sqlite3.connect(self.metadata,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT request_hash FROM room_intents WHERE operation=?',(operation,)).fetchone()
            if not old and db.execute('SELECT id FROM rooms WHERE operation=?',(operation,)).fetchone():raise RoomError(409,'This operation belongs to an earlier room. Use a new request for new room options.')
            if old and old[0]!=digest:raise RoomError(409,'This operation already belongs to different room options. Retry the original request.')
            db.execute('INSERT OR IGNORE INTO room_intents(operation,request_hash) VALUES (?,?)',(operation,digest))
        # Serialize local concurrent callers while Matrix owns the room alias uniqueness.
        with sqlite3.connect(self.metadata,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE');old=db.execute('SELECT room_id FROM room_intents WHERE operation=?',(operation,)).fetchone();room=old[0]
            if not room:
                try:
                    room=self.api('POST','/createRoom',{'preset':'private_chat','visibility':'private','name':name,'room_alias_name':alias,'is_direct':kind=='direct','invite':peers+([AGENT] if invite_agent else []),'creation_content':{'m.federate':False},'initial_state':[{'type':ROOM_KIND,'state_key':'','content':marker},{'type':'m.room.guest_access','state_key':'','content':{'guest_access':'forbidden'}},{'type':'m.room.history_visibility','state_key':'','content':{'history_visibility':'invited'}}]})['room_id']
                except MatrixError as error:
                    # Keep the existing safe HTTP 429 response and wait hint. The UI
                    # retains this intent, including a potentially partial creation.
                    if error.status==429:raise
                    if error.body.get('errcode')!='M_ROOM_IN_USE':raise RoomError(503,'Room creation is unconfirmed. Retry the same options and operation.') from None
                    server=self.user_id.split(':',1)[1]
                    try:room=self.api('GET','/directory/room/'+segment('#'+alias+':'+server))['room_id']
                    except MatrixError:raise RoomError(503,'The existing room could not be verified. Retry the original request.') from None
                if not isinstance(room,str) or not room.startswith('!'):raise RoomError(503,'Room creation is unconfirmed. Retry the original request.')
            # A recovered alias cannot widen the local room set without proving the original intent.
            try:
                state=self.api('GET','/rooms/'+segment(room)+'/state')
                directory=self.api('GET','/directory/list/room/'+segment(room))
            except MatrixError:raise RoomError(503,'The existing room could not be verified. Retry the original request.') from None
            create=next((event for event in state if event['type']=='m.room.create'),{})
            creator=create.get('content',{}).get('creator') or create.get('sender')
            content=lambda kind:next((event.get('content',{}) for event in state if event['type']==kind and event.get('state_key','')==''),{})
            joined=any(event['type']=='m.room.member' and event.get('state_key')==self.user_id and event.get('content',{}).get('membership')=='join' for event in state)
            roster={event.get('state_key'):event.get('content',{}).get('membership') for event in state if event['type']=='m.room.member'}
            expected=peers+([AGENT] if invite_agent else [])
            active={user for user,membership in roster.items() if membership in {'join','invite'}}
            if (any(roster.get(user) not in {'join','invite'} for user in expected) or (not invite_agent and AGENT in active) or
                active!={self.user_id,*expected} or any(event['type']=='m.room.encryption' for event in state) or
                creator!=self.user_id or content(ROOM_KIND)!=marker or not joined or directory.get('visibility')!='private' or
                content('m.room.join_rules').get('join_rule')!='invite' or create.get('content',{}).get('m.federate') is not False or
                content('m.room.guest_access').get('guest_access')!='forbidden' or content('m.room.history_visibility').get('history_visibility')!='invited'):
                raise RoomError(409,'The room no longer matches this private creation request. No room was added.')
            db.execute('UPDATE room_intents SET room_id=? WHERE operation=?',(room,operation))
            db.execute('INSERT OR IGNORE INTO rooms(id,operation) VALUES (?,?)',(room,operation))
            return {'room_id':room,'name':name,'kind':kind,'visibility':'private','invite_agent':invite_agent,'participants':peers}
