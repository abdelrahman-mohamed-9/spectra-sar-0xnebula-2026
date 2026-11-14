# Phase 3 validation — 14 November 2026

Environment: Windows, Python 3.13.7, Chrome headless, Node 24.22.1. Exact Python environment is recorded in `phase3-environment.txt`.

## Current checks

- `tests_phase2` + `tests_phase3`, with `SPECTRA_PHASE1` set: **31 passed, no skipped tests**. Includes original M5 JWT adapter, source-tamper rejection, ownership/restart checks, new API tampering, exclusive worker locking, boundary/small-component screening and complete/incomplete population/asset fixtures. See `phase3-tests.log` and XML.
- Backend suite run from `backend/`: **143 passed, 1 failed**. Failure is the pre-existing generated OpenAPI equality test, reproduced against the original archive in the same environment. See `phase3-backend.log` and `baseline-backend.log`.
- Existing root Phase 1 integration suites: **6 passed, 7 failed** on the untouched archive in the same Windows environment. The modified release showed the same seven failures. Legacy M4 rejects legacy M2 artifact integrity on these fixtures. The Phase 2/3 path uses its own tested receipts and succeeds. These original Phase 1 paths are not certified working on Windows. See `baseline-tests.log` and `phase3-regression.log`.
- An initial combined regression invocation also failed an Alembic lookup because it ran from the repository root. Running the backend suite from its intended directory resolved that lookup; it is not counted as a remaining backend defect.
- Real bundled dataset through HTTP, separate worker and SQLite: **completed**, **59 artifacts downloaded and SHA-256 verified**. See `phase3-http-demo.json`.
- Chrome functional checks: **PASS**, no JavaScript page errors. Login, live analysis, zone selection/evidence, zoom/reset, confidence filter, mobile viewport rendering and disconnect cleanup. Screenshots were inspected. See `phase3-browser.json`, `phase3-dashboard.png`, `phase3-mobile.png`.

## Observations from the real bundled data

The original conservative screen remains 566 pixels. The additional Phase 3 stable/interior filter retains **206 pixels in 7 zones**. Quality-index confidence is approximately 0.607 for these zones. This is not measured accuracy and candidate reduction does not establish a measured false-positive reduction without labels.

Risk is null for every bundled zone because spatial population counts and verified road/building coverage are absent. A controlled software fixture with known counts and geometries verifies the positive risk calculation and checks that incomplete coverage returns null. Synthetic fixtures are tests only and are not presented as observations.

The existing census context and empty mapped-asset queries are preserved. The AOI is not Mendenhall. The supplied original source catalog remains unchanged; `phase3-change-inventory.json` records delivery changes relative to the input archive. `results-phase3/` is a fresh run; original `results/` and historical reports were not relabeled as Phase 3 results.

## Not validated

Independent scientific accuracy, calibrated probabilities, operational flood risk, glacier motion, provider authenticity, complete external population/infrastructure coverage, production PostGIS/Redis/S3, Docker and hosted CI. Original member suites beyond the root/backend and Phase 2/3 suites were not rerun. Windows directory privacy relies on inherited user ACLs. Processing evidence is locally hashed, not externally signed.

This is a tested integrated engineering extension with explicit data gaps, not an operational hazard warning system.
