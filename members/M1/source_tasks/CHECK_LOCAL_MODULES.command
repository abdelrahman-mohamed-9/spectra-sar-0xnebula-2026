#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
printf '\n== M1 T02 catalog parser (test fixtures only) ==\n'
(cd "$ROOT/T02_Real_Scene_Discovery" && python3 -m unittest test_discovery.py)
printf '\n== M1 T03 gatekeeper (no NASA rasters) ==\n'
(cd "$ROOT/T03_Scientific_Validation" && python3 -m unittest discover -s tests -p 'test_*.py')
printf '\n== M1 T04 AOI metadata ==\n'
python3 "$ROOT/T04_AOI_Metadata/scripts/validate_aoi.py"
printf '\n== M1 T05 downloader + raster quality tests ==\n'
(cd "$ROOT/T05_Real_Data_Access" && python3 -m unittest discover -s tests -p 'test_*.py')
printf '\nAll local software checks completed; this does not prove real NASA data were downloaded.\n'
