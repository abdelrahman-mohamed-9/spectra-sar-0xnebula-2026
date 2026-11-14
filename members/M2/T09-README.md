# T09 — M2 Integration & M3 Output Contract (v1.0)

## What this delivers

- `pipeline.py`: orchestrates **T02 input validation → T04 residual registration diagnostics → T03 Lee filtering → a filtered intermediate pair → T05 change detection**, plus optional **T06 model inference → T07 uncertainty** when a **real trained model** is supplied. **T08 independent-label evaluation** runs only when an external reference is supplied.
- `output_schema.json`: machine-checkable JSON Schema for `m3-delivery.json`. M3 can use the artifact relative paths, SHA-256 checksums, CRS/transform and data types.
- `tests/test_t09.py`: integration, safety and contract tests.
- No SAR imagery, ground truth, classification model or scientific accuracy scores are bundled or fabricated.

## Inputs from M1

The real M1 data folder must contain a valid `manifest.json`, before/after RTC **gamma0 linear-power GeoTIFFs**, aligned geospatial grids, valid masks, and matching relative orbit/direction/polarization. Follow `manifest-template.json` and `interface-contract-v1.md`. T02 rejects corrupted or mismatched inputs. Some QA warnings require explicit opt-in.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q

# Real production data only: outputs remain exploratory because subpixel QA is unverified.
python pipeline.py /data/real_M1_pair --out /data/M2_delivery_run_001 --polarization VV --allow-warning

# Optional: only with a trained T06 model from trusted independent labels
python pipeline.py /data/real_M1_pair --out /data/M2_delivery_run_002 --polarization VV --model-dir /models/trained_T06 --allow-warning

# Optional: binary independent labels: 0 unchanged, 1 any change, 255 invalid
python pipeline.py /data/real_M1_pair --out /data/M2_delivery_run_003 --reference /data/independent_binary_ground_truth.tif --provenance /data/provenance.json --allow-warning
```

**Exit codes:** `2` means exploratory run completed and produced a handoff; `3` means the run failed. Exit code 2 is deliberately **not** scientific approval.

> Never run over an existing output folder. Staging uses hardlinks or copies; allow sufficient storage. Never consume an untrusted `joblib` model: pickle-format deserialization can execute code. No `--model-dir` means T06/T07 aren't run and aren't falsely reported as complete.

## Output to M3

`m3-delivery.json` conforms to `output_schema.json`; its `artifacts` paths are relative to the output directory. The core artifacts are T05 change score dB, 4-way change mask (`0` unchanged, `1` decrease, `2` increase, `255` invalid), valid mask and their georeferencing and checksums. Optional class map/probabilities and uncertainty maps are included only when inference ran. Reports remain available in each task folder. T08 receives a **binary converted candidate-change mask**, never the original 4-category mask, if evaluation was supplied.

M3 must **not** interpret radar amplitude change as a proven flood, disaster event, or damage estimate. A local **PASS** in T04 may be limited to integer-pixel correlation; no subpixel accuracy has been certified. Ground-truth accuracy metrics cannot be declared without a real independent reference and verified sampling lineage. Filter window, assumed looks and threshold must be justified and validated for each region/sensor.

## Known technical limitations / remaining gates

1. Reprocess and scientifically validate a **real M1 Sentinel-1 pair** with independent data lineage.
2. Finish subpixel registration QA (target <= 0.5 pixels) before scientific approval.
3. T06 and T07 need a **trained trusted classifier** and external, geographically independent reference data; probabilities are uncalibrated.
4. T08's per-pixel scoring is an exploratory diagnostic and is **not** a spatial-independent audit.
5. This pipeline is synchronous and local; failure during a run can leave a partial output folder. It does not implement resume, atomic publication or cloud job orchestration.
6. The input source and science interpretation must be verified separately by the researchers, and an M3 integration test still needs to run with the M3 application.
