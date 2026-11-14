# M5 / Phase 1 / T05 — SAR Data & Processing Result Models

**Status:** Code implemented, local tests run; PostgreSQL/PostGIS end-to-end ingestion remains unverified until Docker database integration.

## New files
- `src/spectra/domain/schemas.py`: strict Pydantic input/output schemas with provenance checks and bounds.
- `src/spectra/persistence/repositories.py`: seven typed ORM repositories, parameterized lookup, geospatial serialization.
- `src/spectra/persistence/unit_of_work.py`: explicit transaction boundary (`commit` on success, rollback on errors).
- `tests/test_t05.py`: validation, schema and mocked repository tests.

## Integration interfaces
- **M1:** `SarSceneCreate`, `ArtifactCreate`, `ScenePairCreate`. Requires upstream real Sentinel-1 STAC item, provider/collection/source IDs, and actual asset links. An accepted schema does **not** prove an asset was downloaded or calibrated.
- **M2:** `ChangeResultCreate` references a persisted processing job, before/after scene pair, change mask artifact and optional confidence raster. No invented confidence metrics.
- **M3:** `ImpactAssessmentCreate` references M2 result plus real source/method details; population estimates require sourced datasets.
- **M4:** Read contracts support future response models in T06.
- **M6:** Storage references only; authorization and object access controls are future tasks; no public API writes in T05.

## Known limits and risks
- This task does not implement endpoints (T06), data download, storage verification, scientific scene-pair compatibility checks, or row-level authorization.
- The STAC check validates a minimal shape and linked asset URI, not provider ownership, download success, signatures or pixel content.
- GeoJSON validation checks coordinate bounds/ring closure, not full topology. Database insertion should be followed by `ST_IsValid` checks; geospatial features use SRID 4326.
- Cross-record invariants (project ownership, scene pairs in AOI, type of referenced artifact, job state) must be checked in the T06 service layer and/or DB constraints.
- Integration tests with live PostgreSQL/PostGIS and S3-compatible storage remain mandatory before production.

## Run tests
```sh
python -m pip install -e '.[dev]'
python -m pytest -q
```
