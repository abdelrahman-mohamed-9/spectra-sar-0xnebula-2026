# SPECTRA-SAR | M1 T02 — NASA CMR Scene Selection

**Status:** CATALOG CANDIDATES SELECTED — **NOT** SCIENTIFICALLY VALIDATED OR DOWNLOADED

Search timestamp (UTC): 2026-11-13T16:12:00.295936+00:00

## Real catalog findings
- GCOV: 77 entries returned, 8 candidate pairs shortlisted. The 8 include two frames (031 and 032); frame 031 has much better *approximate* coverage of the designated flood AOI bbox.
- GOFF: 65 entries returned, 60 individually stored in `candidate_granules`. Do **not** conflate catalog count with saved detail count.
- Validated GOFF query in this upload returned no matches in the searched time window, but provisional GOFF candidates are available.

## Primary Flood candidate — GCOV (Track 034, Ascending, Frame 031)
- **Before:** 2026-09-20 13:15:12 UTC, `NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001`
- **During flood window:** 2026-10-02 13:15:12 UTC, `NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001`
- Separation: **12 days**.
- Matching filename metadata: PROVISIONAL, track 034, ascending, frame 031, mode 4005, polarization code DHDH, processing CRID P05023.
- CMR footprint polygon intersects approximately **100.0%** and **100.0%** of search AOI rectangle. This is **not** validated pixel-level coverage.
- NOAA NWS reported Mendenhall Lake crest around **5:45 AM AKDT** on 2026-10-02. NISAR candidate observed at **5:15 AM AKDT**, ~**30 minutes before** that crest (if the reported official event time applies to the AOI and local daylight offset). This is promising, **not flood confirmation**.
- Sources: https://www.weather.gov/ajk/suicideBasin ; https://forecast.weather.gov/product.php?format=TXT&glossary=0&issuedby=AJK&product=AFD&site=GID&version=26

### CMR IDs
- Before: `G4319985062-ASF`
- During-flood candidate: `G4338819270-ASF`

### Download URLs (HDF5, may require NASA Earthdata Login)
- Before: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_031_034_A_031_4005_DHDH_A_20260920T131512_20260920T131548_P05023_N_F_J_001.h5
- During flood: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GCOV_PROVISIONAL_V1/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GCOV_032_034_A_031_4005_DHDH_A_20261002T131512_20261002T131548_P05023_N_F_J_001.h5

## Primary Glacier candidate — GOFF
- **Pair:** 2026-09-20 13:15 UTC → 2026-10-02 13:15 UTC (12 days).
- **Granule:** `NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001`
- **CMR ID:** `G4338825825-ASF`
- Approximate AOI bbox coverage by CMR footprint: **95.8%**.
- Download: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_034_A_031_032_4000_SH_20260920T131512_20260920T131548_20261002T131512_20261002T131548_P05023_N_F_J_001.h5

## Glacier backup candidate — GOFF
- **Pair:** 2026-09-21 04:30 UTC → 2026-10-03 04:30 UTC (12 days).
- **Granule:** `NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001`
- **CMR ID:** `G4340767468-ASF`
- Approximate AOI bbox coverage by CMR footprint: **100.0%**.
- Download: https://nisar.asf.earthdatacloud.nasa.gov/NISAR/NISAR_L2_GOFF_PROVISIONAL_V1/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001/NISAR_L2_PR_GOFF_031_043_D_059_032_4000_SH_20260921T043015_20260921T043051_20261003T043015_20261003T043051_P05023_N_F_J_001.h5

## Scientific limitations and next gate (M1 T03)
1. The archive shows the granules exist, but **no HDF5 pixel data have been opened**.
2. **Validate precise raster bounds and AOI** — CMR footprints are approximate, especially around frame edges.
3. GCOV: open **the same L-band co-polarized covariance channel** for both, verify CRS, grid alignment, valid data, scaling, processing version, and artifacts. Do not infer actual channel from filename code alone.
4. Check flood presence against the river-stage chronology. Radar backscatter change is not independently a flood map.
5. GOFF: inspect displacement grid, valid values, units, quality mask, SNR/correlation and spatial coherence **over ice**, not surrounding mountains.
6. Note potential high-latitude provisional NISAR processing artifacts. Do not blend provisional with validated products in the same raw change calculation.
7. Start with a small AOI and NASA Harmony subsetting before attempting full-size HDF5 downloads.

**Decision:** Move to **T03 Scientific Validation** with GCOV 2026-09-20/2026-10-02 frame 031 and GOFF 2026-09-20/2026-10-02 as primary. Do not label T02 as final science approval.
