# Phase 3.1 — continue with the existing Phase 1 pair

The existing 17 and 29 October 2026 SAR pair is retained byte-for-byte. No new SAR images, study area selection or user downloads are required to run the delivered analysis.

This update bundles an additional selectable source entry, `nisar-oct2026-ghsl2025`, containing the original SAR pair plus a GHS-POP 2025 population count raster. The original `nisar-oct2026` entry and pinned catalog remain unchanged for reproducibility.

Start normally with `START-WINDOWS.ps1` (or the existing macOS/Linux launcher). In **Source Pair**, choose **nisar-oct2026-ghsl2025**, then **Run analysis**. The dashboard reports population estimates, source year, confidence and evidence from the updated job. Results already generated are in `results-phase3-population/`.

## Population source

European Commission Joint Research Centre, GHS-POP R2023A, 2025, native 100 m Mollweide grid, people per cell, CC BY 4.0. Retrieved through the public JRC AWS mirror. Only a native-grid window was read; no whole-global download and no resampling of counts. Source URL, extraction method, timestamp and SHA-256 are included in `supplemental/nisar-oct2026-ghsl2025/data/geography/ghsl-source.json` and the run provenance.

Documentation: https://human-settlement.emergency.copernicus.eu/ghs_pop2023.php

Public mirror: https://registry.opendata.aws/ghs-pop/

The 2025 layer is a modelled residential population projection used with October 2026 SAR. It is not a contemporary census or live people count. All 6,342 valid cells in the downloaded window are zero in this source; all candidate zones have complete valid population coverage and estimated exposure 0. This does not establish that nobody lives or travels there. The original coarse Census context remains separately available.

A WorldPop 2026 API extraction was attempted first but returned an all-nodata window. It was rejected and is not included as usable population data.

## Checks and interpretation

Phase 2/3 automated suites: **33 passed**, including the original JWT adapter, unchanged-SAR proof, supplementary catalog integrity, immutable bundled IDs, population coverage and authenticated worker/API results. See `reports/phase3.1-tests.log` and XML. Warnings are retained in the log, chiefly existing affine multiplication deprecations during population-cell intersection.

Chrome: supplementary dataset selected, live job completed, population value and source year displayed, confidence filter and map controls passed, mobile screenshot captured. See `reports/phase3.1-browser.json` and `phase3.1-dashboard.png`. The inherited Phase 1/backend limitations documented in `reports/PHASE3-VALIDATION.md` still apply and were not relabeled as resolved.

`reports/phase3-population-run.json` records a successful run and verification of 50 artifacts, plus byte equality of every original SAR input file. Population exposure is now computable for this source; the other existing coverage/validation indicators remain truthful. No flags were changed to claim verified road/building coverage or independent scientific accuracy. Existing Phase 1/2 capabilities and API paths are retained.

This update does not require replacing the pair with Mendenhall imagery. The user-selected existing AOI is the working study area.
