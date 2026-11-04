"""Rootless Linux mount/PID/network namespaces. Never exposes the host root tree.

Actor: explicit system/runtime mounts, its workspace and dedicated Codex state.
Candidate: read-only runtime/snapshot/inputs, writable outputs, isolated networking.
No subprocess-only fallback. Actual kernel behavior must pass doctor probes.
"""
import json
import os
from pathlib import Path
import shutil
import sys

SYSTEM_DIRS = ('/usr', '/bin', '/sbin', '/lib', '/lib64')
SYSTEM_FILES = ('/etc/ld.so.cache', '/etc/resolv.conf', '/etc/hosts', '/etc/nsswitch.conf',
                '/etc/passwd', '/etc/group', '/etc/localtime', '/etc/services', '/etc/protocols')
SYSTEM_CERTS = ('/etc/ssl/certs', '/usr/local/share/ca-certificates')


def bwrap_base(network):
    binary = shutil.which('bwrap')
    if not binary: raise ValueError('Linux isolation requires bubblewrap: sudo apt-get install bubblewrap')
    if os.geteuid() == 0: raise ValueError('Run research as an ordinary Linux user, never root; install OS packages separately')
    command = [binary, '--die-with-parent', '--new-session', '--unshare-user', '--unshare-pid',
               '--unshare-ipc', '--unshare-uts', '--disable-userns', '--assert-userns-disabled',
               '--cap-drop', 'ALL', '--hostname', 'research-sandbox']
    if not network: command.append('--unshare-net')
    for name in (*SYSTEM_DIRS, *SYSTEM_FILES, *SYSTEM_CERTS):
        if Path(name).exists(): command += ['--ro-bind', name, name]
    command += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--tmpfs', '/run']
    return command


def readonly(command, source):
    source = Path(source).absolute()
    if not source.exists(): raise ValueError(f'Missing sandbox runtime/input: {source}')
    command += ['--ro-bind', str(source), str(source)]


def python_runtime(command, python):
    # CPython venv may use a base interpreter outside /usr (uv/pyenv/etc.). Mount
    # only its installation prefix, never the whole home or repository.
    python = Path(python).absolute()
    prefix = python.resolve(strict=True).parent.parent
    if prefix in (Path('/'), Path.home()): raise ValueError('Python runtime prefix is too broad to expose')
    readonly(command, prefix)
    return prefix


def codex_runtime(command):
    found = shutil.which('codex')
    if not found: raise ValueError('Install Codex CLI and run codex login first')
    executable = Path(found).resolve(strict=True)
    # npm Codex optional native packages are siblings below node_modules/@openai.
    package = next((p for p in executable.parents if p.name == '@openai' and p.parent.name == 'node_modules'), None)
    readonly(command, package or executable)
    node = shutil.which('node')
    extra_path = []
    if node:
        node = Path(node).resolve(strict=True)
        prefix = node.parent.parent
        if prefix not in (Path('/'), Path.home()): readonly(command, prefix)
        else: readonly(command, node)
        extra_path.append(str(node.parent))
    return str(executable), ':'.join([*extra_path, '/usr/local/bin', '/usr/bin', '/bin'])


def linux_actor_command(argv, root, control, actor):
    command = bwrap_base(network=True)
    executable, path = codex_runtime(command)
    # Mask AFTER runtime mounts, including /usr-based installations.
    command += ['--tmpfs', str(root)]
    state = Path(os.environ.get('CODEX_HOME', str(Path.home()/'.codex'))).expanduser().resolve()
    if not state.is_dir(): raise ValueError('Codex state missing; run codex login with a private CODEX_HOME')
    if state == Path.home() or state == Path('/'): raise ValueError('CODEX_HOME must be a dedicated directory')
    command += ['--dir', '/home/research', '--bind', str(state), '/home/research/.codex',
                '--bind', str(actor), str(actor), '--ro-bind', str(actor/'responses'), str(actor/'responses'),
                '--setenv', 'HOME', '/home/research', '--setenv', 'CODEX_HOME', '/home/research/.codex',
                '--setenv', 'PATH', path, '--setenv', 'TMPDIR', '/tmp', '--unsetenv', 'PYTHONPATH',
                '--unsetenv', 'LD_PRELOAD', '--chdir', str(actor)]
    for key in ('SSL_CERT_FILE', 'CODEX_CA_CERTIFICATE'):
        if os.environ.get(key): readonly(command, Path(os.environ[key]).resolve())
    command += ['--remount-ro', str(root), '--remount-ro', '/']
    # Probe commands use system Python; actual actor uses the resolved CLI path.
    actual = [executable, *argv[1:]] if argv[0] == 'codex' else list(argv)
    return [*command, '--', *actual]


def linux_candidate_command(argv, root, python, snapshot, inputs, output, trusted):
    command = bwrap_base(network=False)
    prefix = python_runtime(command, python)
    command += ['--tmpfs', str(root)]
    if prefix == root: raise ValueError('Python base prefix cannot equal the repository root')
    if prefix.is_relative_to(root): readonly(command, prefix)
    readonly(command, Path(python).parent.parent)
    for path in (snapshot, inputs, trusted): readonly(command, path)
    command += ['--bind', str(output), str(output), '--clearenv', '--setenv', 'HOME', '/nonexistent',
                '--setenv', 'OPENBLAS_NUM_THREADS', '4', '--setenv', 'OMP_NUM_THREADS', '4', '--setenv', 'LANG', 'C.UTF-8',
                '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'PYTHONNOUSERSITE', '1',
                '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', '--chdir', str(snapshot),
                '--remount-ro', str(root), '--remount-ro', '/tmp', '--remount-ro', '/run',
                '--remount-ro', '/proc', '--remount-ro', '/', '--', *map(str, argv)]
    return command


def write_command_manifest(path, command):
    Path(path).write_text(json.dumps({'backend':'linux-bubblewrap','argv':command,
                                    'scope':'Explicit mounts, user/PID namespaces; no unisolated fallback'},indent=2)+'\n')
