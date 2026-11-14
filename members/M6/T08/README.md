# M6 — Phase 1 / T08: CI/CD Foundation

This is a **GitHub Actions CI foundation**, not a production deployment pipeline. No GitHub workflow has been executed remotely yet.

## Exact repository layout

Place the package under the **repository root**, not inside another T08 folder:

```text
repo/
  .github/workflows/ci.yml        # copy from T08/.github/workflows/ci.yml
  M6/Phase-1/
    T02/ ... tests/
    T03/ ... tests/
    T04/ ... tests/
    T05/ ... tests/
    T06/ ... tests/
    T07/ ... tests/
    T08/
      scripts/run_offline_tests.py
      scripts/validate_ci.py
      requirements-ci.txt
      tests/test_ci_tools.py
```

**Migration note:** Earlier ZIPs have inconsistent top-level folder names (some contain `SPECTRA-SAR/M6/Phase-1/Txx/`, others `Txx/`). Put the task directories under `repo/M6/Phase-1/Txx` as shown. Do **not** blindly unzip all archives into the same root.

## Run offline locally

```bash
python3 -m pip install -r M6/Phase-1/T08/requirements-ci.txt
python3 -m pytest -q M6/Phase-1/T08/tests
python3 M6/Phase-1/T08/scripts/validate_ci.py --repo-root . --require-all
python3 M6/Phase-1/T08/scripts/run_offline_tests.py --repo-root . --require-all
```

CI triggers on PRs, pushes to main/develop, or manual workflow_dispatch. Set branch protection on `main` to require the `Offline quality checks (M6 T02-T07)` check; configure this in GitHub yourself after the workflow is committed. Workflow permissions are read-only; no cloud keys, service credentials, deployments, or external SAR data are needed.

## What is not proven yet

* GitHub-hosted execution (requires pushing the workflow).
* Live M4 API, PostgreSQL, MinIO/S3 and end-to-end processing.
* Scientific quality against independent ground truth and actual Sentinel-1 imagery.

There are no fabricated end-to-end results. CI should fail if a required task is missing. Some T05 live tests intentionally skip without live services; don't confuse a green offline pipeline with complete scientific verification.
