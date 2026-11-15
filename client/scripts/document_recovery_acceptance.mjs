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
  async function create(page,path,body){
    await page.getByLabel('New document path').fill(path);
    await page.getByRole('button',{name:'Create document',exact:true}).click();
    await expect(page.locator('.page-eyebrow')).toContainText(path,{timeout:30000});
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
