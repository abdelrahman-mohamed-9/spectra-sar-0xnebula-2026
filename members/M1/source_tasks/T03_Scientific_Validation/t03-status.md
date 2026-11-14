# SPECTRA-SAR — M1 / T03 Scientific Validation

## What is actually completed
- Read exact T02 chosen scenes from NASA CMR results supplied by the user.
- Ran catalog compatibility gatekeeper; 27 catalog checks passed, 0 failed.
- GCOV observations 2026-09-20 and 2026-10-02: same track, direction, frame, acquisition mode, polarization and filename-derived CRID.
- Primary GOFF spans the same two timestamps.
- Generated `validation-report.json`; ran 8 automated software tests successfully (using tiny synthetic rasters *only for code tests*, never as study-case data).

## What is not completed
- HDF5/GeoTIFF files have not been downloaded or opened; **no raster-level scientific acceptance**.
- A source footprint roughly intersecting the AOI does not show that pixels are valid within AOI.
- No scientific measurement of inundation, glacier displacement or glacier speed yet.

## Verdict
- **Catalog:** `CATALOG_PASS_RASTER_AND_SCIENCE_PENDING`
- **GCOV raster pair:** `PENDING`
- **GOFF data:** not supplied
- **Overall T03:** **PARTIALLY COMPLETE / WAITING FOR REAL RASTER FILES**

## Next action
Read `download-plan.md`, extract two real matching GCOV GeoTIFFs through Earthdata/Harmony, then run `gatekeeper.py` with `--before` and `--after`.
