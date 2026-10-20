import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
const base=process.argv[2]||'http://127.0.0.1:8767';
const session=await(await fetch(base+'/api/session')).json(),room=session.initialRoom;
async function request(path,method='GET',body){const r=await fetch(base+path,{method,headers:{'X-CSRF-Token':session.csrf,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()}}
const nonce=randomUUID(),source='Move/'+nonce+'/Original.md',name='Archive/'+nonce+'/改名.md',content='---\r\ntitle: Exact\r\n---\r\n\r\n# Unchanged 原文\r\n';
const original=await request('/api/documents','POST',{room,name:source,content,operation:randomUUID()});assert.equal(original.status,200);
const payload={room,source,name,base_blob:original.data.blob,operation:randomUUID()};
const moved=await request('/api/documents/move','POST',payload);assert.equal(moved.status,200);assert.equal(moved.data.path,name);assert.equal(moved.data.blob,original.data.blob);
const retry=await request('/api/documents/move','POST',payload);assert.equal(retry.status,200);assert.equal(retry.data.commit,moved.data.commit);
async function read(path,commit){return request('/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(path)+(commit?'&commit='+commit:''))}
assert.equal((await read(source)).data.blob,null);assert.equal((await read(name)).data.content,content);assert.equal((await read(source,original.data.commit)).data.content,content);
const collision=await request('/api/documents/move','POST',{...payload,source:name,name,operation:randomUUID()});assert.equal(collision.status,400);
const stale=await request('/api/documents/move','POST',{...payload,name:'Other/'+nonce+'.md',operation:randomUUID()});assert.equal(stale.status,409);
assert.equal((await read(name)).data.content,content);
const listed=(await request('/api/documents?room='+encodeURIComponent(room))).data.documents;assert.ok(listed.some(d=>d.name===name));assert.ok(!listed.some(d=>d.name===source));
console.log(JSON.stringify({base,realGit:true,source,name,blob:moved.data.blob,commit:moved.data.commit,atomicMove:true,idempotent:true,exactCRLF:true,historicalSourceReadable:true,staleSourceRejected:true}));
