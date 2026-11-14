# T12 Backend Testing & Validation — Evidence Report

**Project:** SPECTRA-SAR / Member 5 / Phase 1  
**Scope:** T02–T11 backend code plus T12 validation harness.  
**Verification date:** 2026-11-13.

## Executed here

- `python -m pytest -q --disable-warnings` — **135/135 passed** (123 existing + 12 new checks). See `reports/pytest-output.txt`.
- `python -m compileall -q scripts src` — passed.
- API TestClient verified liveness, conservative readiness, missing-credential behavior, JWT-only route rejection, request-ID sanitization, OpenAPI uniqueness, and generated-contract presence.
- Static configuration checks verified declared Compose services, secret environment references, migration files, upload limit.

## NOT verified / outstanding blocking items

1. **Real PostGIS:** no running Docker/PostgreSQL service available; migrations and real spatial queries not executed in a database.
2. **Celery/Redis:** no broker/worker E2E execution; Celery Python dependency absent in this validation runtime.
3. **MinIO/S3:** no real binary object upload, metadata persistence, retrieval, or SHA-256 round trip performed.
4. **Sentinel-1 data:** no real M1 scene/STAC object, M2 change outputs, or M3 impact report supplied; real integration not established.
5. **Security:** legacy internal service API key remains used on older endpoints. User-facing write authorization is not comprehensive; production security review pending.
6. **Performance/recovery:** no load, chaos, restart, recovery, concurrency, or backup/restore tests were run.
7. `/health/ready` deliberately returns 503 (not a false positive readiness status).

**Go/No-Go:** **NO-GO for production deployment or scientific E2E validation.** Unit and mock API regressions pass; integration gate remains open.

## Real service acceptance steps (developer machine with Docker)

1. Configure secrets in `deploy/.env` (unique values; never commit secrets).
2. From `deploy/`, run `docker compose config` then `docker compose up --build -d` and examine all logs for failures.
3. Confirm migrations, PostGIS extension, and all intended spatial tables using PostgreSQL queries.
4. Run `python scripts/integration_smoke.py --api http://127.0.0.1:8000` from an environment with service URLs and valid credentials, with Celery and redis Python dependencies installed.
5. Run a real **consented** M1 Sentinel-1 STAC + asset ingestion into private storage; verify checksum and retrieval, then process an M2 output and an M3 impact record, ensuring matching provenance and project IDs.
6. Verify owner/editor/viewer separation for every exposed read and write route, audit logs, rate limits, private network topology, and expiry/revocation behaviors.
7. Test worker failure/retry, job deduplication, storage rollback, restart behavior and recoverability.

## Deliverables

- `tests/test_t12_validation.py` — 12 additional regression/security/operability checks.
- `scripts/integration_smoke.py` — opt-in non-mutating external service checks.
- `reports/pytest-output.txt` — test execution evidence.
- `reports/validation-report.md` — result and remaining blocker register.

Note: `integration_smoke.py` assumes service URLs are reachable from the execution host. The `deploy/compose.yaml` application env is scoped within Docker containers; export equivalent **host-reachable** environment values before running the script from the host.
