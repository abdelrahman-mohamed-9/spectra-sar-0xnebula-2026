# SPECTRA-SAR — System Interfaces & Handoff Contracts

**Owner:** M6 · **Phase:** 1/9 · **Task:** T01  
**Version:** 0.1 — Proposed contracts, not implemented endpoints  
**Date:** 2026-11-13

## 1. Contract conventions

These structures are **illustrative protocol proposals**, awaiting M1–M5 approval. They are not assertions that named services/files or live endpoints exist.

- `schema_version`: SemVer-compatible string (`0.1.0` for draft samples).
- `run_id`: unique UUID (or equivalent opaque ID), shared by all stages.
- All datetimes: UTC ISO-8601, e.g. `2026-01-01T00:00:00Z` (examples below are **not real observations**).
- Coordinates: store CRS as e.g. `EPSG:32633`; specify bbox coordinate order and CRS explicitly. For JSON geographic geometry, follow GeoJSON WGS84 `[longitude, latitude]` conventions.
- Raster units: specify linear backscatter vs dB; thresholds must declare unit and method. Never treat `dB` difference as a linear ratio.
- Stored artifacts: internal references such as `s3://...` or `file://...` resolved server-side; avoid exposing internal local paths to browsers.
- Enums: `PASS`, `WARNING`, `REJECT`; jobs `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED`.
- All handoff messages include a producer version and input artifact IDs for lineage.
- Any displayed examples use placeholders, **not real NASA/Sentinel observations or completed analyses**.

## 2. End-to-end contract map

| Interface | Producer → Consumer | Message or artifact | Critical validation |
|---|---|---|---|
| IF-01 | Provider → M1 | authentic scene metadata + SAR product | provider/product identifier, authenticity, timestamps, footprint |
| IF-02 | M1 → M2 | `SarPairReady` and aligned rasters/masks | orbit/polarization/geometry compatible; same grid |
| IF-03 | M2 → M3 | `ChangeResult` and change raster/uncertainty | CRS, dimensions, nodata, confidence semantics |
| IF-04 | M3 → M4 | `ImpactResult` with layers and metrics | source overlays, coverage, units and limitations |
| IF-05 | M4 → M5 | job/result REST resources | stable response schemas and safe URLs |
| IF-06 | All → M6 | `ArtifactManifest`, audit events, QA reports | checksums, run IDs, stage statuses, provenance |
| IF-07 | M4 → M1/M2/M3 | run specification / stage invocation | idempotency, parameters, clear error codes |

## 3. IF-01: Scene discovery and authenticity (Provider → M1)

Required metadata for each scene:

```json
{
  "schema_version": "0.1.0",
  "scene_id": "REAL_PROVIDER_PRODUCT_ID_REQUIRED",
  "provider": "REPLACE_WITH_ACTUAL_PROVIDER",
  "mission": "Sentinel-1",
  "product_type": "GRD",
  "acquired_at": "REPLACE_WITH_ACTUAL_UTC_TIMESTAMP",
  "orbit_direction": "ASCENDING",
  "relative_orbit": null,
  "polarizations": ["VV", "VH"],
  "incidence_angle_degrees": null,
  "footprint_geojson": null,
  "provider_record_url": "REPLACE_WITH_VERIFIABLE_URL",
  "source_license": "VERIFY_PROVIDER_TERMS",
  "raw_asset_id": "REPLACE_WITH_ASSET_ID",
  "sha256": "REPLACE_WITH_64_HEX_DIGITS"
}
```

**Must reject** missing/unknown provenance for a production demonstration. Acquisition dates, orbit details and angle are measured/extracted values, not assumed from examples. On a first MVP, prefer one valid polarization channel with a documented calibration approach.

## 4. IF-02: SAR pair prepared (M1 → M2)

**Control payload:** `SarPairReady` (JSON envelope):

```json
{
  "schema_version": "0.1.0",
  "message_type": "SarPairReady",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "status": "PASS",
  "scene_before_id": "REPLACE_WITH_REAL_SCENE_ID",
  "scene_after_id": "REPLACE_WITH_REAL_SCENE_ID",
  "polarization": "VV",
  "orbit_direction": "ASCENDING",
  "incidence_angle_delta_degrees": null,
  "grid": {
    "crs": "REPLACE_WITH_EPSG_CODE",
    "width": null,
    "height": null,
    "transform": null,
    "pixel_spacing_m": null,
    "nodata": null
  },
  "assets": {
    "before_raster": "ASSET_ID_BEFORE",
    "after_raster": "ASSET_ID_AFTER",
    "validity_mask": "ASSET_ID_MASK"
  },
  "backscatter_representation": "dB",
  "processing_steps": [],
  "warnings": [],
  "producer": {"component": "M1", "version": "REPLACE_WITH_VERSION"}
}
```

**Required rules:**

- Only `PASS`/explicitly accepted `WARNING` pairs proceed to M2; `REJECT` terminates the run.
- `before_raster` and `after_raster` must match in CRS, pixel grid, transform, spatial dimensions, and band semantics; nodata/validity mask declared.
- Acquisition timestamps must be increasing, and product/geometric comparability checks documented by M1.
- No assumption that a visually cleaner despeckled image is scientifically better; M2 verifies preservation of meaningful edges/changes.

## 5. IF-03: Change detection (M2 → M3)

```json
{
  "schema_version": "0.1.0",
  "message_type": "ChangeResult",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "input_pair_artifact_id": "REPLACE_WITH_PAIR_ID",
  "status": "SUCCEEDED",
  "method": {"name": "REPLACE_WITH_REAL_METHOD", "version": "REPLACE_WITH_VERSION", "parameters": {}},
  "change_asset_id": "REPLACE_WITH_GEOREFERENCED_RASTER_ID",
  "validity_mask_asset_id": "REPLACE_WITH_MASK_ID",
  "confidence_asset_id": null,
  "confidence_interpretation": "not_provided",
  "threshold": {"value": null, "units": "REPLACE_WITH_UNITS", "selection_method": "REPLACE_WITH_METHOD"},
  "metrics": {"available_ground_truth": false, "evaluation_notes": "No accuracy claims without reference labels"},
  "warnings": [],
  "producer": {"component": "M2", "version": "REPLACE_WITH_VERSION"}
}
```

**Semantic constraints:** `change_asset_id` must be georeferenced and align to the declared analysis grid. `confidence_interpretation` must distinguish `calibrated_probability`, `uncalibrated_score`, or `not_provided`; confidence must not be invented when absent. An event category like `flood` or `fire` is an **interpretation**, requiring method-specific validation, not a generic SAR change label.

## 6. IF-04: Impact and decision intelligence (M3 → M4)

```json
{
  "schema_version": "0.1.0",
  "message_type": "ImpactResult",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "input_change_artifact_id": "REPLACE_WITH_CHANGE_ID",
  "status": "SUCCEEDED",
  "affected_area": {"value": null, "unit": "km2", "measurement_method": "REPLACE_WITH_METHOD"},
  "overlays": [
    {
      "layer_id": "REPLACE_WITH_REAL_LAYER_ID",
      "purpose": "population_or_infrastructure",
      "provider": "REPLACE_WITH_DATASET_NAME",
      "version_or_date": "REPLACE_WITH_DATE",
      "coverage": "REPLACE_WITH_COVERAGE",
      "license": "REPLACE_WITH_LICENSE"
    }
  ],
  "exposure_metrics": [],
  "impact_geojson_asset_id": null,
  "recommendations": [],
  "limitations": ["Exposure is not equivalent to confirmed damage"],
  "producer": {"component": "M3", "version": "REPLACE_WITH_VERSION"}
}
```

**Rule:** If population/building/road reference data are not available, exposure metric is `not_assessed`; don't replace with made-up figures or zero. Exposure is not observed damage, and recommendations must state assumptions.

## 7. IF-05: Backend/API to frontend (M4 → M5)

Proposed API paths — **not yet built**:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Submit AOI, scene IDs or search constraints and method config; returns `202` and `run_id` |
| `GET` | `/api/v1/runs/{run_id}` | Run status, stage, progress/warnings and error details |
| `GET` | `/api/v1/runs/{run_id}/results` | Result metadata and available layers (only if ready) |
| `GET` | `/api/v1/runs/{run_id}/lineage` | Provenance manifest and method versions |
| `GET` | `/api/v1/assets/{asset_id}` | Authenticated/authorized redirect or metadata for short-lived retrieval |
| `GET` | `/health/ready` | Readiness check; does not reveal secrets |

**Example accepted-job response** (illustrative):

```json
{
  "schema_version": "0.1.0",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "status": "QUEUED",
  "created_at": "REPLACE_WITH_CURRENT_UTC_TIMESTAMP",
  "links": {"self": "/api/v1/runs/REPLACE_WITH_RUN_UUID"}
}
```

**Example error response:**

```json
{
  "schema_version": "0.1.0",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "status": "REJECTED",
  "error": {
    "code": "SAR_PAIR_INCOMPATIBLE",
    "message": "Input scenes cannot be compared under the selected method",
    "details": ["Check acquisition geometry and alignment"]
  }
}
```

Suggested HTTP semantics: `400` malformed parameters, `401` unauthenticated, `403` unauthorized, `404` unknown run, `409` invalid state/conflicting request, `422` valid JSON with scientifically invalid input, `429` rate limiting, `500` unexpected service errors. M4 must make a final, documented choice.

## 8. IF-06: Artifact manifest and observability (All → M6)

Every produced file should have a manifest record:

```json
{
  "schema_version": "0.1.0",
  "artifact_id": "REPLACE_WITH_IMMUTABLE_ID",
  "run_id": "REPLACE_WITH_RUN_UUID",
  "producing_stage": "M2",
  "artifact_type": "change_raster",
  "format": "GeoTIFF",
  "uri": "REPLACE_WITH_INTERNAL_STORAGE_REFERENCE",
  "sha256": "REPLACE_WITH_ACTUAL_SHA256",
  "size_bytes": null,
  "created_at": "REPLACE_WITH_ACTUAL_UTC_TIMESTAMP",
  "source_artifact_ids": ["ASSET_ID_BEFORE", "ASSET_ID_AFTER"],
  "software_version": "REPLACE_WITH_GIT_COMMIT_OR_TAG",
  "algorithm_parameters": {},
  "data_lineage_notes": "REPLACE_WITH_PROCESSING_INFORMATION"
}
```

Minimum structured event fields: `timestamp`, `level`, `run_id`, `stage`, `event`, `status`, `duration_ms` (where applicable), `error_code` (when failed). No tokens, credentials, personal data, or signed URLs in logs.

## 9. IF-07: Orchestration and stage failure protocol

**State flow:** `QUEUED → RUNNING → SUCCEEDED`; at any stage `RUNNING → FAILED`, and science screening may yield `REJECTED`. Terminal states must never be represented as success because an intermediate file exists. Stage retries need explicit maximum attempts; idempotency keys prevent duplicate runs/artifacts.

Errors that QA must test:

| Code | Condition | Expected behavior |
|---|---|---|
| `SOURCE_UNVERIFIED` | Unverifiable scene identity/provider | Reject real-data analysis |
| `SAR_PAIR_INCOMPATIBLE` | Polarization/orbit/geometry not supported | Reject or manual review; don't run M2 automatically |
| `GRID_MISMATCH` | Raster dimensions/CRS/transform differ | Fail handoff before algorithm runs |
| `ASSET_CHECKSUM_MISMATCH` | File modified/corrupt | Quarantine artifact and fail |
| `INPUT_ASSET_MISSING` | Required raster or mask absent | Fail gracefully with missing ID |
| `PROCESSING_FAILED` | Scientific processing exception | Mark stage failed; no fake replacement layer |
| `OVERLAY_UNAVAILABLE` | Impact dataset missing | Mark metric `not_assessed`; show explicit limitation |
| `UNAUTHORIZED_ASSET_ACCESS` | Client not permitted to retrieve | Return 403; log without sensitive content |

## 10. Phase 1 minimum QA contract suite

| Test ID | Handoff | Acceptance condition |
|---|---|---|
| CT-01 | IF-01 | Real scene records have verifiable acquisition identifiers/provenance |
| CT-02 | IF-02 | Aligned raster pair with same grid and valid nodata mask |
| CT-03 | IF-02 | Orbit/polarization incompatibility rejected before change detection |
| CT-04 | IF-03 | Change map and quality metadata conform to schema |
| CT-05 | IF-03 | Uncalibrated confidence not mislabeled as probability |
| CT-06 | IF-04 | Missing overlay does not create fake population/building metrics |
| CT-07 | IF-05 | Pending/failed run handled properly by frontend |
| CT-08 | IF-06 | Artifact hashes and lineage verified end-to-end |
| CT-09 | IF-07 | Broken artifact/read failure yields terminal failed state |
| CT-10 | End-to-end | One actual compatible SAR pair produces documented, reproducible outputs through the **implemented** pipeline |

Contract tests should begin with schema fixtures. A pass for synthetic test fixtures **is not evidence** that the real SAR science pipeline has succeeded.

## 11. Interface review checklist

| Boundary | Approval owner | State |
|---|---|---|
| IF-01 SAR scene fields | M1 | Pending |
| IF-02 raster grid / M1→M2 | M1 + M2 | Pending |
| IF-03 change results / M2→M3 | M2 + M3 | Pending |
| IF-04 impact results / M3→M4 | M3 + M4 | Pending |
| IF-05 API resources / M4→M5 | M4 + M5 | Pending |
| IF-06 artifact manifests / all→M6 | M1–M6 | Pending |
| IF-07 run orchestration / M4→workers | M4 + M1–M3 | Pending |

**Document completion:** draft interface map and acceptance test plan written. **Implementation status:** not built, not connected, not measured. Next, ask each boundary owner to sign off and freeze `schema_version` before developing validators or API.
