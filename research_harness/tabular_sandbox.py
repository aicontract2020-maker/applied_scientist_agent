"""Task-local worker isolation; no model account or unisolated fallback."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from .autonomy import bounded_process, excluding, quote


def isolated_worker(root, python, control, trusted, inputs, output, script, arguments, timeout=240):
    python = Path(python).absolute()  # Keep the venv path; resolving its symlink loses site-packages.
    root, control, trusted, inputs, output = map(lambda p: Path(p).resolve(), (root, control, trusted, inputs, output))
    argv = [str(python), '-I', '-B', str(trusted/script), *map(str, arguments)]
    if sys.platform == 'linux':
        from .linux_isolation import linux_candidate_command
        command = linux_candidate_command(argv, root, python, trusted, inputs, output, trusted)
    elif sys.platform == 'darwin':
        binary = shutil.which('sandbox-exec')
        if not binary: raise ValueError('macOS Seatbelt unavailable; no fallback')
        runtime = [python.parent.parent, python.resolve().parent.parent]
        allowed = [trusted, inputs, output]
        profile = '\n'.join(['(version 1)', '(allow default)', '(deny network*)',
            f'(deny file-read* {excluding("/Users", runtime + allowed)} {excluding(root, runtime + allowed)} {excluding(control, allowed)})',
            f'(deny file-write* (require-all (require-not (subpath {quote(output)})) (require-not (subpath "/dev"))))'])
        path = trusted/'sandbox.sb'; path.write_text(profile)
        command = [binary, '-f', str(path), *argv]
    else:
        raise ValueError('Tabular worker requires Linux Bubblewrap or macOS Seatbelt')
    env = {'HOME': '/nonexistent', 'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8',
           'OMP_NUM_THREADS': '1', 'OPENBLAS_NUM_THREADS': '1', 'PYTHONNOUSERSITE': '1'}
    return bounded_process(command, trusted, output, timeout, env, quota=16*1024*1024)


def isolation_probe(root, python):
    """Real kernel test, only synthetic secrets. Failure never downgrades isolation."""
    with tempfile.TemporaryDirectory(prefix='rh-tabular-probe-') as directory:
        control = Path(directory).resolve()
        trusted, inputs, output = (control/x for x in ('trusted', 'inputs', 'output'))
        trusted.mkdir(); inputs.mkdir()
        hidden = control/'validation-targets.json'; hidden.write_text('PRIVATE_FIXTURE')
        holdout = control/'holdout-targets.json'; holdout.write_text('PRIVATE_FIXTURE')
        (inputs/'features.json').write_text('PUBLIC_FIXTURE')
        code = '''import json, pathlib, socket
hidden, holdout, inputs, output, repo = map(pathlib.Path, __import__('sys').argv[1:])
for path in (hidden, holdout, repo/'README.md'):
    try: path.read_bytes()
    except OSError: pass
    else: raise AssertionError('private read allowed')
assert (inputs/'features.json').read_text() == 'PUBLIC_FIXTURE'
try: (inputs/'features.json').write_text('changed')
except OSError: pass
else: raise AssertionError('input write allowed')
try:
    sock = socket.socket(); sock.settimeout(1); sock.connect(('1.1.1.1',53))
except OSError: pass
else: raise AssertionError('network connection allowed')
(output/'probe.json').write_text(json.dumps({'private_labels_denied':True,'repo_denied':True,'input_readonly':True,'network_denied':True,'output_writable':True}))
'''
        (trusted/'probe.py').write_text(code)
        result = isolated_worker(root, python, control, trusted, inputs, output, 'probe.py',
                                 [hidden, holdout, inputs, output, Path(root).resolve()], timeout=15)
        if result['error']:
            raise ValueError('Tabular isolation probe failed; no execution: '+(output/'stderr.log').read_text()[-1500:])
        if (inputs/'features.json').read_text() != 'PUBLIC_FIXTURE': raise ValueError('Input mutated')
        return json.loads((output/'probe.json').read_text())
