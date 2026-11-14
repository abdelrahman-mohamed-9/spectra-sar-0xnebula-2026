# Integration and operations

## Local mode (default)

`phase2.application:create_local_app` calls the original `spectra.main.create_app`, preserving M5 routes and the Phase 1 router. It adds Phase 2 job routes and the dashboard. `scripts/run_local.py` starts the app and a separately supervised worker. The launcher binds only to loopback.

- Phase 2 identity: `Authorization: Bearer <operator token>`; one local operator.
- Original Phase 1 identity: `X-API-Key` using `state/internal-api-key.txt`.
- Phase 2 state: SQLite jobs, event history and hash receipts under `state/`.
- Original Phase 1 run storage: `state/phase1-runs` when launched through START.command.
- Phase 2 sources: bundled read-only catalog or operator-imported dataset catalog.
- No application data or credentials from a local run are packaged in the delivery.

Routes: `GET /api/v1/phase2/datasets`, `GET/POST /api/v1/phase2/jobs`, `GET /jobs/{id}`, `GET /jobs/{id}/events`, `GET /jobs/{id}/artifacts`, `GET /jobs/{id}/artifacts/{name}` (last routes relative to the Phase 2 prefix).

Submission body: `{"dataset":"nisar-oct2026","candidate_mode":"conservative"}` or `"review"`. Four queued/running jobs per owner maximum. One worker per state directory, enforced using a POSIX lock. Exited/interrupted jobs are failed explicitly, not silently resumed. Completed historical runs stay immutable.

## Original M5 JWT mode

After configuring the original M5 PostgreSQL database, migrations, user and JWT secret per `backend/` documentation, set `SPECTRA_PHASE2_STATE` and use:

```bash
export PYTHONPATH="$PWD:$PWD/backend/src:$PWD/phase1_compat/m2"
.venv/bin/python -m uvicorn phase2.m5_adapter:create_integrated_app --factory --host 127.0.0.1 --port 8765
```

In another terminal with the same state directory:

```bash
.venv/bin/python -m phase2.jobs
```

Paste a valid M5 JWT into the dashboard. The adapter calls the original `current_user` dependency and stores that user's ID as the Phase 2 job owner. It does not bypass the original JWT decoder. The integration test exercises real token issuance/decoding with an isolated SQLite User table; it is **not** evidence of a deployed PostGIS cluster.

Phase 2 queue/storage remain SQLite/local files even in JWT mode. Production PostgreSQL job migration, shared object storage, a distributed worker fleet, TLS and deployment-specific operations are not implemented or certified in this release. Do not expose the local shared-token workflow directly to the public internet.

## Docker and CI

`Dockerfile` and `compose.yaml` target the same integrated local app/worker. Configure separate random `SPECTRA_PHASE2_TOKEN` and `INTERNAL_API_KEY` environment variables before `docker compose up --build`. The API is bound to host loopback. Docker was unavailable in the review environment, so build/run is **not verified**. The included GitHub Actions workflow installs the tested Python constraints, runs tests/demo and attempts a Docker build when executed in a real CI runner. No hosted run was claimed.

## Operational limits

- Source catalogs and SQLite receipts are local trust anchors. Hashes do not protect against an administrator rewriting both source bytes and trusted receipts.
- Download budget: 64 MiB per artifact. Imported source trees: 300 MB. Input SAR rasters: 2 million pixels. Crop large scenes before import.
- There is no automatic storage quota/retention. Each job snapshots its source inputs. Monitor state size and archive whole completed runs deliberately.
- Original Phase 1 code and population-gap patch are retained. The legacy Phase 1 impact route still requires its original raster/AOI/OSM inputs; its real-data regression run correctly remains PARTIAL without them. Phase 2 provides the newer geography screening with explicit unavailable exposure.
- Additional cloud/harmony acquisition utilities require `requirements-download.txt` and the user's real provider access. They were not used to fabricate or redownload this release's input pair.

## Optional UI functional harness

With the local server already running, install `jsdom` in a separate development Node environment and run `node scripts/check_dashboard.cjs` with that module available on NODE_PATH. Set SPECTRA_UI_URL and SPECTRA_UI_STATE if using a nondefault URL/state. This submits a real broader-review job for the bundled pair, tests the DOM/HTTP flow and rewrites reports/ui-check.json. It deliberately does not certify browser layout or image rendering. Node is not needed for normal use.
