# SPECTRA-SAR — M6 / Phase 1 / T02: Environment Foundation

**Status:** Implemented development infrastructure scaffolding; **not** an integrated SAR pipeline.  
**Date:** 2026-11-13 · **Owner:** M6 · **Version:** draft 0.1

## Purpose
Provide a repeatable, local-only PostgreSQL + S3-compatible MinIO development environment and safe project skeleton. PostgreSQL is a prospective metadata datastore (schema belongs to M4 / T03). MinIO is a prospective **local development** artifact store; it does not acquire satellite data, verify observations, or replace an authoritative SAR provider. There are **no M1–M5 services** or endpoints inside this deliverable.

## Prerequisites
- Docker Engine/Desktop with Docker Compose v2 plugin (not provided in this package).
- Python 3.10+ for validation and smoke checks.
- Available ports 5432, 9000, 9001 (modifiable).

## Quick start (shell, macOS/Linux)
```bash
cd SPECTRA-SAR/M6/Phase-1/T02
cp .env.example .env
# Edit .env to replace ALL CHANGE_ME values; use unique long secrets.
python3 scripts/validate_env.py
python3 scripts/create_structure.py
# Compose syntax validation; requires Docker Compose installed
docker compose config --quiet
# Start ONLY development infrastructure
docker compose up -d
# Inspect actual health; may take time for first pull
docker compose ps
python3 scripts/smoke_test.py
# Run unit tests (standard library)
python3 -m unittest discover -s tests -v
```

Local endpoints: PostgreSQL on `127.0.0.1:${POSTGRES_PORT}`; MinIO S3 API on `http://127.0.0.1:${MINIO_PORT}`, MinIO console `http://127.0.0.1:${MINIO_CONSOLE_PORT}`. Both services use the **credentials you entered** in `.env`.

**MinIO bucket:** `spectra-artifacts` is only a proposed bucket name; it is **not created automatically**. Bucket provisioning and policies belong to a later integration step. S3 credentials must be resolved server-side and should not be shared with browser clients. The root credentials are for local development only.

### Stop and reset
```bash
docker compose down                # stop; retain volumes
# WARNING: removes local DB and object-store contents irreversibly
docker compose down --volumes
```

## Design and ownership
- `docker-compose.yml`: M6-owned local infra, isolated bridge network, named persistent volumes, localhost-only ports and health checks.
- `.env.example`: M6-owned configuration template. `.env` is intentionally gitignored.
- `scripts/validate_env.py`: offline config safety check (does not print secrets).
- `scripts/smoke_test.py`: checks TCP listener and MinIO readiness. It does **not** test PostgreSQL auth, scientific correctness or end-to-end pipeline.
- `scripts/create_structure.py`: creates member-owned placeholders but never writes member code.
- `tests/`: basic unit tests for the validator.
- `docs/ownership.md`: service interface responsibility and pending decisions.

## Scientific integrity
- Real Sentinel-1 acquisitions and verified scene IDs **must** be supplied by M1; nothing in this task fabricates imagery.
- Align with IF-01..IF-07 from M6 T01: `../T01/system-interfaces.md` in the full project tree.
- Avoid ingesting raw satellite products into the git repository; use provider links and checksummed artifact manifests.

## Limits / acceptance evidence
| Check | Evidence | What it proves |
|---|---|---|
| Python unittest | `python3 -m unittest discover -s tests -v` | validation checks pass |
| Config validation | `python3 scripts/validate_env.py` | non-placeholder config set |
| Compose config | `docker compose config --quiet` | Compose syntax and substitutions valid |
| Runtime status | `docker compose ps` | actual container state/health |
| Smoke test | `python3 scripts/smoke_test.py` | database port and object-store health responsive |
| Full integration | **Not covered** | requires real M1–M5 code, scientific QA and reviewed contracts |

**No claim is made that Docker was started or that containers ran on the user's device.** Run the commands above in the target machine; never commit `.env`.
