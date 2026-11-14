# T08 — Scientific Evaluation & Testing

This module evaluates T05 binary change masks OR T06 semantic class maps using **externally provided georeferenced reference labels** on a matching CRS, raster transform and dimensions, plus a valid-pixel mask (1=valid). It never downloads or synthesizes reference labels and never invents model performance.

## Outputs
`evaluation-report.json`: confusion matrix / TP FP FN TN; binary precision, recall, F1 and IoU; multiclass accuracy, per-class scores and macro F1; optional uncalibrated-score reliability bins and diagnostic ECE. Undefined metrics are `null`, not 100%. Valid pixels only. Output reports are explicitly `PROVISIONAL_REQUIRES_INDEPENDENT_LINEAGE_AUDIT` (with self-reported disjoint region IDs) or `UNVERIFIED_EXPLORATORY`.

## Run
```bash
python -m pytest tests/ -q
python evaluation.py --reference /data/gt_change.tif --prediction /out/T05/change_mask_VV.tif --valid-mask /out/T05/valid_mask_VV.tif --mode binary --provenance /data/evaluation-provenance.json --out /out/T08/change-evaluation.json
python evaluation.py --reference /data/gt_classes.tif --prediction /out/T06/class_map.tif --valid-mask /out/T05/valid_mask_VV.tif --mode multiclass --class-ids 1 2 --score /out/T06/uncalibrated_max_probability.tif --provenance /data/evaluation-provenance.json --out /out/T08/class-evaluation.json
```
To test the pipeline without authentic disjoint evaluation metadata, use `--exploratory`; the report is expressly **not** an independent scientific benchmark. Binary ground truth must be coded 0/1; classes must match explicitly listed IDs; nodata=255 for labels is supported.

`evaluation-provenance.json` example (replace EVERY placeholder with truthful values):
```json
{
  "train_region_ids": ["REAL_TRAIN_REGION"],
  "validation_region_ids": ["REAL_VALIDATION_REGION"],
  "test_region_ids": ["REAL_TEST_REGION"],
  "reference_source": "CITE_ACTUAL_REFERENCE_DATASET_AND_VERSION",
  "model_identifier": "ACTUAL_MODEL_CHECKSUM_OR_RUN_ID"
}
```
Mere distinct strings do not establish truly independent geography. Manually confirm no spatial/temporal/scene leakage and that ground truth is reliable. T04 subpixel alignment, quality masks, representative labels, spatially independent holdouts and real Sentinel-1 data remain prerequisite for scientific signoff. Scores on software-test arrays are NEVER project accuracy numbers. Metrics are pixel-wise (not object-wise); account for spatial autocorrelation and class imbalance.

No actual Sentinel-1 pair or labelled ground truth is bundled; this task is code-complete, **not field validated**.
