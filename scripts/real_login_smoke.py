"""Real Synapse + loopback client HTTP sign-in/isolation smoke.

Requires an explicitly isolated local fixture with two *real* Matrix account
passwords. This is not a browser/IME acceptance and is never run offline.
"""
import argparse
from pathlib import Path
import json
import secrets
import uuid
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.matrix_as import PREFIX
from src.matrix_http import segment
from src.runtime_socket import loopback_url


def run(base, credentials):
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
    print('PASS REAL GIT document save/read across two Matrix users and denied room')

    denied(401, '/api/auth/login', 'POST',
           {'username': alice[0], 'password': 'invalid-login-password'}, login=True)
    denied(403, '/api/auth/logout', 'POST', {}, cookie=bob[1], csrf=alice[2]['csrf'])
    done, _ = call('/api/auth/logout', 'POST', {}, cookie=alice[1], csrf=alice[2]['csrf'])
    assert done['status'] == 'signed_out'
    denied(401, '/api/session', cookie=alice[1])
    assert call('/api/session', cookie=bob[1])[0]['userId'] == bob[0]
    print('PASS REAL MATRIX wrong password, CSRF isolation and current-device logout')
    # Leave Bob's device active for manual browser refresh/logout verification.
    return created['commit']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8791')
    parser.add_argument('--credentials-file', required=True,
                        help='private local smoke-passwords.json; do not commit it')
    args = parser.parse_args()
    creds = json.loads(Path(args.credentials_file).read_text())
    commit = run(args.url, creds)
    print('REAL SYNAPSE HTTP acceptance complete. Git commit:', commit)
    print('NOT verified: physical browser/IME, server restart, public deployment.')


if __name__ == '__main__':
    main()
