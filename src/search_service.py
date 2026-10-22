"""Read-only body search within the current development grants."""
import re
from src.document_service import DocumentError


class SearchService:
    def __init__(self, documents, api, allowed):
        self.documents, self.api, self.allowed = documents, api, allowed

    def query(self, value):
        try:
            valid=isinstance(value,str) and 0<len(value.strip()) and len(value.encode('utf-8'))<=512
        except UnicodeError:
            valid=False
        if not valid:raise DocumentError(400,'Enter a search term of at most 512 UTF-8 bytes.')
        return value

    def messages(self, data):
        if not isinstance(data,dict) or set(data)!={'room','query','next_batch'}:
            raise DocumentError(400,'Expected room, query and next_batch.')
        term=self.query(data['query']);room=data['room']
        if not isinstance(room,str) or not 0<len(room)<=512:raise DocumentError(400,'Invalid room reference.')
        self.allowed(room)
        token=data['next_batch']
        if token is not None and (not isinstance(token,str) or not 0<len(token)<=4096):
            raise DocumentError(400,'Invalid search page token.')
        body={'search_categories':{'room_events':{'search_term':term,'keys':['content.body'],
              'filter':{'rooms':[room],'limit':20},'order_by':'recent','include_state':False}}}
        response=self.api('POST','/search',body,query={'next_batch':token} if token else None)
        page=response['search_categories']['room_events'];events=[]
        for item in page.get('results',[]):
            event=item.get('result',{})
            if event.get('room_id')!=room or event.get('type')!='m.room.message' or not isinstance(event.get('content',{}).get('body'),str):continue
            events.append({'id':event['event_id'],'room':room,'sender':event['sender'],'content':event['content'],'time':event.get('origin_server_ts')})
        next_batch=page.get('next_batch')
        return {'events':events,'next_batch':next_batch if isinstance(next_batch,str) and next_batch!=token else None}

    def files(self, data):
        if not isinstance(data,dict) or set(data)!={'room','query','commit','after'}:
            raise DocumentError(400,'Expected room, query, commit and after.')
        term=self.query(data['query']);self.documents.authorize(data['room'])
        after=data['after'];store=self.documents.store
        if after is not None:store._name(after)
        listed=store.documents(data['commit']);names=sorted(item['name'] for item in listed['documents'] if after is None or item['name']>after)
        results=[];scanned=0;skipped=0;last=None
        pattern=re.compile(re.escape(term),re.IGNORECASE)
        for name in names:
            if scanned>=50 or len(results)>=20:break
            scanned+=1;last=name
            try:snapshot=store.snapshot(name,listed['commit'],max_bytes=65536)
            except (UnicodeError,ValueError):skipped+=1;continue
            content=snapshot['content'] or '';match=pattern.search(content)
            if not match:continue
            start=content.rfind('\n',0,match.start())+1;end=content.find('\n',match.end());end=len(content) if end<0 else end
            excerpt=content[max(start,match.start()-80):min(end,match.end()+140)]
            results.append({'name':name,'commit':listed['commit'],'blob':snapshot['blob'],
                            'line':content.count('\n',0,match.start())+1,'excerpt':excerpt})
        return {'results':results,'commit':listed['commit'],'next_path':last if scanned<len(names) else None,
                'scanned':scanned,'skipped_documents':skipped}
