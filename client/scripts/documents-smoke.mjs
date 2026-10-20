import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
const base=process.argv[2]||'http://127.0.0.1:8834';
const session=await(await fetch(base+'/api/session')).json(),room=session.initialRoom;
async function request(path,method='GET',body){const r=await fetch(base+path,{method,headers:{'X-CSRF-Token':session.csrf,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()}}
const nonce=randomUUID(),a='Smoke/'+nonce+'/A.md',b='Smoke/'+nonce+'/B.md',operation=randomUUID();
const made=await request('/api/documents','POST',{room,name:a,content:'# A original',operation});assert.equal(made.status,200);assert.equal(made.data.path,a);
assert.deepEqual((await request('/api/documents','POST',{room,name:a,content:'# A original',operation})).data,made.data);
const other=await request('/api/documents','POST',{room,name:b,content:'# B unchanged',operation:randomUUID()});assert.equal(other.status,200);
const read=name=>request('/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(name));
assert.equal((await read(a)).data.content,'# A original');
const saved=await request('/api/documents/'+encodeURIComponent(a),'PUT',{room,content:'# A revised',base_blob:made.data.blob,operation:randomUUID()});assert.equal(saved.status,200);assert.equal(saved.data.path,a);
assert.equal((await read(b)).data.content,'# B unchanged');assert.equal((await read(a)).data.content,'# A revised');
assert.equal((await request('/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(a)+'&commit='+made.data.commit)).data.content,'# A original');
assert.equal((await request('/api/documents','POST',{room,name:a,content:'overwrite',operation:randomUUID()})).status,409);
assert.equal((await request('/api/documents','POST',{room,name:'../unsafe.md',content:'x',operation:randomUUID()})).status,400);
const listed=await request('/api/documents?room='+encodeURIComponent(room));assert.ok(listed.data.documents.some(d=>d.name===a));assert.ok(listed.data.documents.some(d=>d.name===b));
console.log(JSON.stringify({base,realGit:true,created:[a,b],idempotentCreate:true,separateSaves:true,fixedHistory:true,noOverwrite:true,invalidPathRejected:true,commits:[made.data.commit,saved.data.commit]}));
