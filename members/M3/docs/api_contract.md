# M3 integration contract (Phase 1)

## Inputs
- AOI GeoJSON polygon, OSM GeoJSON feature collection with tags, WorldPop GeoTIFF with explicit **population unit**, M2 georeferenced change mask *polygon* GeoJSON.
- M2 must supply source provenance and validated georeferencing. Change polygons are **not automatically confirmed disaster zones**.
- `config.json`: `aoi`, `osm`, `population`, `hazard` absolute or relative-to-process working directory paths; `hazard_provenance`, `population_provenance`, `population_unit` mandatory. Optional `source_manifest`, `approve_qa_warning` (requires documented analyst signoff), `hazard_type` (`unknown` default), `evidence_status` (`UNVERIFIED` default), `sar_confidence` (null by default).
- M3 cannot infer radiometric SAR classification from geospatial overlap. The M2→M3 interface must provide event metadata and independent verification.

## Output
`run_manifest.json` with SHA-256 digests plus seven files: `qa_report.json`, `spatial_metrics.json`, `clipped_hazard.geojson`, `exposure_metrics.json`, `risk_assessment.json`, `impact_statistics.json`, `decision_recommendations.json`.

All stage JSON objects require `schema_version = 1.0.0` and `module = SPECTRA-SAR/M3/T0x`. No scores if `REVIEW_REQUIRED`. Client must display provenance, status, QA messages and scientific limitations alongside statistics.

## Security and operational boundaries
- Input sizes, server-side rate limits, authentication, path sandboxing, authorization and quarantine must be implemented at the platform API layer. This local CLI accepts trusted operator-controlled paths; **do not expose directly to arbitrary user-supplied paths**.
- Model outputs are screening guidance, not medical/emergency or evacuation instructions.
- Need field-validation against external disaster products before release.
