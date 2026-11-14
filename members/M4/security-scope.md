# SPECTRA-SAR — Security Requirements & Threat Model

**Project:** SPECTRA-SAR / Dancing with the SARs  
**Owner:** Member 4 — Security, Integrity & Scientific Provenance  
**Phase:** 1/9 — Security, Integrity & Evidence Foundation  
**Task:** T01 — Security Requirements & Threat Modeling  
**Document:** `security-scope.md`  
**Version:** 1.0 (design baseline)  
**Date:** 2026-11-13  
**Status:** Specification complete; implementation and tests pending (T02–T05)

## 1. Purpose and boundaries

Define what must be protected, how threats can affect the scientific integrity of real SAR-derived change detection, and what Member 4 will build to detect tampering, retain traceability, and support trustworthy evidence. The controls in this document are **requirements, not claims of implemented functionality**.

**In scope (Phase 1):** downloaded Sentinel-1 product files and metadata, derived/preprocessed rasters, M2 change masks and confidence outputs, M3 impact outputs, file manifests, reproducibility metadata, evidence records, audit-event format, integrity checks, malicious/accidental modification tests.

**Out of scope for T01:** production identity provider, cloud deployment hardening, live SOC/SIEM, independent cryptographic signatures, full zero-knowledge proof system, certification of scientific correctness, protection against a fully compromised administrator. Those may be scoped in later phases.

## 2. System context and intended data flow

```text
[Official satellite data provider / catalogue]
                    |
                    v
     [M1 acquisition & validation]
       raw SAR + metadata + source URL
                    |
       SHA-256 + manifest at ingestion (M4)
                    |
                    v
        [M1 preprocessing outputs]
                    |
                    v
       [M2 denoising + change detection]
       masks / scores / uncertainties
                    |
                    v
      [M3 impact and decision analysis]
       geographic overlays / risk data
                    |
                    v
          [M5 backend / platform]
          evidence view and export

M4 integrity/provenance functions run at each handoff and record the
input artifact hashes, output artifact hashes, tool/model versions,
parameters, timestamps, and references to parent artifacts.
```

**Trust boundaries:** (B1) external provider → local downloader; (B2) untrusted files/metadata → processing environment; (B3) M1 → M2; (B4) M2 → M3; (B5) analysis outputs → API/UI; (B6) mutable working storage → protected evidence store. Treat all external input and artifacts received from another component as untrusted until validated.

## 3. Protected assets and security objectives

| Asset | Example | Security requirement |
|---|---|---|
| Raw satellite products | Sentinel-1 SAFE files / measurement rasters | Record origin and immutable byte-level SHA-256 digest |
| Metadata | Acquisition time, orbit, polarization, incidence angle, product ID | Validate types and consistency; preserve original metadata |
| Preprocessed rasters | Calibrated/geocoded aligned images | Trace to raw inputs and processing settings |
| M2 outputs | Change map, score, uncertainty estimate | Hash and link to exact input image pair + algorithm version |
| M3 outputs | Risk maps and affected-area summaries | Identify upstream M2 output and external layers used |
| Evidence manifests | JSON records, hashes, source references | Detect edits and unauthorized replacement |
| Audit events | Verification outcomes and handoffs | Chronological trace, with failures visible |
| Operational secrets | Tokens, credentials, API keys | Never store in artifacts, logs, commits, or evidence exports |

**Priority:** Integrity and scientific traceability are primary; availability and confidentiality remain important (notably for secrets and any future private-user data).

## 4. Threat actors and assumptions

- **Accidental operator error:** overwriting rasters, pairing wrong dates or orbit directions, using incorrect metadata.
- **Malicious contributor or compromised account:** swapping analysis files, falsifying scores, deleting trace records.
- **External source/path attacker:** supplying unexpected content through redirects, path traversal, malformed archives, or a fake catalogue entry.
- **Compromised dependency/environment:** malicious library or tampered execution environment changes processing or evidence.
- **Misleading input:** legitimate noisy or misregistered SAR scenes generate incorrect apparent change; this is a scientific validity risk and cannot be solved by hashing.

**Assumptions requiring verification:** team agrees on shared artifact IDs and schemas; product identifiers and source URLs are retained by M1; a separate protected location will hold trusted manifests or their digest references; all components use UTC and stable algorithm/version identifiers.

## 5. Threat model (STRIDE-informed)

Likelihood/impact reflect **initial engineering estimates**, not an audited risk assessment. Priority uses a simple qualitative matrix: High = critical immediate control; Medium = important planned control.

| ID | Threat / scenario | Boundary | Likelihood | Impact | Priority | Required mitigation | Verification |
|---|---|---|---|---|---|---|---|
| TH-01 | Fake source URL/product identity | B1 | Medium | High | High | Allowlist legitimate HTTPS data endpoints; retain catalog/product ID and retrieval URL; record digest at ingestion | Reject unexpected scheme/host; source recorded |
| TH-02 | Downloaded bytes replaced after ingestion | B1/B6 | Medium | High | High | SHA-256 of exact bytes + protected baseline manifest; verify before processing | Flip a byte → FAIL |
| TH-03 | M1/M2 handoff file mismatch | B3 | High | High | High | Artifact ID, digest and metadata contract at each handoff | Mismatch → FAIL, no silent continuation |
| TH-04 | Wrong SAR scene pair (orbit/polarization/angle) | B2/B3 | Medium | High | High | Enforce M1 gatekeeper compatibility status; carry PASS/WARNING/REJECT into evidence | Reject incompatible pair; log reasons |
| TH-05 | Changed inference outputs passed as authentic | B4/B5 | Medium | High | High | Hash every derived artifact; link to upstream hashes and code/model versions | Modified mask → FAIL |
| TH-06 | Tampered provenance/evidence record | B6 | Medium | High | High | Canonical JSON digest + separate protected trust anchor; append-only preferred | Alter field → verification fails |
| TH-07 | Path traversal through filenames/manifests | B2/B5 | Medium | High | High | Restrict to workspace root; reject `..`, symlinks leaving root, unsafe extraction | Traversal attempts rejected |
| TH-08 | Malformed/huge raster or archive exhausts resources | B2 | Medium | Medium | Medium | Limits for file size/count, timeouts, parser validation, safe archive extraction | Oversized/invalid input rejected |
| TH-09 | Secrets leaked into logs/commits | B5/B6 | Medium | High | High | Environment variables/secret manager; redaction; secret scanning | Logs contain no tokens |
| TH-10 | Unauthorized overwriting of trusted manifest | B6 | Medium | High | High | Separate access-controlled baseline/evidence store; backups; audit | Ordinary processing role cannot modify baseline |
| TH-11 | Suppressed or rewritten audit event | B6 | Medium | Medium | Medium | Append-only log destination where feasible, monotonic event IDs, protected retention | Missing event/gap detected or flagged |
| TH-12 | False scientific claim despite valid hashes | B3/B4/B5 | High | High | High | Distinguish integrity PASS from scientific confidence; document registration, parameters, validation and uncertainty | UI/report states independent quality metrics |
| TH-13 | External map layer used without provenance | B4 | Medium | Medium | Medium | Record layer provider, version/date, CRS, license and digest where permitted | M3 output references layer identity |
| TH-14 | Supply-chain modification of processing code | B2/B3 | Medium | High | High | Pin dependencies, review changes, record commit and environment fingerprint | Manifest includes code/version reference |

**Important distinction:** A SHA-256 checksum detects changed bytes **only if the expected hash is trustworthy and stored separately**. A hash does not authenticate a NASA/ESA provider, validate physical interpretation, or prevent an attacker who can replace both file and expected hash. “Zero-knowledge evidence” is a potential later research feature, not something this Phase 1 baseline provides.

## 6. Normative functional security requirements

`MUST` = mandatory for acceptance; `SHOULD` = recommended and may require follow-on work.

| ID | Requirement | Owner | Phase-1 acceptance |
|---|---|---|---|
| SEC-001 | MUST compute SHA-256 over exact bytes of every tracked artifact | M4 (T02) | Same file produces same 64-char lowercase hex digest |
| SEC-002 | MUST verify digest against a separately trusted baseline before downstream reuse | M4/M5 | One-byte edit causes FAIL with reason |
| SEC-003 | MUST fail closed on missing or invalid expected digest for security-gated workflows | M4/M1–M3 | No implicit PASS when reference missing |
| SEC-004 | MUST record stable artifact ID, path/URI, size, digest, media type, timestamp | M4 (T03/T04) | Schema-valid manifest fixture |
| SEC-005 | MUST record provider/product ID, retrieval time, original source URL for raw products | M1 → M4 | One real provider-derived sample traced to source |
| SEC-006 | MUST record parent artifact IDs/hashes for derived files | M1–M3 → M4 | Complete input/output lineage for one pair |
| SEC-007 | MUST record processing operation, code version, parameters, and model version if applicable | M1–M3 → M4 | Reproducibility metadata present |
| SEC-008 | MUST keep verification state distinct from scientific quality/confidence | M2/M3/M4/M5 | Separate fields, UI cannot equate integrity with accuracy |
| SEC-009 | MUST validate all external identifiers, paths, JSON and metadata before use | M1/M4/M5 | Invalid/path traversal fixture rejected |
| SEC-010 | MUST record PASS/FAIL/WARNING and explicit reason codes in verification output | M4 (T02) | Human + machine-readable reports |
| SEC-011 | MUST avoid hardcoded credentials and redact sensitive values from events | All | Automated fixture includes no secret material |
| SEC-012 | MUST retain reproducible audit events across artifact handoffs | M4 (T04) | Event includes actor/component, time, artifact, action, result |
| SEC-013 | SHOULD store baseline manifests in a separately protected append-only or restricted repository | M4/M5 | Documented storage and access design |
| SEC-014 | SHOULD pin and record dependencies and runtime environment | All | Git commit + dependency lock reference |
| SEC-015 | SHOULD store coordinate reference system, footprint and temporal coverage of geospatial outputs | M1–M3 | Spatial metadata included where relevant |
| SEC-016 | MUST preserve M1 gatekeeper validation status for scene pairs, including warnings | M1 → M4 | Evidence references validation decision |

## 7. Evidence and provenance contract (draft for T03/T04)

A record for each artifact **should** contain these fields. The exact JSON Schema will be delivered in T03; this is not a final executable schema.

```json
{
  "schema_version": "1.0",
  "artifact_id": "s1-example-20261113-raw-v1",
  "artifact_type": "raw_sar_product",
  "source": {
    "provider": "COPERNICUS_OR_NASA_CATALOGUE",
    "product_id": "REPLACE_WITH_REAL_ID",
    "retrieval_url": "REPLACE_WITH_REAL_HTTPS_URL",
    "retrieved_at_utc": "2026-11-13T00:00:00Z"
  },
  "integrity": {
    "algorithm": "sha256",
    "digest_hex": "REPLACE_WITH_CALCULATED_64_HEX_DIGIT_HASH",
    "byte_size": 0,
    "verification_status": "NOT_VERIFIED"
  },
  "lineage": {
    "parent_artifact_ids": [],
    "processing_step": "acquisition",
    "code_commit": "REPLACE_WITH_REAL_COMMIT",
    "parameters": {}
  },
  "scientific_quality": {
    "status": "NOT_ASSESSED",
    "notes": "Data integrity and scientific validity are evaluated separately"
  }
}
```

**All values above are placeholders, not real acquisitions or evidence.** Real sample manifests must be generated only from actually downloaded data and computed hashes. Do not submit the example record as a verified result.

### Integration API proposed for team review

- `hash_file(path) -> sha256_hex`
- `verify_file(path, expected_digest) -> {status, reason, observed_digest}`
- `create_artifact_record(artifact, source, parents, execution) -> manifest`
- `verify_lineage(manifest, trusted_parent_digests) -> {status, issues}`

Expected result statuses: `PASS`, `WARNING`, `FAIL`, `NOT_VERIFIED`. Security gates must treat `NOT_VERIFIED` as untrusted, not PASS.

## 8. Phase-1 delivery responsibilities and dependencies

| Dependency | Inputs required by M4 | Agreed next action |
|---|---|---|
| M1 | Real acquired product identifier, URL, SAFE/raster paths, metadata and gatekeeper verdict | M1 provides one valid real pair and their metadata |
| M2 | Input artifact IDs, denoised raster(s), change map, version and params, confidence/uncertainty | M2 emits machine-readable run metadata |
| M3 | Impact map/report artifacts and external GIS layer provenance | M3 emits source layer references |
| M5 | Evidence storage/API boundary and restricted manifest location | Define endpoint/data-storage contract before integration |
| M6 | Product UI/report presentation of evidence (if this is M6's role) | Display verification separate from confidence |

M4 can finish T01 without waiting for the actual data. **T02–T05 integration tests require real output files from M1–M3**; isolated tests may start earlier with controlled fixtures, labeled clearly as tests.

## 9. Validation and acceptance plan

### T01 (this task) — document acceptance checklist

- [x] Define protected assets, scope, and trust boundaries.
- [x] Identify actors, realistic attack scenarios and scientific-integrity hazards.
- [x] Assign initial likelihood/impact priorities.
- [x] Map each threat to mitigation and test expectation.
- [x] Specify functional requirements and ownership.
- [x] Define input/output contracts and cross-member dependencies.
- [x] Mark placeholders and explicitly avoid claiming unverified satellite evidence.
- [ ] Obtain team approval of role assignments, interface contracts, and storage/trust-anchor plan.

### T02–T05 future verification targets (not yet completed)

1. Compute hashes for a real Sentinel-1 product and M1 derivative, store a protected expected value.
2. Run verification twice unchanged → `PASS`; modify one byte → `FAIL`.
3. Verify derived M2/M3 outputs link to the actual upstream digests.
4. Reject missing digest, path traversal, and malformed manifest.
5. Produce a complete provenance chain for one **real** acquisition pair and processing run.
6. Demonstrate that integrity status is independent of M2 model confidence.

## 10. Decisions needed before implementation

1. **Trusted manifest storage:** choose restricted object storage or a separate protected Git repository; saving expected hashes beside mutable files alone is insufficient.
2. **Canonical file and artifact IDs:** team-wide naming and whether ZIP vs extracted SAFE files are individually hashed.
3. **Raw-data immutability:** decide immutable source copy vs content-addressed storage for ingestion.
4. **Roles and access:** document who may write raw files, outputs, manifests, and audit events.
5. **Scientific metadata contract:** agree on CRS, geometry, timestamps, orbit/polarization, and quality/confidence fields with M1/M2/M3.

## 11. Definition of done

**T01 is ready for peer review** when this document is committed to the project repository and assigned owners acknowledge the contracts. **T01 is closed** only after team approval; the rest of Phase 1 is **not** complete until T02–T05 code and tests are implemented against real artifacts.
