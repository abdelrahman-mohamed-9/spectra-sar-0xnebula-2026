# Exact NASA data extraction — quickest route (no full HDF5 download)

**This step is still PENDING**. Catalog URLs are real, but the SAR pixel data have not been retrieved by this package.

## The images to obtain first: GCOV Flood Baseline

1. Open https://search.earthdata.nasa.gov/search and sign in with your own Earthdata Login; do not send anyone credentials.
2. Locate collection `NISAR_L2_GCOV_PROVISIONAL_V1` and search the Juneau/Mendenhall area. Find **these two exact granule IDs**:
   - `NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001`
   - `NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001`
3. Apply the rectangular polygon `aoi/flood-aoi.geojson` using spatial search AOI. Its coordinates are in `metadata/metadata.json`. Trim it to a tighter study footprint if needed; the rectangle itself is NOT a flood boundary.
4. Add **both exact granules** to My Project. Under **Edit Options → Customize Download**, enable **Spatial Subsetting** (trim to selected spatial extent).
5. Under **Variable Subsetting → Edit Variables**, select the **same** `science/LSAR/GCOV/grids/frequencyA/HHHH` for both dates **if it exists in both products** (the filename DHDH implies HH/HV mode but exact dataset must be confirmed). Optionally also `mask` / `numberOfLooks` if available. Use Cloud Optimized GeoTIFF.
6. Leave **No Reprojection** initially or select the same target CRS. The GeoTIFF pixel grids may still differ by a few pixels even at the same CRS: check and align with a documented resampling method before calculating changes.
7. Submit the Harmony job, wait for it to finish, download the real output TIFs, and put them in `data/real-gcov/`. Do not rename a generic GeoTIFF as verified unless you checked the actual polarization and date.
8. Open the real downloaded TIFs, verify valid pixels, spatial overlap and quality. Run T03 `gatekeeper.py` with `--before` and `--after` arguments to perform a raster-level check.

## Glacier motion: GOFF (do only after GCOV)

1. Search `NISAR_L2_GOFF_PROVISIONAL_V1` for exact granule:
   `NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001`
2. Use `aoi/glacier-aoi.geojson`, and choose GOFF offset layers **plus corresponding quality/SNR layers that exist** in this product. Avoid guessing exact nested variable names; inspect options in Harmony.
3. Download cropped COGs; then check units, valid ice coverage, offset outliers, SNR, reference geometry and whether displacement/velocity interpretation is justified. GOFF may contain unfiltered outliers.

## Acceptance is NOT automatic

GCOV change is **radar backscatter change**, not automatically flooded pixels. A satellite pass near a reported flood crest is promising timing only. GOFF offset measurements need quality screening, and the rectangle may include non-glacier terrain.

Official sources:
- https://nisar-docs.asf.alaska.edu/harmony/
- https://nisar-docs.asf.alaska.edu/gcov/
- https://nisar-docs.asf.alaska.edu/goff/
- https://search.earthdata.nasa.gov/search
