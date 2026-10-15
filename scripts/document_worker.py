"""External deterministic document runtime. Only demo.md is granted in this spike."""
import argparse
import os
from pathlib import Path

from scripts.agent_worker import render as echo
from scripts.agent_worker import run_loop, report_failure
from src.gitdocs import Conflict, GitDocs, InvalidPath, PublicationPending
from src.matrix_http import request


def document_result(item):
    return 'Saved demo.md\nGit commit: ' + item['commit'] + '\nBlob: ' + item['blob']


def render(task, store):
    command = task['event']['content'].get('org.didadi.document')
    if not isinstance(command, dict):
        return echo(task), None
    try:
        if command.get('action') == 'read':
            snapshot = store.snapshot('demo.md', command.get('commit'))
            return ('demo.md at Git commit: ' + str(snapshot['commit']) + '\n\n' +
                    (snapshot['content'] if snapshot['content'] is not None else '(document has not been created)')[:12000]), None
        if command.get('action') != 'write':
            raise ValueError('unsupported document action')
        content = command['content']
        if not isinstance(content, str) or len(content) > 6000:
            raise ValueError('document too large')
        # The grant is fixed here, not selected by message content. The event ID is the operation ID.
        item = store.write('demo.md', content, command.get('base_blob'), operation=task['id'],
                           notification={'task_id': task['id'], 'room_id': task['event']['room_id']})
        return document_result(item), item
    except PublicationPending:
        raise  # Do not complete/ack a saved but unpublished operation as a stale-write error.
    except Conflict:
        return 'Document conflict: refresh the Git version and merge your changes. No remote history was overwritten.', None
    except (ValueError, InvalidPath, KeyError):
        return 'Document request rejected: invalid action, content or version.', None


def reconcile(base, token, store):
    # A crash after Matrix ACK but before receipt is reconciled without another notification.
    for item in store.pending():
        task = request(base, 'GET', '/agent/status', token,
                       query={'id': item['notification']['task_id']})['task']
        if task and task['status'] == 'done':
            store.acknowledge(item['operation'])
        elif task and task['status'] == 'failed':
            store.abandon(item['operation'], task.get('last_error') or 'task_failed')


def once(base, token, store, crash_after_commit=False):
    reconcile(base, token, store)
    task = request(base, 'GET', '/agent/tasks', token)['task']
    if not task:
        return False
    try:
        request(base, 'POST', '/agent/validate', token, {'id': task['id'], 'lease': task['lease']})
        item = None
        if task['result'] is not None:
            result = task['result']
        else:
            result, item = render(task, store)
        if item and crash_after_commit:
            os._exit(73)  # Integration-test fault: Git committed; completion has not been sent.
        request(base, 'POST', '/agent/complete', token,
                {'id': task['id'], 'lease': task['lease'], 'result': result})
        if item:
            store.acknowledge(item['operation'])
    except Exception as error:
        report_failure(base, token, task, error)
        raise
    print('completed document-runtime task=' + task['id'], flush=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:9000')
    parser.add_argument('--token-file', required=True)
    parser.add_argument('--repo', required=True)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--crash-after-commit', action='store_true', help='integration-test fault injection')
    args = parser.parse_args()
    token = Path(args.token_file).read_text().strip()
    store = GitDocs(args.repo)
    if args.once:
        once(args.url, token, store, args.crash_after_commit)
    else:
        run_loop(lambda: once(args.url, token, store, args.crash_after_commit), delay=1)
