# SPECTRA-SAR — Phase 2 Release & Acceptance Record

**Build date:** 14 November 2026  
**Release status:** **SOFTWARE IMPLEMENTATION CLOSED — SCIENTIFIC ACCEPTANCE OPEN**  
**Safety of interpretation:** Radar backscatter candidates are **not** confirmed floods, structural damage or population impact.

## This delivery

One integrated project folder: original Phase 1 team code and M5 FastAPI; Phase 2 calibration/QA adapter, M2 conservative/review candidate methods, geographic screening, local integrity receipts, authenticated local dashboard/API, tests and reproducible reports. `results/` has been replaced with the latest re-run, to avoid displaying obsolete population gap statuses. No unrelated sample values were substituted for missing scientific observations.

## Observed test and execution evidence

| Domain | Result | Artifact |
|---|---|---|
| Phase 2 tests | 26 passed, 0 failed, 0 skipped (before contract refresh, same implemented code) | `reports/closure-phase2-tests.txt` |
| Phase 2 + backend contract focused run | 32 passed, 1 skipped | `reports/closure-targeted-contract-tests.txt` |
| M5 available-dependency regression after OpenAPI re-export | 143 passed, 1 deselected, 0 failed | `reports/backend-available-deps.txt` |
| M5 excluded test | Depends on third-party `celery` which is listed by backend dependencies but could not be installed in this offline test environment. **Not validated here.** | `backend/tests/test_phase1_service.py` |
| Original Phase 1 suite at original packaging | 373 passed, 3 skipped (historical snapshot) | `reports/phase1-original-test-summary.json`; later rerun without Celery failed two tests, of which the OpenAPI mismatch was corrected. Do **not** read this historical summary as a fresh full-suite rerun. |
| Local HTTP -> separate worker -> SQLite -> artifact download | `COMPLETED_EXPLORATORY`, 54/54 local SHA-256 downloads matched | `reports/closure-http-demo.json` |
| Browser DOM flow | Passed functional checks | `reports/ui-check.json`; visual rendering **not tested** |
| Docker, PostGIS, Redis, object-storage deployment | **Not validated** (no Docker daemon/remote services here) | `reports/RELEASE-VALIDATION.md` |

The `tests_phase2` suite uses temporary arrays/fixtures where appropriate, which are **never** presented as real SAR or scientific measurements. The bundled actual image pair has its own analysis output and user-provided source receipt, but original NASA file provenance and mixed-version scientific compatibility have not been independently certified.

## Reproduced radar scene comparison

Pair: `NISAR_GCOV_073_055_20261017_20261029_REAL` (user-provided files and metadata). Jointly valid cells: **88,779**. Conservative change-candidate cells: **566**; broader-review cells: **638**. Conservative candidate footprint: **54,520.20 square meters**. Population estimate: **UNAVAILABLE** (not zero). Dataset/site ground-truth accuracy: **BLOCKED_NO_INDEPENDENT_LABELS**. Scientific approval: **false**.

The separate Ghana/USA/Spain benchmark is an external algorithm comparison; **its accuracy numbers must not be attributed to this NISAR pair**.

## Launch (Mac/Linux)

Unzip this archive. Open Terminal inside `SPECTRA-Phase2-Final` and run:

```bash
bash START.command
```

The launcher installs Python dependencies on first run; Python **3.12** is recommended and internet may be needed. The app listens locally on `http://127.0.0.1:8765`. Paste the token printed to Terminal into the dashboard. `bash START.command test` runs the Phase 2 suite. Don't expose the local development API to the public Internet; don't upload tokens or passwords.

## Scientific acceptance still requires outside evidence

1. Independently verified and comparable SAR calibration, geometry, processing versions, co-registration and source authenticity.
2. Independently labeled events/change reference for the analyzed Alaska footprint and scientific domain review.
3. Georeferenced, independently sourced population and asset layers with validated spatial coverage and temporal relevance.
4. Deployment-level testing if Docker, PostgreSQL/PostGIS, distributed workers, or public deployment are required.

**Do not describe those external-validation requirements as completed.** Software is demo/engineering-ready and generates an honest result with explicit gaps; it is not certified for emergency decision-making.
