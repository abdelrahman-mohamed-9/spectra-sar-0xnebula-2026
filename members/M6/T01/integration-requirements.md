# SPECTRA-SAR — System Integration Requirements

**Project:** NASA Space Apps — Dancing with the SARs  
**Owner:** Member 6 (System Integration, QA & Technical Documentation)  
**Phase:** 1 of 9 — Foundation  
**Task:** T01 — System Integration Requirements  
**Version:** 0.1 (proposed baseline; requires team approval)  
**Date:** 2026-11-13

## 1. Goal and scope

Define a **testable, implementation-neutral integration baseline** for the first working end-to-end vertical slice of SPECTRA-SAR. The intended flow is authentic SAR scenes → validated/preprocessed, co-registered SAR assets → defensible change-detection results → geospatial impact summaries → backend API → frontend presentation, with traceable provenance and QA throughout.

**T01 does not implement** an API, a database, a scientific algorithm, or actual integration. It defines agreements needed before M4/M6 begin building and testing them.

### Components and owners

| Member | Responsibility | Primary handoff |
|---|---|---|
| M1 | SAR Data Acquisition & Processing | validated, calibrated/normalized where appropriate, co-registered raster pair and metadata |
| M2 | AI & Scientific Intelligence | change raster, confidence/quality indicators, method and evaluation provenance |
| M3 | Geospatial Impact & Decision Intelligence | vector/raster impact layer, zonal statistics, qualified recommendations |
| M4 | Backend & API | job management, persistence, authenticated API, orchestration |
| M5 | Frontend & Visualization | map views, job status, results, transparent limitations |
| M6 | Integration, QA & Documentation | cross-service contracts, conformance tests, provenance checks, release evidence |

> M4 owns implementation of backend/database unless the team explicitly delegates otherwise. M6 defines integration tests and quality gates, not a competing backend.

## 2. Integration principles

1. **Real data only for factual demonstrations.** Input scenes must resolve to actual downloaded SAR acquisitions from an identifiable provider, with acquisition time, product ID, footprint, processing level, and license/access terms. Synthetic fixtures may be used **only in unit tests**, explicitly labeled `synthetic_test_fixture`; no fabricated events or accuracy claims.
2. **Scientific comparability first.** Any two-scene comparison must run M1 validation: footprint overlap, appropriate product types, compatible polarization, ascending/descending orbit direction, incidence-angle compatibility, and spatial alignment. The previously discussed 2° incidence difference is a **project screening heuristic**, not a universal scientific guarantee; M1 must document/validate it. Ground-range/terrain correction, radiometric handling, nodata and geometries must be documented.
3. **Source imagery never silently altered.** Preserve a traceable source reference and immutable checksum. Preprocessed assets must record transformations and their parameters.
4. **All measurements carry units and geometry.** CRS, pixel size, raster dimensions, bounding box, mask/nodata conventions, and acquisition dates must survive every handoff.
5. **Artifact exchange, not giant JSON payloads.** Large rasters and vectors live in object/file storage; JSON contains references and metadata. URLs must be access-controlled or short-lived as appropriate.
6. **No false precision.** Confidence scores, if produced, must be identified as calibrated probabilities or uncalibrated model scores; uncertainty/quality warnings are displayed and propagated.
7. **Security by default.** Validate URLs and supplied paths, prevent SSRF/path traversal, protect credentials, scope storage reads/writes, log access without leaking secrets, and apply request limits.
8. **Reproducibility.** Record pipeline version, code commit, algorithm parameters, environment and unique run identifiers.
9. **Versioned contracts.** JSON payloads include `schema_version`; breaking changes require team review and version increment.
10. **Fail clearly.** Failures return machine-readable codes and human-readable explanations; downstream stages must not process rejected inputs.

## 3. Functional requirements (acceptance criteria)

| ID | Priority | Requirement | How M6 verifies |
|---|---|---|---|
| INT-001 | Must | Create a `run_id` for each analysis run; link each stage's inputs/outputs | Correlate one run across metadata and logs |
| INT-002 | Must | Ingest two authentic SAR scene records with immutable scene IDs and acquisition timestamps | Assert source provenance is present and non-fixture in demo |
| INT-003 | Must | Check scene compatibility prior to running M2 | Deliberate mismatch produces `REJECT` and stops job |
| INT-004 | Must | Supply co-registered rasters and validity mask, consistent CRS/grid | Compare width, height, transform, CRS, valid masks |
| INT-005 | Must | M2 returns an interpretable change product with threshold/method information | Validate output file, shape/grid, metadata |
| INT-006 | Must | M2 preserves legitimate change and reports uncertainty/quality limits | Inspect metrics and report warnings; no unjustified accuracy claim |
| INT-007 | Must | M3 measures impact only for available trustworthy overlays | Verify overlays' source/date and `not_assessed` for absent layers |
| INT-008 | Must | Backend tracks `QUEUED`, `RUNNING`, `SUCCEEDED`, `FAILED`, `REJECTED` | Query state transitions and terminal error payload |
| INT-009 | Must | Frontend displays acquisition dates, geographic area, legend and limitations | Manual UI acceptance test |
| INT-010 | Must | Each artifact has content hash, producing stage, storage reference and algorithm/version | Cross-check manifest and selected file hashes |
| INT-011 | Must | All handoffs validate against the same versioned schema | Schema tests reject missing/wrong fields |
| INT-012 | Must | One end-to-end demonstration operates on at least one real, properly compatible scene pair | Record runnable steps, scene IDs and verified outputs |
| INT-013 | Must | API protects restricted endpoints and rejects invalid paths/URLs | Auth, unauthorized-access and malicious-input tests |
| INT-014 | Should | Asynchronous jobs expose stage-level progress and recovery hints | Simulate stage failure and inspect status |
| INT-015 | Should | M5 provides export with the run's lineage/limitations | Inspect export contents |
| INT-016 | Should | Repeat analysis with same inputs/config yields comparable outputs within documented numerical tolerance | Re-run and compare output statistics |

## 4. Non-functional requirements

| ID | Requirement | Phase-1 gate |
|---|---|---|
| NFR-001 | Operability | Documented local start/stop procedure and readiness checks for each implemented service |
| NFR-002 | Interoperability | GeoTIFF/COG preferred for rasters; GeoJSON or GeoPackage for vector outputs; JSON over HTTP for control plane |
| NFR-003 | Observability | Structured event fields include `run_id`, `stage`, `timestamp`, `status`, `duration_ms`, `error_code` where applicable |
| NFR-004 | Data integrity | SHA-256 validated at storage write and during QA sampling |
| NFR-005 | Security | No secrets committed; least-privilege storage access; JWT/session protection where applicable; dependency pinning |
| NFR-006 | Resource bounds | Document CPU/RAM/disk demand and enforce input size/job limits; performance targets **TBD after measured real-data pilot** |
| NFR-007 | Auditability | Source attribution, processing parameters, and versions in a downloadable manifest |
| NFR-008 | Accessibility | Human-readable failure messages and legend; avoid a color-only explanation of change |
| NFR-009 | Scientific integrity | No claim of validated flood/fire/glacier/subsidence detection without event-specific data and ground truth or qualified reference labels |

## 5. Proposed architecture and data flow

```text
Real SAR provider → M1 scene catalog/download/validation/preprocessing
                  → asset store (aligned raster A, B + masks + manifest)
                  → M2 noise filtering / change detection / uncertainty
                  → asset store (change layer + quality metadata)
                  → M3 overlay-based impact assessment
                  → asset store (impact layers + summary + caveats)
                  → M4 orchestrator / database / REST API
                  → M5 map + dashboard
                            ↑
                  M6 contract & QA checks across each boundary
```

Suggested MVP strategy: file/object-based handoffs and a thin API; do not block Phase 1 on Kubernetes or advanced microservices.

## 6. Integration decisions required

| Decision | Suggested starting value | Owner | Status |
|---|---|---|---|
| SAR sensor/product | Sentinel-1 GRD for a first amplitude-change MVP; SLC required for interferometric deformation | M1/M2 | OPEN |
| Target geography / event | Select a documented AOI with multiple suitable acquisitions | Whole team | OPEN |
| Raster layout | GeoTIFF (prefer COG), EPSG metadata, aligned grids and masks | M1/M2 | PROPOSED |
| Scientific measurement | Backscatter change for GRD; avoid calling it true ground displacement | M1/M2 | PROPOSED |
| Storage mechanism | Local mounted volumes for development; object storage later | M4/M6 | OPEN |
| Backend API stack | To be chosen by M4; OpenAPI specification is language-agnostic | M4 | OPEN |
| Workflow orchestration | Async run ID + stage state machine | M4/M6 | PROPOSED |
| Impact overlays | Source, collection timestamp and coverage per layer required | M3 | PROPOSED |
| Auth / user roles | Public demo vs team-private decisions | M4/M5 | OPEN |
| Performance budgets | Measure after first real pair; no invented target | M6 | OPEN |

### Scientific caution

GRD amplitude imagery can reveal scattering/backscatter changes that *may correlate* with flooding, burns, surface or vegetation changes. It **cannot by itself establish glacier velocity or precise land subsidence**. Those require appropriate multi-temporal tracking or interferometric techniques, suitable SAR products, co-registration, orbit/geometry checks, and validation. UI wording must match the actual method used.

## 7. Stage acceptance gates

- **Gate A — M1→M2:** `PASS` scene pair; source IDs; authentic acquisition dates; CRS; matching grid/transform; valid pixels; asset checksums; explicit preprocessing history.
- **Gate B — M2→M3:** change product exists; compatible spatial grid; method and threshold; confidence semantics; quality metrics; nodata correctly propagated.
- **Gate C — M3→M4:** region/overlay provenance; impact metrics with units; affected-area basis; `not_assessed` for unsupported impact claims; geometries valid.
- **Gate D — M4→M5:** stable JSON envelope; correct status/error handling; accessible asset URLs or tiles; no secret values in response.
- **Gate E — Demo release:** one authentic scene pair flows through implemented stages, with screenshots/logs and a reproducibility manifest. Unimplemented stages must be shown as unavailable, not simulated results.

## 8. Definition of Done for T01

- [x] Written scope, ownership and boundaries
- [x] Initial functional/non-functional requirement IDs and test criteria
- [x] Proposed handoff formats and quality gates
- [x] Scientific data authenticity and uncertainty safeguards
- [x] Preliminary interface definitions (see `system-interfaces.md`)
- [ ] M1–M5 review and approve their boundary contracts
- [ ] M4 approves endpoint names, persistence, and auth architecture
- [ ] Select actual scene IDs / AOI and validate real data availability
- [ ] Lock schema v1 after review; publish approval record

**T01 status:** Documentation draft complete; **NOT team-approved**, not implemented or integration-tested.
