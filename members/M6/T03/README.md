# SPECTRA-SAR · M6 · Phase 1 · T03 — Database Foundation

**Status:** Schema and database access layer implemented; integration against a running PostgreSQL instance is **not yet verified**. Database design is proposed for M4 review before production adoption.

## Purpose

Real SAR observations and derived outputs require verifiable provenance, processing history, scientifically valid metadata, run status, and artifact traceability. PostgreSQL stores **metadata and references**, not large GeoTIFF files. M1 stores original/processed rasters in object storage (e.g. MinIO configured in T02); database keeps `s3://...` URIs, bytes, sha256, producer and input linkage. No fabricated observations or computed results are seeded.

## Deliverables

- `database-schema.sql`: versioned PostgreSQL schema with 9 tables (including migrations ledger), keys, indexes, constraints and lineage links.
- `migrations/001_initial.sql`: same SQL for initial deployment.
- `database.py`: psycopg 3 connection helper plus safe run create/read/status updates.
- `scripts/migrate.py` and `scripts/check_db.py`: initialize and smoke-check live database.
- `tests/test_database.py`: dependency-free unit/contract tests.

## Integration with T02

Start T02 PostgreSQL on your machine and copy T02 `.env.example` into `.env`, substituting secure secret values. From the T03 directory:

```bash
python3 -m pip install -r requirements.txt
# Host-side access to T02's PostgreSQL port
export DB_HOST=localhost
export POSTGRES_PORT=5432
export POSTGRES_DB=spectra_sar
export POSTGRES_USER=spectra
export POSTGRES_PASSWORD='THE_PASSWORD_YOU_SET_IN_T02'
python3 scripts/migrate.py
python3 scripts/check_db.py
python3 -m unittest discover -s tests -v
```

Alternative (without exposing credentials in shell history): load environment from a local secure secret manager or use a noncommitted `.env` loader. **Never commit credentials.** For container-to-container connections use `DB_HOST=postgres` rather than `localhost`.

**Warning:** T02 has a durable PostgreSQL volume. `CREATE TABLE IF NOT EXISTS` does not upgrade an existing table. The initial migration is for an empty project database only. Later schema upgrades require new incremental migrations and explicit compatibility review. Back up real databases before changes.

## Key ownership and mapping

| T01 interface | Data stored | Owner coordination |
| --- | --- | --- |
| IF-01 provider→M1 | `sar_scenes`, original `artifacts` | M1 checks actual source, license, orbit, acquisition time |
| IF-02 M1→M2 | `run_scene_pairs`, `artifacts`, `stage_executions` | M1 defines aligned raster grid; metadata in artifacts |
| IF-03 M2→M3 | `analysis_results`, `artifacts` | M2 specifies algorithm and confidence meaning |
| IF-04 M3→M4 | `analysis_results`, `artifacts` | M3 includes overlay sources/limitations in JSON metadata |
| IF-05 M4→M5 | `processing_runs` and outputs | M4 implements API and authorization |
| IF-06 all→M6 | `artifact_inputs`, `audit_events` | M6 verifies lineage, checksum, QA |

## Scientific integrity rules

1. `sar_scenes.provider_scene_id` must be the **real provider scene/product ID**; `provider_record_url` must point to a verifiable source.
2. Never claim a raster came from NASA/ESA unless source metadata actually verifies it. Sentinel-1 belongs to ESA Copernicus; NASA Earthdata may provide access to relevant products.
3. The database cannot independently verify remote scene authenticity, orbital matching, correct coregistration, or a SHA-256 matching the stored object. Validate those in M1/M6 pipeline.
4. Storing change scores does **not** prove that a flood/fire occurred; M2/M3 must document reference labels and false positives.
5. Absent population/damage figures are missing/not-assessed, never numeric zero.
6. A database row is not evidence that its referenced `s3://` asset exists; M6 should verify retrieval and hash.

## Known design decisions for team review

- M4 is the source of truth for final SQL/API model; this initial schema must be reconciled with M4's backend before production.
- `artifacts.storage_uri` internal-only: API must return authorized short-lived asset access, not direct credentials.
- `footprint_geojson` / AOI currently JSONB. PostGIS spatial indexes and operations can be introduced after agreement on queries and deployment image.
- Avoid deleting scene/artifact rows referenced in data lineage; `RESTRICT` enforces some of those relationships.
- Cross-row constraints (e.g. before timestamp < after timestamp, same polarization, matching raster grids, input lineage acyclicity and artifact-to-run consistency) are **not enforced by current SQL**: enforce in M1/M2 validators and add database triggers or transactional checks as requirements stabilize.
- Access control, auth, production backup/restore, row-level data segregation, and role-specific SQL grants are not delivered in T03.

## Acceptance

- [x] SQL schema, relationships, constraints and indexes authored
- [x] psycopg connection and basic repository functions authored
- [x] unit tests provided
- [ ] connect to running PostgreSQL and successfully migrate
- [ ] validate actual SAR metadata and MinIO artifact lineage
- [ ] approve schemas with M1–M5 and particularly M4
