# SPECTRA-SAR · Phase 2

This release runs all six Phase 2 roles as one local workflow over the supplied Alaska NISAR pair. The API submits a job, a separate worker harmonizes the pair and analyzes it, and the API serves persisted results after checking each artifact against its database receipt. The run is exploratory because the Alaska reference and scientific checks listed in the report are incomplete.

## Run it

On macOS or Linux, from the extracted directory, use Python 3.14:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
export PYTHONPATH="$PWD:$PWD/phase1_compat/m2"
python scripts/demo.py --state state
```

The demo opens an authenticated server on loopback, submits a real job, launches the worker separately, downloads and independently hashes all registered files, prints the job record, and shuts down the server. The SQLite database and outputs remain in `state/`. No network or credentials are needed for the analysis because the source snapshots are included. Run data grows on each submission. Archive or rotate the local state as needed.

## Run API and worker continuously

In two terminals from the project directory, set `PYTHONPATH` as above and `SPECTRA_PHASE2_STATE` to the same private directory. For the API terminal, also set `SPECTRA_PHASE2_TOKEN` to a strong, random token of at least 32 characters. Start:

```bash
python -m uvicorn phase2.api:create_app --factory --host 127.0.0.1 --port 8000
```

```bash
python -m phase2.jobs
```

Send an authenticated `POST /api/v1/phase2/jobs` with body `{}`, then poll `GET /api/v1/phase2/jobs/{id}`. Use `GET /api/v1/phase2/jobs/{id}/artifacts` for the inventory and append an inventory name to download. `COMPLETED_EXPLORATORY` means computation and storage finished. Science status remains explicitly false. The worker claims one job at a time and marks interrupted jobs failed on restart. Submit a fresh job to retry. The SQLite directory and checked-in catalog are trust anchors. Restrict write access to both.

The included Compose file starts both processes with a private shared volume and binds the API to loopback. Docker and hosted CI are provided as configurations. Neither was run for this delivery.

## Mount on the team's Phase 1 M5 app

From this package with the Phase 1 requirements also installed, add the original Phase 1 directory and its `backend/src` to `PYTHONPATH` and use `phase2.m5_adapter:create_integrated_app` as the Uvicorn factory. Configure the original M5 PostgreSQL URL and JWT settings as in Phase 1. This mounts the same Phase 2 routes and uses M5's existing user identity with per-job ownership. Phase 2 job state is local SQLite in this release. To run the optional integration test against the supplied app with a temporary user table, set `SPECTRA_PHASE1` to the Phase 1 directory. The test checks the original JWT logic and two-user isolation. Production PostGIS, Redis, and object storage require a separate deployment verification.

## Outputs by role

| Role | Outputs |
|---|---|
| M1 | Aligned rasters, individual and joint masks, common-grid manifest and translation diagnostic with independent spatial holdout windows. |
| M2 | Raw and Lee-filtered baselines, robust change masks, threshold-stability and uncertainty rasters, controlled benchmark and separately labeled Sentinel-1 evaluation with a logistic ML comparator. |
| M3 | Equal-area candidate footprint statistics, mapped asset overlap, 2020 census block context, and threshold-stability review priority in GeoTIFF and GeoJSON. |
| M4 | Source snapshot receipt, stage gates, M2 verification, run-level SHA-256 provenance and database receipts for downloads. |
| M5 | Job schema, persistent state and events, independent worker, authenticated submission/status/artifact endpoints and adapter for the existing M5 app. |
| M6 | Tests for real data, invalid inputs, changed bytes, ownership, a separate-worker HTTP demonstration and CI/deployment files. |

The Alaska pair is the supplied 17 and 29 October 2026 NISAR GCOV HHHH extract. The source includes mixed provisional and validated processing. The small internal translation estimate was kept as a diagnostic. Exact source authentication, independent geometry and Alaska change labels remain outstanding. The public Sentinel-1 benchmark compares flood/water labels in a different sensor and region. It cannot establish Alaska accuracy. Census blocks cannot place individuals within the change footprint.

## Data attribution

- NISAR extracts and metadata were provided in the team's Phase 1 snapshot. For product meaning, see the [ASF NISAR GCOV guide](https://hyp3-docs.asf.alaska.edu/nisar-docs/gcov/).
- Ritu Yadav, *Modified Sen1Floods11 Dataset for Change Detection*, [Zenodo 7946594](https://doi.org/10.5281/zenodo.7946594), CC BY 4.0. Three original chips are redistributed unchanged under role-based filenames. Original entries are listed in `data/benchmark-source.json`.
- Population and roads come from [Census TIGERweb](https://tigerweb.geo.census.gov/arcgis/rest/services/). Building queries use [FEMA and ORNL USA Structures](https://gis-fema.hub.arcgis.com/pages/usa-structures). Query details are in `data/geography/geography-source.json`.
- The six scripts under `phase1_compat/m2` are copied from the team's supplied Phase 1 snapshot for reproducibility.
