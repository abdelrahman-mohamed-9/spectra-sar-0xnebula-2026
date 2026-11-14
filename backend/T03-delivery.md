# M5 / Phase 1 / T03 — Delivery

**Deliverables:** `database-schema.sql`, `src/spectra/persistence/models.py`, `database-erd.md`, plus `tests/test_schema.py`.

## Run validation
```bash
python -m pip install -e '.[dev]'
python -m pytest -q
```

## Apply SQL manually only to disposable development DB
```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database-schema.sql
```

> WARNING: Applying standalone DDL is **not** a replacement for Alembic migrations (T04). Use a fresh dev DB; `CREATE TABLE` is not idempotent. Back up first.

## Important limits
- SQL generation/ORM compilation tests are not a real PostgreSQL/PostGIS integration test.
- PostGIS availability, permissions, spatial indexes, actual inserts, constraints, and geometry round trips must be verified in T04 against a running PostGIS instance.
- SQLAlchemy `Geometry` custom type is a DDL-compatible marker, not a GeoAlchemy2 serializer; T04 must implement explicit ST_GeomFromGeoJSON/ST_AsGeoJSON or standard GeoAlchemy2 adapters for safe geometry I/O.
- Cross-table business invariants and domain schemas require validation in API/services after M1–M3 finalize contracts.
