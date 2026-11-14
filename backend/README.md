# SPECTRA-SAR — M5 / Phase 1 / T02: Backend setup

Production-minded **scaffold** consistent with T01 system architecture. It is **not** the final scientific backend.

## Prerequisites
- Python 3.11+ (3.12 recommended), or Docker Compose

## Run locally (macOS / Linux)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn spectra.main:app --reload
```

Windows PowerShell activation: `.venv\Scripts\Activate.ps1`.

- API index: http://127.0.0.1:8000/api/v1/
- Liveness: http://127.0.0.1:8000/health/live
- Readiness: http://127.0.0.1:8000/health/ready
- Swagger: http://127.0.0.1:8000/docs

The readiness endpoint **intentionally returns 503** in T02 even if TCP port probes succeed. TCP reachability is not an authenticated database/storage/queue health check. T04+ will implement verified checks.

## Tests
```bash
python -m pytest -q
```

## Start container stack (optional)
```bash
cp deploy/.env.example deploy/.env
# Edit deploy/.env to set local credentials (never commit secrets).
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
```

PostGIS, Redis and MinIO are **provisioned only**. Tables, migrations, bucket creation, authenticated adapters and Celery jobs are assigned to later tasks. No satellite datasets, detections or derived scientific results are generated here.

## Module ownership
- `core/`: environment and logging
- `api/`: FastAPI routers and health checks
- `domain/`, `persistence/`, `geospatial/`, `storage/`, `integrations/`, `workers/`: extension points; deliberately empty in T02

## Security defaults
- API container runs non-root; `.env` is ignored; CORS is allowlisted; ports bind to localhost in Docker.
- `POSTGRES_PASSWORD` and MinIO secrets must be set for Compose.
- No business API authentication yet; **do not expose** this scaffold publicly.
- Pin/scan image digests and lock dependencies before production deployment.

## T02 acceptance
- [x] Importable FastAPI app with modular layout
- [x] Externalized typed configuration
- [x] Liveness and conservative readiness routes
- [x] OpenAPI documentation and request correlation header
- [x] Dockerfile and Compose dev infrastructure
- [x] Automated API tests (see local test results)
- [ ] Docker build/runtime verification (requires Docker daemon)
- [ ] Verified database/Redis/S3 integration (later tasks)


### T04 — Database connection and migrations
See [T04-delivery.md](T04-delivery.md). Run `alembic upgrade head` on an empty PostgreSQL/PostGIS database before using `/health/database`.


## T05: domain schemas and repositories
See `T05-delivery.md`. Data contracts currently exist independently of HTTP routes; T06 exposes authenticated APIs later.


## T06: REST APIs and service authentication
See `T06-delivery.md`, `openapi.yaml`, `tests/test_t06.py`. All `/api/v1/resources/*` routes need `X-API-Key` with `INTERNAL_API_KEY` set to a secret at least 32 characters long. Not a public multi-tenant API.

### T07: PostGIS geospatial endpoints

See [T07-delivery.md](T07-delivery.md) for HTTP routes, GeoJSON validation,
restrictions on bbox/antimeridian handling, and live integration test gaps.

Geospatial routes are under `/api/v1/geospatial` and require `X-API-Key`.
The geospatial feature converter uses Shapely; database reads use PostGIS.

## T08: processing jobs (Celery / Redis)

T08 adds authenticated `GET /api/v1/processing-jobs/{id}`, `POST /api/v1/processing-jobs/{id}/dispatch`, and `POST /api/v1/processing-jobs/{id}/cancel`. Job state persists in PostgreSQL; the Celery worker uses Redis as its broker. The existing resource POST `/api/v1/resources/jobs` creates the DB row; dispatch is a separate authenticated request. Only queued jobs may be claimed or cancelled. **No SAR analysis handlers are bundled**: they must be integrated from M1/M2/M3 and explicitly registered. See `T08-delivery.md` for commands and limitations (no running-job cancellation; leases/outbox still pending).

## T09 — Private SAR artifact storage

Upload SAR files through `POST /api/v1/storage/artifacts/upload` using trusted
`X-API-Key` and multipart fields `project_id`, `kind`, optional `scene_id`, and
`file`. Request a 5-minute download link at
`GET /api/v1/storage/artifacts/{id}/download-url`. A supported TIFF/PNG/GeoJSON/JSON/ZIP
file is streamed to a bounded temporary file, SHA-256 hashed, uploaded under an
opaque key to a private S3/MinIO bucket, and registered in the `artifacts` table.

**To run locally:** configure `deploy/.env`, run `docker compose -f deploy/compose.yaml up --build -d`
from the backend folder (or `cd deploy && docker compose up --build -d`).
MinIO signed URLs containing `minio:9000` are only accessible inside the Compose
network; use a resolvable public HTTPS hostname behind an authenticated gateway
for external clients. Never expose private object storage credentials in the browser.

See `T09-delivery.md` for current scope and integration limitations.

## T10 — user authentication

See `T10-delivery.md`. New user JWT endpoints live under `/api/v1/auth` and do not replace the **internal-only** service-key routes. Configure `JWT_SECRET` (unique, 32+ chars), run `alembic upgrade head`, and provision users with `python scripts/create_user.py --email user@example.org --project-id <UUID> --role viewer` from backend root. Never expose `INTERNAL_API_KEY` in a browser.
