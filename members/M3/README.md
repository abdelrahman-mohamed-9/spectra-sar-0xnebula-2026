# SPECTRA-SAR | Member 3 — Phase 1 (T01–T09)

**Status:** All nine task deliverables have been collected. Offline unit/integration tests are available. No live WorldPop, OSM, or satellite data is included and no real-event validation is claimed.

## Layout

- `docs/`: T01 scientific requirements, scope and M3 integration contract.
- `T02/`: real OSM/WorldPop acquisition implementation and unit tests.
- `T09/`: orchestration and the **canonical runtime copies** of T03–T08 in `T09/modules/T03` through `T09/modules/T08`, with integration tests.
- `live_test.py`: downloads real OSM/WorldPop and optionally runs T03–T08 if a real M2 geofootprint is supplied.
- `task_archive/T01` through `T09`: complete original per-task deliverables, READMEs, and unit tests (for traceability). **Do not import archived code into the runtime and create duplicate active modules.**
- `data/inputs/M1`, `data/inputs/M2`, `data/inputs/M3`: handoff folders, initially empty. `data/outputs/`: local results.
- `DATA_HANDOFF_CHECKLIST.md`: what each team member must provide.

## Install and test (Python 3.10+; GIS binary wheels required)

```sh
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider T02/tests T09/tests
```

## Real data run

Supply genuine EPSG:4326 study AOI polygon `data/inputs/M3/study_aoi.geojson` and execute:

```sh
python live_test.py --aoi data/inputs/M3/study_aoi.geojson --year 2025 --out live_results
```

If M2 delivered a georeferenced, scientifically documented change footprint, run (replace provenance with real acquisition IDs/dates):

```sh
python live_test.py --aoi data/inputs/M3/study_aoi.geojson --year 2025 --out live_results --hazard data/inputs/M2/change_footprint.geojson --hazard-provenance "Sentinel-1 actual product IDs, dates, preprocessing, M2 method and validation" --hazard-type unknown --evidence-status UNVERIFIED
```

**Important:** generic SAR change does *not* establish confirmed disaster extent. The pipeline may legitimately stop on QA WARNING without documented review. Do not set flags or claim validation merely to force a green result.

## Compatibility/limitations

See `T09/api_contract.md` and `DATA_HANDOFF_CHECKLIST.md`. The live runner uses T02 and T09 paths as supplied; T09 executes T03–T08. T02 provider downloads could be blocked/rate-limited. M3 does not itself produce Sentinel-1 change masks. Raster values must be checked for population units and vintage. No production/API/operational readiness is asserted.
