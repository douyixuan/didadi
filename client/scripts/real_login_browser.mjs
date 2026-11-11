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

  // P0 ROOM-01: real Matrix account A creates an invite-only DM for B.
  // B cannot fetch its timeline until accepting the actor-scoped Matrix invite.
  const directName = 'Real DM ' + randomUUID().slice(0, 8);
  await alice.page.getByLabel('Room type').selectOption('direct');
  await alice.page.getByLabel('Matrix user ID to invite').fill(accounts[1][0]);
  await alice.page.getByRole('button', {name: 'Add person'}).click();
  await alice.page.getByLabel('New local room name').fill(directName);
  await alice.page.getByRole('button', {name: 'Create local room'}).click();
  await expect(alice.page.getByText('Private room created.', {exact: true}))
    .toBeVisible({timeout: 45000});
  const aliceDirectButton = alice.page.locator('nav[aria-label="Rooms"] button.room')
    .filter({hasText: directName});
  await expect(aliceDirectButton).toHaveClass(/room-selected/, {timeout: 30000});
  const createdDirect = new URL(alice.page.url()).searchParams.get('room');
  assert.ok(createdDirect?.startsWith('!'), 'Creator must select the real Matrix room ID');
  // Prove that the creator's live Synapse state contains the invite event;
  // local room registration or a successful createRoom response alone is not
  // proof that Synapse accepted Bob's membership.
  const creatorState = await browserRequest(alice.page,
    '/matrix/_matrix/client/v3/rooms/' + encodeURIComponent(createdDirect) + '/state');
  assert.equal(creatorState.status, 200);
  assert.equal(creatorState.data.find(event =>
    event.type === 'm.room.member' && event.state_key === accounts[1][0])?.content?.membership,
  'invite', 'The creator must observe a genuine Matrix invite for Bob');

  // Room creation and invite delivery are separate asynchronous Matrix events.
  // A single immediate /sync can race the account stream update. Bound the
  // retry, keep the exact room-ID assertion, and never fabricate an invitation.
  let pending = null;
  try {
    await expect.poll(async () => {
      const invited = await browserRequest(bob.page, '/api/rooms/invites');
      assert.equal(invited.status, 200, 'Invitation discovery needs a real authenticated session');
      assert.ok(Array.isArray(invited.data.invites));
      pending = invited.data.invites.find(item => item.room === createdDirect) ?? null;
      return pending !== null;
    }, {timeout: 30000, intervals: [250, 500, 1000, 2000]}).toBe(true);
  } catch (error) {
    // These diagnostics are aggregate-only: no bearer token, user ID, room ID,
    // Matrix invite body or browser storage is written to CI logs.
    const joined = await browserRequest(bob.page, '/matrix/_matrix/client/v3/joined_rooms')
      .catch(() => ({status: 0, data: {}}));
    console.error('INVITE_DELIVERY_TIMEOUT creator=invite bob_joined_count=' +
      (joined.status === 200 && Array.isArray(joined.data?.joined_rooms)
        ? joined.data.joined_rooms.length : 'unavailable'));
    throw error;
  }
  assert.ok(pending.room.startsWith('!'), 'An invitation needs a real Synapse room ID');
  const unauthorizedBeforeJoin = await browserRequest(bob.page,
    '/matrix/_matrix/client/v3/rooms/' + encodeURIComponent(pending.room) + '/messages?dir=b');
  assert.equal(unauthorizedBeforeJoin.status, 403, 'Invite alone cannot read room history');
  const unrelated = await browserRequest(bob.page, '/api/rooms/join', {room: '!foreign:localhost'});
  assert.equal(unrelated.status, 403, 'A known Matrix account cannot join an unregistered room');
  // The invitee's actual UI must notice the new server invitation on its own.
  // Probing the API above is not sufficient browser acceptance.
  await expect(bob.page.getByRole('button', {name: 'Join invitation ' + pending.name}))
    .toBeVisible({timeout: 30000});
  await bob.page.getByRole('button', {name: 'Join invitation ' + pending.name}).click();
  const joinedDirect = bob.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText: directName});
  await expect(joinedDirect).toHaveClass(/room-selected/, {timeout: 30000});
  const directSecret = 'DM after join ' + randomUUID().replaceAll('-', '');
  const discussionPanel = bob.page.locator('.collaboration-panel');
  if (await discussionPanel.evaluate(element => element.classList.contains('panel-closed'))) {
    await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  }
  await bob.page.locator('.composer textarea').fill(directSecret);
  await bob.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
  await expect(bob.page.locator('.timeline')).toContainText(directSecret, {timeout: 45000});
  await alice.page.getByRole('button', {name: 'Refresh rooms'}).click();
  const aliceDirect = alice.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText: directName});
  await aliceDirect.click();
  await expect(alice.page.locator('.timeline')).toContainText(directSecret, {timeout: 45000});
  await bob.page.reload();
  await expect(bob.page.locator('nav[aria-label="Rooms"] button.room').filter({hasText: directName}))
    .toBeVisible({timeout: 30000});
  // Reload closes the collaboration pane; the later private-room composer
  // must be visibly reopened or the real Chromium test stalls on a hidden input.
  await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  console.log('PASS REAL ROOM #70: creator UI, Matrix invitation, before-join denial, joined DM, reload');

  // ROOM-03: unread must be a genuine per-user Matrix notification counter,
  // not a local UI increment. A message in the unselected DM creates unread
  // for Alice; viewing the real timeline acknowledges only that room.
  await alice.page.goto('/?room=' + encodeURIComponent(alice.session.initialRoom));
  await expect(alice.page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 30000});
  assert.equal(new URL(alice.page.url()).searchParams.get('room'), alice.session.initialRoom,
    'Alice must leave the DM selected before the unread test');
  const unreadText = 'Unread DM ' + randomUUID().replaceAll('-', '');
  await bob.page.locator('.composer textarea').fill(unreadText);
  await bob.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
  await expect(bob.page.locator('.timeline')).toContainText(unreadText, {timeout: 45000});
  let unreadProbe = {present: false, count: -1, roomCount: 0};
  try {
    await expect.poll(async () => {
      const result = await browserRequest(alice.page, '/api/rooms/unread');
      assert.equal(result.status, 200, 'Unread snapshot must use Alice real session');
      const counts = result.data.unread || {};
      unreadProbe = {present: Object.prototype.hasOwnProperty.call(counts, createdDirect),
        count: counts[createdDirect] ?? -1, roomCount: Object.keys(counts).length};
      return counts[createdDirect] ?? 0;
    }, {timeout: 30000, intervals: [500, 1000, 2000]}).toBeGreaterThan(0);
  } catch (error) {
    // Aggregate-only diagnostics: no room IDs, account names, content or tokens.
    console.error('UNREAD_MATRIX_DIAGNOSTIC=' + JSON.stringify(unreadProbe));
    throw error;
  }
  const unreadDirect = alice.page.locator('nav[aria-label="Rooms"] button.room')
    .filter({hasText: directName});
  await expect(unreadDirect.getByLabel('Unread messages in ' + directName))
    .toBeVisible({timeout: 30000});
  await unreadDirect.click();
  const aliceDiscussion = alice.page.locator('.collaboration-panel');
  if (await aliceDiscussion.evaluate(node => node.classList.contains('panel-closed'))) {
    await alice.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  }
  await expect(alice.page.locator('.timeline')).toContainText(unreadText, {timeout: 45000});
  await expect.poll(async () => {
    const result = await browserRequest(alice.page, '/api/rooms/unread');
    assert.equal(result.status, 200);
    return result.data.unread?.[createdDirect] ?? -1;
  }, {timeout: 30000, intervals: [500, 1000, 2000]}).toBe(0);
  await alice.page.reload();
  await expect(alice.page.getByRole('button', {name: /Sign out/})).toBeVisible({timeout: 30000});
  await expect(alice.page.locator('nav[aria-label="Rooms"] button.room')
    .filter({hasText: directName}).getByLabel('Unread messages in ' + directName))
    .toHaveCount(0, {timeout: 30000});
  // A non-member cannot use read markers to touch a private room.
  const forbiddenRead = await browserRequest(alice.page, '/api/rooms/read',
    {room: '!foreign:localhost', event: '$other'});
  assert.equal(forbiddenRead.status, 403);
  console.log('PASS REAL ROOM #70: server-derived unread, visible read receipt, refresh and denied foreign read');




  // ROOM-01/04: actual group and channel browser creation, invite, authorization
  // and messaging. Existing synthetic room-type tests are not an E2E substitute.
  for (const kind of ['group', 'channel']) {
    const roomName = 'Real ' + kind + ' ' + randomUUID().slice(0, 8);
    await alice.page.getByLabel('Room type').selectOption(kind);
    await alice.page.getByLabel('Matrix user ID to invite').fill(accounts[1][0]);
    await alice.page.getByRole('button', {name: 'Add person'}).click();
    await alice.page.getByLabel('New local room name').fill(roomName);
    await alice.page.getByRole('button', {name: 'Create local room'}).click();
    await expect(alice.page.getByText('Private room created.', {exact: true}))
      .toBeVisible({timeout: 45000});
    const roomId = new URL(alice.page.url()).searchParams.get('room');
    assert.ok(roomId?.startsWith('!'), kind + ': room must have a real Matrix ID');
    const roomState = await browserRequest(alice.page,
      '/matrix/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/state');
    assert.equal(roomState.status, 200);
    assert.equal(roomState.data.find(e => e.type === 'org.didadi.room')?.content?.kind, kind);
    assert.equal(roomState.data.find(e => e.type === 'm.room.member' &&
      e.state_key === accounts[1][0])?.content?.membership, 'invite');

    const deniedUntilJoin = await browserRequest(bob.page,
      '/matrix/_matrix/client/v3/rooms/' + encodeURIComponent(roomId) + '/messages?dir=b');
    assert.equal(deniedUntilJoin.status, 403, kind + ': invite alone must not grant history');
    let visibleInvite = null;
    await expect.poll(async () => {
      const response = await browserRequest(bob.page, '/api/rooms/invites');
      assert.equal(response.status, 200);
      visibleInvite = response.data.invites.find(item => item.room === roomId) ?? null;
      return visibleInvite !== null;
    }, {timeout: 30000, intervals: [250, 500, 1000, 2000]}).toBe(true);
    const join = bob.page.getByRole('button', {name: 'Join invitation ' + visibleInvite.name});
    await expect(join).toBeVisible({timeout: 30000});
    await join.click();
    const bobRoom = bob.page.locator('nav[aria-label="Rooms"] button.room')
      .filter({hasText: roomName});
    await expect(bobRoom).toHaveClass(/room-selected/, {timeout: 30000});

    const text = kind + ' shared message ' + randomUUID().replaceAll('-', '');
    const panel = bob.page.locator('.collaboration-panel');
    if (await panel.evaluate(node => node.classList.contains('panel-closed'))) {
      await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
    }
    await bob.page.locator('.composer textarea').fill(text);
    await bob.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
    await expect(bob.page.locator('.timeline')).toContainText(text, {timeout: 45000});
    await alice.page.getByRole('button', {name: 'Refresh rooms'}).click();
    const aliceRoom = alice.page.locator('nav[aria-label="Rooms"] button.room')
      .filter({hasText: roomName});
    await aliceRoom.click();
    await expect(alice.page.locator('.timeline')).toContainText(text, {timeout: 45000});
    const reply = kind + ' creator reply ' + randomUUID().replaceAll('-', '');
    await alice.page.locator('.composer textarea').fill(reply);
    await alice.page.locator('.composer').getByRole('button', {name: /^Send/}).click();
    await expect(alice.page.locator('.timeline')).toContainText(reply, {timeout: 45000});
    await expect(bob.page.locator('.timeline')).toContainText(reply, {timeout: 45000});
    await bob.page.reload();
    await expect(bob.page.locator('nav[aria-label="Rooms"] button.room')
      .filter({hasText: roomName})).toBeVisible({timeout: 30000});
  }
  console.log('PASS REAL ROOM #70: group/channel create, Matrix invite, denial, joined messaging and reload');

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
  // The group/channel reload above closes Bob's discussion panel. Reopen it
  // before the later departed-room composer check (otherwise this is a hidden UI).
  const privatePanel = bob.page.locator('.collaboration-panel');
  if (await privatePanel.evaluate(node => node.classList.contains('panel-closed'))) {
    await bob.page.getByRole('button', {name: 'Discussion', exact: true}).click();
  }
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
