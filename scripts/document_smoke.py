"""Real Matrix -> external document runtime -> Git -> thread, including a process crash."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time

from scripts.document_worker import once
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', required=True)
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9000')
    args = parser.parse_args()
    state = json.loads(Path(args.state_file).read_text())
    token = Path(args.token_file).read_text().strip()
    store = GitDocs(args.repo)
    store._git('config','didadi.documentRoom',state['room'])
    room = '/rooms/' + segment(state['room'])
    run = secrets.token_hex(6)

    def api(method, path, data=None):
        return request(args.matrix_url, method, PREFIX + path, state['tokens'][0], data)

    def send(command):
        return api('PUT', room + '/send/m.room.message/docs-' + secrets.token_hex(8), {
            'msgtype': 'm.text', 'body': 'Document smoke ' + run,
            'm.mentions': {'user_ids': [AGENT]}, 'org.didadi.document': command})['event_id']

    def status(task_id):
        return request(args.gateway_url, 'GET', '/agent/status', token, query={'id': task_id})['task']

    def finish(task_id):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            once(args.gateway_url, token, store)
            task = status(task_id)
            if task and task['status'] == 'done':
                reply = api('GET', room + '/event/' + segment(task['reply']))
                assert reply['sender'] == AGENT
                assert reply['content']['m.relates_to']['event_id'] == task_id
                assert reply['content']['org.didadi.task']['id'] == task_id
                return reply['content']['body']
            time.sleep(1)
        raise AssertionError('document task failed to finish')

    # Drain the previous Matrix spike's intentional recovery task.
    while once(args.gateway_url, token, store):
        pass
    before = store.snapshot('demo.md')
    first_text = '# Didadi document loop\n\nCreated from Matrix. ' + run + '\n'
    first_event = send({'action': 'write', 'content': first_text, 'base_blob': before['blob']})
    reply = finish(first_event)
    first = store.snapshot('demo.md')
    assert first['content'] == first_text and first['commit'] in reply
    assert store.pending() == []
    print('PASS real Matrix write -> external runtime -> Git commit -> original thread')

    second_text = first_text + '\nSurvives a worker crash before Matrix completion.\n'
    second_event = send({'action': 'write', 'content': second_text, 'base_blob': first['blob']})
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = subprocess.run([sys.executable, '-m', 'scripts.document_worker',
                                 '--url', args.gateway_url, '--token-file', args.token_file,
                                 '--repo', args.repo, '--once', '--crash-after-commit'], timeout=20)
        if result.returncode == 73:
            break
        assert result.returncode == 0
        time.sleep(1)
    else:
        raise AssertionError('fault injection did not commit and crash')
    restored = GitDocs(args.repo)
    after_crash = restored.snapshot('demo.md')
    assert after_crash['content'] == second_text
    assert len(restored.pending()) == 1
    assert status(second_event)['status'] != 'done'
    reply = finish(second_event)  # Reclaims the expired lease, reuses the operation commit, sends notification.
    assert after_crash['commit'] in reply
    assert store.snapshot('demo.md')['commit'] == after_crash['commit']
    assert store.pending() == []
    print('PASS real worker exit(73) after Git commit: outbox survives, one commit, notification recovered')

    old_read = send({'action': 'read', 'commit': first['commit']})
    read_reply = finish(old_read)
    assert first_text not in read_reply and first['commit'] in read_reply and 'Survives a worker crash' not in read_reply
    stale = send({'action': 'write', 'content': 'stale overwrite', 'base_blob': first['blob']})
    assert 'Document conflict:' in finish(stale)
    assert store.snapshot('demo.md')['commit'] == after_crash['commit']
    print('PASS fixed-version Git read and stale Matrix document write rejected')
    print('PASS document loop smoke completed')


if __name__ == '__main__':
    main()
