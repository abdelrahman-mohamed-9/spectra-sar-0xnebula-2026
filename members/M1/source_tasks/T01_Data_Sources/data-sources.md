# SPECTRA-SAR — M1 / Phase 1 / T01
## NISAR Data Source Discovery & Selection

**Project:** SPECTRA-SAR — Glacier & Flood Intelligence  
**Team:** 0xNEBULA  
**Study area:** Mendenhall Glacier, Mendenhall Lake & Mendenhall Valley, Juneau, Alaska, USA  
**Prepared:** 2026-11-13  
**Task:** T01 — NISAR Data Source & Product Selection  
**Status:** **COMPLETE for source discovery**; local scene availability and valid observation pairs are **NOT YET VERIFIED** (T02).

---

## 1. Decision

Use **NASA NISAR L-band, Level 2** products, obtained through the **Alaska Satellite Facility (ASF)** and NASA Earthdata services.

| Scientific question | Primary product | Dataset short name (Provisional) | Dataset short name (Validated) | Priority |
|---|---|---|---|---|
| Has radar-observed surface water/backscatter changed near Mendenhall Valley? | **L2 GCOV** — Geocoded Polarimetric Covariance | `NISAR_L2_GCOV_PROVISIONAL_V1` | `NISAR_L2_GCOV_V1` | **P0** — main demo |
| How did glacier surface features shift between two acquisitions? | **L2 GOFF** — Geocoded Pixel Offsets | `NISAR_L2_GOFF_PROVISIONAL_V1` | `NISAR_L2_GOFF_V1` | **P1** — only if suitable scenes exist |

**Why GCOV?** It provides radiometrically terrain-corrected and geocoded SAR backscatter (gamma-0 power), suitable for exploring changes in surface scattering and possible inundation. Backscatter change **is not automatically equivalent to a flood mask**; validation and interpretation are necessary.

**Why GOFF?** It provides geocoded pixel-offset measurements from two SAR acquisitions and supporting layers, useful for glacier displacement. GOFF offsets may include outliers and need quality filtering; deriving ground displacement/velocity requires appropriate geometry and time baseline.

**Scientific scope:** A **retrospective case study**, not an operational flood prediction or validated hazard alerting system. Glacier displacement and flood change are separate scientific analyses; do not assert causation from imagery alone.

## 2. Authoritative data sources and roles

| Source | URL | Project use | Status |
|---|---|---|---|
| ASF Vertex | https://search.asf.alaska.edu/ | Geographic/temporal scene discovery and NISAR SAR filters | Official; verified documentation |
| NASA Earthdata Search | https://search.earthdata.nasa.gov/search | Collection/granule discovery; select products; customize downloads | Official; verified documentation |
| ASF NISAR Data User Guide | https://nisar-docs.asf.alaska.edu/ | Product selection, naming, data access and quality caveats | Official; verified documentation |
| GCOV Product Guide | https://nisar-docs.asf.alaska.edu/gcov/ | GCOV calibration, raster layers, polarizations and metadata | Official; verified documentation |
| GOFF Product Guide | https://nisar-docs.asf.alaska.edu/goff/ | Offset layers, posting and unfiltered/outlier caveats | Official; verified documentation |
| NISAR Earthaccess Guide | https://nisar-docs.asf.alaska.edu/earthaccess/ | Programmatic search/download using collection short names | Official; verified documentation |
| NASA Harmony / NISAR | https://nisar-docs.asf.alaska.edu/harmony/ | Export selected HDF5 datasets to GeoTIFF/COG; spatial subset and reproject | Official; verified documentation |
| NASA NISAR Availability | https://nisar-docs.asf.alaska.edu/availability-overview/ | Maturity levels, temporal coverage, gaps | Official; verified documentation |
| NISAR Provisional Known Issues | https://nisar-docs.asf.alaska.edu/provisional-known-issues/ | Quality caveats relevant to high-latitude Alaska | Official; verified documentation |
| NOAA/NWS Suicide Basin | https://www.weather.gov/ajk/suicideBasin | Independent context for historical 2026 outburst flood events | Official event context, **not** a NISAR granule archive |

Other resources in the challenge (CSA RADARSAT, CONAE SAOCOM, NASA ARSET/StoryMaps) are supporting references or contingency options, **not mixed into the primary NISAR time series**.

## 3. Which data maturity to use?

- **PROVISIONAL** (`..._PROVISIONAL_V1`): acquisitions beginning **2026-06-17** through part of **2026-10-23**; calibrated and partially validated. This is the first collection to search for the **August/October 2026 flood events**.
- **VALIDATED** (`..._V1`): released **2026-11-06**; collections include NISAR L-band acquisitions starting **2026-10-21**. Prefer validated products when both dates are supported within this same processing series.
- **BETA**: earlier pre-calibration products; avoid in a change comparison unless scientifically justified.
- **Never casually compare different maturity levels** (Beta/Provisional/Validated), because differences in processor versions can mimic actual landscape change.
- **Known NISAR instrument gap:** `2026-07-27T22:03:25Z` to `2026-08-10T00:55:27Z`. Avoid spending time searching for observations during this permanent gap.
- **High-latitude warning:** provisional data can be affected by ionospheric/geolocation artifacts. Review quality flags and image alignment for Juneau.

## 4. Study area and observation logic

**AOI candidates** (geometry not finalized in T01):
1. **Flood AOI:** Mendenhall Lake, lower Mendenhall River and parts of Mendenhall Valley.
2. **Glacier AOI:** Mendenhall Glacier and the relevant ice surface upstream of the lake.

**Flood-search event windows:** prioritize scene acquisitions covering the region around the **August 2026** outburst event and **2026-10-02** event, with a genuinely useful before/event-time or before/after-water-level comparison. An image acquired after waters recede might not capture the inundation peak.

**Glacier search:** find an existing GOFF product covering the ice surface, inspect its underlying reference/secondary observation dates, valid offsets, quality/SNR layers, and use only if reliable.

These are **search targets, not confirmed acquisitions**. T02 must provide actual ASF/CMR granule IDs and acquisition times.

## 5. Quick access workflow for M1

1. Open [ASF Vertex](https://search.asf.alaska.edu/).
2. Choose **Geographic Search**, Dataset **NISAR**, and draw a small AOI around Juneau/Mendenhall. Filter by **GCOV** and **PROVISIONAL**, then by suitable dates.
3. Record **all candidate granule IDs, acquisition time (UTC), product version/maturity, relative orbit/track, direction, polarization, coverage, and links**.
4. Repeat for **GOFF**, inspecting displacement product validity and reference/secondary image dates.
5. Use [Earthdata Search](https://search.earthdata.nasa.gov/search) and [Harmony](https://nisar-docs.asf.alaska.edu/harmony/) to extract selected layers over a subset into Cloud Optimized GeoTIFF (COG) when available.
6. Create or use a free **NASA Earthdata Login** account for authenticated download; do not put credentials, tokens, or `.netrc` in Git.

**Optional programmatic discovery with `earthaccess`:**

```python
import earthaccess

for short_name in (
    'NISAR_L2_GCOV_PROVISIONAL_V1',
    'NISAR_L2_GOFF_PROVISIONAL_V1',
):
    # Discovery of sample results only; NOT proof of Mendenhall coverage.
    results = earthaccess.search_data(short_name=short_name, count=1)
    print(short_name, 'sample result count:', len(results))
```

For **T02**, add an actual Juneau AOI polygon and bounded acquisition dates to the search before treating results as relevant. Do **not** fetch unrelated example scenes to claim data coverage.

## 6. Scientific/data acceptance rules for T02/T03

**GCOV pair must have:**
- Same study AOI and sufficient overlap after geospatial alignment.
- Comparable **frequency, polarization/covariance diagonal channel** and acquisition geometry; do not hardcode VV/VH when actual scenes may use HH/HV.
- Compatible processing maturity and documented processor/version information.
- Valid geocoding/CRS, pixel spacing, NoData/quality masks and calibrations.
- Observation dates appropriate to the specific phenomenon being claimed.

**GOFF must have:**
- Actual product overlapping Mendenhall Glacier.
- Known acquisition pair/time baseline, available displacement/offset layers, projection and quality/SNR.
- Outlier handling, movement interpretation in correct units and caveats on uncertainty.

**Neither is accepted merely because the collection exists.** Each accepted file must be opened and inspected; metadata and source URL/ID retained.

## 7. Handoff / task status

| Task | State | Evidence / pending output |
|---|---|---|
| **T01 Source discovery** | **DONE** | This document; official product types, short names, access methods and scientific constraints |
| T02 Real scene discovery | **NOT STARTED** | `scene-pair.json`, `goff-scenes.json` with **real scene IDs**, or documented no-match |
| T03 Compatibility validation | **NOT STARTED** | `gatekeeper.py`, `validation-report.json` |
| T04 AOI/metadata preparation | **NOT STARTED** | `flood-aoi.geojson`, `glacier-aoi.geojson`, `metadata.json` |
| T05 Access and sample test | **NOT STARTED** | Opened real raster, `access-report.md` |

**Immediate next action:** M1 searches the **actual** ASF/CMR catalog for Juneau and reports scene IDs. If a usable flood pair is not established within the agreed search window, escalate a scoped fallback rather than blocking the full 18-hour build. The verified product collections alone do **not** validate scene availability.

## 8. Sources checked (2026-11-13)

- ASF NISAR GCOV product documentation — https://nisar-docs.asf.alaska.edu/gcov/
- ASF NISAR GOFF product documentation — https://nisar-docs.asf.alaska.edu/goff/
- ASF NISAR data availability and maturity — https://nisar-docs.asf.alaska.edu/availability-overview/
- ASF Earthdata Search collection names — https://nisar-docs.asf.alaska.edu/earthdata-search/
- ASF Vertex search procedures — https://nisar-docs.asf.alaska.edu/vertex/
- ASF NISAR Harmony — https://nisar-docs.asf.alaska.edu/harmony/
- ASF Provisional known issues — https://nisar-docs.asf.alaska.edu/provisional-known-issues/
- NWS Suicide Basin monitoring — https://www.weather.gov/ajk/suicideBasin
