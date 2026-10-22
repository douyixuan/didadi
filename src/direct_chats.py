"""Current-user Matrix direct-chat preferences; never a room access grant."""
import re
import sqlite3
from src.matrix_http import MatrixError,segment

class DirectChatError(Exception):
    def __init__(self,status,message):self.status,self.message=status,message

class DirectChats:
    def __init__(self,metadata,api,user_id,allowed):
        self.metadata,self.api,self.user_id,self.allowed=str(metadata),api,user_id,allowed
        self.path='/user/'+segment(user_id)+'/account_data/m.direct'
        with sqlite3.connect(self.metadata) as db:db.execute('CREATE TABLE IF NOT EXISTS direct_preferences(actor TEXT NOT NULL, room TEXT NOT NULL, peer TEXT NOT NULL, pending INTEGER NOT NULL, PRIMARY KEY(actor,room))')

    def read(self):
        try:data=self.api('GET',self.path)
        except MatrixError as error:
            if error.status==404 and error.body.get('errcode')=='M_NOT_FOUND':return {}
            raise
        # Refuse to replace unknown data rather than silently discarding it.
        if (not isinstance(data,dict) or len(data)>10000 or any(not isinstance(user,str) or not re.fullmatch(r'@[^\s:]+:[^\s]+',user) or not isinstance(rooms,list) or len(rooms)>10000 or any(not isinstance(room,str) or not room.startswith('!') for room in rooms) for user,rooms in data.items())):
            raise DirectChatError(409,'Direct-chat preferences have an unsupported format. No account data was written.')
        return data

    def remember(self,room,peer):
        with sqlite3.connect(self.metadata) as db:
            old=db.execute('SELECT peer FROM direct_preferences WHERE actor=? AND room=?',(self.user_id,room)).fetchone()
            if old and old[0]!=peer:raise DirectChatError(409,'This direct-chat request belongs to another person.')
            db.execute('INSERT OR IGNORE INTO direct_preferences VALUES (?,?,?,1)',(self.user_id,room,peer))

    def retry(self,room):
        self.allowed(room)
        with sqlite3.connect(self.metadata,timeout=30) as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT peer,pending FROM direct_preferences WHERE actor=? AND room=?',(self.user_id,room)).fetchone()
            if not row:raise DirectChatError(404,'No local direct-chat synchronization request exists for this room.')
            peer,pending=row
            if not pending:return {'room':room,'status':'synced'}
            state=self.api('GET','/rooms/'+segment(room)+'/state')
            roster={event.get('state_key'):event.get('content',{}).get('membership') for event in state if event['type']=='m.room.member'}
            if roster.get(self.user_id)!='join' or {user for user,membership in roster.items() if membership in {'join','invite'}}!={self.user_id,peer}:
                raise DirectChatError(409,'Membership changed. Direct-chat preferences were not changed; review the room first.')
            # Matrix provides whole-event replacement, without conditional updates.
            # Preserve each observed map; re-read before every bounded retry.
            for _ in range(3):
                current=self.read()
                if room not in current.get(peer,[]):
                    merged={user:list(rooms) for user,rooms in current.items()}
                    merged.setdefault(peer,[]).append(room)
                    self.api('PUT',self.path,merged)
                verified=self.read()
                if room in verified.get(peer,[]):
                    db.execute('UPDATE direct_preferences SET pending=0 WHERE actor=? AND room=?',(self.user_id,room))
                    return {'room':room,'status':'synced'}
            raise DirectChatError(503,'Another client changed direct-chat preferences. Retry synchronization; the room already exists.')

    def after_create(self,result):
        if result['kind']!='direct':return result
        self.remember(result['room_id'],result['participants'][0])
        try:status=self.retry(result['room_id'])['status']
        except Exception:status='pending'
        return {**result,'direct_sync':status}

    def snapshot(self):
        data=self.read();joined=set(self.api('GET','/joined_rooms')['joined_rooms'])
        with sqlite3.connect(self.metadata) as db:
            permitted={row[0] for row in db.execute('SELECT id FROM rooms')}&joined
            pending=[{'room':room,'peer':peer} for room,peer in db.execute('SELECT room,peer FROM direct_preferences WHERE actor=? AND pending=1 ORDER BY room',(self.user_id,)) if room in permitted]
        mapped={}
        for peer,rooms in data.items():
            for room in rooms:
                if room in permitted and peer not in mapped.setdefault(room,[]):mapped[room].append(peer)
        return {'mapped':mapped,'pending':pending}
