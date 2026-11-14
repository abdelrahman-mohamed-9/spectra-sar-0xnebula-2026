# T04 — API Integration Plan

**Project:** SPECTRA-SAR | **Owner:** M6 | **Phase:** 1/9 | **Contract:** 0.1.0 (PROPOSED)

## Status and constraints
This is an implementable OpenAPI **specification**, not running backend code. M4 must approve it and implement routes; M5 must approve response needs; M1–M3 must confirm input/output semantics. Never populate demonstrations with synthetic satellite observations or claim impact figures without real source metadata.

## Responsibility and dependencies

| Producer | Consumer | Interface | Required evidence |
|---|---|---|---|
| M1 | M2 | IF-02 SAR pair handoff | real provider IDs, dates, same CRS/grid, polarization, image checksum |
| M2 | M3 | IF-03 change and uncertainty | georeferenced raster, mask, algorithm/version, valid confidence interpretation |
| M3 | M4 | IF-04 decision/impact | real exposure layer provenance, limitations, area units |
| M4 | M5 | IF-05 REST API (this spec) | 202 + run polling, result gating, auth & permissions |
| All | M6 | IF-06 lineage/QA | artifact SHAs, producer versions, input associations |
| M4 | M1–M3 | IF-07 stage orchestration | idempotent work, retries, errors, observable state |

## Implementation order
1. **M4/M6** approve schema `0.1.0` and map resources to T03 tables.
2. **M4** implement authentication/authorization, `POST /runs` and `GET /runs/{run_id}`; persist state using `processing_runs`, `run_scene_pairs`.
3. **M1** register real scenes from verified providers in `sar_scenes`; reject unverifiable or mismatched scene pairs. `scene_before_id`/`scene_after_id` are *provider IDs*, resolved to DB UUID keys.
4. **M4** orchestrate M1→M2→M3; store retries in `stage_executions` and raster metadata in `artifacts`.
5. **M2/M3** persist scientifically qualified results in `analysis_results`; the API MUST not return `SUCCEEDED` with missing change asset.
6. **M4** serve `GET /results` / `GET /lineage` / `GET /assets`; never expose `storage_uri` or credentials to browser.
7. **M5** integrate frontend using an OpenAPI-generated typed client or manually validated types; avoid assuming background processing is instantaneous.
8. **M6** validate integration on an environment with real M1-derived satellite scenes, record errors and sign-off.

## Explicit mapping to T03

| API field | SQL location | Note |
|---|---|---|
| `run_id`, `status`, `created_at` | `processing_runs.id/status/created_at` | UUID IDs |
| provider scene identifiers | `sar_scenes.provider_scene_id` | `provider + ID` disambiguates |
| scene pair + polarization | `run_scene_pairs` | timestamps and compatibility checked upstream |
| `stage`, producer version | `stage_executions.component/producer_version` | latest active stage, do not guess |
| change asset / confidence | `analysis_results.change_asset_id/confidence_asset_id` | null confidence allowed |
| artifacts / checksums | `artifacts` | checksum computed on bytes |
| input asset lineage | `artifact_inputs` | source provenance cannot be fabricated |
| audit context | `audit_events` | no secrets or raw tokens |

## Decisions requiring owner approval
- Authentication mechanism and JWT issuer/audience, owner/tenant authorization model (T03 has **no user/owner table** yet; production authorization requires a migration).
- How API identifies unique provider scenes if same IDs can occur across providers: current `CreateRunRequest` has two IDs without provider namespace. **M4 must either restrict to one configured provider or version contract to accept provider-qualified IDs.**
- Asset download policy and signed URL lifetime.
- AOI maximum area, acceptable date ranges, request rate limits, retention policy.
- Run cancellation/retry endpoints (not in Phase 1 contract).
- Method registry and scientifically accepted comparability criteria for multiple sensors.

## Acceptance checklist
- [ ] OpenAPI 3.1 parsing and local structural checks pass
- [ ] M4/M5 explicitly review fields, auth and errors
- [ ] M1 confirms real source metadata and alignment requirements
- [ ] M2 confirms confidence semantics and output raster metadata
- [ ] M3 confirms limitations and exposure provenance
- [ ] T03 SQL mapping and missing user/owner model resolved
- [ ] End-to-end 202→RUNNING→SUCCEEDED→results verified with REAL data
- [ ] Unauthorized cross-user access rejected; URLs expire
- [ ] All stages have provenance, valid checksum and traceable method version

**Definition of Done:** local contract tests pass AND stakeholder approval + runtime integration tests recorded. The former alone does not close the task operationally.
