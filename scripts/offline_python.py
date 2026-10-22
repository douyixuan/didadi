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
FILES = ('test_gitdocs.py','test_document_service.py')


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
        return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
