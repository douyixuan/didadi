"""Explicit, ephemeral P0 acceptance. Importing this module starts no services."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

VOLUMES=('config','postgres','synapse','gateway')


SAFE_REASONS={'PermissionError','TimeoutExpired','CalledProcessError','FileNotFoundError','Use a fresh checkout without .local, node_modules or dist','Missing documented prerequisite','Tracked or untracked source changes require a separate fresh checkout','Only a local Docker context is supported','A required loopback port is occupied','Generated namespace already exists','Command failed; read private local diagnostics','Owned client exited','Client health deadline exceeded','Refusing an unowned volume'}


class Failure(Exception):
    def __init__(self,code=1,detail='Acceptance failed'):
        self.code=code;self.reason=detail if detail in SAFE_REASONS else 'Acceptance failed';super().__init__(detail)


def docs_only(paths):
    return bool(paths) and all('..' not in PurePosixPath(path).parts and (path in {'README.md','ROADMAP.md','LICENSE'} or
        (any(path.startswith(prefix) for prefix in ('docs/','roadmap/','artifact/')) and
         PurePosixPath(path).suffix in {'.md','.png'})) for path in paths)


def gate_result(scope,exempt,matrix,clean):
    if scope!='success':raise Failure()
    if exempt=='true' and matrix=='skipped' and clean=='skipped':return 'docs-only-exemption'
    if exempt=='false' and matrix=='success' and clean=='success':return 'real'
    raise Failure()


def failure_hint(output):
    # Export source positions and fixed categories, never exception values or logs.
    text=output[-65536:].decode(errors='replace')
    names=r'(?:real_login_browser|document_recovery_acceptance|cross_user_receipt_browser|p072_restore_browser)\.mjs|(?:real_login_smoke|client_server|gitdocs|document_service|matrix_sessions)\.py'
    locations=re.findall('('+names+r')(?::|", line )(\d+)',text)
    categories=[label for pattern,label in (('permission denied','permission-denied'),('no space left on device','storage-full'),('port is already allocated','port-in-use'),('unhealthy','service-unhealthy'),('no module named','missing-module')) if pattern in text.lower()]
    return {'locations':sorted({name+':'+line for name,line in locations}),'categories':categories}


def volume_script(action,name):
    if action not in {'backup','restore'} or name not in VOLUMES:raise ValueError('Invalid volume action')
    common="import tarfile, hashlib\nfrom pathlib import Path, PurePosixPath\n"
    if action=='backup':return common+f"with tarfile.open('/backup/{name}.tar','w') as archive: archive.add('/volume',arcname='data')\n"
    return common+f"""with tarfile.open('/backup/{name}.tar','r') as archive:
    for member in archive.getmembers():
        parts=PurePosixPath(member.name).parts
        if not parts or parts[0]!='data' or '..' in parts or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
            raise ValueError('Unsafe backup member')
    archive.extractall('/volume',filter='fully_trusted')
""".replace("archive.extractall('/volume',filter='fully_trusted')","""# Strip the fixed archive root only after validating every member.
    for member in archive.getmembers():
        member.name='/'.join(PurePosixPath(member.name).parts[1:])
        if member.name:
            archive.extract(member,'/volume',filter='fully_trusted')
            if member.isfile():
                expected=hashlib.sha256(archive.extractfile(member).read()).digest()
                actual=hashlib.sha256((Path('/volume')/member.name).read_bytes()).digest()
                if actual!=expected:raise ValueError('Restored file differs from archived bytes')""")


class CleanRoom:
    def __init__(self,root,version):
        self.root=Path(root).resolve();self.version=version;self.local=self.root/'.local'
        self.source='didadi-p072-'+secrets.token_hex(8);self.restored=self.source+'-restore'
        self.owned=[];self.client=None;self.stages=[];self.passed=False;self.stage_name='preflight'
        self.created=False;self.backup=None;self.tracing=False
        allowed={'PATH','HOME','USER','LOGNAME','TMPDIR','TMP','TEMP','LANG','LC_ALL','LC_CTYPE',
            'LD_LIBRARY_PATH','DYLD_LIBRARY_PATH','DYLD_FALLBACK_LIBRARY_PATH','DOCKER_CONFIG','DOCKER_CONTEXT',
            'CI','GITHUB_ACTIONS','PLAYWRIGHT_BROWSERS_PATH'}
        self.env={key:os.environ[key] for key in allowed if key in os.environ}
        self.env.update({'MATRIX_HTTP_PORT':'8008','GATEWAY_HTTP_PORT':'9000','PYTHONUNBUFFERED':'1',
                         'NPM_CONFIG_USERCONFIG':'/dev/null'})

    def check_fresh(self):
        for path in (self.local,self.root/'client/node_modules',self.root/'client/dist'):
            if path.exists() or path.is_symlink():raise Failure(2,'Use a fresh checkout without .local, node_modules or dist')

    def command(self,args,capture=False,timeout=600):
        log=(self.local if self.local.exists() else self.backup)/'p072-private.log'
        if self.stages:
            program=Path(args[0]).name
            operation=args[2] if len(args)>2 and args[1]=='-m' else Path(args[1]).name if program=='node' and len(args)>1 else program
            self.stages[-1]['command']=operation if re.fullmatch('[A-Za-z0-9_.-]{1,100}',operation) else program
        if capture:
            result=subprocess.run(args,cwd=self.root,env=self.env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        else:
            with log.open('ab') as output:
                output.write(('COMMAND '+json.dumps(args)+'\n').encode());output.flush()
                result=subprocess.run(args,cwd=self.root,env=self.env,stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
        if result.returncode:
            output=(result.stdout or b'')+(result.stderr or b'') if capture else log.read_bytes()
            if self.stages:self.stages[-1]['diagnostic']=failure_hint(output)
            raise Failure(result.returncode,'Command failed; read private local diagnostics')
        return result.stdout.decode() if capture else ''

    def stage(self,name,action):
        if self.tracing:print('P072 STAGE '+name,flush=True)
        self.stage_name=name;entry={'name':name,'exit_code':None};self.stages.append(entry);start=time.monotonic()
        try:action();entry['exit_code']=0
        except Failure as error:entry['exit_code']=error.code;entry['reason']=error.reason;raise
        except Exception as error:entry['exit_code']=1;raise Failure(1,type(error).__name__) from None
        finally:
            entry['seconds']=round(time.monotonic()-start,2)
            if self.tracing:print('P072 RESULT '+name+' exit='+str(entry['exit_code']),flush=True)

    def public_report(self):
        return {'schema':1,'version':self.version,'passed':self.passed,'accepted':False,'environment':'ephemeral-loopback-real',
                'stages':self.stages,'physical_ios_ime':'not-run','branch_protection':'not-changed-or-accepted'}

    def compose(self,project,*args):
        return self.command(['docker','compose','--env-file','/dev/null','-f',str(self.root/'compose.yaml'),'-p',project,*args])

    def prepare(self):
        self.check_fresh()
        # Read-only checks precede all state changes and dependency installation.
        for tool in ('git','docker','node','npm'):
            if not shutil.which(tool):raise Failure(2,'Missing documented prerequisite')
        if sys.version_info < (3,11):raise Failure(2,'Missing documented prerequisite')
        node=subprocess.check_output(['node','--version'],text=True,env=self.env).strip()
        if not re.fullmatch(r'v(?:2[4-9]|[3-9][0-9])\.[0-9]+\.[0-9]+',node):raise Failure(2,'Missing documented prerequisite')
        subprocess.run(['git','--no-lazy-fetch','--version'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,env=self.env)
        help_text=subprocess.check_output(['docker','compose','up','--help'],text=True,env=self.env)
        if '--wait-timeout' not in help_text:raise Failure(2,'Missing documented prerequisite')
        dirty=subprocess.check_output(['git','-c','core.fsmonitor=false','-c','core.hooksPath=/dev/null','status','--porcelain'],cwd=self.root,text=True,env=self.env)
        if dirty:raise Failure(2,'Tracked or untracked source changes require a separate fresh checkout')
        context=json.loads(subprocess.check_output(['docker','context','inspect'],text=True,env=self.env))[0]
        endpoint=context['Endpoints']['docker']['Host']
        if os.environ.get('DOCKER_HOST') or not endpoint.startswith('unix://'):raise Failure(2,'Only a local Docker context is supported')
        self.env['DOCKER_CONTEXT']=context['Name']
        subprocess.run(['docker','info'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True,timeout=30,env=self.env)
        for port in (8008,9000,8791):
            with socket.socket() as probe:
                try:probe.bind(('127.0.0.1',port))
                except OSError:raise Failure(2,'A required loopback port is occupied') from None
        # Exclusive mkdir refuses races and never reuses a private workspace.
        self.local.mkdir(mode=0o700);self.created=True
        npmrc=self.local/'p072-empty-global-npmrc';npmrc.write_text('');npmrc.chmod(0o600)
        self.env['NPM_CONFIG_GLOBALCONFIG']=str(npmrc)
        (self.local/'p072-owner.json').write_text(json.dumps({'source':self.source,'restore':self.restored}))
        for project in (self.source,self.restored):
            for volume in VOLUMES:
                result=subprocess.run(['docker','volume','inspect',project+'_'+volume],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=self.env)
                if result.returncode==0:raise Failure(2,'Generated namespace already exists')

    def start_client(self):
        env={**self.env,'DIDADI_INVITE_PROBE':'1'}
        output=(self.local/'p072-client-private.log').open('ab')
        self.client=subprocess.Popen([sys.executable,'-m','src.client_server','--auth-mode','matrix',
            '--state-file','.local/smoke-state.json','--token-file','.local/agent-token',
            '--repo','.local/documents.git','--metadata','.local/real-login-client.sqlite',
            '--matrix-url','http://127.0.0.1:8008','--gateway-url','http://127.0.0.1:9000','--port','8791'],
            cwd=self.root,env=env,stdout=output,stderr=subprocess.STDOUT)
        output.close()
        for _ in range(45):
            if self.client.poll() is not None:raise Failure(1,'Owned client exited')
            try:
                with urlopen('http://127.0.0.1:8791/',timeout=2) as response:
                    if response.status==200:return
            except OSError:pass
            time.sleep(1)
        raise Failure(1,'Client health deadline exceeded')

    def stop_client(self):
        if self.client and self.client.poll() is None:
            self.client.terminate()
            try:self.client.wait(timeout=10)
            except subprocess.TimeoutExpired:self.client.kill();self.client.wait(timeout=10)
        self.client=None

    def bootstrap(self):
        self.command(['npm','ci','--prefix','client','--ignore-scripts','--no-audit','--no-fund'])
        self.command(['npm','--prefix','client','run','build'])
        self.command(['npm','--prefix','client','install','--no-save','--package-lock=false','--ignore-scripts','--no-audit','--no-fund','@playwright/test@1.56.1'])
        self.command(['./client/node_modules/.bin/playwright','install','chromium','--with-deps'])
        self.owned.append(self.source)
        self.compose(self.source,'up','-d','--wait','--wait-timeout','240')
        self.compose(self.source,'--profile','test','run','--rm','smoke')
        for name in ('agent-token','smoke-state.json','smoke-passwords.json'):
            self.compose(self.source,'cp','appservice:/config/'+name,'.local/'+name)
            (self.local/name).chmod(0o600)
        evidence=self.local/'real-login-browser';evidence.mkdir(mode=0o700)

    def retained_restart(self):
        self.compose(self.source,'down')
        self.compose(self.source,'up','-d','--wait','--wait-timeout','240')
        self.compose(self.source,'--profile','test','run','--rm','smoke', 'python','-u','-m','scripts.matrix_smoke','--check-persistence')

    def reset_limiter(self,project):
        self.compose(project,'restart','synapse');self.compose(project,'up','-d','--wait','--wait-timeout','90','synapse')

    def browser(self,script,*extra):
        self.command(['node','client/scripts/'+script,'--url','http://127.0.0.1:8791',
                      '--credentials-file','.local/smoke-passwords.json','--evidence-dir','.local/real-login-browser',*extra],timeout=900)

    def real_flow(self):
        self.start_client()
        self.command([sys.executable,'-m','scripts.real_login_smoke','--url','http://127.0.0.1:8791',
            '--credentials-file','.local/smoke-passwords.json','--restart-proof','.local/restart-private.json'])
        self.stop_client();self.start_client()
        self.command([sys.executable,'-m','scripts.real_login_smoke','--url','http://127.0.0.1:8791','--check-restart-proof','.local/restart-private.json'])
        self.reset_limiter(self.source);self.browser('real_login_browser.mjs')
        self.stop_client();self.start_client();self.reset_limiter(self.source)
        self.browser('cross_user_receipt_browser.mjs')
        self.reset_limiter(self.source);self.browser('p072_restore_browser.mjs','--phase','capture')

    def backup_restore(self):
        self.stop_client();self.compose(self.source,'stop','--timeout','60')
        self.backup=Path(tempfile.mkdtemp(prefix='didadi-p072-private-'))
        os.chmod(self.backup,0o700)
        for volume in VOLUMES:
            self.stages[-1]['volume']=volume;self.stages[-1]['operation']='backup-owned-stopped-volume'
            original=self.source+'_'+volume;target=self.restored+'_'+volume
            labels=json.loads(self.command(['docker','volume','inspect',original],capture=True))[0]['Labels']
            if labels.get('com.docker.compose.project')!=self.source or labels.get('com.docker.compose.volume')!=volume:raise Failure(2,'Refusing an unowned volume')
            mounts=['--mount','type=bind,src='+str(self.backup)+',dst=/backup']
            self.command(['docker','run','--rm','--network','none','--mount','type=volume,src='+original+',dst=/volume,readonly',*mounts,'python:3.13-slim','python','-c',volume_script('backup',volume)])
            self.stages[-1]['operation']='restore-into-independent-volume'
            self.command(['docker','volume','create','--label','com.docker.compose.project='+self.restored,'--label','com.docker.compose.volume='+volume,target])
            if self.restored not in self.owned:self.owned.append(self.restored)
            self.command(['docker','run','--rm','--network','none','--mount','type=volume,src='+target+',dst=/volume',*mounts,'python:3.13-slim','python','-c',volume_script('restore',volume)])
        self.stages[-1].pop('volume',None);self.stages[-1]['operation']='restore-independent-host-copy'
        # Keep source files intact and inaccessible from the restored canonical path.
        if any(path.is_symlink() for path in self.local.rglob('*')):raise Failure(2,'Refusing an unowned volume')
        shutil.copytree(self.local,self.backup/'host-copy')
        shutil.move(str(self.local),str(self.backup/'source-host'))
        shutil.copytree(self.backup/'host-copy',self.local)
        if os.path.samefile(self.local/'documents.git',self.backup/'source-host/documents.git'):raise Failure()
        self.stages[-1]['operation']='start-independent-restored-stack'
        self.compose(self.restored,'up','-d','--wait','--wait-timeout','240')
        self.stages[-1]['operation']='verify-original-device-cookies-and-data'
        self.start_client();self.browser('p072_restore_browser.mjs','--phase','verify')

    def verify_reuse_refusal(self):
        self.stop_client()
        def fingerprint():
            refs=self.command(['git','--git-dir=.local/documents.git','for-each-ref'],capture=True).encode()
            return hashlib.sha256(refs+(self.local/'p072-session-private.json').read_bytes()+(self.local/'p072-owner.json').read_bytes()).digest()
        before=fingerprint()
        result=subprocess.run([sys.executable,'-m','scripts.p072_clean_room','--allow-real-matrix',
            '--approval-reference','negative-reuse-check'],cwd=self.root,env=self.env,capture_output=True,timeout=30)
        if result.returncode!=1:raise Failure(1,'Acceptance failed')
        try:refusal=json.loads(result.stdout.decode().splitlines()[-1])
        except (ValueError,IndexError):raise Failure() from None
        if refusal.get('reason')!='Use a fresh checkout without .local, node_modules or dist' or refusal.get('exit_code')!=2 or refusal.get('passed') is not False or refusal.get('version')!=self.version or fingerprint()!=before:
            raise Failure()
        self.stages[-1]['negative_command_exit']=1
        self.stages[-1]['state_unchanged']=True

    def cleanup(self):
        self.stop_client()
        # All names are random, checked absent before creating, and owned by this run.
        for project in reversed(self.owned):self.compose(project,'down','--volumes')
        if self.backup:shutil.rmtree(self.backup);self.backup=None

    def execute(self):
        self.tracing=True
        try:
            self.stage('preflight',self.prepare)
            self.stage('clean-start-and-real-users',self.bootstrap)
            self.stage('retained-volume-restart',self.retained_restart)
            self.stage('real-http-and-two-browser-documents',self.real_flow)
            self.stage('independent-four-volume-and-host-restore',self.backup_restore)
            self.stage('reject-state-reuse-without-side-effects',self.verify_reuse_refusal)
            self.passed=True
        finally:
            if self.created:
                try:self.stage('owned-resource-cleanup',self.cleanup)
                except Failure:self.passed=False
                report=self.public_report()
                if self.local.is_dir() and not self.local.is_symlink():
                    (self.local/'p072-report.json').write_text(json.dumps(report,indent=2)+'\n')
                print(json.dumps(report),flush=True)
        return 0 if self.passed else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-real-matrix',action='store_true')
    parser.add_argument('--approval-reference',default='')
    args=parser.parse_args()
    if not args.allow_real_matrix or not args.approval_reference.strip():parser.error('Explicit isolated real-test approval reference required')
    root=Path(__file__).resolve().parents[1]
    version=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}',version):raise Failure(2)
    runner=CleanRoom(root,version)
    try:return runner.execute()
    except Failure as error:
        if not runner.created:print(json.dumps({'passed':False,'accepted':False,'version':version,'stage':'preflight','exit_code':error.code,'reason':error.reason}),flush=True)
        return 1
    except Exception:
        print(json.dumps({'passed':False,'accepted':False,'version':version,'stage':runner.stage_name,'reason':'Unexpected runner failure'}),flush=True)
        return 1  # Private command output never becomes public diagnostics.


if __name__=='__main__':raise SystemExit(main())
