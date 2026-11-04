#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--help" ]]; then
  echo 'Usage: bash scripts/bootstrap.sh [--skip-assets]'
  echo 'Requires Apple Silicon macOS, Python 3.12, git. Override interpreter with PYTHON_BIN.'
  echo 'Installs pinned Python dependencies into .venv-sr; downloads assets unless skipped.'
  exit 0
fi
if [[ $# -gt 1 || ($# -eq 1 && "$1" != "--skip-assets") ]]; then
  echo 'Unknown argument. Use --help.' >&2; exit 2
fi
if [[ "$(uname -s)" != Darwin || "$(uname -m)" != arm64 ]]; then
  echo 'Autonomous research currently supports Apple Silicon macOS Seatbelt. See README for the portable offline demo.' >&2; exit 1
fi
cd "$(dirname "$0")/.."
bootstrap_python="${PYTHON_BIN:-python3.12}"
if ! command -v "$bootstrap_python" >/dev/null; then
  echo 'Install Python 3.12 (brew install python@3.12), or set PYTHON_BIN to its path.' >&2; exit 1
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
.venv-sr/bin/python -m pip install -r requirements-sr.txt -c requirements-sr.lock.txt
.venv-sr/bin/python -m pip check
mkdir -p .cache
.venv-sr/bin/python -m pip freeze > .cache/environment.freeze.txt
if [[ "${1:-}" != --skip-assets ]]; then
  .venv-sr/bin/python -m research_harness setup-assets
fi
echo 'Environment prepared. Install Codex CLI and poppler if needed; run codex login, then:'
echo '  .venv-sr/bin/python -m research_harness doctor'
echo '  .venv-sr/bin/python -m research_harness research --id first-study'
