import {createClient, Direction, MatrixEvent} from 'matrix-js-sdk';

export function errorText(error) {
  return error?.data?.error || error?.message || 'Local backend unavailable. Your draft is preserved.';
}

export async function messagePage(client,room,from=null) {
    const result=await client.createMessagesRequest(room,from,50,Direction.Backward);
    return {events:result.chunk.filter(event=>event.type==='m.room.message').reverse().map(raw=>{
      const event=new MatrixEvent(raw);
      return {id:event.getId(),sender:event.getSender(),content:event.getContent(),time:event.getTs()};
    }),previousCursor:typeof result.end==='string'&&result.end!==from&&result.end!==result.start?result.end:null};
  }

export async function threadPage(client,room,root,from=null){
  const page=await client.relations(room,root,'m.thread','m.room.message',{dir:Direction.Backward,limit:50,...(from?{from}:{})});
  const map=event=>({id:event.getId(),sender:event.getSender(),content:event.getContent(),time:event.getTs()});
  if(!page.originalEvent||page.originalEvent.getId()!==root||page.originalEvent.getType()!=='m.room.message')throw new Error('The thread root is unavailable. Retry opening this thread.');
  return {root:map(page.originalEvent),events:page.events.filter(event=>event.getType()==='m.room.message'&&event.getContent()['m.relates_to']?.rel_type==='m.thread'&&event.getContent()['m.relates_to'].event_id===root).reverse().map(map),previousCursor:typeof page.nextBatch==='string'&&page.nextBatch!==from?page.nextBatch:null};
}

export async function roomMembers(client,room){
  const state=await client.roomState(room);if(!Array.isArray(state))throw new Error('Room people are unavailable. Retry the request.');
  const members=new Map();for(const event of state){const membership=event?.content?.membership,id=event?.state_key;if(event?.type==='m.room.member'&&typeof id==='string'&&id.startsWith('@')&&['join','invite'].includes(membership))members.set(id,{id,name:typeof event.content.displayname==='string'&&event.content.displayname.trim()?event.content.displayname:id,membership});}
  return [...members.values()].sort((a,b)=>a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
}

export async function connect() {
  if(import.meta.env.VITE_PREVIEW_MODE==='synthetic')return (await import('./demo-api')).createDemo();
  const sessionResponse = await fetch('/api/session');
  if (!sessionResponse.ok) throw new Error('Cannot reach the local workspace. Check that the backend is running.');
  const session = await sessionResponse.json();
  const fetchLocal = (url, options = {}) => {
    const headers = new Headers(options.headers);
    headers.set('X-CSRF-Token', session.csrf);
    return fetch(url, {...options, headers});
  };
  // This placeholder is not a credential. The loopback adapter owns the existing test session.
  const client = createClient({baseUrl: location.origin + '/matrix', userId: session.userId,
    accessToken: 'local-development-session', fetchFn: fetchLocal});
  async function api(path, body) {
    const response = await fetchLocal(path, body === undefined ? {} : {
      method: 'POST', headers: {'Content-Type':'application/json'}, body:JSON.stringify(body)});
    const data = await response.json();
    if (!response.ok){const error=new Error(data.error || 'Local request failed. Retry with your draft preserved.');error.status=response.status;error.data=data;throw error;}
    return data;
  }
  const timelinePage=(room,from=null)=>messagePage(client,room,from);
  return {
    session,
    members:room=>roomMembers(client,room),
    ...(session.directChats?{directChats:()=>api('/api/direct-chats'),retryDirect:room=>api('/api/direct-chats/retry',{room})}:{}),
    readSource:(room,repository,path)=>api('/api/repositories/read',{room,repository,path}),
    async uploadAttachment(room,file,operation,root=null){
      const query=new URLSearchParams({room,name:file.name,operation,type:file.type||'application/octet-stream'});if(root)query.set('root',root);
      const response=await fetchLocal('/api/attachments?'+query,{method:'POST',headers:{'Content-Type':file.type||'application/octet-stream'},body:file});const data=await response.json();if(!response.ok){const error=new Error(data.error||'Attachment failed. Retry with the same file.');error.status=response.status;throw error;}return data;
    },
    async downloadAttachment(room,event){
      const response=await fetchLocal('/api/attachments/download?'+new URLSearchParams({room,event}));if(!response.ok){const data=await response.json();const error=new Error(data.error||'Download unavailable.');error.status=response.status;throw error;}
      const header=response.headers.get('Content-Disposition')||'',match=header.match(/filename\*=UTF-8''([^;]+)/i);return {blob:await response.blob(),name:match?decodeURIComponent(match[1]):'attachment'};
    },
    async saveDocument(room,content,base_blob,operation,name='demo.md'){
      const response=await fetchLocal('/api/documents/'+encodeURIComponent(name),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({room,content,base_blob,operation})});
      const data=await response.json();if(!response.ok){const error=new Error(data.error||'Save failed. Keep your draft.');error.status=response.status;error.data=data;throw error;}return data;
    },
    async rooms() {
      const {joined_rooms: ids} = await client.getJoinedRooms();
      let direct=null;if(session.directChats){try{direct=await api('/api/direct-chats')}catch{/* Preference errors are shown separately; messaging remains available. */}}
      return Promise.all(ids.map(async id => {
        const state = await client.roomState(id);
        return {id, name:state.find(e=>e.type==='m.room.name')?.content.name || 'Untitled room',
          directForYou:Boolean(direct?.mapped[id]?.length),
          encrypted:state.some(e=>e.type==='m.room.encryption'),
          kind:state.find(e=>e.type==='org.didadi.room')?.content.kind||'room',joinRule:state.find(e=>e.type==='m.room.join_rules')?.content.join_rule||'unknown',
          agentJoined:state.some(e=>e.type==='m.room.member' && e.state_key===session.agentId && e.content.membership==='join')};
      }));
    },
    threadPage:(room,root,from=null)=>threadPage(client,room,root,from),
    async message(room,id){const raw=await client.fetchRoomEvent(room,id);if(raw.event_id!==id||raw.type!=='m.room.message'||(raw.room_id&&raw.room_id!==room))throw new Error('Quoted message is unavailable.');return {id:raw.event_id,sender:raw.sender,content:raw.content,time:raw.origin_server_ts};},
    timelinePage,
    timeline:async room=>(await timelinePage(room)).events,
    send:(room, content, txn)=>client.sendEvent(room, 'm.room.message', content, txn),
    createRoom:(name,operation,options={})=>api('/api/rooms',{name,operation,...options}),
    searchMessages:(room,query,next_batch=null)=>api('/api/search/messages',{room,query,next_batch}),
    searchDocuments:(room,query,after=null,commit=null)=>api('/api/search/documents',{room,query,after,commit}),
    documents:room=>api('/api/documents?room='+encodeURIComponent(room)),
    fromMessages:request=>api('/api/documents/from-messages',request),
    moveDocument:(room,request)=>api('/api/documents/move',{room,...request}),
    createDocument:(room,name,operation)=>api('/api/documents',{room,name,operation,content:''}),
    document:(room, commit,name='demo.md')=>api('/api/document?room='+encodeURIComponent(room)+(commit?'&commit='+encodeURIComponent(commit):'')+'&path='+encodeURIComponent(name)),
    history:(room,name='demo.md')=>api('/api/history?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(name)),
    task:(room,id)=>api('/api/task?room='+encodeURIComponent(room)+'&id='+encodeURIComponent(id)),
    cancel:(room,id)=>api('/api/task/cancel',{room,id}),
    audit:(room,id)=>api('/api/task/audit?room='+encodeURIComponent(room)+'&id='+encodeURIComponent(id)),
  };
}
