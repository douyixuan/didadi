"""Read and cite fixed Git files through existing repository grants."""
import re
from src.matrix_http import segment
from src.repository_read import RepositoryDenied


class SourceReferences:
    def __init__(self, reader, api, allowed, user_id):
        self.reader,self.api,self.allowed,self.user_id=reader,api,allowed,user_id

    def read(self, request):
        if not isinstance(request,dict) or set(request)!={'room','repository','path'}:
            raise RepositoryDenied('Use one room, repository and file path.')
        room=request['room']
        if not isinstance(room,str):raise RepositoryDenied('Invalid source room.')
        self.allowed(room)
        state=self.api('GET','/rooms/'+segment(room)+'/state')
        if (self.reader is None or any(event['type']=='m.room.encryption' for event in state) or
            not any(event['type']=='m.room.member' and event.get('state_key')==self.user_id and event['content'].get('membership')=='join' for event in state)):
            raise RepositoryDenied('A joined, unencrypted granted room is required.')
        return self.reader.read({'room_id':room,'sender':self.user_id},{'action':'read','repository':request['repository'],'path':request['path']})

    def reference(self, room, reference):
        if not isinstance(reference,dict) or set(reference)!={'repository','path','commit','blob','start','end'}:
            raise RepositoryDenied('Invalid source reference.')
        snapshot=self.read({'room':room,'repository':reference['repository'],'path':reference['path']})
        if reference['commit']!=snapshot['commit'] or reference['blob']!=snapshot['blob']:
            raise RepositoryDenied('The reference does not match the granted source revision.')
        start,end=reference['start'],reference['end'];lines=re.split(r'\r\n|\n|\r',snapshot['content'])
        if lines and lines[-1]=='':lines.pop()
        if type(start)!=int or type(end)!=int or not 1<=start<=end<=len(lines) or end-start>=50:
            raise RepositoryDenied('Select one to 50 existing source lines.')
        excerpt='\n'.join(lines[start-1:end])
        body=f"Source: {snapshot['repository']} / {snapshot['path']}\nCommit: {snapshot['commit']}\nLines: {start}–{end}\n\n{excerpt}"
        if len(body)>3500:raise RepositoryDenied('Select a shorter source excerpt.')
        return body
