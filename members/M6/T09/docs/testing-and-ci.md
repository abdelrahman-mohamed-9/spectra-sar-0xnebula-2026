# QA verification and CI

| Gate | Existing tool | What it can establish | Remaining external dependency |
|---|---|---|---|
| Python config checks | T02 `tests/`, `validate_env.py` | environment config checks | live Docker deployment |
| database schema unit tests | T03 `tests/` | offline helper/schema assumptions | actual PostgreSQL migration |
| OpenAPI proposal tests | T04 `tests/` | syntax, selected schema checks | actual M4 routes, auth |
| SAR metadata + integrity | T05 `pytest`, T06 `unittest` | deterministic fixture behavior | real provider scenes, S3 adapter |
| scientific metric implementations | T07 `pytest` | deterministic metric correctness cases | independent reference dataset, real prediction |
| CI framework | T08 GitHub Actions workflow | local runner validation | remote GitHub Actions execution |

## Commands (repository root)
```bash
python3 -m pip install -r M6/Phase-1/T08/requirements-ci.txt
python3 -m pytest -q M6/Phase-1/T08/tests
python3 M6/Phase-1/T08/scripts/validate_ci.py --repo-root . --require-all
python3 M6/Phase-1/T08/scripts/run_offline_tests.py --repo-root . --require-all
python3 M6/Phase-1/T09/scripts/check_docs.py
```

The final command checks T09 documentation links/required documents only; it is **not** deployment validation.

## Live tests
After PostgreSQL is up, T03 migration is applied, and M4 backend is truly running, follow `T05/README.md` to set `SPECTRA_API_BASE_URL` and `SPECTRA_DATABASE_URL`, and opt in to markers with `--run-integration` and `--run-database`. Failed live tests are real blockers. Skipped live tests are not PASS; record skip counts in release report.

## Branch protection
After pushing `.github/workflows/ci.yml`, confirm a successful GitHub-hosted run and require its actual named status check in branch rules. CI checks do not deploy services; any CD is future work and should require reviewed environments/secrets and gated releases.
