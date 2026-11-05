"""Real Linux boundary probes with NO credentials, model calls or image scores.

For CI/admin verification only. Full doctor/research still requires a real login.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if sys.platform != 'linux':raise SystemExit('This is a Linux kernel check; run doctor on macOS')
from research_harness.doctor import isolation_probe
with tempfile.TemporaryDirectory(prefix='rh-ci-state-') as state:
    os.environ['CODEX_HOME']=state
    result=isolation_probe(check_login=False)
print(json.dumps({'kernel_probes_passed':True,'real_model_or_login_test':False,'results':result},indent=2))
