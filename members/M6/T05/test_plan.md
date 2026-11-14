# SPECTRA-SAR — M6 Phase 1 / T05 Test & QA Plan
Status: **implemented for offline QA; live integration pending**  |  Contract baseline: T04 OpenAPI 3.1 `0.1.0`.

## Goals
1. Check proposed API endpoints, authentication expectations, internal schema references and public data exposure.
2. Validate conservative SAR metadata compatibility at the M1/M2 handoff (QA policy, not scientific proof).
3. Validate file byte counts/SHA-256 integrity and acyclic artifact provenance.
4. Prepare **read-only, opt-in** verification of actual M4 backend and T03 PostgreSQL.
5. Never describe fabricated unit-test metadata as real satellite imagery or actual Earth change.

## Matrix
| Category | Evidence | How to run | Gate |
|---|---|---|---|
| Contract | OpenAPI refs, 6 endpoints, request rejection, authorization policy | `pytest -m contract` | All pass |
| Scientific policy | chronology, orbital direction, shared polarization, incidence-angle project threshold | `pytest -m scientific` | All pass |
| Integrity | file SHA-256 and size, complete acyclic lineage | `pytest -m integrity` | All pass |
| M4 backend | readiness and unauthenticated access | `pytest -m integration --run-integration` | Service present, all pass |
| T03 PostgreSQL | 9 expected tables present | `pytest -m database --run-database` | DB present, pass |

## Validation boundaries
- Example values in offline tests are **synthetic metadata fixtures only**, isolated from production. No generated SAR pixels or fabricated detection results are used.
- Actual product identity, acquisition metadata and retrieval proof must come from M1 and a satellite provider.
- Actual geospatial accuracy requires real, co-registered, radiometrically comparable Sentinel-1 scenes and domain expert/validated reference data; metadata tests alone are insufficient.
- 2-degree incidence angle is a configurable *project default*, not a universal SAR rule.
- Tests currently do not certify scientific change-detection accuracy, DEM processing, geocoding, cloud infrastructure, OAuth/JWT authorization or performance.
- `SPECTRA_API_BASE_URL` targets a test/staging M4 backend. Live tests must not be run against uncontrolled production environments.

## Ownership and acceptance
- M1: confirm acquisition field semantics and strict quality policy.
- M2: add filtering and change-map regression tests when code and real test scenes are available.
- M3: add impact/geospatial checks, GIS reference comparisons and uncertainty reporting.
- M4: implement T04 endpoint schemas, auth and readiness; provide staging endpoint.
- M5: validate frontend uses the documented errors/status states.
- M6: maintain this harness, test reports, defects and regression suite.

## Release gate
**T05 implementation:** files present and offline tests green. **Full Phase 1 integration:** only accepted when M4 and PostgreSQL live checks pass and relevant members sign off.
