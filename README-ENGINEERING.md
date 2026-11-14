# SPECTRA-SAR · Phase 1 + Phase 2 + Phase 3 integrated release

**Phase 3.4 — Mission Review Studio (offline):** Open `judge-demo/index.html` directly in your browser. It contains a transparent, published Sentinel-1 Spain holdout case with ranked detections, retrospective precision/recall comparison, exports and SHA-256 evidence. No login, internet, Python installation or server needed for this one-click demo. The original integrated app also links to `/mission/`. See [JUDGE-START-HERE.txt](JUDGE-START-HERE.txt), [JUDGE-DEMO-2-MIN-PITCH.md](JUDGE-DEMO-2-MIN-PITCH.md), and [JUDGE-POPULATION-INPUT.md](JUDGE-POPULATION-INPUT.md). Population exposure is unavailable without a verified Spain-specific raster; this update never invents exposure numbers.


**Phase 3.2:** Arabic explanations, review priorities, persistent in-app alert acknowledgements, comparison of completed analyses and portable illustrated HTML reports are available. Read [PHASE3.2-GUIDE.md](PHASE3.2-GUIDE.md).

**Latest update — Phase 3.1:** [PHASE3.1-UPDATE.md](PHASE3.1-UPDATE.md) adds a population layer for the existing SAR pair. Select `nisar-oct2026-ghsl2025` in the dashboard to use it. No replacement SAR downloads are needed.

**Phase 3 delivery:** start with [PHASE3-START-HERE.md](PHASE3-START-HERE.md). Native Windows support is available for the integrated Phase 2/3 worker and dashboard through `START-WINDOWS.ps1`. Validation and inherited Phase 1 failures are documented in `reports/PHASE3-VALIDATION.md`. The remainder of this README records the supplied Phase 2 release and its historical limitations.

This package combines the supplied Phase 1 code, its population-gap patch, and the Phase 2 processing engine in one local workspace. It adds a dashboard, reproducible source imports, two candidate screens, additional external ML comparisons, and executable integration checks.

**Engineering release, exploratory science.** The bundled Alaska pair has no independent change labels, mixed processing versions, and no usable spatial population counts. The software never treats these gaps as a successful scientific validation.

## Start on macOS or Linux

Install Python **3.12** (tested), extract the ZIP, open Terminal in this directory and run:

```bash
bash START.command
```

The first launch installs Python dependencies from the package index; internet is needed for installation. Subsequent analysis of the included source snapshots needs no data download or NASA account. Python 3.13/3.14 are accepted by the launcher but were not exercised in this release. Native Windows is not supported by the POSIX worker lock; use WSL or Linux Docker.

The launcher starts the **original M5 application**, mounts both phases, starts a separate supervised worker, opens `http://127.0.0.1:8765`, and prints an operator token. Paste it into the dashboard, select a source pair and candidate screen, then choose **Run analysis**. Ctrl+C stops both processes. Tokens and run data stay in the private `state/` directory, outside the delivered archive.

If the port is busy:

```bash
bash START.command serve --port 8770
```

The token controls one local operator account. It is not a shared-team authentication system. To use real M5 JWT identities, see `docs/INTEGRATION-AND-OPERATIONS.md`.

## What is included

| Role | Implemented behavior |
|---|---|
| M1 | Existing Phase 1 source/processing modules, exact included source receipt, common-grid harmonization, internal subpixel translation diagnostics, immutable pair import CLI. |
| M2 | Existing Lee filtering, fixed baseline, robust conservative candidates, uncentered spatial review candidates, threshold stability, optional independent reference evaluation, original logistic comparator, train-only F2 threshold policy and spatial gradient-boosting experiment. |
| M3 | Selected-screen footprint/asset intersection, population count raster support with coverage checking, explicit missing-source states, candidate priority layers. |
| M4 | Pinned source inventory, stage receipts, source-to-output provenance, verified artifact downloads, client-side SHA-256 download check. |
| M5 | Original Phase 1 backend, local Phase 2 API, M5 JWT adapter, SQLite jobs/events, separate worker, ownership isolation and interrupted-job recovery. |
| M6 | Original member regressions, Phase 2 tests, live HTTP/worker run, DOM functional UI checks, source equality proof, launch scripts, Docker/CI configurations and evidence reports. |

The dashboard has before/after comparison, conservative/broader-review raster views, selected-screen review priority, recent jobs, external comparison metrics and downloads. It uses local assets; no tile server, CDN or external UI library is required.

## Candidate screens

- **Conservative** keeps the original robust-median/MAD screen. Included pair: **566** candidate pixels.
- **Broader review** uses the fixed 3 dB threshold with same-sign component filtering, without subtracting the scene median. Included pair: **638** candidate pixels. This can preserve widespread shifts and also additional false alarms.
- The original unfiltered and Lee-filtered fixed-threshold baselines remain in the results. None of these counts is a count of verified events or people.
- The screen selected when submitting a job controls M3 impact/priority outputs. Switching a visualization tab does not rerun or change that job's impact calculation.

## Check the delivery

```bash
bash START.command test
bash START.command demo
```

`test` runs Phase 2 and the real M5 JWT adapter test. `demo` submits a job through HTTP, executes an independent worker process, downloads all registered files and verifies their hashes. Original Phase 1 regression suites can be run after setup with:

```bash
.venv/bin/python scripts/test_all.py
```

Evidence for this delivery is in `reports/`; the regenerated bundled-pair results are in `results/`. Historical reports are deliberately labeled in `legacy-phase1/` and `legacy-phase2-results/`. Current acceptance status is in `reports/RELEASE-VALIDATION.md`.

## Import another real pair

The importer accepts the **Phase 1 M1 pair contract**, not arbitrary unlabeled before/after images. Supply `manifest.json`, the referenced single-band GeoTIFFs, validity masks and any local GDAL sidecars. Values must be linear SAR power and metadata must truthfully describe the pair. Limit: 2 million pixels per input and 300 MB per imported source tree.

```bash
bash START.command import --id my-pair --pair /absolute/path/to/M1/pair
```

Refresh/reconnect the dashboard to see the new immutable dataset. An existing dataset ID is never overwritten. Missing geographic layers are marked **not provided**, not zero assets. To supply geography and independent labels:

```bash
bash START.command import --id my-labeled-pair \
  --pair /absolute/path/to/M1/pair \
  --geography /absolute/path/to/geography \
  --reference /absolute/path/to/labels.tif \
  --reference-metadata /absolute/path/to/provenance.json
```

See `docs/DATA-CONTRACTS.md` for formats. The importer does not train on the supplied labels: they are reserved for evaluation. Scientific approval still requires independent review.

## Scientific limits that remain

- Alaska scene/source identity is inherited from the supplied Phase 1 receipts; original provider authenticity is not independently established by this package.
- Mixed NISAR processing, missing independent geometric/radiometric certification and missing Alaska reference labels remain material uncertainties.
- The public Sentinel-1 benchmark has two training chips and one held-out chip. The added models did **not** outperform the original logistic baseline on Spain. Results are retained transparently and none is transferred to Alaska.
- The 2020 Census block total is context only. Exposure remains unavailable without valid spatial count data. Empty road/building queries do not prove absence.
- Docker build/run, hosted CI, production PostGIS/Redis/object storage and real-browser visual rendering were not verified here. Local HTTP, original JWT logic, source data and application DOM behavior were exercised.

## Data and code attribution

Source lineage and upstream references are in `docs/SOURCES.md`. No synthetic observations were inserted into the demonstration data. Temporary synthetic arrays are used only in software tests and are explicitly labeled as fixtures.
