# M6 Phase 1 T07 — Verification plan

## Ownership and dependencies
- **M1 SAR acquisition:** supply verified real scene IDs, acquisition times, Sentinel-1 product metadata, calibration/preprocessing method and co-registration QA report.
- **M2 AI/change:** supply binary masks and optional probabilities, model version, processing settings, valid-data mask, raster CRS and transform.
- **M3 geospatial impact:** supply independent hazard/reference datasets where valid, region/event definitions; do not reuse prediction-derived results as ground truth.
- **M4 backend:** retain run ID, asset URIs and status; integrate T07 metrics and provenance links in results payload after API agreement.
- **M5 UI:** display sample counts, missing reference warning and score limitations; avoid unsupported 'scientifically proven' labels.
- **M6 QA:** review references, validate raster alignment, produce metrics, preserve T06 lineage, flag failed gates.

## Checks
| Code | Check | Failure response |
|---|---|---|
| SV-01 | Real SAR source ID and traceable provenance | Block scientific assertion |
| SV-02 | Same CRS, shape, geotransform | Reject and require registration |
| SV-03 | Reference independent and temporally matched | Flag unvalidated |
| SV-04 | NoData/layover/shadow mask recorded | Fail or narrow valid pixels |
| SV-05 | Confusion counts sum to valid pixels | Reject metrics |
| SV-06 | Undefined metrics remain null | Reject misleading zero/one |
| SV-07 | Probabilities bounded [0,1] | Reject calibration assessment |
| SV-08 | Evaluation holdout declared | Flag leakage risk |
| SV-09 | File digests/lineage connect back to M1/M2/T06 | Block release |
| SV-10 | Results consistent with M4 contract | Integration review |

## Status
The test package verifies metric implementation on **small deterministic test fixtures**. It does not contain NASA/Copernicus downloads, labelled SAR events, deployed backend, or accuracy claims. Separate scientific validation requires real independent reference ground truth and a holdout plan.
