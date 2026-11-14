# SPECTRA-SAR · M1 T05 — Final download + integrity-checked raster QA

**Actual task status: not complete until NASA Earthdata produces two real GCOV GeoTIFFs and QA passes.** This package contains **no invented satellite images**. All historical scene identifiers come from the NASA CMR search results previously retrieved on the user's Mac.

## Fastest Mac instructions

1. Download `spectra-m1-t05-final.zip` and keep it in Downloads.
2. Open Terminal and execute:

```bash
cd ~/Downloads
unzip -o spectra-m1-t05-final.zip
cd spectra-m1-t05-final
bash run-on-mac.command
```

3. If an Earthdata username/password is requested, enter it **in your own Mac Terminal only**. Do not send it in chat. A user with an existing Earthdata `.netrc` or `EDL_TOKEN` may not need to enter credentials. This script uses TLS verification and certifi; it never disables HTTPS certificate verification.
4. When the command finishes, upload **`output/t05-status.txt`** and, if it exists, **`output/t05-real-data-qa.json`** to this conversation. If it fails to download, `reports/*-harmony-job.json` contains the error and source ID, with no password.

### Identified NASA source granules

- `G4319985062-ASF` — NISAR L2 GCOV provisional — 2026-09-20 13:15 UTC, before
- `G4338819270-ASF` — NISAR L2 GCOV provisional — 2026-10-02 13:15 UTC, after/possible event imagery
- Collection: `C2854338529-ASF`
- Dataset: `/science/LSAR/GCOV/grids/frequencyA/HHHH`
- Mendenhall flood AOI bounding box W,S,E,N = `-134.70,58.33,-134.40,58.55`

A NISAR image taken near the known flood event time **does not prove** floodwater is visible, even if basic raster QA succeeds. The Glacier GOFF motion workflow remains separate and pending.

## How this differs from the previous package

- Adds an independent checksum-based link from each `*.tif` to its Harmony job manifest, original output filename, exact CMR granule ID, acquisition date, and dataset variable. A locally **renamed** `HHHH` file alone is never accepted as scientific provenance.
- Adds `--verify-only` to inspect existing TIFFs without re-downloading, including if they were acquired manually through NASA Earthdata Search.
- Adds `summarize.py` to write a short, credential-free run-status file after any download attempt.
- Uses certifi CA certificate paths by default to reduce macOS `CERTIFICATE_VERIFY_FAILED` errors without skipping TLS validation.
- Existing-files-only mode: `.venv/bin/python fetch_harmony.py --verify-only`.
- Plan-only mode (no credentials/network): `.venv/bin/python fetch_harmony.py --dry-run`.

## Expected outputs after successful real download

```
data/before_HHHH_20260920.tif
 data/after_HHHH_20261002.tif
reports/before-harmony-job.json
reports/after-harmony-job.json
output/t05-real-data-qa.json
output/before_radar_preview.png
output/after_radar_preview.png
output/t05-status.txt
```

The statuses have strict meanings:

- `BASIC_PAIR_READY_FOR_M2`: matching raster pixel grid and layer and consistent local Harmony job manifests and file checksums (not an independent NASA-signed provenance proof) (scientific flood inference STILL pending).
- `NEEDS_GEOSPATIAL_ALIGNMENT`: inputs are geographically mismatched; don't subtract pixels directly.
- `NEEDS_LAYER_CONFIRMATION` or `NEEDS_PROVENANCE_CONFIRMATION`: need verified data provenance, not just a renamed filename.
- `FILE_MISSING`, `RASTER_OPEN_ERROR`, `AOI_NO_INTERSECTION`, etc.: investigate the failure.

## Fallback

Use [Earthdata Search](https://search.earthdata.nasa.gov/search), search `NISAR_L2_GCOV_PROVISIONAL_V1`, select the exact granules by their IDs, then **Customize Download → Spatial Subsetting → Variable Subsetting → HHHH under frequencyA → GEOTIFF**. Preserve original downloaded filename or NASA job record for scientific provenance. Put each actual export in the `data/` folder with the normalized filenames shown above and run `bash run-on-mac.command --verify-only`.

Sources: https://nisar-docs.asf.alaska.edu/harmony/ and https://harmony-py.readthedocs.io/en/main/user/tutorial.html
