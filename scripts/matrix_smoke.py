"""Real Synapse smoke test. Run inside Compose; failures exit nonzero."""
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sys
import time

from src.matrix_as import AGENT, PREFIX
from src.matrix_http import MatrixError, request, segment

BASE = 'http://synapse:8008'
CONFIG = Path('/config')


def api(method, path, token=None, data=None, query=None):
    return request(BASE, method, PREFIX + path, token, data, query)


def register_user(name, shared):
    nonce = request(BASE, 'GET', '/_synapse/admin/v1/register')['nonce']
    password = secrets.token_urlsafe(24)
    mac = hmac.new(shared.encode(),
                   '\0'.join([nonce, name, password, 'notadmin']).encode(), hashlib.sha1).hexdigest()
    registered = request(BASE, 'POST', '/_synapse/admin/v1/register', data={
        'nonce': nonce, 'username': name, 'password': password, 'admin': False, 'mac': mac})
    return registered, password


def wait_event(token, room, predicate, since=None):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        query = {'timeout': 1000}
        if since:
            query['since'] = since
        response = api('GET', '/sync', token, query=query)
        events = response.get('rooms', {}).get('join', {}).get(room, {}).get('timeline', {}).get('events', [])
        for event in events:
            if predicate(event):
                return event
        since = response['next_batch']
    raise AssertionError('Timed out waiting for expected Matrix event')


def main():
    if '--check-persistence' in sys.argv:
        saved = json.loads((CONFIG / 'smoke-state.json').read_text())
        for token in saved['tokens']:
            event = api('GET', '/rooms/' + segment(saved['room']) + '/event/' + segment(saved['event']), token)
            assert event['content']['body'] == saved['body']
        task = request('http://appservice:9000', 'GET', '/agent/tasks',
                       (CONFIG / 'agent-token').read_text().strip())['task']
        assert task['id'] == json.loads((CONFIG / 'gateway-state.json').read_text())['task']
        request('http://appservice:9000', 'POST', '/agent/complete',
                (CONFIG / 'agent-token').read_text().strip(),
                {'id': task['id'], 'lease': task['lease'], 'result': 'Recovered after restart'})
        print('PASS persisted users, room, message and accepted external task after restart')
        return
    config = json.loads((CONFIG / 'secrets.json').read_text())
    # Missing token must fail before processing, independently of event filtering.
    try:
        request('http://appservice:9000', 'PUT', '/_matrix/app/v1/transactions/unauthorized', data={'events': []})
        raise AssertionError('AS accepted an unauthenticated transaction')
    except MatrixError as error:
        assert error.status == 403
    print('PASS AS rejects unauthenticated transactions')
    run = secrets.token_hex(5)
    alice, alice_password = register_user('alice_' + run, config['registration'])
    bob, bob_password = register_user('bob_' + run, config['registration'])
    a, b = alice['access_token'], bob['access_token']
    try:
        api('POST', '/register', config['as_token'], {
            'type': 'm.login.application_service', 'username': '_didadi_agent_echo', 'inhibit_login': True})
    except MatrixError as error:
        if error.body.get('errcode') != 'M_USER_IN_USE':
            raise
    # Verify AS cannot impersonate a human outside its registered namespace.
    try:
        api('GET', '/account/whoami', config['as_token'], query={'user_id': alice['user_id']})
        raise AssertionError('AS impersonated an out-of-namespace user')
    except MatrixError as error:
        assert error.status == 403
    print('PASS managed identity registration and namespace boundary')
    room = api('POST', '/createRoom', a, {'preset': 'private_chat',
        'name': 'Didadi smoke ' + run, 'invite': [bob['user_id'], AGENT]})['room_id']
    rp = '/rooms/' + segment(room)
    api('POST', rp + '/join', b, {})
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        membership = api('GET', rp + '/state/m.room.member/' + segment(AGENT), a)
        if membership['membership'] == 'join':
            break
        time.sleep(1)
    else:
        raise AssertionError('AS did not accept agent invitation')
    baseline = api('GET', '/sync', b)['next_batch']
    body = 'hello from Alice ' + run
    event_id = api('PUT', rp + '/send/m.room.message/alice-' + run, a,
                   {'msgtype': 'm.text', 'body': body})['event_id']
    wait_event(b, room, lambda e: e.get('event_id') == event_id and e.get('sender') == alice['user_id']
               and e.get('content', {}).get('body') == body, baseline)
    baseline_a = api('GET', '/sync', a)['next_batch']
    reply_id = api('PUT', rp + '/send/m.room.message/bob-' + run, b,
                   {'msgtype': 'm.text', 'body': 'hello from Bob ' + run})['event_id']
    wait_event(a, room, lambda e: e.get('event_id') == reply_id and e.get('sender') == bob['user_id'], baseline_a)
    print('PASS Alice -> Bob and Bob -> Alice via /sync')
    baseline = api('GET', '/sync', b)['next_batch']
    trigger = api('PUT', rp + '/send/m.room.message/echo-' + run, a,
                  {'msgtype': 'm.text', 'body': '!echo ' + run})['event_id']
    reply = wait_event(b, room, lambda e: e.get('sender') == AGENT and
        e.get('content', {}).get('body') == 'Echo: ' + run and
        e.get('content', {}).get('m.relates_to', {}).get('m.in_reply_to', {}).get('event_id') == trigger, baseline)
    print('PASS Synapse -> AS -> managed agent reply -> Bob /sync')
    # Replay a genuine event; deterministic outbound txn IDs should reuse the same reply.
    original = api('GET', rp + '/event/' + segment(trigger), a)
    original['room_id'] = room
    for _ in range(2):
        request('http://appservice:9000', 'PUT', '/_matrix/app/v1/transactions/replay-' + run,
                config['hs_token'], {'events': [original]})
    history = api('GET', rp + '/messages', b, query={'dir': 'b', 'limit': 100})['chunk']
    matches = [e for e in history if e.get('sender') == AGENT and e.get('content', {}).get('body') == 'Echo: ' + run]
    assert len(matches) == 1 and matches[0]['event_id'] == reply['event_id']
    print('PASS immediate transaction replay produces one reply (not a durable task guarantee)')
    # External runtime connects outbound with its own credential (no homeserver token).
    from scripts.agent_worker import once
    gateway = 'http://appservice:9000'
    worker_token = (CONFIG / 'agent-token').read_text().strip()
    try:
        request(gateway, 'GET', '/agent/tasks', config['as_token'])
        raise AssertionError('Gateway accepted homeserver credential as worker')
    except MatrixError as error:
        assert error.status == 403
    baseline = api('GET', '/sync', b)['next_batch']
    task_body = 'summarize milestone ' + run
    task_event = api('PUT', rp + '/send/m.room.message/task-' + run, a, {
        'msgtype': 'm.text', 'body': task_body, 'm.mentions': {'user_ids': [AGENT]},
        'm.relates_to': {'rel_type': 'm.thread', 'event_id': event_id}})['event_id']
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if once(gateway, worker_token):
            break
        time.sleep(1)
    else:
        raise AssertionError('No durable external task')
    external = wait_event(b, room, lambda e: e.get('content', {}).get('org.didadi.task', {}).get('id') == task_event, baseline)
    assert external['content']['body'] == 'External agent received: ' + task_body
    assert external['content']['m.relates_to']['event_id'] == event_id
    original_task = api('GET', rp + '/event/' + segment(task_event), a)
    original_task['room_id'] = room
    for txn in ['durable-replay-' + run, 'durable-replay-' + run, 'different-' + run]:
        request(gateway, 'PUT', '/_matrix/app/v1/transactions/' + txn, config['hs_token'], {'events': [original_task]})
    assert request(gateway, 'GET', '/agent/tasks', worker_token)['task'] is None
    print('PASS durable mention task, outbound runtime, original thread, credential separation and replay')
    # Leave a genuine accepted task pending across the CI container recreation.
    recovery_id = api('PUT', rp + '/send/m.room.message/recovery-' + run, a, {
        'msgtype': 'm.text', 'body': 'Recover this task', 'm.mentions': {'user_ids': [AGENT]}})['event_id']
    recovery_event = api('GET', rp + '/event/' + segment(recovery_id), a)
    recovery_event['room_id'] = room
    request(gateway, 'PUT', '/_matrix/app/v1/transactions/recovery-' + run,
            config['hs_token'], {'events': [recovery_event]})
    (CONFIG / 'gateway-state.json').write_text(json.dumps({'task': recovery_event['event_id']}))
    (CONFIG / 'smoke-state.json').write_text(json.dumps({
        'tokens': [a, b], 'room': room, 'event': event_id, 'body': body}))
    # Real Matrix credentials, not fictional identities. Test-only; never display or
    # publish. Preserve separate from the state file used by fixture-mode adapters.
    passwords = CONFIG / 'smoke-passwords.json'
    passwords.write_text(json.dumps({alice['user_id']: alice_password,
                                     bob['user_id']: bob_password}))
    passwords.chmod(0o600)
    print('PASS Matrix smoke completed; private password fixture stored with mode 0600')


if __name__ == '__main__':
    main()
