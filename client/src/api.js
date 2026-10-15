import {createClient, Direction, MatrixEvent} from 'matrix-js-sdk';

export function errorText(error) {
  return error?.data?.error || error?.message || 'Local backend unavailable. Your draft is preserved.';
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
    if (!response.ok) throw new Error(data.error || 'Local request failed. Retry with your draft preserved.');
    return data;
  }
  return {
    session,
    async rooms() {
      const {joined_rooms: ids} = await client.getJoinedRooms();
      return Promise.all(ids.map(async id => {
        const state = await client.roomState(id);
        return {id, name:state.find(e=>e.type==='m.room.name')?.content.name || 'Untitled room',
          encrypted:state.some(e=>e.type==='m.room.encryption'),
          agentJoined:state.some(e=>e.type==='m.room.member' && e.state_key===session.agentId && e.content.membership==='join')};
      }));
    },
    async timeline(room) {
      const result = await client.createMessagesRequest(room, null, 50, Direction.Backward);
      return result.chunk.filter(event=>event.type==='m.room.message').reverse().map(raw=>{
        const event = new MatrixEvent(raw);
        return {id:event.getId(), sender:event.getSender(), content:event.getContent(), time:event.getTs()};
      });
    },
    send:(room, content, txn)=>client.sendEvent(room, 'm.room.message', content, txn),
    createRoom:(name, operation)=>api('/api/rooms', {name,operation}),
    document:(room, commit)=>api('/api/document?room='+encodeURIComponent(room)+(commit?'&commit='+encodeURIComponent(commit):'')),
    history:room=>api('/api/history?room='+encodeURIComponent(room)),
    task:(room,id)=>api('/api/task?room='+encodeURIComponent(room)+'&id='+encodeURIComponent(id)),
    cancel:(room,id)=>api('/api/task/cancel',{room,id}),
    audit:(room,id)=>api('/api/task/audit?room='+encodeURIComponent(room)+'&id='+encodeURIComponent(id)),
  };
}
