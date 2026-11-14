# SPECTRA-SAR · M5 T11 — Cross-module integration contracts

**Version:** `0.1.0-draft` · **Owner:** M5 · **Status:** PROPOSED, not signed off by M1–M4/M6.

This document describes **implemented M5 interfaces as of T10**, then lists items that still need agreement or engineering work. No satellite data has been fabricated or claimed to be processed. `contracts/generated/` is produced from the actual FastAPI app and Pydantic classes with `python scripts/export_contracts.py`.

## A. Non-negotiable conventions

- Base API path `/api/v1`; JSON UTF-8, except file uploads use multipart/form-data. IDs are UUID strings; timestamps timezone-aware ISO 8601.
- Geospatial vector coordinates **WGS 84 / EPSG:4326**: GeoJSON coordinates `[longitude, latitude]`. Raster pixel georeferencing may differ and **must include native raster CRS/transform and NoData metadata**. No silent reprojection.
- File content is stored in private S3/MinIO; database stores stable references, metadata and SHA-256 (if supplied). Upload validates file format and size; do not treat the extension alone as evidence of authenticity.
- The client must preserve provider identifiers, STAC asset links, observation period, polarization, orbit, processing algorithm/version, scene pair and source data references. Never generate measured area, population count, model confidence or risk category without running the respective scientific module.
- Requests to `/resources`, `/storage`, `/geospatial`, `/processing-jobs` require internal `X-API-Key` in the current implementation. **Do not embed this secret in M4's browser code.** Browser endpoints in `/auth` use bearer JWT and have limited project-scoped read functionality.
- `X-Request-ID` may be sent for tracing; replies echo a sanitized ID. `400/422` invalid request; `401` missing credentials; `403` forbidden role (on user endpoints); `404` not found; `409` conflicting state/reference; `503` dependency unavailable. The exact behavior varies by route, so generated OpenAPI is normative for present HTTP routes.

## B. Integration boundaries

### M1 → M5: data ingestion and scientific gate

1. M1 supplies real STAC Feature metadata for each Sentinel-1 observation; use `SarSceneCreate` (`contracts/generated/m1_sar_scene.schema.json`). `provider_item_id` must match `stac_item.id`, and STAC must have provider asset links. Persist via `POST /resources/scenes`.
2. M1 identifies an AOI and selects distinct before/after observation IDs with scientific quality gates; `ScenePairCreate` includes `validation_status` (`pending/pass/warning/reject`) and `validation_report`. Persist via `POST /resources/scene-pairs`.
3. Upload calibrated/preprocessed raster as `POST /storage/artifacts/upload` with actual bytes and metadata. `ArtifactCreate` represents an already stored object (not the file bytes).
4. **Before accepting M1:** get a *real* sample STAC item, a raster path + checksum, native CRS, polarization, orbit direction/relative orbit, incidence angles, calibration stage and actual pair-quality decisions.

### M2 → M5: change-detection evidence

1. M2 works from M1's validated pair and records its run under `ProcessingJobCreate` (`job_type=change_detection`), with a stable idempotency key chosen by caller.
2. Save change mask (and optional confidence map) as artifacts, then submit `ChangeResultCreate` with `job_id`, `scene_pair_id`, `change_mask_artifact_id`, optional `confidence_artifact_id`, `changed_area_m2`, `mean_confidence ∈ [0,1]`, `algorithm`, `algorithm_version`, and evaluation metrics. `POST /resources/change-results`.
3. Units, CRS, NoData, mask encoding, uncertainty calibration, threshold selection, and evaluation dataset details must be delivered by M2. Never infer `changed_area_m2` from non-georeferenced pixel counts.
4. Current Celery handler registry has **no real M2 handler registered**; enqueuing a job is *not proof* of analysis.

### M3 → M5: impact assessment

1. M3 takes an existing `change_result_id`, references its sources, and submits `ImpactAssessmentCreate`: `assessment_type`, optional `risk_level`, `affected_area` GeoJSON, `population_estimate`, and **methods_and_sources**. `POST /resources/impact-assessments`.
2. M3 defines defensible risk thresholds, geospatial overlay resolution, exposure layers, uncertainty and attribution. Population or risk values may be absent until justified by datasets.
3. M5 supports internal `GET /geospatial/impacts/within?project_id=...&bbox=minLon,minLat,maxLon,maxLat`; bbox must be WGS84, within +/-180 longitude and +/-90 latitude, with min less than max. Antimeridian-crossing AOIs require split queries.

### M4 ↔ M5: UI and interactive maps (owner confirmation needed)

- **Currently browser-safe:** `POST /auth/login`, `GET /auth/me`, `GET /auth/projects/{project_id}/artifacts`, `GET /auth/projects/{project_id}/jobs`. These require bearer JWT except login.
- **Not browser-safe:** all internal service-key endpoints listed above, including storage presigned-URL endpoint and geometry queries. Backend must first implement project-scoped JWT endpoints for map geometries, download authorization, uploads, actions and user-visible errors; M4 must not call internal APIs directly.
- M4 should send the team its actual pages, required filters, expected mapping libraries, allowed user roles and download/visualization needs. Nothing in T11 implies those missing public APIs already exist.

### M6 ↔ M5: Security / DevOps (owner confirmation needed)

- Provide server-side secret storage and rotation for `X-API-Key`, JWT signing secret, DB/MinIO/Redis access; enforce TLS and private networks. Do not commit real secrets or publicly expose MinIO internal addresses.
- Startup ordering: PostGIS → migrations → API; Redis/MinIO + Celery workers must be healthy separately. Check `/health/live` and `/health/ready`; readiness is not proof scientific processors are configured.
- Establish DB backup/restore, object reconciliation, observability, audit trace, queue retry/dead-letter policy, deployment rollout and RBAC threat model. Validate reproducible container deployment and integration tests on real infrastructure.

## C. Suggested end-to-end processing sequence (not executed yet)

1. **M1** retrieves/validates real Sentinel-1 source data and provides STAC references; M5 persists scenes and artifacts.
2. **M1** submits approved scene pair; if `reject`, processing must not proceed. **Currently this gate is a policy requirement and not fully enforced by the job endpoints.**
3. M5 creates `preprocess`/`denoise`/`change_detection`/`impact_assessment` jobs with references. Dispatch via `/processing-jobs/{id}/dispatch` only when scientific Celery handlers have been registered.
4. **M2** processes valid imagery and publishes verifiable change mask + provenance; M5 stores artifact references and change result.
5. **M3** intersects change evidence with defensible geographic/exposure layers and publishes impact assessment with sources.
6. **M4** views data exclusively through JWT/project-scoped APIs **once they are built**; do not route browser requests through internal service-key endpoints.

## D. Authentication matrix

| Interface | Caller | Current auth | Deployment suitability |
|---|---|---|---|
| `/api/v1/resources/*` | M1/M2/M3 backend services | `X-API-Key` | Internal trusted network only |
| `/api/v1/storage/*` | Backend services | `X-API-Key` | Internal only, file and URL access must be audited |
| `/api/v1/processing-jobs/*` | Backend worker/orchestrator | `X-API-Key` | Internal only |
| `/api/v1/geospatial/*` | Backend services | `X-API-Key` | Internal only; not tenant-scoped for browsers |
| `/api/v1/auth/login` | User / browser | Credentials | Needs rate limiting, TLS and session/refresh policy before production |
| `/api/v1/auth/me` and `/auth/projects/*` | User / browser | Bearer JWT + RBAC | Limited read APIs only |

## E. Contract acceptance checklist

- [ ] M1 supplies real provider STAC Feature, raw/calibrated raster with CRS and metadata, and scene pair scientific validation.
- [ ] M2 supplies mask sample, nodata definition, confidence scale, actual algorithm/version, metrics and raster provenance.
- [ ] M3 supplies real geospatial impact sample, authoritative source layers and risk threshold definitions.
- [ ] M4 confirms UI owner and pages, and agrees never to expose internal service credentials.
- [ ] M6 confirms infrastructure owner and completes credential lifecycle, TLS, recovery, queue monitoring and backup approach.
- [ ] M5 implements project-scoped user endpoints for maps/actions/download and enforces inter-module compatibility and pair admission.
- [ ] Full Docker/PostGIS/MinIO/Redis/Celery integration tests pass with **real** scenes and outputs; no synthetic data used as evidence of science correctness.

## F. Contract change process

- `contract_version` follows semver after first team signoff. Breaking API changes increment major version; additive optional fields increment minor; documentation corrections increment patch.
- Each owner should share a real redacted sample, schema version, changelog, failure cases and test fixture with provenance. Do not copy provider access tokens into fixtures.
- `contracts/generated/` are generated read-only artifacts; update Pydantic models or FastAPI route definitions, then run `python scripts/export_contracts.py` and `pytest tests/test_t11_contracts.py`.
