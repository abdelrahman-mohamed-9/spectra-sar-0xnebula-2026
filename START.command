#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
chosen="${SPECTRA_PYTHON:-}"
if [ ! -x .venv/bin/python ]; then
  if [ -z "$chosen" ]; then
    for candidate in python3.12 python3.13 python3.14 python3; do
      if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(not ((3,12) <= sys.version_info[:2] <= (3,14)))'; then chosen="$candidate"; break; fi
    done
  fi
  if [ -z "$chosen" ]; then echo 'Install Python 3.12, 3.13 or 3.14 first. Python 3.12 is the tested version.'; exit 1; fi
  "$chosen" -m venv .venv
fi
fingerprint="$(.venv/bin/python -c 'import hashlib; from pathlib import Path; print(hashlib.sha256(Path("requirements.txt").read_bytes()+Path("requirements-dev.txt").read_bytes()+Path("backend/pyproject.toml").read_bytes()+Path("constraints-tested.txt").read_bytes()).hexdigest())')"
if [ ! -f .venv/.spectra-installed ] || [ "$(cat .venv/.spectra-installed)" != "$fingerprint" ]; then
  .venv/bin/python -m pip install -r requirements-dev.txt -c constraints-tested.txt
  printf '%s' "$fingerprint" > .venv/.spectra-installed
fi
export PYTHONPATH="$PWD:$PWD/backend/src:$PWD/phase1_compat/m2"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2
case "${1:-serve}" in
  serve) shift || true; exec .venv/bin/python scripts/run_local.py "$@" ;;
  test) export SPECTRA_PHASE1="$PWD"; exec .venv/bin/python -m pytest -q tests_phase2 ;;
  demo) exec .venv/bin/python scripts/demo.py --state state-demo ;;
  import) shift; exec .venv/bin/python -m phase2.datasets "$@" ;;
  *) echo 'Usage: bash START.command [serve|test|demo|import]'; exit 1 ;;
esac
