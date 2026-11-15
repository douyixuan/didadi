// Private cookie proof stays local. Only synthetic screenshots leave isolated CI.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {chromium,expect} from '@playwright/test';
function option(key){const i=process.argv.indexOf(key);if(i<0||i+1>=process.argv.length)throw new Error('Missing '+key);return process.argv[i+1];}
const base=option('--url'),phase=option('--phase'),evidence=option('--evidence-dir');
assert.match(base,/^http:\/\/127\.0\.0\.1:\d+$/);assert.ok(['capture','verify'].includes(phase));
const accounts=Object.entries(JSON.parse(await readFile(option('--credentials-file'),'utf8')));assert.equal(accounts.length,2);
const state=JSON.parse(await readFile('.local/smoke-state.json','utf8'));
const docs=JSON.parse(await readFile(evidence+'/p071-git-proof.json','utf8')).documents;assert.equal(docs.length,2);
const browser=await chromium.launch({headless:true}),contexts=[];
const proofFile='.local/p072-session-private.json';
async function call(page,path,body,method){return page.evaluate(async({path,body,method})=>{
  const session=await (await fetch('/api/session')).json();
  const response=await fetch(path,{method:method||(body?'POST':'GET'),headers:{'Content-Type':'application/json','X-CSRF-Token':session.csrf},...(body?{body:JSON.stringify(body)}:{})});
  return {status:response.status,data:await response.json()};
},{path,body,method});}
async function openAccount([id,password],cookies){
  const context=await browser.newContext({baseURL:base});contexts.push(context);if(cookies)await context.addCookies(cookies);
  const page=await context.newPage();let logins=0;page.on('request',request=>{if(new URL(request.url()).pathname==='/api/auth/login')logins++;});await page.goto('/');
  if(!cookies){await page.getByLabel('Matrix user ID').fill(id);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();}
  await expect(page.getByRole('button',{name:/Sign out/})).toBeVisible({timeout:45000});
  const session=await call(page,'/api/session');assert.equal(session.status,200);assert.equal(session.data.userId,id);assert.equal(session.data.liveMatrix,true);
  if(cookies)assert.equal(logins,0,'Restored devices must not log in again');return {context,page,session:session.data};
}
try{
  const prior=phase==='verify'?JSON.parse(await readFile(proofFile,'utf8')):null;
  const users=[];for(let i=0;i<accounts.length;i++)users.push(await openAccount(accounts[i],prior?.cookies[i]));
  const [alice,bob]=users;assert.notEqual(alice.session.userId,bob.session.userId);
  if(prior)for(let i=0;i<users.length;i++)assert.equal(users[i].session.csrf,prior.csrf[i]);
  const denied=await alice.page.evaluate(async csrf=>(await fetch('/api/auth/logout',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:'{}'})).status,bob.session.csrf);
  assert.equal(denied,403);assert.equal((await call(alice.page,'/api/session')).status,200);
  for(const actor of users){
    const event=await call(actor.page,'/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(state.room)+'/event/'+encodeURIComponent(state.event));
    assert.equal(event.status,200);assert.equal(event.data.content.body,state.body);
    for(const doc of docs){
      assert.match(doc.path,/^p071\/[a-f0-9]{32}\/(A\.md|Archive\/B\.md)$/);assert.match(doc.commit,/^[a-f0-9]{40}$/);
      const immutable=execFileSync('git',['--git-dir=.local/documents.git','show',doc.commit+':'+doc.path],{encoding:'utf8'});
      const loaded=await call(actor.page,'/api/document?'+new URLSearchParams({room:actor.session.documentRoom,path:doc.path}));
      assert.equal(loaded.status,200);assert.equal(loaded.data.content,immutable);assert.equal(loaded.data.blob,doc.blob);
      const selected=await actor.page.locator('.page-eyebrow').textContent();
      if(!selected.includes(doc.path))await actor.page.getByRole('button',{name:doc.path,exact:true}).click();
      await expect(actor.page.locator('.markdown-body')).toContainText(doc.marker,{timeout:30000});
    }
  }
  let privateRoom,privateEvent,marker;
  if(phase==='capture'){
    const created=await call(bob.page,'/api/rooms',{name:'P072 restored private '+randomUUID(),kind:'group',participants:[],operation:randomUUID()});
    assert.equal(created.status,200);privateRoom=created.data.room_id;marker='Private restore '+randomUUID();
    const sent=await call(bob.page,'/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(privateRoom)+'/send/m.room.message/'+randomUUID(),{msgtype:'m.text',body:marker},'PUT');assert.equal(sent.status,200);privateEvent=sent.data.event_id;
    await writeFile(proofFile,JSON.stringify({cookies:await Promise.all(users.map(x=>x.context.cookies())),csrf:users.map(x=>x.session.csrf),privateRoom,privateEvent,marker}),{mode:0o600});
  }else ({privateRoom,privateEvent,marker}=prior);
  const route='/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(privateRoom)+'/event/'+encodeURIComponent(privateEvent);
  assert.equal((await call(alice.page,route)).status,403);
  const own=await call(bob.page,route);assert.equal(own.status,200);assert.equal(own.data.content.body,marker);
  if(phase==='verify'){
    // The copied live cookies succeeded without any /api/auth/login request.
    const stranger=await browser.newContext({baseURL:base});contexts.push(stranger);
    const response=await stranger.request.get('/api/session');assert.equal(response.status(),401);
    await alice.page.screenshot({path:evidence+'/p072-restored-alice.png',fullPage:true});
    await bob.page.screenshot({path:evidence+'/p072-restored-bob.png',fullPage:true});
    console.log('PASS REAL P072 independent restore: two original device cookies, immutable A/B, original message, private-room denial and unknown-session denial');
  }else console.log('PASS REAL P072 captured private live-device proof before backup (no credentials exported)');
}finally{for(const context of contexts)await context.close();await browser.close();}
