# T10 — Phase 1 Integration Validation

This is an **evidence-gathering and readiness gate**, not a substitute for an end-to-end test. Checks are separated into:

1. Local package presence checks (T01–T09).
2. Opt-in live service probes (M4 health endpoint and PostgreSQL schema).
3. Signed-off evidence manifest placeholders for M1–M5, real SAR run, scientific reference validation and hosted GitHub CI.

## Quick start

```bash
python3 -m unittest discover -s tests -v
python3 integration_validator.py --member-root ../ --output reports/integration-report.json
```

The second command is expected to return status **2 (BLOCKED)** without live integrations and evidence. `FAIL` returns code 1, fully passed checks 0. Reports contain no credentials.

## Live deployment checks (only with approved services)

```bash
export SPECTRA_BACKEND_URL='http://localhost:8000'
export DATABASE_URL='postgresql://user:password@localhost:5432/spectra' # set privately; never commit
python3 integration_validator.py --member-root ../ --evidence-manifest evidence-manifest.json --evidence-root /path/to/auditable-evidence --output reports/integration-report.json
```

`psycopg[binary]` is optional for the database gate. Keep URLs/tokens out of CI artifacts and PR logs. Service readiness checks merely verify HTTP 200 and parseable JSON; they are not authenticated run-to-result validations.

## Evidence contract

`evidence-manifest.json` contains a `records` mapping with these identifiers: `e2e.M1` ... `e2e.M5`, `e2e.real_sar`, `e2e.scientific`, `e2e.github`. Each record must specify a relative file `path` under `--evidence-root` and `sha256` (lowercase hex). Never mark a check PASS without the actual evidence file and matching hash. Pass only means integrity matched, **not** that claims in the file were verified. Reviewer sign-off remains mandatory.

For a full scientific acceptance, obtain official provider scene IDs, pre/post acquisition dates, orbit/polarization metadata and licensing, calibrated georegistered outputs, M2 prediction rasters, independent reference labels, method versions, T07 quality report, provenance checks, M3 impact results and authorized frontend render. See `phase1-checklist.md`.
