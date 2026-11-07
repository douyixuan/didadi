// P0 #71: genuine two-user Matrix/Chromium/Git receipt navigation.
// Isolated CI loopback only; credentials never appear in logs or artifacts.
import assert from 'node:assert/strict';
import {readFile, mkdir} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {randomUUID} from 'node:crypto';
import {chromium, expect} from '@playwright/test';

function option(key) {
  const index=process.argv.indexOf(key);
  if(index<0||index+1>=process.argv.length)throw new Error('Missing '+key);
  return process.argv[index+1];
}
const base=option('--url'),credentialsFile=option('--credentials-file');
const evidenceDir=option('--evidence-dir');
if(!/^http:\/\/(?:127\.0\.0\.1|localhost):[0-9]+$/.test(base)) {
  throw new Error('Refusing non-loopback real Matrix browser acceptance');
}
const accounts=Object.entries(JSON.parse(await readFile(credentialsFile,'utf8')));
if(accounts.length!==2||accounts.some(([id,password])=>!id.startsWith('@')||typeof password!=='string'||!password)){
  throw new Error('Expected two genuine ephemeral Matrix accounts');
}
await mkdir(evidenceDir,{recursive:true,mode:0o700});

async function call(page,path){
  return page.evaluate(async url=>{
    const response=await fetch(url,{credentials:'same-origin'});
    return {status:response.status,data:await response.json()};
  },path);
}
const browser=await chromium.launch({headless:true});
const contexts=[];
async function signIn([id,password]){
  const context=await browser.newContext({baseURL:base});
  contexts.push(context);
  const page=await context.newPage();
  await page.goto('/');
  await page.getByLabel('Matrix user ID').fill(id);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.getByRole('button',{name:/Sign out/})).toBeVisible({timeout:45000});
  const session=await call(page,'/api/session');
  assert.equal(session.status,200);
  assert.equal(session.data.userId,id);
  assert.equal(session.data.liveMatrix,true);
  return {page,session:session.data};
}
try{
  const alice=await signIn(accounts[0]);
  const bob=await signIn(accounts[1]);
  const room=alice.session.documentRoom;
  assert.equal(room,bob.session.documentRoom);
  assert.notEqual(alice.session.userId,bob.session.userId);

  const name='receipt-acceptance/'+randomUUID().replaceAll('-','')+'.md';
  const marker='P0 real cross-author Git receipt '+randomUUID().replaceAll('-','');
  await expect(alice.page.getByLabel('New document path')).toBeEnabled({timeout:30000});
  await alice.page.getByLabel('New document path').fill(name);
  await alice.page.getByRole('button',{name:'Create document'}).click();
  await expect(alice.page.locator('.page-eyebrow')).toContainText(name,{timeout:30000});
  const editor=alice.page.locator('.document-surface [contenteditable="true"]').first();
  await expect(editor).toBeVisible({timeout:30000});
  await editor.fill('# Real receipt\n\n'+marker);
  await alice.page.getByRole('button',{name:'Save changes'}).click();
  await expect(alice.page.locator('.document-statusbar')).toContainText('All changes saved',{timeout:45000});

  const saved=await call(alice.page,'/api/document?room='+encodeURIComponent(room)+'&path='+encodeURIComponent(name));
  assert.equal(saved.status,200);
  assert.match(saved.data.commit,/^[a-f0-9]{40}$/);
  assert.ok(saved.data.content.includes(marker));
  // Verify canonical Git at exact revision rather than a synthetic client snapshot.
  const immutable=execFileSync('git',['--git-dir=.local/documents.git','show',saved.data.commit+':'+name],{encoding:'utf8'});
  assert.equal(immutable,saved.data.content);

  // Matrix contains metadata-only receipts; Bob is a separate authorized member.
  const timeline=await call(bob.page,
    '/matrix/_matrix/client/v3/rooms/'+encodeURIComponent(room)+'/messages?dir=b');
  assert.equal(timeline.status,200);
  const receipt=timeline.data.chunk.find(event=>
    event.content?.['org.didadi.document.commit']?.commit===saved.data.commit);
  assert.ok(receipt,'Bob must receive the real Matrix Git-version receipt');
  assert.equal(receipt.sender,alice.session.userId);
  assert.equal(receipt.content['org.didadi.document.commit'].author,alice.session.userId);
  assert.equal(receipt.content['org.didadi.document.commit'].path,name);
  assert.ok(!JSON.stringify(receipt).includes(marker),'Matrix event leaked the Git body');

  await bob.page.reload();
  await expect(bob.page.getByRole('button',{name:name,exact:true})).toBeVisible({timeout:30000});
  await bob.page.getByRole('button',{name:name,exact:true}).click();
  await expect(bob.page.locator('.markdown-body')).toContainText(marker,{timeout:30000});
  await bob.page.getByRole('button',{name:'Discussion',exact:true}).click();
  // Before the fix, Bob saw only Alice's plain receipt, not a version button.
  const open=bob.page.locator('.timeline').getByRole('button',{name:'Open document version'});
  await expect(open).toHaveCount(2,{timeout:45000}); // create + edited Git commit
  await open.last().click();
  await expect(bob.page.getByRole('complementary',{name:'Version history'})).toBeVisible({timeout:30000});
  await expect(bob.page.locator('.markdown-body')).toContainText(marker,{timeout:30000});
  await bob.page.screenshot({path:evidenceDir+'/cross-author-git-receipt.png',fullPage:true});
  console.log('PASS REAL P0 #71 cross-user Matrix receipt -> browser Git version; commit '+saved.data.commit);
}finally{
  for(const context of contexts)await context.close();
  await browser.close();
}
