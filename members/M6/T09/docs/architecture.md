# Architecture, ownership, and boundaries

```text
Official SAR provider / verifiable Sentinel-1 scene metadata
                     |
                     v
            M1 SAR acquisition / calibration / co-registration
                     |  aligned geospatial raster + metadata + provenance
                     v
           M2 speckle handling + change detection + confidence
                     |  mask/probability and model parameters
                     v
            M3 geospatial impact and explainable indicators
                     |  impact geometry, evidence, limitations
                     v
            M4 authorized Backend / API / persistence
                     |
                     v
            M5 frontend / dashboards / maps

M6: cross-cutting validation / reproducibility / tests / documentation
Infrastructure: T02 PostgreSQL metadata + MinIO object storage proposal
```

## Ownership matrix
| Member | Owns | M6 acceptance evidence |
|---|---|---|
| M1 | scene selection, verified satellite source, alignment, raster outputs | provider IDs, acquisition timestamps, product parameters, checksums, CRS/transform |
| M2 | scientifically motivated denoising, detection algorithms, uncertainty | reproducible model version, masks/probabilities, NoData policy, evaluation inputs |
| M3 | geospatial impact assessment | validated overlays, independent reference provenance, missing-data warnings |
| M4 | authoritative database, HTTP APIs, auth, async jobs | implemented OpenAPI agreement, access controls, live checks |
| M5 | frontend visualizations | consumed API schema, map CRS agreement, error states |
| M6 | QA, integration docs, reproducibility, CI scaffolding | traceable test reports, provenance checks, decision log |

## Data ownership boundaries
- PostgreSQL T03 is metadata and relations, not storage for large SAR rasters. M4 must confirm SQL ownership.
- MinIO T02 is object storage **proposal** for local development; do not treat it as real satellite provider.
- `s3://` paths refer to objects; a DB row or an object-store ETag does not prove a SHA-256 match.
- Original radar scenes must not be invented; provider source is authoritative only when record and product match.
- A `CHANGE` prediction is an interpretation, not automatically proof of flood/fire/deforestation; require uncertainty and external verification.

## Known limits
No published deployment diagram proves actual endpoints are running. Authentication, production backups, observability, object-store verification, immutable evidence manifests, and full scientific benchmarking remain integration tasks.
