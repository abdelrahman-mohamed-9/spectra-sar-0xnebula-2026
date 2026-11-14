# SPECTRA-SAR / M6 / Phase 1 / T07 — Scientific Results Verification

Executable **evaluation utilities**, not a trained model or proof of change-detection performance.

## Files
- `scientific_metrics.py`: binary confusion/overlap metrics, probability calibration metrics.
- `verification.py`: required independent reference provenance and raster grid alignment checks.
- `scripts/evaluate_npy.py`: CLI for aligned `.npy` prediction/reference masks and metadata JSON.
- `quality-metrics.md`, `verification-plan.md`: scientific criteria, ownership and acceptance gates.
- `tests/`: deterministic unit tests, not real SAR scenes.

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

## Evaluate *real* results only after M1/M2/M3 provide independent reference & co-registered rasters
```bash
python scripts/evaluate_npy.py \
  --prediction /data/m2_change.npy \
  --reference /data/independent_reference.npy \
  --prediction-meta /data/pred_meta.json \
  --reference-meta /data/ref_meta.json \
  --valid-mask /data/valid_mask.npy \
  --probabilities /data/m2_change_probabilities.npy \
  --output /data/verification-report.json
```
The probability and valid mask inputs are optional; if omitted, scoring covers all pixels. The `.npy` masks must already be aligned and reference labels verifiably independent. No raw .tif reader is supplied; use `rasterio`/GDAL in an M1-M2 adapter after checking transforms and NoData.

Metadata JSON example (replace every example value with values extracted from the real geospatial raster and reference process):
```json
{"crs":"EPSG:32636","transform":[10,0,500000,0,-10,3300000],"width":512,"height":512,"reference_source":"REPLACE_WITH_INDEPENDENT_REFERENCE","reference_date":"YYYY-MM-DD","reference_method":"REPLACE_WITH_DOCUMENTED_METHOD"}
```
No event-specific numerical accuracy thresholds are promised or fabricated. Agree with M2/M3 on real assessment criteria. Link report artifact hash/run ID into M6 T06 and M4 T04 when integrated.
