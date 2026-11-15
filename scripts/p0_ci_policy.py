"""Classify changed paths and evaluate the stable gate. Never create test identities."""
import argparse
import os
from pathlib import Path
import re
import subprocess
from scripts.p072_clean_room import docs_only,gate_result,Failure


def changed_paths(base,head,root=None):
    if not all(re.fullmatch('[0-9a-f]{40}',value or '') and value!='0'*40 for value in (base,head)):
        return None
    # --no-renames checks both removed code paths and newly added documentation.
    try:
        return subprocess.check_output(['git','-C',str(root or Path(__file__).resolve().parents[1]),
            'diff','--name-only','--no-renames','-z',base,head],stderr=subprocess.DEVNULL).decode().rstrip('\0').split('\0')
    except subprocess.CalledProcessError:return None


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('mode',choices=('scope','gate'));args=parser.parse_args()
    if args.mode=='scope':
        paths=changed_paths(os.environ.get('BASE_SHA'),os.environ.get('HEAD_SHA'))
        exempt=docs_only(paths or [])
        with open(os.environ['GITHUB_OUTPUT'],'a') as output:output.write('docs_only='+str(exempt).lower()+'\n')
        print('SCOPE: docs-only exemption' if exempt else 'SCOPE: code requires both genuine jobs')
        return 0
    try:result=gate_result(*(os.environ.get(name,'') for name in ('SCOPE_RESULT','DOCS_ONLY','MATRIX_RESULT','CLEAN_RESULT')))
    except Failure:
        print('FAIL: classification or required genuine acceptance did not succeed');return 1
    print('EXEMPT: documentation only; no real acceptance claimed' if result=='docs-only-exemption' else 'PASS: both genuine Matrix and fresh-checkout restore acceptance succeeded')
    return 0


if __name__=='__main__':raise SystemExit(main())
