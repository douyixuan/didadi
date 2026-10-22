"""Advertise existing synthetic Bob identities, without creating or copying credentials."""
import argparse
import json
from pathlib import Path
import re
from src.matrix_http import request
from src.matrix_as import PREFIX
from src.runtime_socket import loopback_url

def configure(state_file,matrix_url,output):
    loopback_url(matrix_url,'http');state=json.loads(Path(state_file).read_text());tokens=state.get('tokens',[])
    if len(tokens)!=2:raise ValueError('Use the existing two-person synthetic fixture.')
    users=[request(matrix_url,'GET',PREFIX+'/account/whoami',token)['user_id'] for token in tokens]
    if not re.fullmatch(r'@alice_[a-f0-9]+:didadi\.localhost',users[0]) or not re.fullmatch(r'@bob_[a-f0-9]+:didadi\.localhost',users[1]):raise ValueError('Only the existing isolated Alice/Bob fixture is supported.')
    value=[users[1]];path=Path(output)
    if path.exists():
        if path.is_symlink() or json.loads(path.read_text())!=value:raise ValueError('Do not replace existing contact configuration.')
    else:
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as file:json.dump(value,file)
        path.chmod(0o600)
    return value

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--state-file',required=True);parser.add_argument('--matrix-url',required=True);parser.add_argument('--output',required=True);args=parser.parse_args();configure(args.state_file,args.matrix_url,args.output);print('Configured one existing local synthetic contact; no identity or credential was created.')
