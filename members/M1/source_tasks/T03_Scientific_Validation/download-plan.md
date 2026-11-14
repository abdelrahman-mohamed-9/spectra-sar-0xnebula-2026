# M1 T03 — Download plan for real NISAR files

These identifiers come from the user-supplied NASA CMR results in T02. A download URL being listed does **not** mean an HDF5 file has been opened or scientifically verified.

## Exact granule candidates

### Flood before — 20 Sep 2026

- Granule ID: `NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001`
- CMR ID: `G4319985062-ASF`
- Official ASF HTTPS: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001.h5
- Optional QA statistics: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001_QA_STATS.h5

### Flood during-event candidate — 2 Oct 2026

- Granule ID: `NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001`
- CMR ID: `G4338819270-ASF`
- Official ASF HTTPS: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001.h5
- Optional QA statistics: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001_QA_STATS.h5

### GOFF glacier motion — primary

- Granule ID: `NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001`
- CMR ID: `G4338825825-ASF`
- Official ASF HTTPS: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001.h5
- Optional QA statistics: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001_QA_STATS.h5

### GOFF glacier motion — backup

- Granule ID: `NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001`
- CMR ID: `G4340767468-ASF`
- Official ASF HTTPS: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001.h5
- Optional QA statistics: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001_QA_STATS.h5

## Lightest access path (recommended)

1. Log in to [NASA Earthdata Search](https://search.earthdata.nasa.gov/search) with your own free Earthdata account.
2. Search NISAR GCOV Provisional for Mendenhall Valley and use the **exact granule IDs above** to confirm the two observations. Select the two matching GCOV granules.
3. In **My Project → Customize Download**, enable spatial subsetting to the chosen flood AOI. In **Edit Variables**, export the **same actual diagonal covariance intensity** on both dates (for instance `frequencyA/HHHH`, only if present in both files).
4. Export to georeferenced GeoTIFF/COG. Use a matching CRS, resolution and grid; the gatekeeper rejects different grids rather than silently resampling them.
5. Do the same for GOFF if time permits, selecting appropriate displacement and quality/SNR layers for the glacier AOI; a single offset raster is not sufficient to estimate a trustworthy physical velocity.
6. Run `gatekeeper.py --before /actual/before.tif --after /actual/after.tif --goff /actual/goff.h5` on files you actually downloaded.

The primary GOFF product uses two epochs **20 Sep / 2 Oct 2026**. Its `h5` can be large, so prefer Harmony spatial subsetting when possible.

## Scientific caution

The GOFF displacement layers are not post-processed to remove outliers by NASA; use quality/SNR and independent checks before any speed claim.
Flood-water interpretation must use a water-sensitive method and actual raster evidence. A NISAR pass near the reported flood crest is a promising time alignment, not a proof of flooding in the product.
