# SPECTRA-SAR — M1 T03 Scientific Validation

## Scope

The T02 NASA CMR discovery returned real catalog granule identifiers for a 20 Sep → 2 Oct 2026 GCOV pair over Mendenhall Valley, and a GOFF product referencing the same acquisition epochs. **That does not prove an actual flood signal or valid displacement pixels.** The T03 gatekeeper checks catalog metadata now and optionally inspects local real SAR HDF5/GeoTIFF files when provided.

## Run immediately (no packages required)

On a Mac, extract the ZIP to Downloads and run:

```bash
cd ~/Downloads/spectra-m1-t03
python3 gatekeeper.py --selection inputs/selected-scenes.json --output validation-report.json
```

Expected: `CATALOG: CATALOG_PASS_RASTER_AND_SCIENCE_PENDING`, `SCIENCE READY: NO`.

Run software tests (standard library):

```bash
python3 -m unittest discover -s tests -v
```

Some raster tests will be skipped without `rasterio` or `numpy` installed.

## To validate genuine downloaded files

The preferred workflow is to use [Earthdata Search](https://search.earthdata.nasa.gov/search) > select the exact granule IDs from `inputs/selected-scenes.json` > `My Project` > `Customize Download` and use [Harmony's NISAR service](https://nisar-docs.asf.alaska.edu/harmony/) to extract just the **matching real diagonal backscatter layer** from both GCOV scenes, spatially clipped and reprojected to exactly the same target CRS and grid. Suitable GCOV real intensity candidates depend on product contents and include `HHHH` and `HVHV` (verify). `GCOV` values are gamma0 **linear power**; do not treat as dB unless transformed deliberately.

Once real files are on your machine, run:

```bash
python3 -m pip install numpy rasterio h5py
python3 gatekeeper.py \
  --selection inputs/selected-scenes.json \
  --before /path/to/real_before_HHHH.tif \
  --after /path/to/real_during_HHHH.tif \
  --goff /path/to/real_goff.h5 \
  --output validation-report.json
```

The program inspects the supplied file structure, sample valid pixels, georeferencing and, for matched GeoTIFFs, grid compatibility. **Do not** describe the data as verified inundation or credible ice velocity before scientific review of pixel quality, physical units, SNR/outliers, and independent event evidence. The HDF5 checker is deliberately structural only and reports further steps still required.

## T03 verdict policy

- `CATALOG_PASS_RASTER_AND_SCIENCE_PENDING`: filename/CMR metadata checks passed; *not* science-ready.
- `CATALOG_REJECTED`: some catalog metadata mismatch; do not start analysis with this pair.
- Raster geometry PASS: COGs share a grid and contain sample finite pixels; physical correctness still pending.
- `scientific_acceptance.status` is `NOT_APPROVED` until an explicit expert / subsequent review of actual raster data and the event. There is **no automated claim of a flood**.

## Member handoff

- M2: same-polarization matching GCOV diagonal layers and verified AOI grid, once available.
- M3: AOI & CRS, but no physical inundation extent before change detection.
- M4: NASA CMR source granules + signed provenance of files when possible.
- M5: consume structured `validation-report.json`; block scientific claims when `science_approved == false`.
- M6: show candidate dates and processing status, without mislabeling unverified maps.

NASA product sources: https://nisar-docs.asf.alaska.edu/gcov/ , https://nisar-docs.asf.alaska.edu/goff/ , https://nisar-docs.asf.alaska.edu/harmony/ .
