# SPECTRA-SAR — M2 AI & Scientific Requirements

**Workstream:** Member 2 — AI & Scientific Intelligence  
**Phase:** 01 / 09 — AI & Scientific Intelligence Foundation  
**Task:** T01 — AI & Scientific Requirements  
**Status:** Specification drafted; implementation and real-scene acceptance tests pending  
**Version:** 1.0 | **Date:** 2026-11-13

## 1. Purpose
Build a scientifically defensible, reproducible radar-backscatter change detection engine that consumes **real, calibrated, georeferenced Sentinel-1 imagery** supplied by M1 and exports geospatial changes, per-pixel uncertainty, provenance and interpretable evidence for M3's impact assessment. This document defines requirements; it does not claim a trained or validated model.

## 2. Scope and non-goals

### In scope for Phase 1
- Validate M1 imagery, masks, metadata, and acquisition comparability.
- Assess alignment, perform optional corrective co-registration, and flag unusable pairs.
- Apply configurable speckle filtering when appropriate; preserve unfiltered inputs.
- Compute interpretable baseline change scores and thresholded change maps.
- Produce georeferenced masks, summary statistics, and machine-readable quality/confidence indicators.
- Evaluate changes on *real* imagery and record all model parameters and limitations.

### Explicitly outside Phase 1 guarantees
- No unverified claim of detecting *floods, fires, glacier motion, and subsidence* with one generic amplitude-difference classifier.
- No promise that amplitude change alone proves cause, direction of physical movement or ground subsidence. Glacier velocity generally needs feature/offset tracking or InSAR methods; precise subsidence generally needs phase-preserving SLC/InSAR time-series processing, which **cannot** be recovered from GRD/RTC amplitude images.
- No claim that any neural classifier is trained, calibrated, or deployable without labeled real data and independent validation.

## 3. Data policy and science assumptions
- **Real-world observation only** for demonstrated results: ESA/Copernicus Sentinel-1 scene IDs or documented, derived RTC products. Synthetic fixtures are allowed only for isolated unit tests, never as substitute evidence in demo results.
- Primary product: M1-supplied geocoded **RTC backscatter**, preferably linear-power gamma0 terrain (for example, ASF RTC or equivalent), with valid masks and provenance. Calibrated, terrain-corrected sigma0 is an alternate path if consistently used for both dates. Never silently mix gamma0 and sigma0.
- Current baseline supported polarization: `VV`, optional `VH` when both acquisitions have it. Extensions to HH/HV require explicit validation.
- Prefer comparable acquisition geometry: same relative orbit/track, orbit direction, acquisition mode and polarization. Incidence-angle difference target ≤2° is a **project screening heuristic**, not a universal Sentinel-1 physics rule; flag exceptions for review rather than inventing automatic scientific equivalence.
- Each before/after pair must be aligned on the same CRS, affine transform, pixel size, bounds and valid-pixel intersection. Image dimensions alone do not establish coregistration.
- Input must explicitly identify backscatter units (`linear_power` or `dB`), coefficient (`gamma0_terrain`, `sigma0`, etc.), whether prior denoising/filtering was applied, and any layover/shadow mask.

## 4. Actors and integration boundaries
- **M1 (producer):** supplies preprocessed real scenes, acquisition/source manifests, masks, metadata, and reproducible processing provenance. M1 owns download, calibration and terrain correction.
- **M2 (this workstream):** validates, filters, compares, scores, evaluates, and packages results. M2 must not re-run RTC blindly or pretend M1 already coregistered dates.
- **M3 (consumer):** combines change products with exposure/population/infrastructure layers and builds decision-support products. M3 must not treat `change_probability` or `confidence` as a causal or damage estimate.

## 5. Functional requirements

| ID | Priority | Requirement | Testable acceptance condition |
|---|---|---|---|
| FR-01 | MUST | Ingest real M1 rasters and scene manifest | Input parses and source/acquisition IDs are retained |
| FR-02 | MUST | Validate metadata and pair comparability | Missing/contradictory units, polarization, CRS or source IDs fail with actionable reason |
| FR-03 | MUST | Read geospatial arrays with nodata/valid masks | No invalid pixel enters statistics or output valid region |
| FR-04 | MUST | Verify alignment and spatial overlap | Grid equality and overlap recorded; mismatches rejected or explicitly reprojected with a logged method |
| FR-05 | MUST | Speckle filtering option | Baseline identity and Lee-type filter supported; parameters/provenance saved |
| FR-06 | MUST | Compute interpretable change scores | dB difference and symmetric absolute change are available for matched polarization |
| FR-07 | MUST | Produce thresholded candidate-change mask | Threshold, direction, valid-pixel count and change area recorded |
| FR-08 | MUST | Provide uncertainty/quality layers | Validity + quality flags and confidence semantics explicitly documented |
| FR-09 | MUST | Export geo-aligned outputs | GeoTIFF/COG-compatible rasters preserve CRS, transform, nodata, bounds |
| FR-10 | MUST | Export machine-readable summary for M3 | JSON schema with dates, source IDs, areas, reliability flags, parameters and file URIs |
| FR-11 | MUST | Repeatable runs | Same input and settings yield identical baseline outputs within numerical tolerance |
| FR-12 | MUST | No false causal claims | Outputs labeled `candidate_backscatter_change`, not confirmed wildfire/flood/subsidence |
| FR-13 | SHOULD | Flood-specific mapping module | On appropriate reference sites, use contextual water/backscatter logic with known caveats |
| FR-14 | SHOULD | Ground-truth evaluation | Precision/recall/F1/IoU computed only where trustworthy annotations exist |
| FR-15 | SHOULD | Optional supervised model | Training/inference code and real dataset/model card required before enabling production predictions |

## 6. Non-functional requirements
- **Scientific integrity:** Never conflate detection confidence, geolocation accuracy, causal attribution and actual hazard probability. Explicitly state absence of validation.
- **Provenance:** Record scene IDs, acquisition UTC timestamps, data provider, processing chain, coefficient/units, orbit metadata, resolution, filter, threshold and code/model version.
- **Safety of decisions:** M3 outputs must be labeled decision-support, not authoritative emergency advisories; high-risk regions require expert review.
- **Robustness:** Fail closed with structured errors for incompatible geometry/metadata; do not auto-cast all zeros to valid data.
- **Scalability:** Windowed/chunked raster processing (not loading giant scenes blindly); deterministic baseline. Performance benchmarks measured on actual available hardware, not claimed in advance.
- **Security:** Treat imagery/metadata as untrusted inputs; enforce limits on raster dimensions, path handling, archive expansion and remote URI schemes.
- **Observability:** JSON logging of stage, input IDs, warnings, elapsed time, input/output checksums.

## 7. M1 → M2 proposed input contract (to agree with M1)
```json
{
  "pair_id": "<stable-id>",
  "source": "Sentinel-1",
  "before": {
    "scene_id": "<real scene or derived-product identifier>",
    "acquired_utc": "<ISO-8601 UTC>",
    "raster_by_pol": {"VV": "<local-or-managed-uri-to-geotiff>", "VH": "<optional-uri>"},
    "valid_mask_uri": "<uri>",
    "quality_mask_uri": "<optional-uri>"
  },
  "after": {
    "scene_id": "<real scene or derived-product identifier>",
    "acquired_utc": "<ISO-8601 UTC>",
    "raster_by_pol": {"VV": "<uri>", "VH": "<optional-uri>"},
    "valid_mask_uri": "<uri>",
    "quality_mask_uri": "<optional-uri>"
  },
  "common": {
    "backscatter_coefficient": "gamma0_terrain",
    "units": "linear_power",
    "orbit_direction": "ASCENDING",
    "relative_orbit": "<integer or null>",
    "instrument_mode": "IW",
    "crs": "<EPSG code or WKT>",
    "pixel_size_m": "<nominal pixel spacing; exact resolution is distinct>",
    "preprocessing": {
      "radiometric_calibration": true,
      "terrain_correction": true,
      "speckle_filter_applied": false,
      "processor": "<name/version>"
    }
  }
}
```
**Contract rules:** Values in angle brackets are placeholders, not fabricated metadata. Orbit and look-geometry differences belong to per-scene metadata when differing; actual implementation should store these per-scene, with pairwise comparison performed by validation. Raster geotransforms are read from GeoTIFF and compared rather than trusting JSON strings. `pixel_size_m` must not be used as a meter value for geographic CRS. Require a projected CRS when computing area directly from pixels, or use geodesic computation.

## 8. M2 → M3 proposed output contract
```json
{
  "pair_id": "<stable-id>",
  "product_type": "candidate_backscatter_change",
  "input_scene_ids": ["<before-id>", "<after-id>"],
  "change_score_uri": "<GeoTIFF URI>",
  "change_mask_uri": "<GeoTIFF URI>",
  "valid_mask_uri": "<GeoTIFF URI>",
  "quality_flags_uri": "<GeoTIFF URI>",
  "confidence_uri": null,
  "confidence_kind": "not_calibrated",
  "change_area_km2": null,
  "algorithm": {"name": "db_difference_threshold", "version": "<version>", "parameters": {}},
  "evaluation": {"ground_truth_available": false, "metrics": null},
  "warnings": ["Candidate radar change does not uniquely identify an event type"],
  "provenance_uri": "<JSON URI>"
}
```
`confidence_uri` stays null until a properly defined and assessed confidence estimate exists. `change_area_km2` is populated only after area is computed using valid georeferencing.

## 9. Verification and sign-off plan
1. Obtain at least one **real paired Sentinel-1 observation** with disclosed IDs, dates, masks, and processing history from M1; no stock photos, fabricated imagery or unexplained arrays.
2. Confirm both rasters represent the same coefficient/units and comparable geometry; assess alignment and common valid region.
3. Run identity + speckle filter variants and retain before/after images using identical rendering stretch. Inspect preservation of edges and water boundaries.
4. Run baseline change detection; inspect change histogram and independently check spatial locations against supporting event evidence.
5. Export GeoTIFF and JSON, load in GIS, verify correct orientation/extent, valid masks, coordinate reference system, and integration with M3.
6. Where independent labels exist, calculate precision/recall/F1/IoU with spatial separation of evaluation data. Otherwise mark evaluation `unavailable` and do not invent performance scores.
7. Record exact parameters and limitations in a run report, then obtain M1/M3 interface sign-off.

## 10. Definition of Done — T01
- [x] Document scientific scope, interfaces, and functional requirements.
- [x] State data validity, processing, and evidence standards.
- [x] Define proposed acceptance criteria and evaluation principles.
- [ ] M1 confirms input contract and delivers identified real samples.
- [ ] M3 confirms output contract.
- [ ] Phase-1 real-scene run demonstrates compliance (later tasks T02–T09).

**T01 document preparation is complete. T01 cross-team sign-off is pending; the full Phase 1 is not complete.**

## References
- Copernicus Sentinel-1 data and processing: https://documentation.dataspace.copernicus.eu/Data/Sentinel1.html
- Copernicus Sentinel-1 GRD processing and band semantics: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html
- ASF HyP3 Sentinel-1 RTC Product Guide: https://hyp3-docs.asf.alaska.edu/hyp3-docs/guides/rtc_product_guide/


## Integration contract decision (v1.1)
The team integration baseline is defined in `interface-contract-v1.md` and illustrated by `manifest-template.json`. It selects Sentinel-1 IW RTC terrain gamma0 in linear power, Float32 GeoTIFF, VV mandatory with optional paired VH, UTM shared grids, real scene provenance, explicit masks and a georeferenced M2→M3 output contract. These are design decisions awaiting implementation and three-member interface sign-off; they do not assert that real scenes have been processed or science validated.
