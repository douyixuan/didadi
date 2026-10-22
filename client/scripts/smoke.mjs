// Real SDK requests through the restricted local adapter; no model or external credentials.
import assert from 'node:assert/strict';
import {createClient,Direction} from 'matrix-js-sdk';
const base=process.argv[2]||'http://127.0.0.1:8767';
const session=await (await fetch(base+'/api/session')).json();
assert.ok(!JSON.stringify(session).includes('access_token'));
const localFetch=(url,init={})=>{const headers=new Headers(init.headers);headers.set('X-CSRF-Token',session.csrf);return fetch(url,{...init,headers});};
const sdk=createClient({baseUrl:base+'/matrix',userId:session.userId,accessToken:'local-development-session',fetchFn:localFetch});
async function api(path,body){const response=await localFetch(base+path,body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();assert.equal(response.status,200,JSON.stringify(value));return value;}
const {joined_rooms:rooms}=await sdk.getJoinedRooms();assert.ok(rooms.includes(session.initialRoom));
await sdk.roomState(session.initialRoom);
const nonce=crypto.randomUUID(),room=session.initialRoom;
const content={msgtype:'m.text',body:'SDK roundtrip '+nonce,'m.mentions':{user_ids:[session.agentId]}};
const one=await sdk.sendEvent(room,'m.room.message',content,nonce);
const two=await sdk.sendEvent(room,'m.room.message',content,nonce);
assert.equal(one.event_id,two.event_id);
async function waitTask(id){for(let i=0;i<90;i++){const result=await api('/api/task?room='+encodeURIComponent(room)+'&id='+encodeURIComponent(id));if(result.task?.status==='done')return result.task;await new Promise(r=>setTimeout(r,1000));}throw Error('Task did not complete');}
const echo=await waitTask(one.event_id);assert.equal(echo.body,'External agent received: '+content.body);
const timeline=await sdk.createMessagesRequest(room,null,50,Direction.Backward);
assert.equal(timeline.chunk.filter(event=>event.event_id===one.event_id).length,1);
console.log('PASS real matrix-js-sdk room state, send, duplicate transaction and external reply');
const original=await api('/api/document?room='+encodeURIComponent(room));
const text='# Client SDK verification\n\nWritten through the React client adapter. '+nonce+'\n';
async function saveDocument(content,base_blob,operation){
 const response=await localFetch(base+'/api/documents/demo.md',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({room,content,base_blob,operation})});
 const value=await response.json();return {status:response.status,value};
}
const operation=crypto.randomUUID();const saved=await saveDocument(text,original.blob,operation);
assert.equal(saved.status,200);assert.equal(saved.value.status,'saved');
assert.equal((await saveDocument(text,original.blob,operation)).value.commit,saved.value.commit);
const latest=await api('/api/document?room='+encodeURIComponent(room));assert.equal(latest.content,text);
const historical=await api('/api/document?room='+encodeURIComponent(room)+'&commit='+original.commit);assert.equal(historical.content,original.content);
const stale=await saveDocument('stale SDK request',original.blob,crypto.randomUUID());assert.equal(stale.status,409);assert.equal(stale.value.status,'conflict');
assert.equal((await api('/api/document?room='+encodeURIComponent(room))).commit,latest.commit);
const created=await api('/api/rooms',{name:'Client smoke '+nonce.slice(0,6),operation:nonce});
assert.equal((await api('/api/rooms',{name:'Client smoke '+nonce.slice(0,6),operation:nonce})).room_id,created.room_id);
assert.ok((await sdk.getJoinedRooms()).joined_rooms.includes(created.room_id));
console.log('PASS adapter Git save/history/conflict and idempotent real private room creation');
sdk.stopClient();
