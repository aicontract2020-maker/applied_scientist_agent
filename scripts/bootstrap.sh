#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo 'Usage: bash scripts/bootstrap.sh [--skip-assets]'
  echo 'Requires Apple Silicon macOS or Linux x86_64/aarch64, Python 3.12, git. Override interpreter with PYTHON_BIN.'
  echo 'Installs pinned Python dependencies into .venv-sr; downloads assets unless skipped.'
  exit 0
fi
if [[ $# -gt 1 || ($# -eq 1 && "$1" != "--skip-assets") ]]; then
  echo 'Unknown argument. Use --help.' >&2; exit 2
fi
bootstrap_os="$(uname -s)"
bootstrap_arch="$(uname -m)"
if [[ "$bootstrap_os" == Linux && ("$bootstrap_arch" == x86_64 || "$bootstrap_arch" == aarch64) ]]; then
  if [[ "$(id -u)" == 0 ]]; then echo 'Use an ordinary account, not root/sudo, for bootstrap and research.' >&2; exit 1; fi
  if ! command -v bwrap >/dev/null; then echo 'Install bubblewrap first (Ubuntu: sudo apt-get install bubblewrap).' >&2; exit 1; fi
elif [[ "$bootstrap_os" != Darwin || "$bootstrap_arch" != arm64 ]]; then
  echo 'Supported: Apple Silicon macOS or Linux x86_64/aarch64 with rootless Bubblewrap. No unsafe fallback.' >&2; exit 1
fi
cd "$(dirname "$0")/.."
bootstrap_python="${PYTHON_BIN:-python3.12}"
if ! command -v "$bootstrap_python" >/dev/null; then
  echo 'Install Python 3.12 + venv support (Ubuntu 24.04: sudo apt-get install python3.12-venv), or set PYTHON_BIN.' >&2; exit 1
fi
bootstrap_python="$("$bootstrap_python" -c 'import os,sys; print(os.path.realpath(sys.executable))')"
"$bootstrap_python" -c 'import sys; assert sys.version_info[:2] == (3,12), "Use Python 3.12 for the pinned SR environment"'
if [[ ! -d .venv-sr ]]; then "$bootstrap_python" -m venv .venv-sr; fi
.venv-sr/bin/python -c 'import sys; assert sys.version_info[:2] == (3,12), "Existing .venv-sr is not Python 3.12; choose a fresh clone"'
# Normalize only our venv's interpreter aliases to the same real binary. This avoids
# an intermediate ~/.local/bin symlink crossing the candidate read boundary.
"$bootstrap_python" - <<'PYTHON'
import os
from pathlib import Path
for name in ('python', 'python3', 'python3.12'):
    alias = Path('.venv-sr/bin') / name
    if alias.is_symlink():
        target = alias.resolve(strict=True)
        temporary = alias.with_name(alias.name + '.normalized')
        temporary.symlink_to(target)
        os.replace(temporary, alias)
PYTHON
.venv-sr/bin/python -m ensurepip --upgrade
if [[ "$bootstrap_os" == Linux ]]; then
  # Keep this pilot CPU-only; do not pull multi-GB CUDA dependencies from PyPI.
  .venv-sr/bin/python -m pip install --no-deps torch==2.8.0+cpu torchvision==0.23.0+cpu --index-url https://download.pytorch.org/whl/cpu
  .venv-sr/bin/python -m pip install -r requirements-sr.txt -c requirements-sr-linux.lock.txt
else
  .venv-sr/bin/python -m pip install -r requirements-sr.txt -c requirements-sr.lock.txt
fi
.venv-sr/bin/python -m pip check
mkdir -p .cache
.venv-sr/bin/python -m pip freeze > .cache/environment.freeze.txt
if [[ "${1:-}" != --skip-assets ]]; then
  .venv-sr/bin/python -m research_harness setup-assets
fi
echo 'Environment prepared. Install Codex CLI and poppler if needed; run codex login, then:'
echo '  .venv-sr/bin/python -m research_harness doctor'
echo '  .venv-sr/bin/python -m research_harness research --id first-study'
