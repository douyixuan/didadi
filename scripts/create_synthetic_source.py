"""Create a new local-only source fixture; never modify an existing source."""
import os
from pathlib import Path
import json
import subprocess

from src.matrix_as import PREFIX
from src.matrix_http import request
from src.runtime_socket import loopback_url


def create(root, matrix_url):
    root=Path(root).resolve();loopback_url(matrix_url,'http')
    local=root/'.local'/'bundle';source=local/'synthetic-source';path=local/'repository-grants.json'
    for directory in [root/'.local',local]:
        if directory.is_symlink():raise ValueError('The fixture directory is a symlink.')
    if source.exists() or source.is_symlink():
        raise ValueError('The synthetic source already exists. Use a fresh extraction.')
    if path.exists() or path.is_symlink():
        raise ValueError('The source grant already exists. Use a fresh extraction.')
    state_path=local/'smoke-state.json'
    if state_path.is_symlink():raise ValueError('The fixture state is a symlink.')
    state=json.loads(state_path.read_text())
    user=request(matrix_url,'GET',PREFIX+'/account/whoami',state['tokens'][0])['user_id']
    # Validate prerequisites before creating any source files or grants.
    if not isinstance(state['room'],str) or not state['room'] or not isinstance(user,str) or not user:
        raise ValueError('Invalid fixture identity or room.')
    for directory in [root/'.local',local]:directory.mkdir(exist_ok=True);directory.chmod(0o700)
    source.mkdir()
    environment={key:value for key,value in os.environ.items() if not key.startswith('GIT_')}
    environment.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0')
    def git(*args):
        return subprocess.check_output(['git','-c','core.hooksPath='+os.devnull,
            '-c','core.fsmonitor=false','-c','commit.gpgsign=false','-C',str(source),*args],
            stderr=subprocess.DEVNULL,env=environment)
    git('init','-q','--template=');git('config','user.name','Synthetic Fixture')
    git('config','user.email','fixture@example.invalid')
    (source/'example.py').write_text('def greet(name):\n    return "Hello, " + name\n')
    git('add','example.py');git('commit','-qm','synthetic source fixture')
    commit=git('rev-parse','HEAD').decode().strip()
    grants={'repositories':{'synthetic-example':{'path':str(source),'commit':commit,
        'files':['example.py'],'rooms':[state['room']],'senders':[user]}}}
    with path.open('x') as output:json.dump(grants,output)
    path.chmod(0o600)
    return grants


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--matrix-url',default='http://127.0.0.1:'+os.environ.get('MATRIX_HTTP_PORT','8020'))
    args=parser.parse_args()
    create(Path(__file__).resolve().parent.parent,args.matrix_url)
    print('Created the synthetic source grant. No LLM is connected.')
