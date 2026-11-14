# Local setup and reproducible verification

## Prerequisites
- Python **3.10+**, `python3`, `pip`, Git; macOS/Linux shell examples (Windows PowerShell commands differ).
- Docker Desktop or Docker Engine + **Docker Compose v2** for optional PostgreSQL/MinIO.
- Source ZIPs T01–T08 supplied by your team. This T09 does not bundle or replace their contents.

## 1. Assemble canonical repo paths

Earlier archives have inconsistent wrappers: T01 is `T01/`; T04/T06/T07/T08 are `Txx/`; T02/T03/T05 include `SPECTRA-SAR/M6/Phase-1/Txx/`. **Do not** extract every archive directly at repo root. Use the included archive-normalization script (`scripts/assemble_member6.py`), with your trusted ZIP directory:

```bash
# Run inside the extracted T09 folder, choose YOUR real ZIP directory and repo destination
python3 scripts/assemble_member6.py \
  --archives /path/to/your/zip-files \
  --output /path/to/your/repo \
  --dry-run
# Inspect listed files and destination first; then remove --dry-run
python3 scripts/assemble_member6.py \
  --archives /path/to/your/zip-files \
  --output /path/to/your/repo
```

The output layout is `repo/M6/Phase-1/T01` … `T09`. The script picks the **T02_FIXED** archive and refuses to overwrite pre-existing destinations. Copy this T09 folder into `repo/M6/Phase-1/T09` separately, and copy `repo/M6/Phase-1/T08/.github/workflows/ci.yml` to `repo/.github/workflows/ci.yml` (create directories). Check in the YAML workflow only after review.

## 2. Start development infrastructure (T02)

```bash
cd /path/to/your/repo/M6/Phase-1/T02
cp .env.example .env
# edit ALL CHANGE_ME values in .env; use unique strong passwords
python3 scripts/validate_env.py
python3 scripts/create_structure.py
docker compose config --quiet
docker compose up -d
docker compose ps
python3 scripts/smoke_test.py
```

This starts PostgreSQL and MinIO **only**; no ingestion or inference service. Ports are bound on `127.0.0.1` by the provided Compose file: Postgres `5432`, MinIO API `9000`, console `9001` by default. `spectra-artifacts` is a *proposed* bucket not created automatically. Change ports in `.env` if occupied.

## 3. Initialize the proposed database (T03)

```bash
cd /path/to/your/repo/M6/Phase-1/T03
python3 -m pip install -r requirements.txt
# Supply credentials from the T02 .env without committing them
export DB_HOST=localhost POSTGRES_PORT=5432 POSTGRES_DB=spectra_sar POSTGRES_USER=spectra
# Supply POSTGRES_PASSWORD securely; don't paste it into shared logs
python3 scripts/migrate.py
python3 scripts/check_db.py
```

T03 initial migration is intended for a fresh development database. For pre-existing installations, review migrations with M4 and back up data; do not assume `CREATE TABLE IF NOT EXISTS` upgrades old tables.

## 4. Run test harness and CI offline (T05, T08)

```bash
cd /path/to/your/repo
python3 -m pip install -r M6/Phase-1/T08/requirements-ci.txt
python3 -m pytest -q M6/Phase-1/T08/tests
python3 M6/Phase-1/T08/scripts/validate_ci.py --repo-root . --require-all
python3 M6/Phase-1/T08/scripts/run_offline_tests.py --repo-root . --require-all
```

T05 live tests are opt-in and may skip. For them to pass, M4 must deploy the proposed API and real database must be running. Follow `T05/README.md` for env vars and flags. **Offline green != end-to-end validated.**

## 5. Shut down safely

```bash
cd /path/to/your/repo/M6/Phase-1/T02
docker compose down
```

`docker compose down --volumes` **deletes** local PostgreSQL and MinIO persistent contents; do not run on valued data.
