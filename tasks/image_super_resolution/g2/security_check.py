"""Actual OS boundary checks on existing files; no model inference or scientific trial."""
import json
import subprocess
import tempfile
from pathlib import Path

from research_harness.autonomy import ROOT, PYTHON, actor_profile, candidate_profile

base = Path(tempfile.mkdtemp(prefix='rh-g2-isolation-check-')).resolve()
actor, control = base/'actor', base/'control'
for folder in (actor, control, actor/'responses', control/'trusted', control/'snapshot', control/'inputs', control/'output'):
    folder.mkdir(exist_ok=True)
(control/'secret.txt').write_text('synthetic secret marker')
hr = ROOT/'external/SelfExSR/data/Set14/image_SRF_2/img_001_SRF_2_HR.png'
alias = Path('/System/Volumes/Data') / str(hr).lstrip('/')
paths = {'hidden_reference': str(hr), 'volume_alias': str(alias), 'control_state': str(control/'secret.txt')}
code = '''import json, pathlib, socket
paths = PATHS
result = {}
for key,path in paths.items():
    try:
        pathlib.Path(path).read_bytes(); result[key]='UNEXPECTED_ALLOWED'
    except PermissionError:
        result[key]='DENIED'
    except FileNotFoundError:
        result[key]='MISSING_ALIAS'
try:
    pathlib.Path(FORBIDDEN_WRITE).write_text('bad');result['outside_write']='UNEXPECTED_ALLOWED'
except PermissionError:
    result['outside_write']='DENIED'
EXTRA
print(json.dumps(result))
'''.replace('PATHS',repr(paths)).replace('FORBIDDEN_WRITE',repr(str(base/'outside.txt')))
for kind in ('actor','candidate'):
    script = actor/'probe.py' if kind=='actor' else control/'trusted/probe.py'
    if kind=='actor':
        text=code.replace('EXTRA','')
        profile=actor_profile(control,actor)
        python='/usr/bin/python3'
    else:
        text=code.replace('EXTRA', '''import numpy, cv2
result['numpy_import']='OK'
try:
    socket.create_connection(('1.1.1.1',443),timeout=1);result['network']='UNEXPECTED_ALLOWED'
except PermissionError:
    result['network']='DENIED'
''')
        profile=candidate_profile(control,control/'snapshot',control/'inputs',control/'output',control/'trusted')
        python=str(PYTHON)
    script.write_text(text)
    policy=base/f'{kind}.sb';policy.write_text(profile)
    result=subprocess.run(['/usr/bin/sandbox-exec','-f',str(policy),python,'-B',str(script)],cwd=script.parent,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError(f'{kind} isolation setup failed: {result.stderr}')
    value=json.loads(result.stdout)
    assert value['hidden_reference']=='DENIED' and value['control_state']=='DENIED' and value['outside_write']=='DENIED',value
    assert value['volume_alias'] in ('DENIED','MISSING_ALIAS'),value
    if kind=='candidate':assert value['network']=='DENIED' and value['numpy_import']=='OK',value
    print(json.dumps({'kind':kind,**value}))
