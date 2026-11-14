# Data integrity and scientific validity

## Real data acceptance
M1 uses genuine externally verifiable Sentinel-1 scenes and original scene metadata. Store the official provider product ID and source link; acquisition timestamp, platform, polarization, orbit/pass direction, incidence angle, resolution/units and licensing when available. Never describe local fixtures as real observations.

## SAR-specific scientific gates
1. Verify both scenes cover the intended AOI and time window, and preserve provider record/scene IDs.
2. Screen orbit direction, polarization, acquisition geometry and appropriate radiometric processing. A fixed incidence difference alone is not proof of full comparability.
3. Check true spatial co-registration, common CRS, transform, pixel size, extent, NoData, and masked invalid areas before comparing pixels.
4. Track any filtering, resampling, calibration, normalization and model settings; avoid claiming noise filtering always improves output.
5. Use independently sourced event labels/reference geometry for accuracy claims; document label date and method.
6. Include confidence/uncertainty and avoid conflating image change with a confirmed disaster or quantified damage.

## T06 checks
`T06/integrity_validator.py` verifies local file bytes and sizes against recorded SHA-256. `T06/provenance.py` checks record structure and lineage consistency. `T06/scripts/verify_manifest.py` cannot independently fetch/verify S3 resources; remote objects are unverified unless a later authenticated adapter is implemented. Hash equality with an untrusted supplied manifest is not source authentication.

## T07 evaluation
Use `T07/scripts/evaluate_npy.py` on truly co-registered `.npy` predicted/reference arrays with independent reference provenance. It computes confusion/overlap metrics, and optional calibration metrics when proper probability inputs are provided. `rasterio`/GDAL geospatial raster ingestion is a future adapter, not included in T07. Metrics without independent reference **must not** be reported as validated model accuracy.

## Responsible interpretation
- Scene metadata and hashes prove traceability only within their trust limits.
- Evaluation metrics may be affected by class imbalance, spatial leakage, seasonal variation, terrain, cloud-independent radar artifacts, and reference quality.
- Report sample count, valid coverage, class prevalence, confidence intervals (if calculated) and known failure modes.
