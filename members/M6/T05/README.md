# M6 / Phase 1 / T05 — Testing & QA Foundation

This package is a **test harness**, not a deployed SAR application. It includes a snapshot of the T04 proposal `api-contract.yaml`; the source of truth should be maintained with M4 and updated when that contract changes.

## Prerequisites
Python 3.10+ recommended; locally run from this `T05` folder.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

Run subsets: `python -m pytest -m contract`, `-m scientific`, or `-m integrity`.

## Optional LIVE checks (no data inserted)
Start T02 and migrate T03 first. When M4 has deployed the API and schema is approved, set variables:

```bash
export SPECTRA_API_BASE_URL=http://127.0.0.1:8000
export SPECTRA_DATABASE_URL='postgresql://USER:PASSWORD@127.0.0.1:5432/spectra_sar'
python -m pytest -m integration --run-integration
python -m pytest -m database --run-database
```

Never commit `.env`, credentials or test logs with secrets. The API tests require M4 to actually implement T04; otherwise they will fail or skip by design. Do not treat skipped live tests as production validation.

## Package
- `pytest.ini`, `requirements.txt`: runner configuration and dependencies
- `src/qa_validators.py`: metadata compatibility checks, hash validation, DAG lineage
- `tests/test_contract.py`: proposal contract checks
- `tests/test_scientific.py`: offline scientific *metadata policy* tests
- `tests/test_integrity.py`: artifact integrity and lineage tests
- `tests/test_integration_live.py`: opt-in M4 checks
- `tests/test_database_live.py`: opt-in database schema check
- `test_plan.md`: acceptance matrix and responsibilities
- `api-contract.yaml`: copy from T04; reconcile any API changes with M4
