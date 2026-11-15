// Real #70 negative acceptance. Existing ephemeral users only; never log tokens or bodies.
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {expect} from '@playwright/test';
import {loginCooldown} from './login_cooldown.mjs';

export async function verifyRoomIsolation({alice,bob,accounts,request,evidenceDir,matrix='http://127.0.0.1:8008'}) {
  alice.page.setDefaultTimeout(30000);bob.page.setDefaultTimeout(30000);
  assert.match(matrix,/^http:\/\/(127\.0\.0\.1|localhost):\d+$/,'Only isolated loopback Matrix is allowed');
  const stamp=randomUUID().replaceAll('-',''),secret='P070private'+stamp,forbiddenBodies=[secret];
  const v3=room=>'/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(room);
  const v1=(room,root)=>'/matrix/_matrix/client/v1/rooms/'+encodeURIComponent(room)+'/relations/'+encodeURIComponent(root)+'/m.thread/m.room.message';
  async function io(page,path,body,method=body===undefined?'GET':'POST') {
    return page.evaluate(async({path,body,method})=>{
      const session=await (await fetch('/api/session')).json();
      const response=await fetch(path,{method,headers:{'X-CSRF-Token':session.csrf,...(body===undefined?{}:{'Content-Type':'application/json'})},...(body===undefined?{}:{body:JSON.stringify(body)})});
      const type=response.headers.get('Content-Type')||'';
      return {status:response.status,data:type.includes('json')?await response.json():null};
    },{path,body,method});
  }
  async function text(page,room,body,relation) {
    const result=await io(page,v3(room)+'/send/m.room.message/'+randomUUID(),{msgtype:'m.text',body,...(relation?{'m.relates_to':relation}:{})},'PUT');
    assert.equal(result.status,200,'Authorized real message send failed');return result.data.event_id;
  }
  async function discussion(page) {
    const panel=page.locator('.collaboration-panel');
    if(await panel.evaluate(node=>node.classList.contains('panel-closed')))
      await page.getByRole('button',{name:'Discussion',exact:true}).click();
  }
  async function select(page,title) {
    await page.getByRole('button',{name:'Refresh rooms'}).click();
    const room=page.locator('nav[aria-label="Rooms"] button.room').filter({hasText:title});
    await expect(room).toBeVisible({timeout:30000});await room.click();await expect(room).toHaveClass(/room-selected/);
    await discussion(page);
  }
  async function create(page,title,participants=[]) {
    const result=await request(page,'/api/rooms',{name:title,kind:'group',participants,operation:randomUUID()});
    assert.equal(result.status,200,'Real room setup failed');return result.data.room_id;
  }
  async function attachment(page,filename) {
    const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/attachments'&&r.request().method()==='POST');
    await page.getByLabel('Attach file',{exact:true}).setInputFiles({name:filename,mimeType:'text/plain',buffer:Buffer.from('P070 synthetic attachment\n')});
    await page.getByRole('button',{name:'Send attachment',exact:true}).click();
    const uploaded=await response;assert.equal(uploaded.status(),200);return (await uploaded.json()).event_id;
  }
  // Delay genuine server responses rather than fabricate fixture content.
  async function hold(page,predicate,trigger,marker=secret) {
    let ready,release;const seen=new Promise(resolve=>{ready=resolve}),gate=new Promise(resolve=>{release=resolve});
    let used=false,finished;const completed=new Promise(resolve=>{finished=resolve});
    const match=url=>predicate(url);
    const handler=async route=>{
      if(used)return route.continue();used=true;
      const original=route.request();let consumed;
      const bodyDone=new Promise(resolve=>{consumed=resolve});
      const complete=request=>{if(request===original)consumed('delivered')};
      const failed=request=>{if(request===original)consumed('cancelled-by-navigation')};
      page.on('requestfinished',complete);page.on('requestfailed',failed);
      try{
        const response=await route.fetch();assert.equal(response.status(),200,'Held response must be an authorized real read');
        assert.ok((await response.text()).includes(marker),'Held response must contain actual source content');
        ready();await gate;
        try{await route.fulfill({response});finished(await bodyDone);}catch{finished('cancelled-by-navigation');}
      }catch(error){ready(error);finished('failed');await route.abort().catch(()=>{});}
      finally{page.off('requestfinished',complete);page.off('requestfailed',failed);}
    };
    await page.route(match,handler);await trigger();
    let timer;const error=await Promise.race([seen,new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Real response hold was not reached')),30000);})]).finally(()=>clearTimeout(timer));
    if(error)throw error;
    return async()=>{release();const outcome=await completed;await page.unroute(match,handler);assert.notEqual(outcome,'failed');
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));return outcome;};
  }
  const article=(page,id)=>page.locator('[data-event-id='+JSON.stringify(id)+']');
  async function denied(page,path,body,method) {
    const result=await io(page,path,body,method);
    assert.ok([403,404].includes(result.status),'Unauthorized route must be rejected');
    assert.ok(forbiddenBodies.every(body=>!JSON.stringify(result.data).includes(body)),'Denial exposed old content');
  }
  async function search(page,term) {
    await page.getByRole('button',{name:'Open full-text search',exact:true}).click();
    await page.getByRole('textbox',{name:'Search body text',exact:true}).fill(term);
    await page.getByRole('button',{name:'Search',exact:true}).click();
  }
  async function loginOn(page,account) {
    await expect(page.getByRole('main',{name:'Matrix sign in'})).toBeVisible({timeout:30000});
    await page.getByLabel('Matrix user ID',{exact:true}).fill(account[0]);
    // Rate limiting is not an authentication or isolation failure. Retry only a real 429.
    const started=Date.now();
    for(let attempt=0;attempt<4;attempt++){
      await page.getByLabel('Password',{exact:true}).fill(account[1]);
      const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/auth/login'&&r.request().method()==='POST');
      await page.getByRole('button',{name:'Sign in',exact:true}).click();const result=await response;
      if(result.status()!==429){assert.equal(result.status(),200,'Account switch login failed');break;}
      assert.ok(attempt<3,'Login limiter did not recover');
      const data=await result.json();await page.waitForTimeout(loginCooldown(data,Date.now()-started));
    }
    await expect(page.getByRole('button',{name:/Sign out/})).toBeVisible({timeout:45000});
    assert.equal((await request(page,'/api/session')).data.userId,account[0]);
  }

  const title='P070 revocation '+stamp.slice(0,8),room=await create(alice.page,title,[accounts[1][0]]);
  await expect.poll(async()=>{const result=await request(bob.page,'/api/rooms/invites');return result.data.invites.some(item=>item.room===room);},{timeout:45000}).toBe(true);
  assert.equal((await request(bob.page,'/api/rooms/join',{room})).status,200);
  // Seed more than the 50-event page using the actor's normal room-authorized API.
  for(let n=0;n<53;n++)await text(alice.page,room,secret+' history '+n);
  const root=await text(alice.page,room,secret+' root');
  await text(alice.page,room,secret+' reply',{'rel_type':'m.thread','event_id':root,'m.in_reply_to':{'event_id':root}});
  await select(alice.page,title);const filename='p070-'+stamp.slice(0,8)+'.txt';
  const file=await attachment(alice.page,filename);
  await select(bob.page,title);await expect(article(bob.page,root)).toBeVisible({timeout:30000});
  const download=bob.page.waitForEvent('download');
  await bob.page.getByRole('button',{name:'Download '+filename,exact:true}).click();
  const stream=await (await download).createReadStream(),chunks=[];for await(const chunk of stream)chunks.push(chunk);
  assert.equal(Buffer.concat(chunks).toString(),'P070 synthetic attachment\n');
  const safe=bob.session.initialRoom;
  const safeState=await request(bob.page,v3(safe)+'/state');
  assert.equal(safeState.status,200);
  const safeName=safeState.data.find(event=>event.type==='m.room.name')?.content.name;
  assert.ok(safeName,'A distinct authorized destination room is required');
  const chooseSafe=async()=>{await bob.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText:safeName}).click();};
  const older=await hold(bob.page,url=>decodeURIComponent(url.pathname)===decodeURIComponent(v3(room)+'/messages')&&Boolean(url.searchParams.get('from')),async()=>{
    await bob.page.getByRole('button',{name:'Load earlier messages',exact:true}).click();
  });
  await chooseSafe();assert.equal(await older(),'delivered');
  await expect(bob.page.locator('.timeline')).not.toContainText(secret);
  await select(bob.page,title);
  const thread=await hold(bob.page,url=>decodeURIComponent(url.pathname)===decodeURIComponent(v1(room,root)),async()=>{
    await article(bob.page,root).getByRole('button',{name:'View thread',exact:true}).click();
  });
  await chooseSafe();assert.equal(await thread(),'delivered');await expect(bob.page.locator('.timeline')).not.toContainText(secret);
  await bob.page.screenshot({path:evidenceDir+'/p070-cross-room-late-responses.png',fullPage:true});

  // A real safe room must reject event/file references belonging to the source room.
  await denied(bob.page,v3(safe)+'/send/m.room.message/'+randomUUID(),{msgtype:'m.text',body:'forbidden quote','m.relates_to':{'m.in_reply_to':{'event_id':root}}},'PUT');
  await denied(bob.page,v1(safe,root));
  await denied(bob.page,'/api/attachments/download?'+new URLSearchParams({room:safe,event:file}));
  await select(bob.page,title);
  await expect.poll(async()=>{const result=await request(bob.page,'/api/search/messages',{room,query:secret,next_batch:null});return result.data.events?.length||0;},{timeout:45000}).toBeGreaterThan(0);
  // Authenticate the existing creator device before holding requests, so login throttling cannot time out the race probes.
  let token;const creatorLoginStarted=Date.now();
  try{
    for(let attempt=0;attempt<4;attempt++){
      const response=await fetch(matrix+'/_matrix/client/v3/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({type:'m.login.password',identifier:{type:'m.id.user',user:accounts[0][0]},password:accounts[0][1]})});
      const data=await response.json();
      if(response.status===429){assert.ok(attempt<3);await new Promise(r=>setTimeout(r,loginCooldown(data,Date.now()-creatorLoginStarted)));continue;}
      assert.equal(response.status,200,'Isolated creator device login failed');token=data.access_token;break;
    }
    assert.ok(token);
    await article(bob.page,root).getByRole('button',{name:'Quote',exact:true}).click();
    const kickedOlder=await hold(bob.page,url=>decodeURIComponent(url.pathname)===decodeURIComponent(v3(room)+'/messages')&&Boolean(url.searchParams.get('from')),async()=>{
      await bob.page.getByRole('button',{name:'Load earlier messages',exact:true}).click();
    });
    const kickedThread=await hold(bob.page,url=>decodeURIComponent(url.pathname)===decodeURIComponent(v1(room,root)),async()=>{
      await article(bob.page,root).getByRole('button',{name:'View thread',exact:true}).click();
    });
    const oldSearch=await hold(bob.page,url=>url.pathname==='/api/search/messages',()=>search(bob.page,secret));
      const response=await fetch(matrix+'/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/kick',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({user_id:accounts[1][0],reason:'Isolated P070 acceptance'})});
      assert.equal(response.status,200,'Real Synapse creator kick failed');
      const membership=await fetch(matrix+'/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/state/m.room.member/'+encodeURIComponent(accounts[1][0]),{headers:{'Authorization':'Bearer '+token}});
      assert.equal(membership.status,200);assert.equal((await membership.json()).membership,'leave');
    await expect(bob.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText:title})).toHaveCount(0,{timeout:30000});
    assert.equal(await kickedOlder(),'delivered');assert.equal(await kickedThread(),'delivered');await oldSearch();await expect(bob.page.getByRole('dialog',{name:'Search messages and document text'})).toHaveCount(0);
    await expect(bob.page.locator('body')).not.toContainText(secret);
    for(const path of [v3(room)+'/messages?dir=b',v3(room)+'/state',v3(room)+'/event/'+encodeURIComponent(root),v1(room,root)])await denied(bob.page,path);
    await denied(bob.page,'/api/search/messages',{room,query:secret,next_batch:null});
    await denied(bob.page,'/api/attachments/download?'+new URLSearchParams({room,event:file}));
    await denied(bob.page,v3(room)+'/send/m.room.message/'+randomUUID(),{msgtype:'m.text',body:'denied after kick','m.relates_to':{'m.in_reply_to':{'event_id':root}}},'PUT');
    await bob.page.screenshot({path:evidenceDir+'/p070-real-kick-eviction.png',fullPage:true});
    console.log('PASS REAL ROOM #70: actual kick, stale search eviction, denied history/thread/quote/file/search');

  }finally{
    if(token){const logout=await fetch(matrix+'/_matrix/client/v3/logout',{method:'POST',headers:{'Authorization':'Bearer '+token},body:'{}'});assert.equal(logout.status,200,'Creator test device logout failed');}
  }

  // Same page/profile switches Bob -> Alice -> Bob. An old successful search is held across logout.
  const privateTitle='P070 identity '+stamp.slice(0,8),privateRoom=await create(bob.page,privateTitle);
  const identitySecret='P070identity'+stamp;forbiddenBodies.push(identitySecret);
  const identityRoot=await text(bob.page,privateRoom,identitySecret);
  await select(bob.page,privateTitle);await expect(article(bob.page,identityRoot)).toBeVisible({timeout:30000});
  const identityFile=await attachment(bob.page,'identity-'+stamp.slice(0,8)+'.txt');
  await article(bob.page,identityRoot).getByRole('button',{name:'Quote',exact:true}).click();
  await expect.poll(async()=>{const result=await request(bob.page,'/api/search/messages',{room:privateRoom,query:identitySecret,next_batch:null});return result.data.events?.length||0;},{timeout:45000}).toBeGreaterThan(0);
  const lateIdentity=await hold(bob.page,url=>url.pathname==='/api/search/messages',()=>search(bob.page,identitySecret),identitySecret);
  await bob.page.getByRole('button',{name:'Close search',exact:true}).click();
  await bob.page.getByRole('button',{name:/Sign out/}).click();await loginOn(bob.page,accounts[0]);
  await lateIdentity();
  await expect(bob.page.locator('body')).not.toContainText(identitySecret);
  await expect(bob.page.locator('nav[aria-label="Rooms"]')).not.toContainText(privateTitle);
  for(const path of [v3(privateRoom)+'/messages?dir=b',v3(privateRoom)+'/event/'+encodeURIComponent(identityRoot),v1(privateRoom,identityRoot)])await denied(bob.page,path);
  await denied(bob.page,'/api/search/messages',{room:privateRoom,query:identitySecret,next_batch:null});
  await denied(bob.page,'/api/attachments/download?'+new URLSearchParams({room:privateRoom,event:identityFile}));
  await denied(bob.page,v3(privateRoom)+'/send/m.room.message/'+randomUUID(),{msgtype:'m.text',body:'denied account quote','m.relates_to':{'m.in_reply_to':{'event_id':identityRoot}}},'PUT');
  await bob.page.screenshot({path:evidenceDir+'/p070-same-browser-account-isolation.png',fullPage:true});
  await bob.page.getByRole('button',{name:/Sign out/}).click();await loginOn(bob.page,accounts[1]);
  bob.session=(await request(bob.page,'/api/session')).data;
  await select(bob.page,privateTitle);await expect(bob.page.locator('.timeline')).toContainText(identitySecret,{timeout:30000});
  console.log('PASS REAL ROOM #70: same-browser account switch, delayed response, quote/file/search/history isolation and return');
}
