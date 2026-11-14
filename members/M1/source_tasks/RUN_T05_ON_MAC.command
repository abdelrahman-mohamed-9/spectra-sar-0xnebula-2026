#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/T05_Real_Data_Access"
bash run-on-mac.command "$@"
