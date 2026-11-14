# NASA SPECTRA-SAR — M3 Phase 1 / T09

## What ships
Real orchestration of previous T03–T08 implementations, with provenance, checksums, status gates, regression tests and an API interface contract. T01/T02 are specifications/source acquisition; they are not executed by this pipeline. All source files are bundled in `modules/`.

## Quickstart
```bash
python -m pip install -r requirements.txt
python -m pytest -q -p no:cacheprovider tests
python pipeline.py --config config.example.json --out results/run01
```
Edit `config.example.json` first with real, **existing** files, and set truthfully verified metadata. The example file has deliberate placeholder paths and will fail until updated.

## Caution
- Tests use synthetic *test-only* fixtures; passing tests does **not** prove processing of live Sentinel-1 / WorldPop or OSM data.
- The M2 hazard input MUST be an actual georeferenced change footprint with provenance; **a change footprint cannot be called a flood or wildfire without separate validation**.
- Risk config and recommendation rules are uncalibrated defaults and not production operational guidance.
- T03 WARNING requires explicit analyst approval; REJECT always halts the pipeline.
- Inspect `run_manifest.json` for file provenance and exact SHA256 identities of input/output.
- This run is **not** proof that T02 downloader works against live endpoints; live smoke test and reference-event verification remain open.

## Acceptance gates
1. Test suite passes on clean install.
2. End-to-end fixture run produces seven stage outputs and hashes.
3. Missing input, corrupt data or T03 REJECT fail closed.
4. Unknown hazard/missing calibrated SAR confidence -> `REVIEW_REQUIRED`, no numeric risk score.
5. Live run uses operator-provided authentic assets and documents source/license, temporal alignment, AOI, raster units, analyst QA and independent reference validation.
