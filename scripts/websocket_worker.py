"""External outbound WebSocket document runtime with bounded reconnect backoff."""
import argparse
import json
import logging
from pathlib import Path
import random
import time

from websockets.sync.client import connect
from scripts.document_worker import once
from src.gitdocs import GitDocs
from src.matrix_http import MatrixError
from src.repository_read import RepositoryReader
from src.runtime_socket import loopback_url


class SocketTransport:
    def __init__(self, socket): self.socket = socket

    def __call__(self, base, method, path, token=None, data=None, query=None):
        self.socket.send(json.dumps({'method': method, 'path': path, 'data': data, 'query': query}))
        result = json.loads(self.socket.recv(timeout=50))
        if not result['ok']:
            raise MatrixError(result['status'], result['error'])
        return result['result']


def connect_runtime(url, token):
    loopback_url(url, 'ws')
    return connect(url, additional_headers={'Authorization': 'Bearer ' + token}, proxy=None,
                   compression=None, max_size=4 * 1024 * 1024, max_queue=4, ping_interval=10, ping_timeout=10,
                   close_timeout=2)


def run(url, token, store, repositories=None, *, stop=None):
    loopback_url(url, 'ws')
    failures = 0
    while stop is None or not stop.is_set():
        try:
            with connect_runtime(url, token) as socket:
                transport = SocketTransport(socket)
                while stop is None or not stop.is_set():
                    once('', '', store, repositories=repositories, transport=transport)
                    failures = 0
        except Exception as error:
            delay = min(30, 2 ** min(failures, 5)) + random.random() * .2
            failures += 1
            logging.warning('Runtime connection iteration failed (%s); reconnecting', type(error).__name__)
            if stop is not None: stop.wait(delay)
            else: time.sleep(delay)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='ws://127.0.0.1:9020/runtime')
    parser.add_argument('--token-file', required=True); parser.add_argument('--repo', required=True)
    parser.add_argument('--repository-grants')
    args = parser.parse_args()
    reader = RepositoryReader.from_file(args.repository_grants) if args.repository_grants else None
    run(args.url, Path(args.token_file).read_text().strip(), GitDocs(args.repo), reader)
