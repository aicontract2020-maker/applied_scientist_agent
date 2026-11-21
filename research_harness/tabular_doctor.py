"""Installation diagnostics for frozen tabular execution, never research permission."""
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from .portable import ROOT
from .tabular_baseline import environment
from .tabular_sandbox import isolation_probe


_PROBE_KEYS = {'private_labels_denied', 'repo_denied', 'input_readonly',
               'network_denied', 'output_writable'}
_IMPORT_CHECK = """import json, sys
import numpy, scipy, sklearn, joblib, threadpoolctl
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR
print(json.dumps({'prefix': sys.prefix, 'imports_ok': True}))
"""


def doctor(*, probe_isolation=False, root=ROOT):
    root = Path(root).absolute()
    python = root/'.venv-tabular/bin/python'  # Preserve venv symlink, as execution does.
    checks = []
    install = 'Run bash scripts/bootstrap-tabular.sh with Python 3.12; no data or Codex needed.'

    def check(name, action, fix):
        try:
            detail = action()
        except Exception as exc:
            checks.append({'name': name, 'status': 'FAIL', 'detail': str(exc), 'fix': fix})
            return False
        checks.append({'name': name, 'status': 'PASS', 'detail': detail})
        return True

    def require(condition, detail):
        if not condition:
            raise ValueError(detail)
        return detail

    supported = check('platform', lambda: require(
        (sys.platform == 'darwin' and platform.machine() == 'arm64') or
        (sys.platform == 'linux' and platform.machine() in ('x86_64', 'aarch64')),
        f'{sys.platform}/{platform.machine()}; supported: macOS Apple Silicon or Linux x86_64/aarch64'),
        'Use a supported platform; never remove isolation checks.')
    interpreter = check('interpreter', lambda: require(python.is_file() and os.access(python, os.X_OK),
                        f'Expected executable: {python}'), install)
    if supported and interpreter:
        versions = check('locked_environment', lambda: environment(python), install)
    else:
        versions = False
        checks.append({'name': 'locked_environment', 'status': 'SKIPPED', 'detail': 'Platform or interpreter failed.'})

    def imports():
        value = json.loads(subprocess.check_output(
            [str(python), '-I', '-B', '-c', _IMPORT_CHECK], text=True, stderr=subprocess.PIPE, timeout=30))
        if (not isinstance(value, dict) or value.get('imports_ok') is not True
                or Path(value.get('prefix', '')).resolve() != python.parent.parent.resolve()):
            raise ValueError('Scientific imports or checkout virtual environment identity failed')
        return value

    if versions:
        check('scientific_imports', imports, install)
    else:
        checks.append({'name': 'scientific_imports', 'status': 'SKIPPED', 'detail': 'Locked environment not verified.'})

    if sys.platform == 'linux':
        check('ordinary_user', lambda: require(os.geteuid() != 0, 'Linux execution requires a non-root user'),
              'Run as your ordinary server account; install OS packages separately.')
        check('isolation_tool', lambda: require(shutil.which('bwrap') is not None, 'Bubblewrap must be available'),
              'Ask the administrator to install bubblewrap; see docs/LINUX.md. Do not disable host security policy.')
    elif sys.platform == 'darwin':
        check('isolation_tool', lambda: require(shutil.which('sandbox-exec') is not None, 'macOS Seatbelt must be available'),
              'Use a supported macOS environment with sandbox-exec; no unisolated fallback.')
    else:
        checks.append({'name': 'isolation_tool', 'status': 'SKIPPED', 'detail': 'Unsupported platform.'})

    prerequisites = all(item['status'] == 'PASS' for item in checks)
    attempted = False
    verified = False

    def probe():
        value = isolation_probe(root, python)
        if not isinstance(value, dict) or set(value) != _PROBE_KEYS or any(v is not True for v in value.values()):
            raise ValueError('Native isolation probe returned missing or unsuccessful boundaries')
        return value

    if probe_isolation and prerequisites:
        attempted = True
        verified = check('actual_isolation', probe,
                         'Inspect the host isolation setup (docs/LINUX.md on Linux); do not bypass it or retry research.')
    else:
        checks.append({'name': 'actual_isolation', 'status': 'SKIPPED' if probe_isolation else 'NOT_REQUESTED',
                       'detail': 'Prerequisites failed.' if probe_isolation else
                       'Not tested; explicitly use --probe-isolation for the synthetic kernel probe.'})
    ok = prerequisites and (verified if probe_isolation else True)
    return {'schema_version': 1, 'ok': ok,
            'status': ('ENVIRONMENT_AND_ISOLATION_CHECKS_PASSED' if verified else
                       'ENVIRONMENT_CHECKS_PASSED') if ok else 'BLOCKED_ENVIRONMENT',
            'scope': 'Frozen Abalone/Airfoil baseline and candidate worker execution only; excludes proposal actor and Codex login.',
            'root': str(root), 'python': str(python), 'checks': checks,
            'isolation_probe_requested': probe_isolation, 'isolation_probe_attempted': attempted,
            'isolation_verified': verified, 'execution_authorized': False,
            'research_state_changed': False, 'research_data_read': False, 'model_call_made': False,
            'note': 'Diagnostic snapshot, not approval or scientific evidence. Original execution checks and isolation still apply. An explicit probe creates temporary synthetic files and attempts a denied network connection.'}
