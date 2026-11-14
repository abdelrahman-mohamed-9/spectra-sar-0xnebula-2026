# SPECTRA-SAR | NASA NISAR Data Provenance and Integrity Receipts

**Team:** 0xNEBULA  
**Challenge:** NASA Space Apps Cairo 2026 - Dancing with the SARs

## The exact observations

The following values are read from the project manifest and checked against the project input-provenance JSON and actual packaged GeoTIFF data.

| Property | Before | After |
|---|---|---|
| Acquisition (UTC) | 2026-10-17T06:24:24Z | 2026-10-29T06:24:25Z |
| Collection | NISAR_L2_GCOV_PROVISIONAL_V1 | NISAR_L2_GCOV_V1 |
| Processing identifier | P05023 | P05036 |
| Polarization / covariance term | HHHH | HHHH |

**Before granule:** `NISAR_L2_PR_GCOV_033_073_D_055_4005_DHDH_A_20261017T062424_20261017T062502_P05023_N_F_J_001`

**After granule:** `NISAR_L2_PR_GCOV_034_073_D_055_4005_DHDH_A_20261029T062425_20261029T062502_P05036_N_F_J_001`

**Original HDF5 URLs recorded in the project manifest** (opening the data files may require NASA Earthdata permissions):
- Before: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_033_073_D_055_4005_DHDH_A_20261017T062424_20261017T062502_P05023_N_F_J_001/NISAR_L2_PR_GCOV_033_073_D_055_4005_DHDH_A_20261017T062424_20261017T062502_P05023_N_F_J_001.h5
- After: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_V1/NISAR_L2_PR_GCOV_034_073_D_055_4005_DHDH_A_20261029T062425_20261029T062502_P05036_N_F_J_001/NISAR_L2_PR_GCOV_034_073_D_055_4005_DHDH_A_20261029T062425_20261029T062502_P05036_N_F_J_001.h5

**HDF5 layer:** `//science/LSAR/GCOV/grids/frequencyA/HHHH`
**Local subset:** 293 x 303 pixels; 10.0 m grid; EPSG:3413.

## Verified SHA-256 of local raster input bytes

- Before (`before_HHHH.tif`): `c1f87d53de0de13c48712c633bc8e5bfd6ae281441fcee876dc3c0bf49bee6e8`
- After (`after_HHHH.tif`): `396680ad535b69fbc34d18d82a877e6aab4371a70d1f6791f69fbcdd25c495ac`

The same exact bytes were verified at **four file paths each** in the locally available project:

### Before
- `data/nisar/before_HHHH.tif` - 311,691 bytes
- `data/real-nisar-oct2026-pair/before_HHHH.tif` - 311,691 bytes
- `results-phase3/sources/nisar/before_HHHH.tif` - 311,691 bytes
- `results-phase3-population/sources/nisar/before_HHHH.tif` - 311,691 bytes

### After
- `data/nisar/after_HHHH.tif` - 310,776 bytes
- `data/real-nisar-oct2026-pair/after_HHHH.tif` - 310,776 bytes
- `results-phase3/sources/nisar/after_HHHH.tif` - 310,776 bytes
- `results-phase3-population/sources/nisar/after_HHHH.tif` - 310,776 bytes

**Scientific boundaries:** these hashes are file-integrity checks for local raster copies, not NASA signatures of the original `.h5` granules. The two NASA granules have different processing identifiers / collections (P05023 Provisional vs P05036 V1), which can introduce cross-version biases. We have not established independent scientific validity, event attribution, original HDF5 integrity, or confirmed flooding/damage. M1 exported rasters are transformed artifacts and can have different hashes.

## Sources
- [NASA/ASF NISAR GCOV product guide](https://nisar-docs.asf.alaska.edu/gcov/)
- [NISAR data products overview](https://nisar-docs.asf.alaska.edu/products-overview/)
- [NASA/ASF Earthdata access instructions](https://nisar-docs.asf.alaska.edu/earthaccess/)
- Project records: `data/nisar/manifest.json`, `data/nisar/input-provenance.json`, `results/provenance.json`.

## Local verification

From the root of the extracted project:

```bash
shasum -a 256 data/nisar/before_HHHH.tif data/nisar/after_HHHH.tif
```

Check the printed 64-character hashes against the values above. A match confirms the local bytes, not the original satellite product authenticity.
