# Member interfaces and handoff protocol

Refer to `T01/system-interfaces.md` (IF-01 … IF-07) and `T04/integration-plan.md` as proposal baselines. Any schema change must be approved with producing and consuming members, especially M4 for API/DB.

| Handoff | Payload/evidence required | Contract gate |
|---|---|---|
| Provider → M1 | provider name, official scene/product ID, URL, licensing, acquisition time | traceable scene, source matched to actual downloaded bytes |
| M1 → M2 | before/after raster URIs, polarization, orbit, incidence data, transform/CRS, NoData, hashes | alignment and metadata compatibility validated; source IDs retained |
| M2 → M3 | change-mask/score/probability URI, model+code version, spatial grid, confidence semantics, valid-mask | georeferencing matches inputs; uncertain pixels represented |
| M3 → M4 | impact layers and documented references, uncertainty and assumptions | cannot present unassessed figures as zero |
| M4 → M5 | authorized versioned HTTP response and stable status/error model | M5 handles running, completed, failed, and unauthorized cases |
| All → M6 | reproducible run ID, input/output hashes, processing parameters, reference provenance | intact lineage DAG, reproducible reports, signed-off science scope |

## Suggested integration sequence
1. Confirm ownership and freeze a v0.1 schema/contract with M4.
2. M1 supplies *one verified real* Sentinel-1 scene pair and processing metadata; M6 records its IDs and hashes (do not place large files in Git).
3. M2 reads aligned output and produces an actual change mask, probability field if calibrated, and algorithm metadata.
4. M3 verifies AOI overlaps and obtains **independent** assessment reference where available.
5. M4 implements endpoints from T04, links T03 records to stored artifacts, configures auth and error policies.
6. M5 consumes backend responses; M6 runs opt-in T05 checks and T07 metrics against independent reference.
7. Capture command, Git commit, model/data version, timestamps, test report, and any failed gates.

## Interface change control
Propose the change in an issue/PR with owner, schema diff, example real-world metadata (redact secrets), consumer impact, migration steps, regression tests, and approval. Never silently change T05's copied contract independently of T04.

## Evidence format
For every run: provider record URL; product ID; input hash; processing versions/config; output hash and URI; georeferencing and units; valid-mask/NoData handling; verification source; test command/version/results; reviewer/date. Mark pending items as **not verified**, not PASS.
