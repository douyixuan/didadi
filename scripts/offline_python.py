"""Curated local Git/policy tests, with fail-fast transport and process guards."""
from contextlib import ExitStack
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from src import matrix_http  # Import inert stdlib HTTP definitions before guarding sockets.

ROOT = Path(__file__).resolve().parents[1]
FILES = ('test_gitdocs.py','test_document_service.py','test_search_service.py','test_attachment_service.py','test_source_references.py','test_room_service.py','test_direct_chats.py')


def main():
    run = subprocess.run

    def local_git(arguments, **kwargs):
        if (not isinstance(arguments, list) or not arguments or arguments[0] != 'git' or
                any(item in arguments for item in ('fetch', 'push', 'ls-remote', 'clone')) or '-C' not in arguments or
                not Path(arguments[arguments.index('-C') + 1]).resolve().is_relative_to(Path(tempfile.gettempdir()).resolve())):
            raise AssertionError('Offline checks permit only temporary local Git subprocesses')
        return run(arguments, **kwargs)

    with ExitStack() as guards:
        guards.enter_context(patch.dict(os.environ, {'DIDADI_ALLOW_REAL_MATRIX': '0', 'DIDADI_INTEGRATION_APPROVAL_REF': ''}))
        for target in ('socket.socket', 'socket.create_connection', 'src.matrix_http.request'):
            guards.enter_context(patch(target, side_effect=AssertionError('Offline transport forbidden')))
        guards.enter_context(patch('subprocess.run', side_effect=local_git))
        suite = unittest.TestSuite()
        for name in FILES:
            suite.addTests(unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern=name))
        # Only in-process proxy checks; HTTP server fixtures remain out of this suite.
        for name in (
            'test_only_explicit_rooms_routes_and_identity_are_proxied',
            'test_platform_matrix_proxy_rejects_document_bodies_before_send',
            'test_quote_and_thread_references_are_validated_before_send',
            'test_only_requester_in_granted_room_can_cancel',
            'test_thread_relations_are_room_scoped_and_never_allow_identity_or_limit_overrides',
        ):
            suite.addTests(unittest.defaultTestLoader.loadTestsFromName('test_client_server.ClientServerTests.' + name))
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
