# SPECTRA Phase 3 — integrated extension

This release extends the supplied project in place. Existing Phase 1 routes, Phase 2 routes, candidate modes, source snapshots and dashboard remain available. New runs also generate `Phase3/` artifacts. Historical runs without those artifacts remain readable.

## Start

Windows with Python 3.13: run `powershell -ExecutionPolicy Bypass -File .\START-WINDOWS.ps1` from the extracted folder. First run installs dependencies. Keep the terminal open; copy the printed operator token into the dashboard at http://127.0.0.1:8765. State uses your Windows user directory's inherited ACL; keep the extracted folder private. No shared-user Windows ACL provisioning is implemented.

macOS/Linux: the original `bash START.command` remains available. To run the new tests after setup: `.venv/bin/python -m pytest -q tests_phase2 tests_phase3`. Windows: `powershell -ExecutionPolicy Bypass -File .\START-WINDOWS.ps1 test`.

## What was actually in Phase 1 / Phase 2

Verified by code inspection, not by treating historical reports as fresh test results:

| Area | Existing Phase 1/2 implementation | Phase 3 extension |
|---|---|---|
| M1 | Member SAR modules; manifest contracts; common-grid reprojection; held-out window translation checks | Joint coverage, radiometric median/MAD/quantiles, terrain-mask availability; these diagnostics feed quality review |
| M2 | Mask-aware Lee filter, log ratio, robust MAD and fixed-threshold screens, connected-component filtering, threshold stability, optional reference evaluation | Additional stable/interior/minimum-size screen; quality-adjusted uncalibrated confidence raster; per-zone confidence |
| M3 | Equal-area intersection, road length/building counts, population count-raster support, census context | Per-zone population/buildings/roads, explicit risk policy and levels; risk stays null when required coverage is missing |
| M4 | Source catalog, import receipts, stage inventories and verified artifact downloads | Ordered SHA-256 linked processing records, input/output hashes and processing code hashes |
| M5 | Original FastAPI app, SQLite queue/events/results, ownership checks, worker and JWT adapter | Phase 3 results persisted in existing results/receipts; verified `/api/v1/phase2/jobs/{job_id}/phase3` endpoint; Windows worker locking |
| M6 | Existing dashboard, before/after swipe, mode selection, downloads and job history | Local interactive vector map, pan/zoom/reset, confidence filter, risk/confidence colours, zone details, exposure table and evidence panel |

No new database is required: the existing SQLite JSON result and receipt columns store the additive Phase 3 contract atomically with job completion. The existing owner restriction applies to the new endpoint. API prefix remains Phase 2 intentionally for backward compatibility.

## Scientific interpretation

The bundled AOI is approximately longitude -153.13 to -153.06, latitude 64.62 to 64.66 in Alaska. It is not the Mendenhall Valley proposed in the referenced conversation. No replacement observations have been invented or downloaded.

The Phase 3 screen keeps same-sign, four-connected components of at least 9 pixels after removing one pixel around invalid data and grid boundaries and requiring threshold stability >=0.99. It can remove real small changes. Confidence is a heuristic quality index, not a calibrated probability: threshold stability × geometry factor × processing factor. Unknown geometry receives 0.5, known geometry uses clip(1−p90 residual/2,0,1). Matching known processing identifiers receive 1, otherwise 0.7. This policy is transparent but requires independent validation.

Risk review score = 100 × confidence × mean(min(people/100,1), min(buildings/10,1), min(road metres/1000,1)). Medium begins at 30; high at 60. These are prototype policy choices, not scientific hazard thresholds. The score describes review priority from observed SAR candidates and exposure; it is not flood probability, damage, expected loss or a glacier velocity measurement.

## Missing external inputs

- Independent pair-specific change labels and geometric/radiometric reference measurements.
- Suitable real SAR pair for Mendenhall if that is the intended study area; GOFF/displacement measurements for glacier motion.
- A population raster with people-per-cell values and complete valid coverage; block totals cannot substitute for spatial exposure.
- Verified building and road coverage. Empty source queries do not establish absence. Road layers represent the implemented infrastructure category; utilities and critical facilities need additional layers and category-specific models.
- Terrain/shadow/layover flags where missing in the original pair and harmonized processing versions.

Import real geography through the existing `phase2.datasets` importer and `docs/DATA-CONTRACTS.md`. In `geography-source.json`, provide `population_raster` with `file`, `source`, `units: people_per_cell`; set `roads.coverage_verified` and `buildings.coverage_verified` to true only when you have verified source coverage. Missing/partial population coverage yields null risk, never zero. Population within each cell is assumed uniform. Sources are pinned in the import catalog and included in evidence.

SHA-256 detects differences relative to the recorded local bytes. The chain is not signed or externally anchored and does not establish provider authenticity. Processing-log timestamps record receipt assembly after the stages finish, not stage durations.

## Delivery evidence

See `reports/PHASE3-VALIDATION.md` for checks run for this release. Older `reports/`, `results/` and legacy reports retain their original Phase 1/2 meaning. `results-phase3/` contains the new bundled-data example if present. Do not compare raw counts with accuracy: fewer candidates does not prove fewer false positives on unlabeled real data.
