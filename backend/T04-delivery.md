# Member 5 — T04: Database Connection & Migrations

## Implemented
- SQLAlchemy PostgreSQL psycopg3 engine, connection pooling, DI session lifecycle.
- Initial Alembic revision with nine T03 tables, nine indexes, and PostGIS extension.
- `/health/database` verifies SQL connectivity, the extension, and Alembic revision (does NOT claim Redis/MinIO readiness).
- Compose `migrate` one-shot job required before launching API.
- Automated tests validate migration discovery, schema DDL definitions, and failure behavior.

## Run against a **new empty database** (Docker required)
```bash
cd backend/deploy
cp .env.example .env
# set new strong values for POSTGRES_PASSWORD, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD
# avoid tracked files for credentials; DO NOT commit .env
docker compose up --build -d
# Watch migration exit 0 and API startup:
docker compose logs migrate api db
# inspect schema version and PostGIS availability:
docker compose exec db psql -U spectra -d spectra -c "SELECT version_num FROM alembic_version;"
docker compose exec db psql -U spectra -d spectra -c "SELECT PostGIS_Version();"
curl -i http://127.0.0.1:8000/health/database
```
To run migrations manually against an existing **empty** PostgreSQL/PostGIS instance: set DATABASE_URL and `alembic upgrade head` from `backend/`. Never run downgrade on production; it drops all nine tables. Existing T03 manually initialized schemas are not automatically migratable: compare schema and audit before stamping.

## Verification scope
Local automated tests are **not** evidence of a live PostgreSQL/PostGIS connection or working Docker engine. Those require execution on a machine with Docker/PostGIS installed. SQL snapshots and ORM schema must remain synchronized when changes occur; produce a new Alembic revision instead of editing applied revisions.

## Pending
- T05 domain DTOs/repositories, ingestion rules, transactions and API workflows.
- Production access roles, backups, secrets management and observability.
