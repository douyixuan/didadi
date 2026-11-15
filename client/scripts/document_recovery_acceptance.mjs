// Genuine two-user Document API/Git/browser acceptance, isolated CI only.
import assert from 'node:assert/strict';
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
    await expect(page.locator('.document-statusbar')).toContainText('All changes saved',{timeout:30000});
  }
  async function edit(page,text){
    if(!await editor(page).isVisible())await page.getByRole('button',{name:'Edit',exact:true}).click();
    await editor(page).fill(text);
    await expect(page.getByText('Unsaved draft kept on this browser only.',{exact:false})).toBeVisible({timeout:30000});
  }
  async function save(page,status=200){
    const response=page.waitForResponse(r=>new URL(r.url()).pathname.startsWith('/api/documents/')&&r.request().method()==='PUT');
    await page.getByRole('button',{name:'Save changes',exact:true}).click();
    const result=await response;assert.equal(result.status(),status);
    if(status===200)await expect(page.locator('.document-statusbar')).toContainText('All changes saved',{timeout:30000});
    return result.json();
  }
  async function create(path,body){
    await alice.page.getByLabel('New document path').fill(path);
    await alice.page.getByRole('button',{name:'Create document',exact:true}).click();
    await expect(alice.page.locator('.page-eyebrow')).toContainText(path,{timeout:30000});
    await edit(alice.page,body);await save(alice.page);
  }
  let completed=false;
  const grant=await fetch(powerURL,{method:'PUT',headers,body:JSON.stringify(temporary)});assert.equal(grant.status,200);
  try{
    // Both paths are created and edited through the actual UI, never fixtures.
    await create(a,base);await create(b,stableB);
    await alice.page.reload();
    await expect(alice.page.locator('.page-eyebrow')).toContainText(b,{timeout:30000});
    assert.ok((await read(alice.page,a)).data.content.includes(base));
    assert.ok((await read(alice.page,b)).data.content.includes(stableB));
    await bob.page.reload();await open(alice.page,a);await open(bob.page,a);
    const common=(await read(bob.page,a)).data;
    await edit(alice.page,winner);await edit(bob.page,loser);
    await save(alice.page);
    const winnerDoc=(await read(alice.page,a)).data;
    const beforeConflict=await history(alice.page,a);
    assert.notEqual(common.blob,winnerDoc.blob);
    const failed=await save(bob.page,409);assert.equal(failed.status,'conflict');
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
    assert.ok((await read(alice.page,a)).data.content.includes(resolved));
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
    completed=true;
    console.log('PASS REAL DOCUMENT #71: two users, two UI documents, same-base conflict, isolated drafts after reload, network retry, confirmed move/reopen and exact export');
  }finally{
    const restore=await fetch(powerURL,{method:'PUT',headers,body:JSON.stringify(levels)});assert.equal(restore.status,200,'Original fixture power levels must be restored');
    const check=await fetch(powerURL,{headers});assert.equal(check.status,200);assert.deepEqual(await check.json(),levels);
    // Retain the actual failure screen; do not replace it with cleanup navigation.
    if(completed){await alice.page.reload();await bob.page.reload();await open(alice.page,returnPath);await open(bob.page,returnPath);}
  }
}
