#!/usr/bin/env bash
# Run real 17 Oct / 29 Oct 2026 NISAR HHHH user data through the existing integrated M1-M6 pipeline.
set -euo pipefail
cd "$(dirname "$0")"
DATA_DIR="${SPECTRA_REAL_DATA_DIR:-$HOME/Desktop/SPECTRA-SAR/data}"
if [ ! -s "$DATA_DIR/before.tif" ] || [ ! -s "$DATA_DIR/after.tif" ]; then
  echo "Missing REAL before.tif or after.tif in $DATA_DIR"
  echo 'The 2026-10-17 and 2026-10-29 real NASA TIFFs must remain on your Mac.'
  exit 2
fi
if [ ! -x .venv/bin/python ] || [ ! -f .venv/.spectra-installed ]; then
  echo 'Setting up existing project dependencies (no NASA re-download)...'
  bash START.command doctor || code=$?
  if [ ! -x .venv/bin/python ] || [ ! -f .venv/.spectra-installed ]; then
    echo 'Python dependency setup failed; inspect output above.'; exit 2
  fi
fi
.venv/bin/python -m phase1.import_real_nisar --data "$DATA_DIR" --output "$(pwd)/data/real-nisar-oct2026-pair"
echo 'Running ORIGINAL TEAM M1→M2→M3→M4→M5→M6 modules...'
set +e
.venv/bin/python -m phase1 run --config "$(pwd)/config/local.json" \
  --pair-dir "$(pwd)/data/real-nisar-oct2026-pair" > REAL-NISAR-LAST-RUN.log 2>&1
rc=$?
set -e
cat REAL-NISAR-LAST-RUN.log
printf '\n--- RUN SUMMARY ---\n'
.venv/bin/python - <<'PY'
import json
from pathlib import Path
root=Path('runs')
runs=sorted((p for p in root.iterdir() if (p/'run.json').is_file()),key=lambda p:(p/'run.json').stat().st_mtime,reverse=True)
if not runs:raise SystemExit('No run report found; see REAL-NISAR-LAST-RUN.log')
p=runs[0]
report=json.loads((p/'run.json').read_text())
print('RUN:',p.resolve())
print('OVERALL:',report.get('status'))
print('SCIENTIFICALLY APPROVED:',report.get('scientific_approval'))
for name,v in report.get('stages',{}).items():
 print(name,':',v.get('status'),'-',v.get('detail',''))
Path('REAL-NISAR-RUN-PATH.txt').write_text(str(p.resolve())+'\n')
PY
if [ "$rc" -eq 0 ]; then
 echo 'SOFTWARE PIPELINE FINISHED (EXPLORATORY; not science-approved).'
elif [ "$rc" -eq 2 ]; then
 echo 'PIPELINE PARTIAL/BLOCKED. Run folder logs identify which stage needs scientific input.'
else
 echo "PIPELINE ERROR code $rc. See REAL-NISAR-LAST-RUN.log."
fi
printf 'API, when launched separately: http://127.0.0.1:8765/docs\n'
exit "$rc"
