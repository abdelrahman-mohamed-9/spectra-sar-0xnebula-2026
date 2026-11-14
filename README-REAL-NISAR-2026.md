# Run on REAL NASA NISAR Oct 17 / Oct 29, 2026 data

This is the same original integrated team archive with an extra, **non-destructive** importer for your actual `~/Desktop/SPECTRA-SAR/data/before.tif` and `after.tif`. Do not run the outdated NASA download flow; it expects Sept 20 / Oct 2, 2026 source products.

## One command on your Mac

```bash
cd ~/Downloads/SPECTRA-PHASE1-REAL-DATA-INTEGRATED
bash RUN_REAL_NISAR.command
```

(If you unzipped this archive elsewhere, change only the first `cd` path.)

The command reuses the original M1–M6 orchestrator, checks source files, creates real-data masks and provenance in `data/real-nisar-oct2026-pair/`, runs all available stages, creates `runs/<uuid>/run.json`, and prints a member-by-member summary. It does **not** fetch NASA again, change existing TIFFs, create fake data, or claim science approval. To change the input directory, set `SPECTRA_REAL_DATA_DIR=/path/to/data` before launching.

If an older local API is already running at `127.0.0.1:8765`, this runner does not start a competing API. To serve the new project later, stop the old server and run `bash START.command serve` in this new folder. An API is not necessary for the batch analysis.

## Scientific caveats

The 2026-10-17 data is PROVISIONAL P05023; the 2026-10-29 data is VALIDATED P05036. This may produce false change signals. It is an exploratory backscatter comparison, not a verified disaster impact map, and it is for a *different AOI* than Mendenhall Valley. The original code separately flags missing incidence-angle QA, independent ground truth, layover/shadow mask and M3's OSM/population exposure layers. Without those external layers, M3 may be BLOCKED but M4/M5/M6 audit paths can finish; inspect run reports for exact statuses.

## Verifiable content

The importer records actual SHA256 sums of source GeoTIFFs, exact ASF granule identifiers and product URLs given by the user, geospatial grid and valid-positive-pixel counts. Hashes do not prove NASA source authenticity. Input imagery is not included in the ZIP because it is on the user's Mac. All original member code remains inside the package.
