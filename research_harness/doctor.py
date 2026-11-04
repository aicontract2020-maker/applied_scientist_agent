"""Preflight checks. No model calls, scores, training, or scientific experiments."""
import importlib.metadata
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .portable import ROOT, verify_sources


def isolation_probe(check_login=True):
    from .autonomy import PYTHON, actor_profile, candidate_profile
    with tempfile.TemporaryDirectory(prefix='rh-doctor-') as directory:
        base = Path(directory).resolve(); actor=base/'agent'; control=base/'control'
        for path in [actor,actor/'responses',control,control/'snapshot',control/'inputs',control/'output',control/'trusted']:
            path.mkdir(exist_ok=True)
        marker = ROOT/'.cache/doctor-marker'; marker.parent.mkdir(exist_ok=True)
        # Unique file in the repo checks HR denial even when the clone lives outside /Users.
        with tempfile.NamedTemporaryFile(dir=marker.parent, prefix='doctor-private-', delete=False) as f:
            private = Path(f.name); f.write(b'synthetic marker')
        (control/'secret').write_text('synthetic control')
        (actor/'responses/reply').write_text('trusted reply')
        (base/'outside').write_text('outside marker')
        (control/'inputs/read-only').write_text('input marker')
        (actor/'escape').symlink_to(control/'secret')
        code = '''import json, pathlib, socket
result={}
for label, path in PATHS.items():
 try:
  pathlib.Path(path).read_bytes(); result[label]='ALLOWED'
 except (PermissionError, FileNotFoundError): result[label]='DENIED'
try:
 pathlib.Path(OUTSIDE).write_text('forbidden');result['outside_write']='ALLOWED'
except (PermissionError, FileNotFoundError):result['outside_write']='DENIED'
try:
 pathlib.Path(REPLY).write_text('forbidden');result['response_write']='ALLOWED'
except (PermissionError, FileNotFoundError):result['response_write']='DENIED'
EXTRA
print(json.dumps(result))
'''.replace('PATHS',repr({'repo_read':str(private),'control_read':str(control/'secret'),'symlink_escape':str(actor/'escape')})).replace('OUTSIDE',repr(str(base/'outside'))).replace('REPLY',repr(str(actor/'responses/reply')))
        results = {}
        try:
            for kind in ('actor','candidate'):
                profile = actor_profile(control,actor) if kind=='actor' else candidate_profile(control,control/'snapshot',control/'inputs',control/'output',control/'trusted')
                extra = "assert pathlib.Path(RESPONSE).read_text()=='trusted reply'\n".replace('RESPONSE',repr(str(actor/'responses/reply'))) if kind=='actor' else '''import numpy, cv2
result['imports']='OK'
assert pathlib.Path(INPUT).read_text()=='input marker'
try:
 pathlib.Path(INPUT).write_text('forbidden');result['input_write']='ALLOWED'
except PermissionError:result['input_write']='DENIED'
try:
 socket.socket().connect(('1.1.1.1',443));result['network']='ALLOWED'
except (PermissionError, OSError) as exc:
 if isinstance(exc, PermissionError) or exc.errno in (101, 113):result['network']='DENIED'
 else:raise
'''
                extra=extra.replace('INPUT',repr(str(control/'inputs/read-only')))
                if sys.platform=='linux' and kind=='candidate':
                    host_netns=__import__('os').readlink('/proc/self/ns/net')
                    extra+=f"\nimport os\nassert os.readlink('/proc/self/ns/net') != {host_netns!r}\nresult['network_namespace_isolated']=True\n"
                script=(actor if kind=='actor' else control/'trusted')/'probe.py';script.write_text(code.replace('EXTRA',extra))
                sb=base/f'{kind}.sb';sb.write_text(profile)
                argv=[('/usr/bin/python3' if kind=='actor' else str(PYTHON)),'-B',str(script)]
                if sys.platform=='linux':
                    from .linux_isolation import linux_actor_command, linux_candidate_command
                    argv=linux_actor_command(argv,ROOT,control,actor) if kind=='actor' else linux_candidate_command(argv,ROOT,PYTHON,control/'snapshot',control/'inputs',control/'output',control/'trusted')
                elif sys.platform=='darwin':
                    argv=['/usr/bin/sandbox-exec','-f',str(sb),*argv]
                else: raise ValueError('Unsupported OS: no unisolated fallback')
                completed=subprocess.run(argv,capture_output=True,text=True,timeout=30)
                if completed.returncode:raise ValueError(f'{kind} isolation failed: {completed.stderr[-800:]}')
                value=json.loads(completed.stdout)
                if any(value.get(k)!='DENIED' for k in ('repo_read','control_read','outside_write','response_write','symlink_escape')):
                    raise ValueError(f'{kind} filesystem boundary failed: {value}')
                if kind=='candidate' and (value.get('network')!='DENIED' or value.get('imports')!='OK' or value.get('input_write')!='DENIED'):
                    raise ValueError(f'Candidate network/import probe failed: {value}')
                if sys.platform=='linux':
                    # Separate PID namespace must hide the host controller, not only its files.
                    host_pid=__import__('os').getpid()
                    process_probe=script.parent/'pid-probe.py'
                    process_probe.write_text(f"from pathlib import Path\nassert not Path('/proc/{host_pid}/cmdline').exists()\n")
                    pid_argv=linux_actor_command(['/usr/bin/python3',str(process_probe)],ROOT,control,actor) if kind=='actor' else linux_candidate_command([str(PYTHON),str(process_probe)],ROOT,PYTHON,control/'snapshot',control/'inputs',control/'output',control/'trusted')
                    subprocess.run(pid_argv,capture_output=True,text=True,timeout=30,check=True)
                    value['host_pid_hidden']=True
                results[kind]=value
            if sys.platform=='linux' and check_login:
                login=linux_actor_command(['codex','login','status'],ROOT,control,actor)
                checked=subprocess.run(login,capture_output=True,text=True,timeout=30)
                if checked.returncode:raise ValueError('Codex auth is unavailable inside Linux boundary. Use a dedicated file-backed CODEX_HOME and codex login --device-auth')
                results['actor_login']='AVAILABLE'
            if (actor/'responses/reply').read_text()!='trusted reply':raise ValueError('Actor overwrote controller response')
            if (base/'outside').read_text()!='outside marker':raise ValueError('Outside host file modified')
            if (control/'inputs/read-only').read_text()!='input marker':raise ValueError('Candidate changed trusted input')
        finally:
            private.unlink(missing_ok=True)
        return results


def doctor(network=False):
    checks=[]
    def check(name, function, fix):
        try:
            detail=function();checks.append({'name':name,'ok':True,'detail':detail})
        except Exception as exc:
            checks.append({'name':name,'ok':False,'detail':str(exc),'fix':fix})
    def require(condition, message):
        if not condition:raise ValueError(message)
        return message
    check('platform',lambda:require((sys.platform=='darwin' and platform.machine()=='arm64') or (sys.platform=='linux' and platform.machine() in ('x86_64','aarch64')),'Supported: Apple Silicon macOS or Linux x86_64/aarch64 with rootless Bubblewrap'),'Use a supported OS and a non-root account; do not disable isolation')
    check('python',lambda:require(sys.version_info[:2]==(3,12),f'Python {platform.python_version()} (required 3.12)'),'Run bootstrap.sh with Python 3.12')
    check('repo_environment',lambda:require(Path(sys.prefix).resolve()==(ROOT/'.venv-sr').resolve(),'Interpreter must use this clone’s .venv-sr'), 'Use .venv-sr/bin/python after bootstrap')
    def dependencies():
        found={}
        for line in (ROOT/('requirements-sr-linux.lock.txt' if sys.platform=='linux' else 'requirements-sr.lock.txt')).read_text().splitlines():
            if not line or line.startswith('#'):continue
            name,expected=line.split('==');actual=importlib.metadata.version(name)
            if actual!=expected:raise ValueError(f'{name}: expected {expected}, installed {actual}')
            found[name]=actual
        import numpy,cv2,torch,torchvision,timm
        if sys.platform=='linux' and torch.version.cuda is not None:raise ValueError('Linux pilot requires the pinned CPU-only torch build')
        return found
    check('python_dependencies',dependencies,'bash scripts/bootstrap.sh')
    for tool in ('git','pdftotext'):
        check(tool,lambda tool=tool:require(shutil.which(tool) is not None,f'{tool} available'),'Install git and poppler: macOS brew install poppler; Ubuntu sudo apt-get install git poppler-utils')
    def codex():
        helptext=subprocess.check_output(['codex','exec','--help'],text=True,stderr=subprocess.PIPE,timeout=15)
        for flag in ['--ignore-user-config','--ephemeral','--json','--output-last-message']:
            if flag not in helptext:raise ValueError(f'Codex CLI lacks {flag}; tested 0.144.0')
        global_help=subprocess.check_output(['codex','--help'],text=True,stderr=subprocess.PIPE,timeout=15)
        if '--search' not in global_help:raise ValueError('Codex CLI lacks live --search')
        result=subprocess.run(['codex','login','status'],capture_output=True,text=True,timeout=15)
        if result.returncode:raise ValueError('Codex not logged in; run codex login')
        return subprocess.check_output(['codex','--version'],text=True,stderr=subprocess.PIPE,timeout=15).strip()
    check('codex_login_and_flags',codex,'Install Codex CLI, then run codex login in your own terminal')
    check('assets',lambda:(verify_sources(), 'Pinned repositories, weights and 100 Urban100 pairs verified')[1],'Run python -m research_harness setup-assets; inspect mismatches, never reset blindly')
    if sys.platform=='linux':
        check('non_root_user',lambda:require(__import__('os').geteuid()!=0,'Linux research must run as a non-root user'),'Run as your ordinary server account, not sudo/root')
        check('bubblewrap',lambda:require(shutil.which('bwrap') is not None,'bubblewrap must be installed'),'Ubuntu: sudo apt-get install bubblewrap; user namespaces must be permitted')
    if all(x['ok'] for x in checks if x['name'] in ('platform','python_dependencies')):
        check('actual_os_isolation',isolation_probe,'macOS: normalize aliases/use a normal terminal. Linux: install bwrap and ask the admin to permit unprivileged user namespaces (AppArmor/seccomp may restrict them). No unsafe fallback.')
    else:
        checks.append({'name':'actual_os_isolation','ok':False,'detail':'Prerequisite failed','fix':'Resolve platform/Python dependencies first'})
    if network:
        def connectivity():
            import urllib.request
            for url in ['https://arxiv.org/abs/2108.10257','https://github.com/JingyunLiang/SwinIR']:
                with urllib.request.urlopen(url,timeout=20) as response:
                    if response.status!=200:raise ValueError(f'HTTP {response.status}')
            return 'arXiv and GitHub reachable; model access/billing still not verified without a real call'
        check('network',connectivity,'Check proxy, TLS certificates and outbound HTTPS')
    return {'ok':all(x['ok'] for x in checks),'isolation_backend':'linux-bubblewrap' if sys.platform=='linux' else 'macos-seatbelt','checks':checks,'model_call_made':False,'scope':'Local prototype checks; not multi-tenant security certification'}
