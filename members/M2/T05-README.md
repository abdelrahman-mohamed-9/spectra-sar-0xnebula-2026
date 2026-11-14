# Member 2 / Phase 1 / T05 — SAR Change Detection Engine

## Scope
A working, deterministic, tile-based **signed log-ratio** candidate detector for paired Sentinel-1 IW RTC products provided by M1 (GeoTIFF, gamma0 terrain linear power, same projected grid). It does **not** classify floods, buildings or environmental cause. No synthetic satellite claims.

## Outputs
- `change_score_db_VV.tif` float32, nodata=-9999, score = 10 log10(after/before)
- `change_mask_VV.tif` uint8: 0=no candidate, 1=decrease, 2=increase, 255=invalid/nodata
- `valid_mask_VV.tif` uint8: 1=usable, 0=invalid
- `change-summary.json`: provenance, counts, area estimates, explicit limitations

Threshold defaults to 3 dB as a **demonstration heuristic**, not a scientifically validated threshold; calibrate to real site and temporal conditions. Invalid, layover/shadow, nonpositive and nonfinite inputs are excluded by the T02 loader. Outputs preserve the CRS/transform of M1. Per-pixel area computed from square-meter projected grid. Counts are candidate pixels, not observed damage.

## Setup and smoke tests
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

## Run with actual M1 data
```bash
python change_detector.py /absolute/path/M1_pair --out /absolute/path/M2_change \
  --polarization VV --threshold-db 3.0 --tile-size 512 \
  --allow-unverified-registration
```
The last option is **an explicit exploratory-only bypass**, because T04 currently checks integer shifts only and **cannot certify subpixel registration**. Remove this bypass from the scientific production workflow once an independent subpixel QA module and machine-verifiable registration PASS artifact exist.

The CLI exit code `2` indicates output successfully generated but scientific QA is pending. `3` means failed; API raises errors. Review `change-summary.json` rather than assuming success from exit code alone.

## Dependencies
Input contract v1.1 from T01; T02 paired GeoTIFF validator and T04 registration diagnostics. T03 denoising is **not automatically incorporated** into this script: M1 pair rasters must be intentionally selected for the analysis. Apply T03 to each image separately only after scientific assessment, documenting parameters. Do not mix filtered and unfiltered rasters in comparisons.

## Still needed for scientific signoff
1. Actual Sentinel-1 RTC pair with M1 scene provenance + orbit details and integrity checks.
2. Verified subpixel residual registration (target <=0.5 pixel).
3. Site-specific temporal/seasonal false-positive analysis, masking as necessary.
4. Threshold sensitivity and evaluation against trusted independent ground truth.
5. Output review by M3; T09 integration contract.

## Security & trust
Never execute code from manifest; file paths are constrained by T02. Use trusted M1 inputs. Diagnostic only: do not use pixel counts as authoritative disaster impact, safety or emergency decision support.
