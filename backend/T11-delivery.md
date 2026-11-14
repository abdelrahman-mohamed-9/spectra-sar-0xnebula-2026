# T11 Delivery — Integration Contracts with M1–M4 & M6

**Status:** implemented contract documentation + machine-readable schemas + consistency tests; team acceptance pending.

## Deliverables

- `docs/integration-contracts.md` — comprehensive team-facing roles, boundaries, authentication, failure modes, proposed scientific workflow, and acceptance criteria.
- `contracts/integration-manifest.json` — machine-readable cross-team handoffs and outstanding decisions.
- `contracts/api-examples.json` — endpoint templates with no fabricated scientific observations.
- `contracts/generated/openapi.json` — FastAPI-generated OpenAPI snapshot.
- `contracts/generated/*.schema.json` — six actual Pydantic JSON Schemas covering M1–M3 scene, pair, artifact, job, change and impact records.
- `scripts/export_contracts.py` — reproducible schema export.
- `tests/test_t11_contracts.py` — checks that docs reference existing routes and generated schemas match code.

## Running

```bash
python -m pip install -e '.[dev]'
PYTHONPATH=src python scripts/export_contracts.py
python -m pytest -q
```

## Validation

- 123/123 pytest tests passed locally on 2026-11-13, including 7 new T11 tests.
- One pre-existing JWT test uses an intentionally short secret and produces a security warning; **production secrets must be strong**. No PostgreSQL/Redis/MinIO/Celery production-stack or real satellite-data end-to-end integration was conducted in T11.

## What is not finished

- M1/M2/M3 real samples, scientific details, and signoff.
- Confirmation that M4 and M6 responsibilities are assigned as assumed.
- Browser-safe user-scoped map/asset/write APIs and consistent per-project RBAC across all services.
- Scientific gate enforcement for rejected scene pairs, scientific handler installation, and true queued-worker evidence.
- End-to-end tests using real Sentinel-1 inputs and actual M1/M2/M3 outputs (T12).

**Next:** T12 integration testing and verification. Do not label the platform production-ready based on isolated local tests.
