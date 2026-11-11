"""Real Synapse + loopback client HTTP sign-in/isolation smoke.

Requires an explicitly isolated local fixture with two *real* Matrix account
passwords. This is not a browser/IME acceptance and is never run offline.
"""
import argparse
from pathlib import Path
import json
import os
import secrets
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.matrix_as import PREFIX
from src.matrix_http import segment
from src.runtime_socket import loopback_url


def run(base, credentials, restart_proof=None):
    loopback_url(base, 'http')
    if not isinstance(credentials, dict) or len(credentials) != 2:
        raise ValueError('Expected exactly two locally generated Matrix login accounts.')
    identities = list(credentials.items())

    def call(path, method='GET', payload=None, cookie=None, csrf=None, login=False):
        headers = {'Origin': base}
        if cookie:
            headers['Cookie'] = cookie
        if csrf:
            headers['X-CSRF-Token'] = csrf
        if login:
            headers['X-Didadi-Login'] = '1'
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = Request(base + path, method=method, headers=headers,
                      data=None if payload is None else json.dumps(payload).encode())
        with urlopen(req, timeout=20) as response:
            return json.load(response), response.headers.get('Set-Cookie', '').split(';', 1)[0]

    def denied(status, *args, **kwargs):
        try:
            call(*args, **kwargs)
        except HTTPError as exc:
            assert exc.code == status, ('Unexpected response', exc.code, status)
            return
        raise AssertionError('Unauthorized operation unexpectedly succeeded.')

    denied(401, '/api/session')
    sessions = []
    for user_id, password in identities:
        # The password is never printed, put in a query string or persisted by this script.
        login, cookie = call('/api/auth/login', 'POST',
                             {'username': user_id, 'password': password}, login=True)
        assert login['userId'] == user_id and cookie.startswith('didadi_session=')
        session, _ = call('/api/session', cookie=cookie)
        assert session['userId'] == user_id and session['liveMatrix'] is True
        assert session['documentSave'] == 'direct-v1'
        assert not ({'password', 'access_token'} & set(session))
        refresh, _ = call('/api/session', cookie=cookie)
        assert refresh['userId'] == user_id and refresh['csrf'] == session['csrf']
        sessions.append((user_id, cookie, session))
    alice, bob = sessions
    assert alice[2]['userId'] != bob[2]['userId']
    assert alice[2]['csrf'] != bob[2]['csrf']
    room = alice[2]['documentRoom']
    assert room == bob[2]['documentRoom']
    for user_id, cookie, session in sessions:
        rooms, _ = call('/matrix' + PREFIX + '/joined_rooms', cookie=cookie)
        assert room in rooms['joined_rooms'], (user_id, 'must join workspace room')
    print('PASS REAL MATRIX sign-in, refresh, two users, shared-room membership')

    path = '/matrix' + PREFIX + '/rooms/' + segment(room)
    transaction = 'auth-' + secrets.token_hex(8)
    event, _ = call(path + '/send/m.room.message/' + transaction,
                    'PUT', {'msgtype': 'm.text', 'body': 'Real Matrix login smoke ' + transaction,
                            'm.mentions': {'user_ids': []}},
                    cookie=alice[1], csrf=alice[2]['csrf'])
    observed, _ = call(path + '/event/' + segment(event['event_id']),
                       cookie=bob[1], csrf=bob[2]['csrf'])
    assert observed['sender'] == alice[0] and observed['event_id'] == event['event_id']
    print('PASS REAL MATRIX authenticated Alice message readable by Bob')

    name = 'auth-validation/' + secrets.token_hex(12) + '.md'
    body = '# Real login integration\n\nCreated by ' + alice[0] + '\n'
    created, _ = call('/api/documents', 'POST', {'room': room, 'name': name,
                       'content': body, 'operation': str(uuid.uuid4())},
                      cookie=alice[1], csrf=alice[2]['csrf'])
    assert created['status'] == 'saved'
    assert len(created['commit']) == 40
    document, _ = call('/api/document?' + urlencode({'room': room, 'path': name}),
                       cookie=bob[1], csrf=bob[2]['csrf'])
    assert document['content'] == body and document['commit'] == created['commit']
    denied(403, '/api/document?' + urlencode({'room': '!outside:localhost', 'path': name}),
           cookie=bob[1], csrf=bob[2]['csrf'])
    # A second file must retain an independent Git body/version. It is saved
    # through Document Service; neither document body belongs in Matrix events.
    second_name = 'auth-validation/' + secrets.token_hex(12) + '.md'
    second_body = '# Second independent file\n\n' + secrets.token_hex(16) + '\n'
    second, _ = call('/api/documents', 'POST', {'room': room, 'name': second_name,
                      'content': second_body, 'operation': str(uuid.uuid4())},
                     cookie=alice[1], csrf=alice[2]['csrf'])
    assert second['status'] == 'saved' and second['path'] == second_name
    first_again, _ = call('/api/document?' + urlencode({'room': room, 'path': name}),
                          cookie=bob[1])
    second_again, _ = call('/api/document?' + urlencode({'room': room, 'path': second_name}),
                           cookie=bob[1])
    # A document snapshot without ?commit uses the entire Git repository HEAD.
    # Adding the second document advances HEAD even though the first blob is unchanged.
    assert first_again['content'] == body and first_again['blob'] == created['blob']
    assert second_again['content'] == second_body and second_again['blob'] == second['blob']
    assert first_again['commit'] == second_again['commit'] == second['commit']
    assert second['commit'] != created['commit']
    historical, _ = call('/api/document?' + urlencode({
        'room': room, 'path': name, 'commit': created['commit']}), cookie=bob[1])
    assert historical['content'] == body and historical['blob'] == created['blob']
    assert historical['commit'] == created['commit']

    # Room members without power-level 50 may read but cannot publish Git content.
    denied(403, '/api/documents/' + name, 'PUT',
           {'room': room, 'content': 'unauthorized overwrite',
            'base_blob': created['blob'], 'operation': str(uuid.uuid4())},
           cookie=bob[1], csrf=bob[2]['csrf'])
    assert call('/api/document?' + urlencode({'room': room, 'path': name}),
                cookie=alice[1])[0]['content'] == body

    for saved, secret_body in ((created, body), (second, second_body)):
        assert not saved['receipt_pending'] and saved['receipt']['event_id']
        receipt, _ = call(path + '/event/' + segment(saved['receipt']['event_id']),
                          cookie=bob[1])
        metadata = receipt['content']['org.didadi.document.commit']
        assert metadata['path'] == saved['path'] and metadata['commit'] == saved['commit']
        assert metadata['author'] == alice[0]
        assert secret_body not in json.dumps(receipt)
        assert receipt['content']['body'].startswith('Saved ')
    print('PASS REAL GIT two documents, stable versions, denied write and metadata-only receipts')

    # P0 #71 DOC-01/DOC-04 real-service acceptance: move the *second*
    # document without disturbing the first document or its restart proof.
    # This runs in the trusted isolated Synapse + Document API + Git job;
    # unlike the synthetic client smoke, both sessions are real Matrix users.
    moved_name = 'auth-validation/renamed-' + secrets.token_hex(12) + '.md'
    move_payload = {'room': room, 'source': second_name, 'name': moved_name,
                    'base_blob': second['blob'], 'operation': str(uuid.uuid4())}
    moved, _ = call('/api/documents/move', 'POST', move_payload,
                    cookie=alice[1], csrf=alice[2]['csrf'])
    assert moved['status'] == 'saved'
    assert moved['path'] == moved_name
    assert moved['blob'] == second['blob'], 'Move rewrote the Markdown blob'
    assert moved['commit'] != second['commit'], 'Move did not record Git history'
    retried, _ = call('/api/documents/move', 'POST', move_payload,
                      cookie=alice[1], csrf=alice[2]['csrf'])
    assert retried['commit'] == moved['commit'], 'Same operation duplicated Git effects'
    relocated, _ = call('/api/document?' + urlencode({'room': room, 'path': moved_name}),
                        cookie=bob[1])
    assert relocated['content'] == second_body and relocated['blob'] == second['blob']
    no_longer_current, _ = call('/api/document?' + urlencode({
        'room': room, 'path': second_name}), cookie=bob[1])
    assert no_longer_current['blob'] is None, 'Old path still resolves in current Git tree'
    original_revision, _ = call('/api/document?' + urlencode({
        'room': room, 'path': second_name, 'commit': second['commit']}), cookie=bob[1])
    assert original_revision['content'] == second_body
    assert original_revision['blob'] == second['blob']
    retained_first, _ = call('/api/document?' + urlencode({'room': room, 'path': name}),
                             cookie=bob[1])
    assert retained_first['content'] == body and retained_first['blob'] == created['blob']
    # The same Matrix membership must not imply write authority.
    denied(403, '/api/documents/move', 'POST',
           {'room': room, 'source': moved_name, 'name': 'forbidden.md',
            'base_blob': moved['blob'], 'operation': str(uuid.uuid4())},
           cookie=bob[1], csrf=bob[2]['csrf'])
    denied(400, '/api/documents/move', 'POST',
           {'room': room, 'source': moved_name, 'name': '../escape.md',
            'base_blob': moved['blob'], 'operation': str(uuid.uuid4())},
           cookie=alice[1], csrf=alice[2]['csrf'])
    assert moved['receipt'] and not moved['receipt_pending']
    receipt_event, _ = call(path + '/event/' + segment(moved['receipt']['event_id']),
                            cookie=bob[1])
    receipt_meta = receipt_event['content']['org.didadi.document.commit']
    assert receipt_meta['path'] == moved_name and receipt_meta['commit'] == moved['commit']
    assert receipt_meta['author'] == alice[0]
    assert second_body not in json.dumps(receipt_event), 'Move leaked document body into Matrix'
    print('PASS REAL GIT document move: byte-exact, immutable history, idempotent, forbidden write/path, metadata receipt')

    # A genuine room created by Bob becomes available only to Bob. The global
    # local room index must never override live Matrix membership checks.
    private, _ = call('/api/rooms', 'POST',
                      {'name': 'Private verification ' + secrets.token_hex(4),
                       'kind': 'group', 'participants': [], 'operation': str(uuid.uuid4())},
                      cookie=bob[1], csrf=bob[2]['csrf'])
    private_room = private['room_id']
    assert private_room != room
    alice_rooms, _ = call('/matrix' + PREFIX + '/joined_rooms', cookie=alice[1])
    bob_rooms, _ = call('/matrix' + PREFIX + '/joined_rooms', cookie=bob[1])
    assert private_room in bob_rooms['joined_rooms']
    assert private_room not in alice_rooms['joined_rooms']
    denied(403, '/matrix' + PREFIX + '/rooms/' + segment(private_room) + '/messages?dir=b',
           cookie=alice[1])
    print('PASS REAL MATRIX two-user private-room membership isolation')

    denied(401, '/api/auth/login', 'POST',
           {'username': alice[0], 'password': 'invalid-login-password'}, login=True)
    denied(403, '/api/auth/logout', 'POST', {}, cookie=bob[1], csrf=alice[2]['csrf'])
    done, _ = call('/api/auth/logout', 'POST', {}, cookie=alice[1], csrf=alice[2]['csrf'])
    assert done['status'] == 'signed_out' and done['matrix_revocation'] == 'confirmed'
    denied(401, '/api/session', cookie=alice[1])
    assert call('/api/session', cookie=bob[1])[0]['userId'] == bob[0]
    print('PASS REAL MATRIX wrong password, CSRF isolation and current-device logout')
    # Keep one genuine device cookie private for the independently restarted
    # backend to verify rehydration without a new Matrix password login.
    # This file is sensitive local test state. Never upload it as a CI artifact.
    if restart_proof is not None:
        path = Path(restart_proof)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        descriptor = os.open(path, flags, 0o600)
        with os.fdopen(descriptor, 'w') as out:
            json.dump({'user': bob[0], 'cookie': bob[1], 'csrf': bob[2]['csrf'],
                       'room': room, 'path': name, 'commit': created['commit'],
                       'body': body}, out)
    # Leave Bob's real device active until --check-restart-proof revokes it.
    return created['commit']


def verify_restart(base, restart_proof):
    """Prove a new HTTP server process restored the same live Matrix device."""
    loopback_url(base, 'http')
    record_path = Path(restart_proof)
    record = json.loads(record_path.read_text())
    headers = {'Cookie': record['cookie'], 'Origin': base}
    def retrieve(route):
        with urlopen(Request(base + route, headers=headers), timeout=20) as response:
            return json.load(response)
    session = retrieve('/api/session')
    assert session['liveMatrix'] is True
    assert session['userId'] == record['user']
    assert session['csrf'] == record['csrf']
    doc = retrieve('/api/document?' + urlencode({
        'room': record['room'], 'path': record['path']}))
    assert doc['content'] == record['body']
    # The default revision is repository HEAD; another document may advance it.
    # The original version must still be available via its immutable commit.
    pinned = retrieve('/api/document?' + urlencode({
        'room': record['room'], 'path': record['path'], 'commit': record['commit']}))
    assert pinned['content'] == record['body'] and pinned['commit'] == record['commit']
    # The verified original handle is locally revoked and upstream logout
    # is attempted. A stale cookie cannot rehydrate again on any new process.
    request = Request(base + '/api/auth/logout', method='POST',
        headers={**headers, 'Content-Type': 'application/json',
                 'X-CSRF-Token': record['csrf']}, data=b'{}')
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
        assert result['status'] == 'signed_out'
        assert result['matrix_revocation'] == 'confirmed', 'Real Synapse must revoke this device'
    try:
        retrieve('/api/session')
        raise AssertionError('Logged out cookie rehydrated after backend restart')
    except HTTPError as error:
        assert error.code == 401
    # Do not retain a plaintext cookie even in ephemeral CI state.
    record_path.unlink()
    print('PASS REAL SYNAPSE device survives actual backend process restart and Git read, then logs out')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8791')
    parser.add_argument('--credentials-file',
                        help='private local smoke-passwords.json; do not commit it')
    parser.add_argument('--restart-proof',
                        help='write one private one-time session record for a subsequent backend restart')
    parser.add_argument('--check-restart-proof',
                        help='after restarting the backend, validate and revoke the retained device')
    args = parser.parse_args()
    if args.check_restart_proof:
        if args.credentials_file or args.restart_proof:
            parser.error('Restart verification must not accept new credentials')
        verify_restart(args.url, args.check_restart_proof)
        return
    if not args.credentials_file:
        parser.error('--credentials-file is required')
    creds = json.loads(Path(args.credentials_file).read_text())
    commit = run(args.url, creds, args.restart_proof)
    print('REAL SYNAPSE HTTP acceptance complete. Git commit:', commit)
    print('NOT verified: physical browser/IME or public deployment. Restart checked separately.')


if __name__ == '__main__':
    main()
