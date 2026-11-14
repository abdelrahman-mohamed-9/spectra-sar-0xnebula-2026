# Data Provenance Contract v1

## Pipeline ownership
- **M1:** record Sentinel-1 official data source, acquisition metadata, processing inputs, actual bytes and SHA-256.
- **M2:** provide model/filter versions, parameter metadata, input artifact IDs, output digest and size; report uncertainty limitations.
- **M3:** record geospatial overlay input IDs, output hashes, decision/impact output provenance; avoid unsupported impact claims.
- **M4:** persist records transactionally into T03 PostgreSQL tables, enforce access control, bind run IDs and stage execution IDs.
- **M5:** show acquisition, processing provenance and unverified badges; never label unchecked data as verified.
- **M6:** validate exported lineage consistency and integrity, check integration evidence, report failures.

## Required scene attributes
`id` UUID, `provider` string, `provider_scene_id` string, `provider_record_url` HTTPS, `source_license` string. The full T03 `sar_scenes` record additionally requires mission, product type, acquisition time, orbit direction, polarizations, etc., which M1/M4 must persist.

## Required artifact attributes
`id` UUID, `scene_id` UUID or null, `run_id` UUID or null, `artifact_type`, `storage_uri` (`file://relative/path` or `s3://bucket/key`), lowercase `sha256` (64 hex chars), nonnegative `bytes_size`, optional `producer_component`, `input_artifact_ids` list of UUIDs. At least one of `scene_id` / `run_id` must exist.

## Guarantees and limitations
- A manifest SHA-256 detects accidental changes **relative to a separately trusted digest**; anyone can recompute an unsigned manifest and its digest.
- Hash validation protects against undetected data modification when compared with a trusted original digest. It does not authenticate a download source.
- Checks do not establish valid SAR calibration, coregistration, change significance, or trustworthiness of AI predictions.
- `s3://` assets are **explicitly not verified** by the local verifier. Add authenticated remote checksum retrieval and object-version pinning before production use.
- Manifest is an export format. M4 owns persistence, SQL transactions, authentication and authorization.
- Must not include credentials, access tokens, or signed download URLs in manifests.

## Integration follow-up
Agree with M4 on a single manifest schema/version policy and per-run atomic storage of provenance edges. Agree with M1 on license and HTTPS provider reference provenance. Apply T05 tests to end-to-end live data before declaring phase complete.
