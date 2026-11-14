# Unified integration decisions

## Source selection

The six source archives and their exact hashes are recorded in `reports/source-archives.json`.

- M1 acquisition tasks: M1–M6 archive; actual Before raster and receipts: M2 final archive; acquisition implementation: M1/M2/M3 archive.
- M2: latest M2 final handoff, including its explicit NISAR contract. Older embedded M2 copies were removed.
- M3: genuine M3 partner source from M2 final (T02 acquisition and T09 containing T03–T08).
- M4: genuine `M4_phase1` evidence and integrity implementation from M4 team handoff.
- M5: genuine M2/M3/M5 backend, extended rather than replaced by the M1 substitute API.
- M6: genuine Phase 1 integration, provenance, validation and test modules. The M1 substitute frontend is not relabeled as M6.

## Active architecture

`phase1` is the orchestrator. Each member retains its scientific implementation. Separate Python subprocesses prevent collisions between generic modules named `pipeline`, `provenance`, `geo_loader` and `integrity`.

M1 immutable snapshot → M2 original processing → M3 polygon adapter + optional original impact pipeline → M4 original evidence → M5 local run contract/API or distributed publisher → M6 original provenance verifier.

The M3 bridge is also available when independent exposure inputs are absent; that state remains PARTIAL. A zero-candidate mask is a legitimate result, not an exception or permission to synthesize a hazard polygon.

## Concrete fixes

- HHHH accepted by M4 and M5 handoff validators, consistent with the latest explicit NISAR M2 contract. M4 schema now accepts the diagonal GCOV channel.
- Canonical M2/M3 paths replace old backend embedded duplicates.
- M3 receives a union Polygon/MultiPolygon feature while preserving the full candidate feature collection separately.
- Candidate sieving cannot invent changes by filling small unchanged holes.
- Input/output snapshots, hashes, normalized paths, no overwriting, propagated stage status, partial-run reporting and protected artifact downloads.
- Authenticated API served by the original M5 app; local file mode does not falsely claim a PostgreSQL/Redis/MinIO deployment.
- Added Alembic to backend dependencies; database health checks the actual `0002_auth_rbac` head, not obsolete `0001_postgis_initial`.
- `/health/ready` checks PostGIS/schema, Redis PING and authenticated S3 bucket access. Missing infrastructure remains 503.
- M6 live tests and T10 database gate updated to M5's active routes and real table names. Historical T04/T05 proposals are explicitly superseded by `backend/contracts/generated/openapi.json`. M5 owns the active schema; do **not** execute M6's alternative legacy SQL on the M5 database.
- A fixed Celery `other` handler now accepts `pipeline=phase1`, requires a real DB scene-pair match, runs/validates results, uploads artifacts to MinIO and writes ChangeResult/ImpactAssessment/AuditEvent records in the job transaction. It does not mark partial or blocked science runs as succeeded.
- Existing NASA jobs resume by default; explicit `--new-job` preserves previous receipts. Passwords/tokens are not bundled.
- Regenerated OpenAPI and contracts from the application actually delivered.

## Distributed deployment (configured; not live-tested here)

After local setup:

```bash
.venv/bin/python scripts/setup.py
docker compose --env-file .local.env up --build -d
```

Use root `compose.yaml`, not old member compose files. The root build includes the scientific modules and adapters. M5 owns one PostGIS schema. API is bound to `127.0.0.1:8000`; Redis and MinIO remain private to Docker. Config and optional input files are mounted from `config/` and `inputs/`; both worker and API share the `runfiles` volume.

Create project, AOI, true source-scene records and scene pair through existing authenticated M5 resource routes. A queued `other` processing job must reference that project/pair and use:

```json
{"pipeline":"phase1","config_name":"with-impact.json"}
```

Dispatch with the existing `/api/v1/processing-jobs/{job_id}/dispatch` endpoint. The recorded provider_item_id values must match the actual input manifest scene IDs. Partial runs need their inputs fixed and a new job ID. Job success denotes completed exploratory computation, not scientific approval. Object-store outages or DB commit failures can require orphan-object reconciliation; this is not an exactly-once distributed system.

## Scope limits

- Actual After raster absent; real Before checked against its supplied hash.
- No independent source authenticity or NASA signature is inferred from hashes or filenames.
- Without true impact datasets, no population/building-loss result is generated.
- No trained AI model or independently labeled event data supplied. Optional M2 T06–T08 remain available with genuine model/reference arguments. Only load models you trust.
- Subpixel co-registration certification, independently measured accuracy, flood causation and GOFF glacier motion are not established by this release.
- Cloud deployment, Docker services and hosted CI have not been executed here.
