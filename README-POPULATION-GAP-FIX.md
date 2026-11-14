# SPECTRA-SAR M3 population NoData quick fix

**This patch does NOT create or replace population data**. It only handles the scientifically important case in which the real WorldPop GeoTIFF has *no usable pixels*, but a modeled AOI population aggregate is available. It preserves the strict T03 validation `REJECT` and labels M3 as `PARTIAL_DATA_GAP`, while allowing M1, M2, M4, M5 and M6 to complete their existing software steps.

- M3 candidate SAR-change geometry is retained, not classified as damage.
- Calls the official WorldPop `/v3/population` for the **same experimental AOI** and year 2026; can succeed even when the raster lacks valid cells.
- If the aggregate request fails, marks `UNAVAILABLE`; doesn't infer zero.
- **Never** turns NoData into 0, and never represents the aggregate total as spatial exposure to the candidate change footprint.
- Does not invent OSM features/buildings or change QA to `PASS`.
- Writes `data/real-m3-impact/M3-POPULATION-DATA-GAP.json` and `M3-LIVE-EXECUTION-REPORT.json`.
- Creates a new run with M3 `PARTIAL_DATA_GAP`; all scientifically relevant uncertainties remain.
- Prints `COMPLETED_WITH_POPULATION_DATA_GAP` (not fully verified impact).

## Install and run on Mac

Unzip this small patch over the EXISTING project directory `~/Downloads/SPECTRA-PHASE1-REAL-DATA-INTEGRATED/`. Keep previous images/runs untouched. Then:

```bash
bash ~/Downloads/SPECTRA-PHASE1-REAL-DATA-INTEGRATED/RUN_POPULATION_GAP_FIX.command
```

This is an honest demo-completion route, **not** an approved population-exposure calculation. To calculate exposure, replace with independently verified genuine population raster with valid spatial cells.
