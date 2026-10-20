// Synthetic real Matrix history via the same SDK page adapter as the UI.
import assert from 'node:assert/strict';
import {createClient} from 'matrix-js-sdk';
import {messagePage} from '../src/api.js';
import {mergeMessages} from '../src/messageHistory.js';
const base=process.argv[2]||'http://127.0.0.1:8767';
const session=await(await fetch(base+'/api/session')).json();
const localFetch=(url,init={})=>{const headers=new Headers(init.headers);headers.set('X-CSRF-Token',session.csrf);return fetch(url,{...init,headers});};
const sdk=createClient({baseUrl:base+'/matrix',userId:session.userId,accessToken:'local-development-session',fetchFn:localFetch});
const nonce=crypto.randomUUID();
const response=await localFetch(base+'/api/rooms',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:'History acceptance '+nonce.slice(0,6),operation:nonce})});assert.equal(response.status,200);const room=(await response.json()).room_id;
for(let i=0;i<65;i++)await sdk.sendEvent(room,'m.room.message',{msgtype:'m.text',body:'history-'+nonce+'-'+i},nonce+'-'+i);
const first=await messagePage(sdk,room);assert.equal(first.events.length,50);assert.ok(first.previousCursor);assert.ok(first.events.at(-1).content.body.endsWith('-64'));assert.ok(!first.events.some(e=>e.content.body==='history-'+nonce+'-0'));
await sdk.sendEvent(room,'m.room.message',{msgtype:'m.text',body:'history-'+nonce+'-65'},nonce+'-65');
const second=await messagePage(sdk,room,first.previousCursor);const replay=await messagePage(sdk,room,first.previousCursor);assert.deepEqual(second.events.map(e=>e.id),replay.events.map(e=>e.id));
let events=mergeMessages(second.events,first.events),cursor=second.previousCursor,pages=2;
while(cursor&&pages<10){const page=await messagePage(sdk,room,cursor);events=mergeMessages(page.events,events);cursor=page.previousCursor;pages++;}
assert.equal(cursor,null);const relevant=events.filter(e=>e.content.body?.startsWith('history-'+nonce+'-'));assert.equal(relevant.length,65);assert.deepEqual(relevant.map(e=>e.content.body),Array.from({length:65},(_,i)=>'history-'+nonce+'-'+i));
const latest=await messagePage(sdk,room);const combined=mergeMessages(events,latest.events);assert.equal(combined.filter(e=>e.content.body?.startsWith('history-'+nonce+'-')).length,66);
console.log('PASS real Matrix pagination: >50 messages, stable cursor retry, chronological complete older history, dedup and new message preserved');sdk.stopClient();
