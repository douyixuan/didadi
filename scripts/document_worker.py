"""External deterministic runtime. Document IO belongs to the scoped Document API."""
import argparse
import os
from pathlib import Path

from scripts.agent_worker import run_loop, report_failure
from src.agent_document_api import AgentDocuments, DocumentClient
from src.matrix_http import request


def service_for(base, token, store, repositories=None, transport=None):
    if isinstance(store, (AgentDocuments, DocumentClient)):
        return store
    # Development compatibility: cohost the same service with existing --repo callers.
    # This mode is an API boundary, not filesystem/process isolation.
    send = transport or request
    return AgentDocuments(store, lambda method,path,data=None,query=None:
        send(base,method,path,token,data=data,query=query), repositories)


def reconcile(base, token, store, transport=None):
    return service_for(base,token,store,transport=transport).reconcile()


def once(base, token, store, crash_after_commit=False, repositories=None, transport=None):
    send = transport or request
    documents = service_for(base,token,store,repositories,transport)
    documents.reconcile()
    task = send(base, 'GET', '/agent/tasks', token)['task']
    if not task: return False
    try:
        send(base, 'POST', '/agent/validate', token, {'id':task['id'], 'lease':task['lease']})
        response = documents.execute({'id':task['id'], 'lease':task['lease']})
        if response['committed'] and crash_after_commit:
            os._exit(73)
        send(base, 'POST', '/agent/complete', token,
             {'id':task['id'], 'lease':task['lease'], 'result':response['result'], 'outcome':response['outcome']})
        documents.reconcile()
    except Exception as error:
        report_failure(base,token,task,error,transport)
        raise
    print('completed document-runtime task=' + task['id'], flush=True)
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:9000')
    parser.add_argument('--token-file', required=True)
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--repo', help='development cohost compatibility')
    group.add_argument('--document-url', help='loopback Document API; runtime needs no Git mount')
    parser.add_argument('--repository-grants', help='cohost-only explicit read grants')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--crash-after-commit', action='store_true')
    args=parser.parse_args(); token=Path(args.token_file).read_text().strip()
    if args.document_url:
        if args.repository_grants: parser.error('configure grants on the Document API')
        documents=DocumentClient(args.document_url,token); repositories=None
    else:
        from src.gitdocs import GitDocs
        from src.repository_read import RepositoryReader
        documents=GitDocs(args.repo)
        repositories=RepositoryReader.from_file(args.repository_grants) if args.repository_grants else None
    if args.once: once(args.url,token,documents,args.crash_after_commit,repositories)
    else: run_loop(lambda: once(args.url,token,documents,args.crash_after_commit,repositories),delay=1)
