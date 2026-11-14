# T06 — Authenticated REST API Foundation

## Delivered

- `src/spectra/api/v1/resources.py`: authenticated, versioned POST/GET handlers for SAR scenes, artifacts, scene pairs, processing jobs, change results, impact assessments; list scenes with bounded pagination.
- `src/spectra/api/v1/security.py`: fail-closed internal API-key auth for trusted workers, using constant-time comparison.
- `src/spectra/api/v1/router.py`: router mounting and `/api/v1/` service index.
- `src/spectra/core/config.py`: `INTERNAL_API_KEY` env setting.
- `deploy/compose.yaml`: injects required secret into API container.
- `tests/test_t06.py`: HTTP-level authentication, validation, response, rollback, pagination and OpenAPI smoke tests.
- `openapi.yaml`: static OpenAPI schema generated from actual FastAPI app.

## Design choices

These endpoints are **internal service-to-service** APIs, not public end-user APIs. `X-API-Key` authenticates *all* trusted workers equally. There is **no multi-tenant authorization, per-user account auth, or fine-grained project ACL** in T06. Do NOT expose the service publicly. For production use managed identities, RBAC, scopes, rate limiting, audited access, secret rotation and deployment-level TLS.

HTTP path prefix: `/api/v1/resources/`; endpoints:

| Resource | POST | GET by UUID | GET collection |
|---|---|---|---|
| scenes | Yes | Yes | Yes (limit 1-100 / offset) |
| artifacts | Yes | Yes | No |
| scene-pairs | Yes | Yes | No |
| jobs | Yes | Yes | No |
| change-results | Yes | Yes | No |
| impact-assessments | Yes | Yes | No |

Status codes: 201 created; 200 retrieved; 401 unauthorized; 404 not found; 409 DB constraint conflict; 422 invalid input; 503 auth misconfigured. DB connectivity failures propagate as 5xx; infrastructure exception mapping and tracing will be strengthened later.

### Local development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
# put generated token in INTERNAL_API_KEY in .env
uvicorn spectra.main:app --reload
python -m pytest -q
```

Or via Docker (requires a working Docker daemon, credentials and PostGIS migration):

```bash
cp deploy/.env.example deploy/.env
# fill POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, INTERNAL_API_KEY
# INTERNAL_API_KEY must be at least 32 characters
docker compose --env-file deploy/.env -f deploy/compose.yaml up --build -d
```

Use `X-API-Key: <secret>` header with the generated secret. Example request (requires live PostGIS DB + migrated schema, valid existing project):

```bash
curl -H "X-API-Key: $INTERNAL_API_KEY" http://127.0.0.1:8000/api/v1/resources/scenes
```

### Scientific data guarantees

The database stores metadata and references to real assets. T06 does **not** fetch/verify STAC assets, perform SAR processing, dispatch jobs, compute risk, or create synthetic datasets. `stac_item` input passes structural checks only; actual satellite products must be verified by M1 and provenance workflows.

### Verified in execution environment

- Automated tests passed (includes existing T02–T05 tests).
- OpenAPI YAML built from the actual app.
- Docker/PostgreSQL live execution **not** validated here (no Docker daemon accessible in the test environment).

### Known follow-up work

- T07: geospatial GeoJSON APIs and CRS/topology rules.
- T08: real async worker queue, idempotent dispatch, transitions and retries.
- T10: end-user/project RBAC and stronger API auth.
- Authenticated integration tests against actual PostGIS after Docker deployment.
