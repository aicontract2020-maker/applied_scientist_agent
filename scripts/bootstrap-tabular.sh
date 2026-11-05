#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
TABULAR_PYTHON="${PYTHON_BIN:-python3.12}"
"$TABULAR_PYTHON" -c 'import sys; assert sys.version_info[:2] == (3,12), "Use Python 3.12"'
TABULAR_PYTHON="$("$TABULAR_PYTHON" -c 'import os,sys; print(os.path.realpath(sys.executable))')"
if [[ ! -d .venv-tabular ]]; then "$TABULAR_PYTHON" -m venv .venv-tabular; fi
.venv-tabular/bin/python -c 'import sys; assert sys.version_info[:2] == (3,12), "Existing environment is not Python 3.12"'
.venv-tabular/bin/python -m pip install --only-binary=:all: -r requirements-tabular.lock.txt
.venv-tabular/bin/python -m pip check
echo 'Tabular environment ready. No dataset, model account, training or research run was started.'
