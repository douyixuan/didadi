// Genuine two-user Document API/Git/browser acceptance, isolated CI only.
import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {expect} from '@playwright/test';

export async function verifyDocumentRecovery({alice,bob,accounts,request,evidenceDir,matrix,token,returnPath}) {
  assert.match(matrix,/^http:\/\/(127\.0\.0\.1|localhost):\d+$/);
  const room=alice.session.documentRoom;
  assert.equal(room,bob.session.documentRoom);
  const powerURL=matrix+'/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/state/m.room.power_levels';
  const headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'};
  const previous=await fetch(powerURL,{headers});assert.equal(previous.status,200);
  const levels=await previous.json();
  // Existing owner delegates the existing document-write level to the other
  // existing synthetic member, only for this test. Always restore original state.
  const temporary={...levels,users:{...levels.users,[accounts[1][0]]:50}};
  const stamp=randomUUID().replaceAll('-','');
  const a='p071/'+stamp+'/A.md',b='p071/'+stamp+'/B.md',moved='p071/'+stamp+'/Archive/B.md';
  const base='P071 shared paragraph '+stamp,winner='P071 Alice winner '+stamp,loser='P071 Bob retained draft '+stamp;
  const stableB='P071 independent B '+stamp,resolved='P071 explicitly resolved '+stamp,retryB='P071 failed network draft '+stamp;
  const read=(page,path)=>request(page,'/api/document?'+new URLSearchParams({room,path}));
  const history=(page,path)=>request(page,'/api/history?'+new URLSearchParams({room,path}));
  const editor=page=>page.locator('.document-surface [contenteditable="true"]').first();
  async function open(page,path){
    if(!(await page.locator('.page-eyebrow').textContent().catch(()=>''))?.includes(path)) {
      await expect(page.getByRole('button',{name:path,exact:true})).toBeEnabled({timeout:30000});
      await page.getByRole('button',{name:path,exact:true}).click();
    }
    await expect(page.locator('.page-eyebrow')).toContainText(path,{timeout:30000});
    await expect(page.getByRole('button',{name:path+', current document',exact:true}).locator('strong')).toHaveText(path.split('/').at(-1));
    await expect(page.locator('.document-statusbar')).toContainText('All changes saved',{timeout:30000});
  }
  async function edit(page,text){
    if(!await editor(page).isVisible())await page.getByRole('button',{name:'Edit',exact:true}).click();
    await editor(page).fill(text);
    await expect(page.getByText('Unsaved draft kept on this browser only.',{exact:false})).toBeVisible({timeout:30000});
  }
  async function save(page,status=200,expectedBase){
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/api/documents/')&&r.request().method()==='PUT');
    await page.getByRole('button',{name:'Save changes',exact:true}).click();
    const result=await response;assert.equal(result.status(),status);
    if(expectedBase)assert.equal(result.request().postDataJSON().base_blob,expectedBase);
    if(status===200)await expect(page.locator('.document-statusbar')).toContainText('All changes saved',{timeout:30000});
    return result.json();
  }
  async function create(page,path,body){
    await page.getByLabel('New document path').fill(path);
    await page.getByRole('button',{name:'Create document',exact:true}).click();
    await expect(page.locator('.page-eyebrow')).toContainText(path,{timeout:30000});
    await expect(page.getByRole('button',{name:path+', current document',exact:true}).locator('strong')).toHaveText(path.split('/').at(-1));
    await edit(page,body);await save(page);
  }
  let completed=false;
  const grant=await fetch(powerURL,{method:'PUT',headers,body:JSON.stringify(temporary)});assert.equal(grant.status,200);
  try{
    // Both paths are created and edited through the actual UI, never fixtures.
    await create(alice.page,a,base);await bob.page.reload();await create(bob.page,b,stableB);
    await alice.page.reload();await open(alice.page,b);
    await alice.page.reload();
    await expect(alice.page.locator('.page-eyebrow')).toContainText(b,{timeout:30000});
    assert.ok((await read(alice.page,a)).data.content.includes(base));
    assert.ok((await read(alice.page,b)).data.content.includes(stableB));
    await bob.page.reload();await open(alice.page,a);await open(bob.page,a);
    const common=(await read(bob.page,a)).data;
    await edit(alice.page,winner);await edit(bob.page,loser);
    await save(alice.page,200,common.blob);
    const winnerDoc=(await read(alice.page,a)).data;
    const beforeConflict=await history(alice.page,a);
    assert.notEqual(common.blob,winnerDoc.blob);
    const failed=await save(bob.page,409,common.blob);assert.equal(failed.status,'conflict');
    await expect(bob.page.getByText('This document has a newer version',{exact:true})).toBeVisible();
    await expect(editor(bob.page)).toContainText(loser);
    assert.deepEqual((await read(alice.page,a)).data,winnerDoc);
    assert.deepEqual(await history(alice.page,a),beforeConflict);
    assert.ok((await read(alice.page,b)).data.content.includes(stableB));
    await bob.page.screenshot({path:evidenceDir+'/p071-conflict-draft.png',fullPage:true});
    await bob.page.reload();
    await expect(bob.page.locator('.page-eyebrow')).toContainText(a,{timeout:30000});
    await expect(bob.page.getByRole('heading',{name:'Unsaved draft found on this browser',exact:true})).toBeVisible();
    await bob.page.getByRole('button',{name:'Restore local draft',exact:true}).click();
    await expect(editor(bob.page)).toContainText(loser);
    await expect(bob.page.getByText(/This draft is based on an older Git version/)).toBeVisible();
    await editor(bob.page).fill(resolved);
    await bob.page.getByRole('button',{name:'I reviewed and merged latest Git text',exact:true}).click();
    await save(bob.page);
    const resolvedA=(await read(alice.page,a)).data;assert.ok(resolvedA.content.includes(resolved));
    assert.ok((await read(alice.page,b)).data.content.includes(stableB));
    // Abort before transport: no backend write is fabricated or hidden.
    await open(bob.page,b);await edit(bob.page,retryB);
    const bBefore=(await read(alice.page,b)).data,bHistory=await history(alice.page,b);
    const matcher=url=>url.pathname==='/api/documents/'+encodeURIComponent(b);
    await bob.page.route(matcher,route=>route.request().method()==='PUT'?route.abort('failed'):route.continue());
    await bob.page.getByRole('button',{name:'Save changes',exact:true}).click();
    await expect(bob.page.getByText('Couldn’t complete the request',{exact:true})).toBeVisible();
    await bob.page.unroute(matcher);
    assert.deepEqual((await read(alice.page,b)).data,bBefore);
    assert.deepEqual(await history(alice.page,b),bHistory);
    await bob.page.reload();
    await expect(bob.page.locator('.page-eyebrow')).toContainText(b,{timeout:30000});
    await bob.page.getByRole('button',{name:'Restore local draft',exact:true}).click();
    await expect(editor(bob.page)).toContainText(retryB);
    await expect(bob.page.locator('body')).not.toContainText(loser);
    await save(bob.page);
    await bob.page.screenshot({path:evidenceDir+'/p071-recovered-network-draft.png',fullPage:true});
    // Confirmed move updates selection; reload must reopen the new path.
    await bob.page.getByRole('button',{name:'Read',exact:true}).click();
    await bob.page.getByLabel('Move document to path').fill(moved);
    await bob.page.getByRole('button',{name:'Move document',exact:true}).click();
    await expect(bob.page.locator('.page-eyebrow')).toContainText(moved,{timeout:30000});
    await bob.page.reload();await expect(bob.page.locator('.page-eyebrow')).toContainText(moved,{timeout:30000});
    const final=(await read(bob.page,moved)).data;
    assert.ok(final.content.includes(retryB));assert.ok((await read(alice.page,a)).data.content.includes(resolved));
    const download=bob.page.waitForEvent('download');
    await bob.page.getByRole('button',{name:'Export Markdown',exact:true}).click();
    const file=await download,stream=await file.createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);
    assert.equal(Buffer.concat(chunks).toString('utf8'),final.content);
    await bob.page.screenshot({path:evidenceDir+'/p071-moved-reopened-exported.png',fullPage:true});
    // Existing fixed-version UI remains usable for A without changing B.
    await open(bob.page,a);
    await bob.page.getByRole('button',{name:'Version history',exact:true}).click();
    await bob.page.getByRole('button',{name:/Previous version/}).first().click();
    await expect(bob.page.getByText('You’re viewing an earlier version.',{exact:false})).toBeVisible();
    await expect(bob.page.locator('.markdown-body')).toContainText(winner);
    await bob.page.screenshot({path:evidenceDir+'/p071-history-return-control.png',fullPage:true});
    await bob.page.getByRole('complementary',{name:'Version history'}).getByRole('button',{name:'Back to latest',exact:true}).click();
    await expect(bob.page.locator('.markdown-body')).toContainText(resolved);
    await expect(bob.page.getByRole('complementary',{name:'Version history'})).toHaveCount(0);
    await bob.page.screenshot({path:evidenceDir+'/p071-history-return-accessible.png',fullPage:true});
    // Actual selected message -> Git document with a native source permalink.
    await bob.page.goto('/?room='+encodeURIComponent(room));
    const panel=bob.page.locator('.collaboration-panel');
    if(await panel.evaluate(node=>node.classList.contains('panel-closed')))await bob.page.getByRole('button',{name:'Discussion',exact:true}).click();
    const sourceText='P071 source message '+stamp;
    const sent=bob.page.waitForResponse(r=>new URL(r.url()).pathname.includes('/send/m.room.message/')&&r.request().method()==='PUT');
    await bob.page.locator('.composer textarea').fill(sourceText);
    await bob.page.locator('.composer').getByRole('button',{name:/^Send/}).click();
    const sentResponse=await sent;assert.equal(sentResponse.status(),200);const event=(await sentResponse.json()).event_id;
    const replyText='P071 thread source '+stamp;
    await bob.page.locator('.timeline article').filter({hasText:sourceText}).getByRole('button',{name:'Reply',exact:true}).click();
    const replied=bob.page.waitForResponse(r=>new URL(r.url()).pathname.includes('/send/m.room.message/')&&r.request().method()==='PUT');
    await bob.page.locator('.composer textarea').fill(replyText);
    await bob.page.locator('.composer').getByRole('button',{name:/^Send/}).click();
    const replyResponse=await replied;assert.equal(replyResponse.status(),200);const reply=(await replyResponse.json()).event_id;
    await bob.page.getByLabel('Select message '+event,{exact:true}).check();
    await bob.page.getByLabel('Select message '+reply,{exact:true}).check();
    const copied='p071/'+stamp+'/From-message.md';
    await bob.page.getByLabel('Document path from messages').fill(copied);
    // Lose a genuine successful create acknowledgement; do not fake the result.
    const copyPattern=url=>url.pathname==='/api/documents/from-messages';let firstSaved,firstPayload,acknowledgementError;
    await bob.page.route(copyPattern,async route=>{
      if(firstSaved)return route.continue();
      try{firstPayload=route.request().postDataJSON();const response=await route.fetch();assert.equal(response.status(),200);
        firstSaved=await response.json();assert.equal(firstSaved.status,'saved');
      }catch(error){acknowledgementError=error;}
      await route.abort('failed');
    });
    await bob.page.getByRole('button',{name:'Create document from messages',exact:true}).click();
    await expect(bob.page.locator('.message-document-form [role="status"]')).toContainText('Retry the same selection to confirm',{timeout:30000});
    await expect(bob.page.getByLabel('Document path from messages')).toHaveValue(copied);
    await expect(bob.page.getByLabel('Document path from messages')).toBeDisabled();
    await bob.page.unroute(copyPattern);if(acknowledgementError)throw acknowledgementError;
    const git=args=>execFileSync('git',['--git-dir=.local/documents.git',...args],{encoding:'utf8'});
    const head=git(['rev-parse','refs/heads/main']);
    const beforeHistory=git(['log','--format=%H','refs/heads/main','--',copied]);
    const retryResponse=bob.page.waitForResponse(r=>new URL(r.url()).pathname==='/api/documents/from-messages'&&r.request().method()==='POST');
    await bob.page.getByRole('button',{name:'Create document from messages',exact:true}).click();
    const retried=await retryResponse;assert.equal(retried.status(),200);assert.deepEqual(retried.request().postDataJSON(),firstPayload);
    assert.equal((await retried.json()).commit,firstSaved.commit);assert.equal(git(['rev-parse','refs/heads/main']),head);assert.equal(git(['log','--format=%H','refs/heads/main','--',copied]),beforeHistory);
    await expect(bob.page.locator('.page-eyebrow')).toContainText(copied,{timeout:30000});
    const source=(await read(bob.page,copied)).data;
    assert.ok(source.content.includes(sourceText)&&source.content.includes(replyText));
    const sourceLinks=bob.page.locator('.markdown-body').getByRole('link',{name:'Open source message',exact:true});
    await expect(sourceLinks).toHaveCount(2);
    for(const [index,id] of [event,reply].entries())assert.equal(decodeURIComponent(await sourceLinks.nth(index).getAttribute('href')),'https://matrix.to/#/'+room+'/'+id);
    const original=await request(bob.page,'/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/event/'+encodeURIComponent(event));
    assert.equal(original.status,200);assert.equal(original.data.content.body,sourceText);
    await bob.page.screenshot({path:evidenceDir+'/p071-message-document-source.png',fullPage:true});
    // Keep source links in a second real Git version, then hold the older
    // authorized snapshot while clicking the still-visible old page's link.
    await bob.page.route('https://matrix.to/**',route=>route.abort());
    await bob.page.getByRole('button',{name:'Edit',exact:true}).click();
    await expect(editor(bob.page)).toContainText(sourceText,{timeout:30000});
    await editor(bob.page).press('ControlOrMeta+End');await editor(bob.page).press('Enter');
    const newerNote='P071 newer source version '+stamp;await editor(bob.page).pressSequentially(newerNote);
    await expect(bob.page.getByText('Unsaved draft kept on this browser only.',{exact:false})).toBeVisible({timeout:30000});await save(bob.page);
    await bob.page.getByRole('button',{name:'Read',exact:true}).click();await expect(sourceLinks).toHaveCount(2);
    const newerSource=(await read(bob.page,copied)).data;
    assert.ok(newerSource.content.includes(newerNote));assert.notEqual(newerSource.blob,source.blob);
    // The rich editor may insert at the heading or a body block depending on
    // its active selection. Both belong to the read surface. Verify canonical
    // Git text plus that entire surface, independent of presentation placement.
    await expect(bob.page.locator('.document-surface')).toContainText(newerNote);
    await bob.page.getByRole('button',{name:'Version history',exact:true}).click();
    let ready,release,finished,entered=false;const held=new Promise(resolve=>{ready=resolve}),gate=new Promise(resolve=>{release=resolve}),done=new Promise(resolve=>{finished=resolve});
    const versionPattern=url=>url.pathname==='/api/document'&&url.searchParams.get('path')===copied&&url.searchParams.get('commit')===source.commit;
    await bob.page.route(versionPattern,async route=>{entered=true;let failure;
      try{const response=await route.fetch();assert.equal(response.status(),200);const data=await response.json();assert.equal(data.commit,source.commit);assert.ok(data.content.includes(sourceText));ready(null);await gate;await route.fulfill({response});}
      catch(error){failure=error;ready(error);await route.abort().catch(()=>{});}finally{finished(failure);}
    });
    let primaryFailure;
    try{
      await bob.page.getByRole('button',{name:/Previous version/}).first().click();
      let timer;const failure=await Promise.race([held,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Historical snapshot hold was not reached')),30000)})]).finally(()=>clearTimeout(timer));if(failure)throw failure;
      await expect(bob.page.locator('.markdown-body')).toHaveAttribute('aria-busy','true');
      const localOrigin=new URL(bob.page.url()).origin;await sourceLinks.first().click();
      await bob.page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      assert.equal(new URL(bob.page.url()).origin,localOrigin);await expect(bob.page.locator('.page-eyebrow')).toContainText(copied);
      await expect(bob.page.getByRole('button',{name:'All messages',exact:true})).toHaveCount(0);
      await bob.page.screenshot({path:evidenceDir+'/p071-source-loading-guard.png',fullPage:true});
    }catch(error){primaryFailure=error;throw error;}
    finally{release();const failure=entered?await done:null;await bob.page.unroute(versionPattern);if(failure&&!primaryFailure)throw failure;}
    await bob.page.getByRole('complementary',{name:'Version history'}).getByRole('button',{name:'Back to latest',exact:true}).click();
    await expect(bob.page.locator('.document-surface')).toContainText(newerNote,{timeout:30000});
    const latestSource=(await read(bob.page,copied)).data;assert.equal(latestSource.blob,newerSource.blob);assert.equal(latestSource.content,newerSource.content);
    // Normal clicks stay in this app. Block the portable external fallback so
    // a regression never contacts matrix.to. Root and reply return to context.
    const joined=await request(bob.page,'/matrix/_matrix/client/v3/joined_rooms');assert.equal(joined.status,200);
    const other=joined.data.joined_rooms.find(id=>id!==room);assert.ok(other,'Use an existing other joined room for source return');
    await bob.page.goto('/?room='+encodeURIComponent(other));await expect(bob.page.locator('.page-eyebrow')).toContainText(copied,{timeout:30000});
    await expect.poll(()=>new URL(bob.page.url()).searchParams.get('room')).toBe(other);
    const otherLabel=await bob.page.locator('nav[aria-label="Rooms"] button.room-selected > span').first().evaluate(node=>node.firstChild.textContent);
    const otherPanel=bob.page.locator('.collaboration-panel');if(await otherPanel.evaluate(node=>node.classList.contains('panel-closed')))await bob.page.getByRole('button',{name:'Discussion',exact:true}).click();
    const roomDraft='P071 unsent other-room draft '+stamp;await bob.page.locator('.composer textarea').fill(roomDraft);
    const sourceMarkers=[];const observeMarker=request=>{const path=new URL(request.url()).pathname;
      if(path==='/api/rooms/read'&&request.method()==='POST'&&request.postDataJSON().room===room)sourceMarkers.push('workspace-read');
      if(decodeURIComponent(path)==='/matrix/_matrix/client/v3/rooms/'+room+'/read_markers')sourceMarkers.push('matrix-read');};
    bob.page.on('request',observeMarker);
    const origin=new URL(bob.page.url()).origin;
    for(const [index,id] of [event,reply].entries()){
      const sourceResponse=bob.page.waitForResponse(response=>decodeURIComponent(new URL(response.url()).pathname)==='/matrix/_matrix/client/v3/rooms/'+room+'/event/'+id&&response.request().method()==='GET');
      await sourceLinks.nth(index).click();assert.equal((await sourceResponse).status(),200);
      assert.equal(new URL(bob.page.url()).origin,origin);
      await expect.poll(()=>new URL(bob.page.url()).searchParams.get('room')).toBe(room);
      const all=bob.page.getByRole('button',{name:'All messages',exact:true});await expect(all).toBeVisible({timeout:30000});
      await expect(all.locator('..')).toContainText('Thread '+event.slice(0,10));
      await expect(bob.page.locator('.timeline')).toContainText(sourceText,{timeout:30000});
      await expect(bob.page.locator('.timeline')).toContainText(replyText,{timeout:30000});
    }
    await bob.page.screenshot({path:evidenceDir+'/p071-in-app-source-return.png',fullPage:true});
    const returnRoom=bob.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText:otherLabel});await expect(returnRoom).toHaveCount(1);await returnRoom.click();
    await expect.poll(()=>new URL(bob.page.url()).searchParams.get('room')).toBe(other);await expect(bob.page.locator('.composer textarea')).toHaveValue(roomDraft);
    await bob.page.screenshot({path:evidenceDir+'/p071-source-return-preserved-room-draft.png',fullPage:true});await bob.page.locator('.composer textarea').fill('');
    assert.equal(sourceMarkers.length,0,'Source navigation must not mark the whole room read');bob.page.off('request',observeMarker);
    await bob.page.unroute('https://matrix.to/**');
    console.log('PASS REAL DOCUMENT #71: lost create acknowledgement retries identical operation without extra Git commit; root/reply source links return in-app');

    const proofs=[{path:a,commit:resolvedA.commit,blob:resolvedA.blob,marker:resolved},{path:moved,commit:final.commit,blob:final.blob,marker:retryB}];
    const receipts=await request(bob.page,'/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/messages?dir=b');
    assert.equal(receipts.status,200);
    for(const proof of proofs){
      const receipt=receipts.data.chunk.find(event=>event.content?.['org.didadi.document.commit']?.commit===proof.commit);
      assert.ok(receipt,'Final real Git version must have a Matrix receipt');
      assert.equal(receipt.content['org.didadi.document.commit'].author,accounts[1][0]);
      assert.equal(receipt.content['org.didadi.document.commit'].path,proof.path);
      for(const text of [base,winner,loser,stableB,resolved,retryB])assert.ok(!JSON.stringify(receipt).includes(text),'Receipt must not contain document text');
    }
    await writeFile(evidenceDir+'/p071-git-proof.json',JSON.stringify({documents:proofs},null,2),{mode:0o600});
    completed=true;
    console.log('PASS REAL DOCUMENT #71: two users, two UI documents, same-base conflict, isolated drafts after reload, network retry, confirmed move/reopen and exact export');
  }finally{
    const restore=await fetch(powerURL,{method:'PUT',headers,body:JSON.stringify(levels)});assert.equal(restore.status,200,'Original fixture power levels must be restored');
    const check=await fetch(powerURL,{headers});assert.equal(check.status,200);assert.deepEqual(await check.json(),levels);
    // Retain the actual failure screen; do not replace it with cleanup navigation.
    if(completed){await alice.page.reload();await bob.page.reload();await open(alice.page,returnPath);await open(bob.page,returnPath);}
  }
}


// Called in a new browser pair after both backend and Synapse restarts.
export async function verifyPersistedDocuments({alice,bob,request,evidenceDir}) {
  const proof=JSON.parse(await readFile(evidenceDir+'/p071-git-proof.json','utf8'));
  assert.equal(proof.documents.length,2);
  for(const doc of proof.documents){
    assert.match(doc.path,/^p071\/[a-f0-9]{32}\/(A\.md|Archive\/B\.md)$/);
    assert.match(doc.commit,/^[a-f0-9]{40}$/);assert.match(doc.blob,/^[a-f0-9]{40}$/);
    const author=execFileSync('git',['--git-dir=.local/documents.git','show','-s','--format=%an',doc.commit],{encoding:'utf8'}).trim();
    assert.equal(author,bob.session.userId,'Immutable Git commit must attribute the actual writer');
    const subject=execFileSync('git',['--git-dir=.local/documents.git','show','-s','--format=%s',doc.commit],{encoding:'utf8'}).trim();
    assert.ok(subject.startsWith('docs('+doc.path+'):'));
    const immutable=execFileSync('git',['--git-dir=.local/documents.git','show',doc.commit+':'+doc.path],{encoding:'utf8'});
    const blob=execFileSync('git',['--git-dir=.local/documents.git','rev-parse',doc.commit+':'+doc.path],{encoding:'utf8'}).trim();
    assert.equal(blob,doc.blob);assert.ok(immutable.includes(doc.marker));
    for(const actor of [alice,bob]){
      const result=await request(actor.page,'/api/document?'+new URLSearchParams({room:actor.session.documentRoom,path:doc.path}));
      assert.equal(result.status,200);assert.equal(result.data.content,immutable);assert.equal(result.data.blob,doc.blob);
      // Open each retained path through the genuine UI, after a fresh page load.
      await actor.page.reload();
      const selected=await actor.page.locator('.page-eyebrow').textContent();
      if(!selected.includes(doc.path))await actor.page.getByRole('button',{name:doc.path,exact:true}).click();
      await expect(actor.page.locator('.markdown-body')).toContainText(doc.marker,{timeout:30000});
    }
  }
  await bob.page.screenshot({path:evidenceDir+'/p071-after-backend-restart.png',fullPage:true});
  console.log('PASS REAL DOCUMENT #71: post-backend/Synapse restart both users read exact immutable Git bytes for both documents');
}
