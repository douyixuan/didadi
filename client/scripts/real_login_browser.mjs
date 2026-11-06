// Genuine browser acceptance against an isolated, running Synapse + Git workspace.
// Invoke ONLY from the explicitly approved Real Matrix integration workflow.
// Never use fixture credentials, Vercel preview, public accounts or a mocked server.
import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
import {chromium, expect} from '@playwright/test';

function option(name, fallback = null) {
  const index = process.argv.indexOf(name);
  if (index < 0) return fallback;
  if (index + 1 >= process.argv.length) throw new Error('Missing value for ' + name);
  return process.argv[index + 1];
}

const base = option('--url', 'http://127.0.0.1:8791');
const credentialsFile = option('--credentials-file');
const evidenceDir = option('--evidence-dir', '.local/real-login-browser');
if (!credentialsFile) throw new Error('--credentials-file is required');
if (!/^http:\/\/(?:127\.0\.0\.1|localhost):[0-9]+$/.test(base)) {
  throw new Error('Browser real-login acceptance is restricted to a loopback server');
}
const accounts = Object.entries(JSON.parse(await readFile(credentialsFile, 'utf8')));
if (accounts.length !== 2 || accounts.some(([user, secret]) =>
  !user.startsWith('@') || typeof secret !== 'string' || !secret)) {
  throw new Error('Expected two genuine private Matrix accounts');
}
await mkdir(evidenceDir, {recursive: true, mode: 0o700});

async function browserRequest(page, path, body = undefined) {
  return page.evaluate(async ({path, body}) => {
    const sessionResponse = await fetch('/api/session', {credentials: 'same-origin'});
    const session = await sessionResponse.json();
    const headers = {'X-CSRF-Token': session.csrf};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    const response = await fetch(path, {
      credentials: 'same-origin',
      method: body === undefined ? 'GET' : 'POST',
      headers,
      ...(body === undefined ? {} : {body: JSON.stringify(body)}),
    });
    return {status: response.status, data: await response.json()};
  }, {path, body});
}

const browser = await chromium.launch({headless: true});
const opened = [];
async function signIn(userId, password) {
  const context = await browser.newContext({baseURL: base});
  const page = await context.newPage();
  opened.push({page, context});
  await page.goto('/');
  await expect(page.getByRole('main', {name: 'Matrix sign in'})).toBeVisible();
  await page.getByLabel('Matrix user ID').fill(userId);
  await page.getByLabel('Password').fill(password);
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 45000});
  const response = await page.evaluate(async () => {
    const r = await fetch('/api/session', {credentials: 'same-origin'});
    return {status: r.status, session: await r.json()};
  });
  assert.equal(response.status, 200);
  assert.equal(response.session.userId, userId);
  assert.equal(response.session.liveMatrix, true);
  assert.equal(response.session.documentSave, 'direct-v1');
  assert.ok(!JSON.stringify(response.session).includes('access_token'));
  const cookie = (await context.cookies()).find(c => c.name === 'didadi_session');
  assert.ok(cookie?.httpOnly && cookie.sameSite === 'Strict', 'real cookie must be HttpOnly/SameSite Strict');
  assert.ok(!await page.evaluate(() => document.cookie.includes('didadi_session=')));
  return {context, page, session: response.session, cookie: cookie.value};
}

let proof = null;
try {
  const alice = await signIn(...accounts[0]);
  const bob = await signIn(...accounts[1]);
  assert.notEqual(alice.session.userId, bob.session.userId);
  assert.notEqual(alice.session.csrf, bob.session.csrf);
  assert.notEqual(alice.cookie, bob.cookie);

  // Real UI creates a new Markdown document using the current user's session.
  const marker = 'Browser proof ' + randomUUID().replaceAll('-', '');
  const name = 'browser-proof/' + randomUUID().replaceAll('-', '') + '.md';
  await expect(alice.page.getByLabel('New document path')).toBeEnabled({timeout: 30000});
  await alice.page.getByLabel('New document path').fill(name);
  await alice.page.getByRole('button', {name: 'Create document'}).click();
  await expect(alice.page.locator('.page-eyebrow')).toContainText(name, {timeout: 30000});
  await alice.page.getByRole('button', {name: 'Edit', exact: true}).click();
  const editor = alice.page.locator('.document-surface [contenteditable="true"]').first();
  await expect(editor).toBeVisible({timeout: 30000});
  await editor.fill(marker);
  await expect(alice.page.getByText('Unsaved changes', {exact: true})).toBeVisible();
  await alice.page.getByRole('button', {name: 'Save changes'}).click();
  await expect(alice.page.locator('.document-statusbar')).toContainText('All changes saved', {timeout: 45000});

  // The browser reads the actual Document API; the workflow independently
  // verifies this exact immutable revision against the bare Git repository.
  const saved = await browserRequest(alice.page,
    '/api/document?room=' + encodeURIComponent(alice.session.documentRoom) +
    '&path=' + encodeURIComponent(name));
  assert.equal(saved.status, 200);
  assert.ok(saved.data.content.includes(marker));
  assert.match(saved.data.commit, /^[0-9a-f]{40}$/);
  proof = {path: name, commit: saved.data.commit, marker};

  await alice.page.reload();
  await expect(alice.page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 30000});
  await bob.page.reload();
  await expect(bob.page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 30000});
  await expect(bob.page.getByRole('button', {name: name})).toBeVisible({timeout: 30000});
  await bob.page.getByRole('button', {name: name}).click();
  await expect(bob.page.locator('.markdown-body')).toContainText(marker, {timeout: 30000});
  await bob.page.getByRole('button', {name: 'Edit', exact: true}).click();
  await expect(bob.page.getByRole('button', {name: 'Save changes'})).toBeDisabled();

  // Browser-to-Matrix messaging must be visible to the other real account.
  const message = 'Browser message ' + randomUUID().replaceAll('-', '');
  await alice.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  await alice.page.locator('.composer textarea').fill(message);
  await alice.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
  await expect(alice.page.locator('.timeline')).toContainText(message, {timeout: 45000});
  await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  await bob.page.reload();
  await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  await expect(bob.page.locator('.timeline')).toContainText(message, {timeout: 45000});

  // A private Bob-only Matrix room must not be visible to Alice.
  const privateName = 'Browser private ' + randomUUID().slice(0, 8);
  const privateRoom = await browserRequest(bob.page, '/api/rooms', {
    name: privateName,
    kind: 'group', participants: [], operation: randomUUID(),
  });
  assert.equal(privateRoom.status, 200, 'Bob should be able to create a real private room');
  const isolated = await browserRequest(alice.page,
    '/matrix/_matrix/client/v3/rooms/' +
    encodeURIComponent(privateRoom.data.room_id) + '/messages?dir=b');
  assert.equal(isolated.status, 403, 'Alice must be denied Bob-only room content');

  // Genuine Matrix member leaves a room from the browser. Its earlier
  // private timeline must disappear and every old HTTP room route be denied.
  // This is a #70 membership-revocation slice, not full #70 acceptance.
  await bob.page.getByRole('button', {name: 'Refresh rooms'}).click();
  const newPrivate = bob.page.locator('nav[aria-label="Rooms"] button.room')
    .filter({hasText: privateName});
  await expect(newPrivate).toBeVisible({timeout: 30000});
  await newPrivate.click();
  await expect(newPrivate).toHaveClass(/room-selected/, {timeout: 30000});
  const privateMessage = 'Departed room secret ' + randomUUID().replaceAll('-', '');
  await bob.page.locator('.composer textarea').fill(privateMessage);
  await bob.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
  await expect(bob.page.locator('.timeline')).toContainText(privateMessage, {timeout: 45000});
  const deniedLeave = await browserRequest(alice.page, '/api/rooms/leave',
    {room: privateRoom.data.room_id});
  assert.equal(deniedLeave.status, 403, 'Non-member cannot leave another account room');
  await bob.page.getByRole('button', {name: 'Leave current room'}).click();
  await expect(newPrivate).toHaveCount(0, {timeout: 30000});
  await expect(bob.page.locator('.timeline')).not.toContainText(privateMessage, {timeout: 30000});
  const departedRead = await browserRequest(bob.page,
    '/matrix/_matrix/client/v3/rooms/' +
    encodeURIComponent(privateRoom.data.room_id) + '/messages?dir=b');
  assert.equal(departedRead.status, 403, 'Live membership must deny departed-room history');
  const departedAgain = await browserRequest(bob.page, '/api/rooms/leave',
    {room: privateRoom.data.room_id});
  assert.equal(departedAgain.status, 403, 'Repeated leave cannot reacquire membership');
  console.log('PASS REAL ROOM #70: browser room leave, message eviction, non-member denial, denied stale reads');

  // Wrong passwords are genuinely rejected; current-device logout must not
  // invalidate another browser's real Matrix session or shared Git document.
  const invalid = await browser.newContext({baseURL: base});
  const invalidPage = await invalid.newPage();
  opened.push({context: invalid, page: invalidPage});
  await invalidPage.goto('/');
  await invalidPage.getByLabel('Matrix user ID').fill(accounts[0][0]);
  await invalidPage.getByLabel('Password').fill('wrong-browser-password');
  // The HTTP smoke immediately before the browser already used real password
  // logins from this same loopback IP. Synapse can temporarily reply 429
  // (rc_login.address); that is NOT proof an incorrect password was rejected.
  // Retry only after the reported cooldown and require an actual 401.
  let invalidPasswordRejected = false;
  for (let attempt = 0; attempt < 4; attempt++) {
    await invalidPage.getByLabel('Password').fill('wrong-browser-password');
    const loginResponse = invalidPage.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/auth/login' &&
      response.request().method() === 'POST');
    await invalidPage.getByRole('button', {name: 'Sign in', exact: true}).click();
    const response = await loginResponse;
    if (response.status() === 429) {
      if (attempt === 3) throw new Error('Matrix login limiter did not recover after bounded retries');
      const body = await response.json().catch(() => ({}));
      const reported = Number(body.retry_after_ms);
      const pause = Number.isFinite(reported) && reported > 0
        ? Math.min(45000, Math.max(1500, reported + 500)) : 12000;
      console.log('Real Matrix login rate-limited; retrying invalid-password check after cooldown');
      await invalidPage.waitForTimeout(pause);
      continue;
    }
    assert.equal(response.status(), 401, 'Wrong password must yield a real Matrix 401, not a transport error');
    await expect(invalidPage.getByRole('alert')).toContainText(/Matrix rejected/, {timeout: 20000});
    invalidPasswordRejected = true;
    break;
  }
  assert.equal(invalidPasswordRejected, true, 'Wrong password was never rejected by Matrix');
  await expect(invalidPage.getByRole('main', {name: 'Matrix sign in'})).toBeVisible();

  await alice.page.getByRole('button', {name: /Sign out/}).click();
  await expect(alice.page.getByRole('main', {name: 'Matrix sign in'})).toBeVisible({timeout: 30000});
  const signedOut = await alice.page.evaluate(async () =>
    (await fetch('/api/session', {credentials: 'same-origin'})).status);
  assert.equal(signedOut, 401);
  await bob.page.reload();
  await expect(bob.page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 30000});
  const stillThere = await browserRequest(bob.page,
    '/api/document?room=' + encodeURIComponent(bob.session.documentRoom) +
    '&path=' + encodeURIComponent(name));
  assert.equal(stillThere.status, 200);
  assert.ok(stillThere.data.content.includes(marker));

  await writeFile(evidenceDir + '/git-proof.json', JSON.stringify(proof, null, 2),
    {mode: 0o600});
  await bob.page.screenshot({path: evidenceDir + '/authenticated-document.png', fullPage: true});
  console.log('PASS REAL BROWSER: two Matrix logins, password rejection, persisted cookies, UI Git save, cross-user read-only, Matrix messages, room isolation and sign-out');
  console.log('GIT proof path=' + proof.path + ' commit=' + proof.commit);
} catch (error) {
  for (let index = 0; index < opened.length; index++) {
    const page = opened[index].page;
    if (!page.isClosed()) {
      await page.screenshot({path: evidenceDir + '/failure-' + index + '.png', fullPage: true}).catch(() => {});
    }
  }
  throw error;
} finally {
  await browser.close();
}
