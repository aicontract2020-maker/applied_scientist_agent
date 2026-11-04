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


def isolation_probe():
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
        code = '''import json, pathlib, socket
result={}
for label, path in PATHS.items():
 try:
  pathlib.Path(path).read_bytes(); result[label]='ALLOWED'
 except PermissionError: result[label]='DENIED'
try:
 pathlib.Path(OUTSIDE).write_text('forbidden');result['outside_write']='ALLOWED'
except PermissionError:result['outside_write']='DENIED'
EXTRA
print(json.dumps(result))
'''.replace('PATHS',repr({'repo_read':str(private),'control_read':str(control/'secret')})).replace('OUTSIDE',repr(str(base/'outside')))
        results = {}
        try:
            for kind in ('actor','candidate'):
                profile = actor_profile(control,actor) if kind=='actor' else candidate_profile(control,control/'snapshot',control/'inputs',control/'output',control/'trusted')
                extra = '' if kind=='actor' else '''import numpy, cv2
result['imports']='OK'
try:
 socket.socket().connect(('127.0.0.1',9));result['network']='ALLOWED'
except PermissionError:result['network']='DENIED'
'''
                script=(actor if kind=='actor' else control/'trusted')/'probe.py';script.write_text(code.replace('EXTRA',extra))
                sb=base/f'{kind}.sb';sb.write_text(profile)
                completed=subprocess.run(['/usr/bin/sandbox-exec','-f',str(sb),('/usr/bin/python3' if kind=='actor' else str(PYTHON)),'-B',str(script)],capture_output=True,text=True,timeout=30)
                if completed.returncode:raise ValueError(f'{kind} isolation failed: {completed.stderr[-800:]}')
                value=json.loads(completed.stdout)
                if any(value.get(k)!='DENIED' for k in ('repo_read','control_read','outside_write')):
                    raise ValueError(f'{kind} filesystem boundary failed: {value}')
                if kind=='candidate' and (value.get('network')!='DENIED' or value.get('imports')!='OK'):
                    raise ValueError(f'Candidate network/import probe failed: {value}')
                results[kind]=value
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
    check('platform',lambda:require(sys.platform=='darwin','Full autonomous SR requires macOS; offline demo is portable'),'Use a Mac; do not disable the isolation profile')
    check('python',lambda:require(sys.version_info[:2]==(3,12),f'Python {platform.python_version()} (required 3.12)'),'Run bootstrap.sh with Python 3.12')
    def dependencies():
        found={}
        for line in (ROOT/'requirements-sr.txt').read_text().splitlines():
            if not line or line.startswith('#'):continue
            name,expected=line.split('==');actual=importlib.metadata.version(name)
            if actual!=expected:raise ValueError(f'{name}: expected {expected}, installed {actual}')
            found[name]=actual
        import numpy,cv2,torch,torchvision,timm
        return found
    check('python_dependencies',dependencies,'bash scripts/bootstrap.sh')
    for tool in ('git','pdftotext'):
        check(tool,lambda tool=tool:require(shutil.which(tool) is not None,f'{tool} available'),'Install git and poppler (brew install poppler)')
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
    if all(x['ok'] for x in checks if x['name'] in ('platform','python_dependencies')):
        check('actual_os_isolation',isolation_probe,'Use an ordinary macOS terminal; nested restricted runtimes may reject sandbox-exec')
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
    return {'ok':all(x['ok'] for x in checks),'checks':checks,'model_call_made':False,'scope':'Local prototype checks; not multi-tenant security certification'}
