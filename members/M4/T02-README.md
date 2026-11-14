# M4 / Phase 1 / T02 — Data Integrity Verification

**Deliverable:** `integrity.py` (Python 3.10+, standard library only). This module can hash *real* downloaded Sentinel-1 `.zip`, `.tif`, metadata, or derived files as raw bytes. It never fabricates satellite imagery.

## Run

```bash
# From this directory (change /real/sar/files to an existing directory of actual SAR products):
python3 integrity.py hash /real/sar/files/scene.tif

# Create a baseline from real artifacts; filenames are relative to --root:
python3 integrity.py create --root /real/sar/files --manifest /separate/protected/baseline.json scene.tif metadata.json

# Check bytes against baseline:
python3 integrity.py verify --root /real/sar/files --manifest /separate/protected/baseline.json

# Single-file verification if you already have a trusted digest:
python3 integrity.py check /real/sar/files/scene.tif THE_ACTUAL_64_CHAR_SHA256

# Independent tests use labeled synthetic byte fixtures only:
python3 -m unittest -v test_integrity.py
```

`verify` returns JSON with global `status` and one entry per file (`PASS` / `FAIL`, reason, observed hash). Exit code: `0` pass, `1` verification failure, `2` malformed request/manifest. `create` refuses overwriting an existing baseline.

## Security and scientific caveats

- Put **trusted baseline outside writable processing storage**, with restricted permissions and backups. A file and its digest changed together can appear valid without a protected trust anchor. The CLI cannot enforce cloud ACLs.
- Store baseline as a separate trusted artifact; `integrity.py` doesn't cryptographically sign or authenticate manifests. T03/T04 will define the evidence/provenance record and M5 storage policy.
- SHA-256 hashes bytes, not scientific correctness, registration quality, acquisition origin, or actual Sentinel-1 product authenticity. M1 verifies source/product metadata and proper scene pairing.
- This implementation rejects symlinks and path traversal, and checks for file mutation during baseline creation, but concurrent replacement during verification and adversarial writable directory races still require isolated or immutable storage.
- Feed M1's actual input product and metadata filenames into `create` after M1 finishes acquisition. This is required before claiming real Sentinel-1 integration.

## M1 integration inputs needed

1. Actual local product paths relative to an agreed root directory (SAFE/ZIP/GeoTIFF as used).
2. Confirmation that products are fully written before hashing, plus authoritative catalogue IDs and original source URLs.
3. A separate protected baseline storage location agreed with M5/security owner.

## Scope / status

**Implemented and tested:** hashing, expected-hash verification, multi-artifact manifest, streaming I/O, traversal/symlink restrictions, input validation, fail-closed error reporting.

**Not yet demonstrated:** real M1 Sentinel-1 artifact verification, authenticated upstream provider, team protected-baseline configuration, cross-service gating, T03/T04 scientific provenance.
