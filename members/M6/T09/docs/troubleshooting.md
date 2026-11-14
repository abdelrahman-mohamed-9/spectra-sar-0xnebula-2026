# Troubleshooting runbook

| Symptom | First checks | Safe resolution |
|---|---|---|
| `docker: command not found` | Is Docker installed and active? | Install/start Docker Desktop or Engine; confirm `docker compose version` |
| `docker compose config` fails | `.env` absent or placeholder values; YAML file path | `cp .env.example .env`; replace `CHANGE_ME`; run `python3 scripts/validate_env.py` from T02 |
| Port already allocated | `docker compose ps`, host process using 5432/9000/9001 | Change `POSTGRES_PORT`, `MINIO_PORT`, `MINIO_CONSOLE_PORT` in `.env`; restart |
| `pg_isready` is healthy, migration fails | Credentials/host from T02 not exported to T03; database not initialized | Use host `DB_HOST=localhost`, matching username/password/db name; do not log secret |
| `ModuleNotFoundError: psycopg` | T03 requirements not installed in current environment | `python3 -m pip install -r requirements.txt` in T03 |
| MinIO endpoint answers but bucket missing | Bucket is not auto-created in T02 | Create bucket through approved admin tooling with limited privileges and confirm policies |
| CI reports missing T0x | Wrong folder wrappers from ZIP extraction | Use T09 assembly script to normalize `repo/M6/Phase-1/Txx` |
| Live test skipped | Opt-in flag/env not set or services unavailable | Enable only after M4 API and DB are operational; never count skip as passed integration |
| `/health/ready` returns 404/connection refused | T04 is a spec, not an implementation | M4 must deploy service according to approved contract |
| SHA-256 mismatch | File was changed/partial/wrong object | Quarantine artifact, re-download from verified source and re-record hash with audit trail |
| `s3://` object unverified | T06 only validates local files | Implement authenticated MinIO/S3 streaming SHA-256 verifier; ETag is insufficient |
| Raster masks misalign | CRS/transform/shape differences | Have M1 reproject/coregister, establish common valid mask; don't force evaluation |
| Perfect accuracy on tiny sample | Data leakage, trivial fixture, class imbalance | Validate against independent spatial/temporal real-world labels before claiming performance |

**Never** post `.env` contents, access tokens, or personally identifying provider keys into bug reports. Include redacted command, environment, stack trace, run ID, artifact hash, and expected/actual behavior.
