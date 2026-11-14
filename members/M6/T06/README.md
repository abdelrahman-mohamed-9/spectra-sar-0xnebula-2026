# SPECTRA-SAR — M6, Phase 1, T06: Data Integrity & Provenance

## Purpose
Track **actual** Sentinel-1 source-scene identifiers and process artifacts through M1 → M2 → M3 → M4 using PostgreSQL T03 fields and T05 QA checks. This component **does not download satellite images, generate imagery, or certify scientific conclusions**.

## Files
- `integrity_validator.py`: streaming SHA-256+size verification, local file root containment.
- `provenance.py`: versioned canonical JSON manifest, scene attribution, artifact lineage DAG, consistency checks.
- `scripts/verify_manifest.py`: verify manifest and all local files; exit 2 if S3 objects are unverified.
- `tests/test_provenance.py`: executable unit tests with fixture **bytes**, not simulated SAR data.
- `provenance-contract.md`: ownership, field mapping, and scientific limitations.

## Run tests (Python >=3.10, no third-party packages)
```bash
python3 -m unittest discover -s tests -v
```

## Use with actual satellite products
M1 provides official provider scene ID, HTTPS record URL, license, and original downloaded artifact; hash the actual downloaded bytes with `hash_file`. Use `make_manifest` to link source scene and subsequent processing outputs. Save manifest JSON to durable storage. For local verification:
```bash
python3 scripts/verify_manifest.py /path/to/manifest.json --root /trusted/data/root
```
`file://` URIs in the manifest are **relative to `--root`** (e.g. `file://scene/S1.zip`). The command does not reach remote resources. `s3://` objects are counted as unverified (exit 2). For MinIO use an authenticated S3 adapter in later tasks; do not confuse ETags with SHA-256. A passing hash verifies bytes against a recorded claim, **not that the claim is genuine**. Production requires tamper-resistant manifest storage, trusted provider metadata and signatures/access controls.

## Database mapping (T03)
- `scenes[].id, provider, provider_scene_id, provider_record_url, source_license` → `sar_scenes`.
- `artifacts[].id, run_id, scene_id, storage_uri, sha256, bytes_size, artifact_type` → `artifacts`.
- `artifacts[].input_artifact_ids` → `artifact_inputs` rows (`output_artifact_id`, `input_artifact_id`).
- `producer_component` maps to `stage_executions.component` **only when** `produced_by_stage_id` is recorded; it's an extra manifest field, not an `artifacts` SQL column.
- This is a *portable export*, **not** a SQL migration or ORM implementation.

## Acceptance gates
1. All local file checks pass; 2. every provenance edge points to an existing input; 3. no cycles; 4. scene provider identifiers and licensing recorded; 5. no unexplained unverified remote assets; 6. M1/M4 review source provenance and integration implementation.
