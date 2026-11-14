# T07 — Confidence & Uncertainty Estimation (diagnostic stage)

## Inputs

Requires the same actual Sentinel-1 RTC pair directory from M1 used by T06 and
T06 classification output, generated **with the updated T06 in this package**.
T06 now also exports `class_probabilities.tif` (one band per training class)
and `class_ids` metadata in band order. No model is shipped or invented.

## Outputs

- `normalized_entropy.tif` — model ambiguity [0,1]; **not calibrated confidence**
- `top_two_margin.tif` — difference between top 2 model class scores [0,1]
- `uncalibrated_max_probability.tif` — RF probability-like score [0,1]
- `review_required.tif` — 1 needs review, 0 not flagged, 255 invalid
- `uncertainty-summary.json` — counts, provenance, caveats, no scientific signoff

All GeoTIFF outputs preserve the SAR pair geospatial grid and use tile-wise reading.
Invalid pixels have explicit nodata. Review threshold default is 0.60, heuristic.

## Usage

```bash
python -m pytest tests/ -q
python ai_classifier.py infer /path/to/real_M1_pair --model-dir /path/to/real_trained_model --out /path/to/T06_classification --allow-unverified-registration
python uncertainty.py /path/to/real_M1_pair --classification-dir /path/to/T06_classification --out /path/to/T07_diagnostics --allow-unverified-registration
```

The bypass **only** allows exploratory testing and does NOT establish scientific
registration quality. T06 supervised ML must have a trusted trained model and
proper ground-truth labels; no claim of real accuracy or flood recognition without them.

## QA & limitations

Unit tests use small arrays for software correctness only, not satellite validation.
T07 checks raster grid, class IDs, probability normalization, class/probability
consistency, and validity masks. **IMPORTANT:** it is not calibrated uncertainty
and cannot infer whether scene labels or the ground truth are correct. Quality
masks from the original M1 pair are used for valid-pixel selection, but no
single combined scientific quality index is claimed. Spatially independent
validation plus calibration reliability diagrams / ECE and coverage/accuracy
curves are future requirements before scientific confidence reporting.

Security: only load trusted, locally generated T06 joblib models; the T06 hash
check verifies consistency but is not a defense against malicious pickle files.
