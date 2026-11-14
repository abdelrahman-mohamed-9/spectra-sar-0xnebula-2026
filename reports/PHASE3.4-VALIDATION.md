# SPECTRA 3.4 — engineering validation (14 Nov 2026)

## Verified by actual execution in this build

- Real source GeoTIFFs (before, after, labels) matched the first VV band, shape, affine grid and CRS of the held-out Spain tile.
- The bundled spatial ML prediction mask exactly matches the published benchmark evaluation report confusion-matrix counts: TP 11,316 / FP 2,975 / TN 216,625 / FN 31,203.
- Independently recomputed fixed -3 dB screen matches original report: TP 24,104 / FP 15,450 / TN 204,150 / FN 18,415.
- Dataset is **not** the NASA NISAR Alaska scene; this is a separate Sentinel-1 Spain research case.
- Display frames are generated from the genuine TIFFs, not fabricated imagery. Reference labels are never used to rank candidate regions.
- Evidence manifest includes SHA-256 digests for the source data, original external evaluation and derived display artifacts.
- Matched population raster import was evaluated with a **software-test-only synthetic** fixture, excluded from the product. The code area-weights source cell counts and marks incomplete coverage unavailable. This is NOT validation of real population estimates for Spain.
- Full `tests_phase2` + `tests_phase3` regression: **45 passed, 1 skipped**. See `phase3.4-tests.txt`.
- HTML inline JavaScript passed `node --check` syntax validation.
- FastAPI static integration verified `GET /`, `GET /mission/`, `GET /mission/mission-data.json`, and `GET /mission/ml-overlay.png` all HTTP 200 in a TestClient session.

## Explicitly not verified

- Browser-based visual rendering and click/download behavior: local Chromium navigations were blocked by administrator policy in the execution environment, for both `file://` and loopback HTTP. Not represented as visually validated.
- Operational accuracy of radar-event detection, quality score calibration, glacier velocity estimation, damage assessment, number of residents actually affected, or flood forecasting.
- Availability of an independently sourced and geospatially matched Spanish population count raster. The production demo therefore reports **Unavailable**, never zero.
- End-to-end NASA authentication/provider-origin signatures. SHA-256 checks only validate local file consistency.

## Rebuild demo

```
python scripts/build_judge_demo.py
```

Optional real modeled population raster instructions: `JUDGE-POPULATION-INPUT.md`.
