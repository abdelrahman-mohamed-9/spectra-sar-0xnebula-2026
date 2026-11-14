# M1 — What do I need from each teammate?

## Critical blocker (not another teammate)
The only immediate **blocking** dependency for M1 T05 is the **NASA Earthdata/Harmony login and actual data access on the user's Mac**, plus successful raster QA. Source discovery has already identified two GCOV granules. Until real `before_HHHH_20260920.tif` and `after_HHHH_20261002.tif` are downloaded and checked, M2 cannot legitimately report actual flood change calculations for this case.

## Team inputs requested (parallel work; NOT blockers for discovery/download)

| Member | Request from them to M1 | Suggested artifact | Urgency |
|---|---|---|---|
| **M2 (AI)** | Exact accepted SAR layer(s), float/linear-vs-dB policy, preferred raster grid/NoData input spec, expected GOFF offset/quality fields | `ai-input.schema.json`, `input-requirements.md` | High — before handing over downloaded images |
| **M3 (Impact/GIS)** | Confirm/adjust exact flood and glacier AOIs and which subregions/statistics are needed; avoid using provisional bounding rectangles as hazard footprints | `flood-aoi.geojson`, `glacier-aoi.geojson` (reviewed) | High — before scientific masking |
| **M4 (Security)** | Evidence/provenance field names, checksums and source manifest format for downloaded rasters/processed outputs | `evidence.schema.json` | Medium — integrate while download starts |
| **M5 (Backend)** | Agreed dataset/analysis JSON API contract, object/file storage locations and readiness flag meaning; preferably `M1_TO_M2` handoff schema too | `analysis.schema.json`, `storage-contract.md` | High — before integration |
| **M6 (Frontend/GIS)** | Target preview output (PNG / tile / COG), projection and layer naming for display, chronology and map attribution | `frontend-types.ts`, `layer-requirements.md` | Medium — can proceed from M1 metadata |

## M1 deliverables owed to teammates

| Member | What M1 sends |
|---|---|
| **M2** | Actual verified GCOV before/after TIFFs + `T05` QA report + channel/CRS/grid metadata; later verified GOFF offset and uncertainty layer |
| **M3** | Agreed AOIs + georeferencing, and ultimately change-mask context provided in coordination with M2 |
| **M4** | Exact NASA CMR IDs, CMR query provenance, product URLs, downloaded-file SHA-256 checksums / Harmony job records |
| **M5** | `T04_AOI_Metadata/metadata/metadata.json`, data locations, availability and schema, NASA granule IDs, QA status |
| **M6** | Bounding boxes, acquisition times, appropriate raster previews/COGs and relevant caveats when image data exists |

**Important:** M1 can continue T05 NOW without waiting for the five teammates. Other contracts can be confirmed in parallel. Raw data is not confirmed until downloaded and QA succeeds; GOFF motion is a separate pending check.
