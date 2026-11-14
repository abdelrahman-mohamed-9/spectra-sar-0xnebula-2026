#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if command -v open >/dev/null 2>&1; then
  open "judge-demo/index.html"
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "judge-demo/index.html"
else
  echo "Open this file in a browser: $PWD/judge-demo/index.html"
fi
