# SPECTRA-SAR | Member 4 | Phase 1 — Security, Integrity & Evidence

## Deliverables
- T01: `security-scope.md` — security requirements and threat model (design for team review).
- T02: `integrity.py`, `test_integrity.py`, `T02-README.md` — SHA-256 manifests and verification.
- T03: `evidence.schema.json` — JSON Schema 2020-12 for structured SAR scientific evidence.
- T04: `provenance.py` — build/verify evidence manifests, including source-scenes, producer, processing, claims, artifact bytes.
- T05: `test_provenance.py` — schema, tamper, missing-file, injection/path and reference tests.

## Setup
Python 3.10+ (recommended Python 3.11+). Run `python -m pip install 'jsonschema>=4.18,<5'` for T03/T04.

## Run tests
`python -m unittest discover -s . -p 'test_*.py' -v`

## Build a provenance evidence record
1. Put **real** M1 or M2 outputs in `/path/to/data` (e.g. `processed/s1_after.tif`).
2. Write `metadata.json` with actual M1 scene IDs and source URLs from trustworthy source records:
```json
{
  "source_scenes": [{"scene_id":"REAL_SCENE_ID","provider":"Copernicus Data Space","product_type":"GRD","acquisition_time_utc":"2026-01-01T00:00:00Z","source_url":"https://dataspace.copernicus.eu/"}],
  "producer": {"member":"M1","component":"sar-preprocessor","version":"0.1.0"},
  "algorithm":"calibration-and-terrain-correction",
  "parameters":{}, "claims":[]
}
```
3. Run `python provenance.py build --root /path/to/data --metadata metadata.json --output evidence.json processed/s1_after.tif`
4. Run `python provenance.py verify --root /path/to/data --record evidence.json`
5. Independently protect/version `evidence.json` and `baseline.json` (e.g. signed manifest or access-controlled immutable store); a changed evidence record paired with changed files can fool self-referential checks.

## Integration contracts and dependencies
- **M1:** Provide authentic Sentinel-1 product IDs, scene acquisition metadata, downloaded files, processing outputs, and original provider reference/checksums where available.
- **M2:** Provide processed/analysis files, parameter sets, algorithm versions, confidence definition and supporting artifacts.
- **M3:** Provide geospatial risk outputs + input links and uncertainty notes.
- **M5:** Provide protected storage, permissions, audit retention policy, secure artifact reference URLs/IDs, signature verification / trusted baseline management.
- **M6:** Agree on API contracts and evidence display semantics if applicable.

## Scope and limitations
- These modules do not download Sentinel-1 data, authenticate a Copernicus source, validate the physics of a change-detection result, sign manifests, provide remote audit logging, or guarantee immutable storage. Local test fixtures are **not satellite data**.
- `integrity_status=UNVERIFIED` is intentional for newly generated evidence records. `verify` checks bytes against the record, but cannot independently authenticate the record.
- Python-side symlink/race protections are best effort; hardened deployments need OS-level filesystem isolation, restricted permissions and immutable baselines.
- Human review and end-to-end real SAR integration remain pending.
