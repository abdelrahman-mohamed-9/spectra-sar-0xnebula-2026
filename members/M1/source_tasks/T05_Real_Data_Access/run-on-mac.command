#!/bin/bash
set -u
cd "$(dirname "$0")" || exit 1
# Reuse supported Python 3.12–3.14 when installed, otherwise use default.
if command -v python3.13 >/dev/null 2>&1; then PYTHON=python3.13
elif command -v python3.12 >/dev/null 2>&1; then PYTHON=python3.12
elif command -v python3.14 >/dev/null 2>&1; then PYTHON=python3.14
else PYTHON=python3
fi
printf 'Using %s: ' "$PYTHON"
"$PYTHON" -V || exit 1
if [ ! -d .venv ]; then
  "$PYTHON" -m venv .venv || exit 1
fi
. .venv/bin/activate
python -m pip install --quiet --upgrade pip || exit 1
python -m pip install -r requirements.txt certifi || exit 1
# Avoid the macOS python.org SSL trust-store issue without disabling verification.
export SSL_CERT_FILE="$(python -m certifi)"
export REQUESTS_CA_BUNDLE="$SSL_CERT_FILE"
python fetch_harmony.py "$@"
RESULT=$?
python summarize.py || true
echo "===== FINAL T05 STATUS ====="
if [ -f output/t05-status.txt ]; then cat output/t05-status.txt; fi
exit "$RESULT"
