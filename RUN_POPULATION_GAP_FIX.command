#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
echo "SPECTRA-SAR M3: WorldPop spatial NoData scientific fallback"
if [ ! -x .venv/bin/python ]; then
  echo "ERROR: Existing .venv missing. Run your original START.command first."; exit 2
fi
.venv/bin/python -m phase1.finish_m3_live
printf '\nM3 report: %s\n' "$PWD/M3-LIVE-EXECUTION-REPORT.json"
