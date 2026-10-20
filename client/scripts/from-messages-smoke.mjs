import assert from 'node:assert/strict';import {randomUUID} from 'node:crypto';
const base=process.argv[2]||'http://127.0.0.1:8767',session=await(await fetch(base+'/api/session')).json(),room=session.initialRoom;
async function request(path,method='GET',body){const r=await fetch(base+path,{method,headers:{'X-CSRF-Token':session.csrf,'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()}}
const nonce=randomUUID(),bodies=['Selected source '+nonce,'Literal fenced text\n```\n<script>not executable</script>\n```'],events=[];
for(let i=0;i<bodies.length;i++){const sent=await request('/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/send/m.room.message/'+nonce+'-'+i,'PUT',{msgtype:'m.text',body:bodies[i]});assert.equal(sent.status,200);events.push(sent.data.event_id)}
const payload={room,name:'From-messages/'+nonce+'.md',events,operation:randomUUID()},created=await request('/api/documents/from-messages','POST',payload);assert.equal(created.status,200);assert.equal(created.data.path,payload.name);
const read=await request('/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(payload.name));assert.equal(read.status,200);for(const body of bodies)assert.ok(read.data.content.includes(body));for(const id of events)assert.ok(read.data.content.includes(encodeURIComponent(id)));
assert.ok(read.data.content.includes('````text\n'+bodies[1]+'\n````'));
const retry=await request('/api/documents/from-messages','POST',payload);assert.equal(retry.status,200);assert.equal(retry.data.commit,created.data.commit);
assert.equal((await request('/api/documents/from-messages','POST',{...payload,content:'spoofed client body'})).status,400);
assert.equal((await request('/api/documents/from-messages','POST',{...payload,room:'!other:local',name:'Other.md',operation:randomUUID()})).status,403);
const failed=await request('/api/documents/from-messages','POST',{...payload,name:'Missing-source/'+nonce+'.md',events:[events[0],'$nonexistent-'+nonce],operation:randomUUID()});assert.equal(failed.status,400);const absent=await request('/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent('Missing-source/'+nonce+'.md'));assert.equal(absent.data.blob,null);
console.log(JSON.stringify({base,room,path:payload.name,events,commit:created.data.commit,realMatrix:true,realGit:true,canonicalSourceText:true,sourceLinks:true,idempotent:true,clientBodyRejected:true,crossRoomRejected:true,noPartialDocument:true,implicitLLM:false}));
