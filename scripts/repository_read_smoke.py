"""Real Matrix -> scoped synthetic Git read -> report document -> original thread."""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import time

from scripts.document_worker import once
from src.gitdocs import GitDocs
from src.matrix_as import AGENT, PREFIX
from src.matrix_http import request, segment
from src.repository_read import RepositoryReader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--state-file', required=True); parser.add_argument('--token-file', required=True)
    parser.add_argument('--matrix-url', default='http://127.0.0.1:8008')
    parser.add_argument('--gateway-url', default='http://127.0.0.1:9000')
    args = parser.parse_args(); state = json.loads(Path(args.state_file).read_text())
    token = Path(args.token_file).read_text().strip(); base = args.gateway_url
    def api(method, path, data=None):
        return request(args.matrix_url, method, PREFIX + path, state['tokens'][0], data)
    sender = api('GET', '/account/whoami')['user_id']; room = state['room']
    def send(command):
        return api('PUT', '/rooms/' + segment(room) + '/send/m.room.message/' + secrets.token_hex(12),
                   {'msgtype': 'm.text', 'body': 'Inspect explicitly granted synthetic fixture; no LLM.',
                    'm.mentions': {'user_ids': [AGENT]}, 'org.didadi.repository': command})['event_id']
    def finish(identifier, store, reader):
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            task = request(base, 'GET', '/agent/status', token, query={'id': identifier})['task']
            if task and task['status'] == 'done':
                return api('GET', '/rooms/' + segment(room) + '/event/' + segment(task['reply']))
            if task and task['status'] in {'failed', 'cancelled'}:
                raise AssertionError('repository task terminated')
            once(base, token, store, repositories=reader)
            time.sleep(.2)
        raise AssertionError('repository task timeout')
    with tempfile.TemporaryDirectory(prefix='didadi-repository-fixture-') as directory:
        root = Path(directory); source = root / 'source'; source.mkdir()
        def git(*values):
            return subprocess.check_output(['git', '-C', str(source), *values], stderr=subprocess.DEVNULL)
        git('init', '-q'); git('config', 'user.name', 'Synthetic Fixture'); git('config', 'user.email', 'fixture@example.invalid')
        (source / 'main.py').write_text('print("synthetic-only")\n')
        (source / 'private.txt').write_text('not granted')
        git('add', '.'); git('commit', '-qm', 'isolated synthetic fixture')
        commit = git('rev-parse', 'HEAD').decode().strip(); before = git('show-ref')
        reader = RepositoryReader({'repositories': {'fixture': {'path': str(source), 'commit': commit,
            'files': ['main.py'], 'rooms': [room], 'senders': [sender]}}})
        store = GitDocs(root / 'documents.git')
        command = {'action': 'report', 'repository': 'fixture', 'path': 'main.py', 'base_blob': None}
        identifier = send(command); reply = finish(identifier, store, reader)
        snapshot = store.snapshot('demo.md'); assert commit in snapshot['content']
        assert 'no LLM analysis' in snapshot['content']
        assert snapshot['commit'] in reply['content']['body']
        assert reply['content']['m.relates_to']['event_id'] == identifier
        denied = send({**command, 'path': 'private.txt'})
        rejected = finish(denied, store, reader)
        assert 'request rejected' in rejected['content']['body']
        assert store.snapshot('demo.md')['commit'] == snapshot['commit']
        assert git('show-ref') == before and git('status', '--porcelain') == b''
    print('PASS real Matrix mention -> fixed synthetic source -> deterministic Git Markdown report -> original thread; denied path has no document write; source refs/worktree unchanged')


if __name__ == '__main__': main()
