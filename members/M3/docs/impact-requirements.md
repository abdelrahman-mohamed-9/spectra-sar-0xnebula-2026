# SPECTRA-SAR — M3 / Phase 1 / T01
## Impact Assessment Requirements

**Document ID:** SPECTRA-M3-P1-T01-REQ  
**Version:** 1.0 — 2026-11-13  
**Owner:** Member 3 — Geospatial & Decision Intelligence  
**Status:** Requirements baseline (design approved for implementation; software/data integration not yet completed)

## 1. Mission
Transform georeferenced SAR-derived event/change products from M2 into *traceable exposure estimates* and *decision-support indicators*. Identify how much land overlaps a hazard footprint, which mapped assets intersect it, and how many residents may be within it. **Never equate an image change automatically with confirmed damage, a confirmed hazard, or an actual casualty.**

## 2. Scope
### In scope — Phase 1 foundation
- Flood-inundation footprints as the primary concrete hazard workflow.
- Wildfire/burned-area footprints as the second supported hazard *only when M2 supplies a hazard-specific, validated burned-area classification*; generic SAR change alone is insufficient.
- Event/AOI geometry ingestion, validation, provenance, geospatial overlays and coverage diagnostics.
- Area affected, people potentially exposed, affected roads/buildings/critical facilities, descriptive risk tiers, and uncertainty/quality flags.
- Reproducible output contract for the downstream dashboard/API and M4+ modules.

### Out of scope — Phase 1
- Generating SAR change masks (M2), downloading/calibrating raw SAR (M1).
- Claiming actual structural damage, deaths, economic loss, flood depth, water velocity or fire intensity based only on a change mask.
- Operational evacuation commands, emergency alerts or autonomous high-stakes decisions.
- Training a predictive disaster model without appropriate labeled ground truth.
- Fully operational ingestion APIs and analytical engine in T01 (later tasks).

## 3. Scientific input contract: M2 → M3 (proposed; requires M2 agreement)
Every analysis requires:

| Field | Required | Meaning / validation |
|---|---|---|
| `event_id` | yes | Stable non-empty identifier |
| `hazard_type` | yes | `flood` or `wildfire_burn` |
| `analysis_timestamp_utc` | yes | ISO 8601 UTC |
| `pre_event_acquired_utc` / `post_event_acquired_utc` | yes | Acquisition times; before < after |
| `aoi` | yes | Valid Polygon/MultiPolygon GeoJSON, EPSG:4326 |
| `hazard_raster_uri` OR `hazard_polygons_uri` | yes | Georeferenced, readable GeoTIFF or GeoJSON/GPKG |
| `hazard_class_semantics` | yes | Explicit positive/negative/NoData values; flood water vs burned area |
| `crs`, `pixel_size`, `nodata` | yes for raster | Spatial metadata and NoData meaning |
| `confidence_uri` or `confidence_status` | yes | Optional confidence map, otherwise `unavailable` (not fabricated) |
| `processing_version` | yes | M2 pipeline/software version |
| `source_scene_ids` | yes | Genuine satellite scene IDs / source URI(s) |
| `quality_flags` | yes | Layover, shadow, cloud for optical corroboration, registration, speckle/residual issues, etc. |
| `validation_reference` | conditional | Independent comparison data, if actually available |

**Contract decision:** `hazard_type=unknown` or an unclassified generic change map **must not** produce hazard-specific exposure numbers labeled as flood/fire. Result: `INSUFFICIENT_EVIDENCE`, with a non-hazard change-area overlay only if expressly requested.

## 4. External datasets and provenance
| Source | Intended use | Important constraint |
|---|---|---|
| WorldPop Global2 population counts (~100 m / 1 km) | Estimated people potentially exposed | Modelled count per grid cell, not an on-scene headcount; record edition, year, resolution and license |
| OpenStreetMap extracts / Overpass | Roads, mapped buildings, hospitals, schools, bridges | Incomplete and inconsistent coverage; ODbL attribution, rate limits, and missing tags matter |
| Copernicus Emergency Management Service mapping / GFM / EFFIS | Independent event comparison where temporal and spatial coverage align | Not all events/areas covered; a comparison map is not guaranteed ground truth |
| Administrative boundaries from traceable, licensed data | Region statistics and clipping | Confirm boundary source, vintage, CRS and license |

For every dataset record: `provider`, `dataset_name`, `dataset_version`, `source_url`, `downloaded_at_utc`, `observation_year_or_date`, `spatial_resolution`, `crs`, `license`, `checksum`, `coverage_fraction`, and `limitations`.

**Policy:** No synthetic population/building/hazard observations are allowed in real-result reporting. Fixtures may be synthetic **only within explicitly labelled automated tests**, never passed off as project evidence.

## 5. Functional requirements (FR)
| ID | Priority | Requirement | Acceptance criterion |
|---|---|---|---|
| FR-01 | MUST | Validate event schema, hazard semantics, time order and data provenance | Invalid/unknown inputs rejected with machine-readable reason |
| FR-02 | MUST | Validate geometry, CRS, NoData, AOI overlap and resolution | Bad CRS/geometry/no intersection returns explicit diagnostic |
| FR-03 | MUST | Align layers to a suitable analysis grid/CRS without corrupting categorical labels or population totals | Geometries overlap spatially; class masks resampled by nearest-neighbor; population totals preserved or discrepancies reported |
| FR-04 | MUST | Compute hazard footprint area in km² using appropriate area computation | Result excludes NoData, reports pixel/geometric method |
| FR-05 | MUST | Estimate population within classified hazard polygon | People-per-cell totals apportioned by documented intersection method; estimate and limitations included |
| FR-06 | MUST | Count/estimate exposure of mapped buildings and facilities | Distinguish `intersects`, `centroid_inside`, and `fully_contained`; count unique IDs |
| FR-07 | MUST | Report exposed road length (km) by highway type where available | Clip lines to footprint and calculate geodesic/equal-area-appropriate lengths |
| FR-08 | MUST | Assign configurable descriptive *screening* risk tier | Versioned thresholds and inputs provided; NEVER present as validated casualty/damage probability |
| FR-09 | MUST | Propagate quality flags and data coverage to outputs | `LOW_CONFIDENCE` / `INSUFFICIENT_DATA` when appropriate, never silently zero |
| FR-10 | MUST | Produce geospatial layers + summary JSON with source lineage | Output schema validation passes |
| FR-11 | SHOULD | Compare footprint to independent event mapping when available | IoU, precision, recall with independently defined labels, or explicit `not_evaluated` |
| FR-12 | SHOULD | Expose region-by-region summaries | Administrative aggregation reconciles with global total within documented overlaps |
| FR-13 | SHOULD | Generate explanatory decision-support statements | Rules cite metrics and uncertainty; no commands claiming official authority |

## 6. Non-functional requirements (NFR)
- **Reproducibility:** preserve input checksums, dataset revisions, parameters, code revision, timestamps; identical versioned inputs yield numerically consistent results within floating-point tolerance.
- **Data integrity:** never turn NoData into zero exposure. Keep `unknown` separate from `0`.
- **Geospatial precision:** use projected appropriate CRS / geodesic measures for area and length; record methods; avoid raw lat/lon degree-based area.
- **Robustness:** handle empty polygons, multipolygons, invalid rings, antimeridian issues, partial coverage, non-overlap and API failures.
- **Security:** validate remote file sizes/types, avoid untrusted pickle/executable data, restrict URL schemes/hosts by deployment policy, set timeout/retry limits.
- **Performance targets (engineering acceptance targets, NOT measured):** complete a 100 km² AOI using cached raster/vector inputs in ≤ 120 s on the agreed reference machine; memory ≤ 4 GiB. Benchmark later in T09 and revise targets if necessary.
- **Explainability:** every reported indicator states units, algorithm, threshold version and caveat.
- **Source compliance:** attribute OpenStreetMap contributors / ODbL; WorldPop CC BY 4.0 as applicable; check license per exact dataset.

## 7. Output contract (proposed)
```json
{
  "event_id": "<real-event-id>",
  "hazard_type": "flood",
  "status": "SUCCESS|PARTIAL|INSUFFICIENT_DATA|INSUFFICIENT_EVIDENCE|FAILED",
  "metrics": {
    "affected_area_km2": null,
    "population_potentially_exposed_estimate": null,
    "mapped_buildings_intersecting": null,
    "mapped_critical_facilities_intersecting": null,
    "mapped_roads_exposed_km": null
  },
  "risk": {"screening_tier": null, "method_version": "v0.1", "validated": false},
  "confidence": {"classification_quality": "unknown", "population_estimate_uncertainty": "not_quantified"},
  "coverage": {"population_fraction": null, "osm_coverage_assessment": "unknown"},
  "provenance": {"m2_processing_version": null, "inputs": [], "reference_data": []},
  "flags": [],
  "artifacts": {"hazard_geojson_uri": null, "exposure_geojson_uri": null},
  "generated_at_utc": null
}
```
*All `null` fields mean unavailable/not calculated, never zero.* Example above is a **schema illustration**, not measured satellite output.

## 8. Engineering decisions required before implementation
1. M2 confirms output mask semantics and whether flood/fire classification is genuinely validated, not generic change.
2. Team selects an actual AOI, event interval, real scene IDs and legally reusable supporting datasets.
3. Team chooses a single official administrative boundary source and a population year aligned to event date (or reports mismatch).
4. Define minimum coverage criteria and review whether screening-tier thresholds have external validation.
5. M3 and dashboard/backend owners ratify JSON paths and file storage convention.

## 9. Phase-1 T01 definition of done
- [x] Requirements and preliminary input/output contract written.
- [x] Real-source plan and key licensing/limitations stated.
- [x] Acceptance tests and explicit exclusions defined.
- [ ] M2 signs off on the interface contract.
- [ ] Real AOI/event and data vintage chosen by team.
- [ ] Scientific review of chosen indicators / thresholds.

**T01 document drafting complete; integration sign-off pending.** No code implementation or real event analysis is implied.

## 10. Primary references
- NASA ARSET, *Measuring Floods, Subsidence, and Sea Ice with SAR*, flood-mapping limitations: https://disasters.nasa.gov/sites/default/files/2023-11/SAR_Part3.pdf
- WorldPop data catalog: https://hub.worldpop.org/project/categories?id=3
- WorldPop v3 API & methodology: https://api.worldpop.org/v3/documentation
- OpenStreetMap license: https://www.openstreetmap.org/copyright
- Overpass API usage/constraints: https://wiki.openstreetmap.org/wiki/Overpass_API
- Copernicus EMS access: https://emergency.copernicus.eu/data/
