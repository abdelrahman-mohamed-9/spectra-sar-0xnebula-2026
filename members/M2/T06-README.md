# M2 T06 — Supervised SAR Change Classification

## Scientific scope and non-claims

This is a **real trainable Random Forest pipeline**, not a pretrained flood/disaster detector. The preceding T05 produces radiometric change candidates (increase/decrease); it cannot justify semantic labels. T06 only learns semantic classes when a researcher supplies real co-registered reference labels, a `classes.json` class dictionary, and matched M1 GeoTIFF input. No ground truth dataset is bundled, no fabricated imagery/accuracy metrics are claimed, and no trained model ships in this package. Inference requires a trained artifact.

Pixel features: before and after gamma0 in dB, signed and absolute change in dB, masked 7x7 local before/after means and change standard deviation. It excludes invalid, nodata, zero/negative power, and layover/shadow masks. The output uses original georeferencing. Train loads full scene to memory (plan memory budget), inference uses haloed tiles. Default Random Forest: 100 trees, deterministic seed 42, balanced_subsample weights. Ground-truth classes must be explicit user-supplied integers 1..254; 255 is invalid.

## Install and run tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -q
```

## Required M1 / reference deliverables

- M1 pair directory with manifest.json, before/after gamma0 linear-power GeoTIFFs and quality masks matching the T01/T02 schema.
- Independent **verified** classification reference raster `reference_labels.tif`, exactly aligned with the M1 pixel grid. Unknown / unlabeled pixels are 0 or 255. Do not train on T05's threshold masks and then report the threshold as ground truth.
- `classes.json`, for example `{"1":"flood", "2":"other"}` **only when** a qualified source has actually annotated these categories. These are example label definitions, not a supplied dataset.
- Reference-label provenance (event/location/date/source/annotation method/limitations).

## Training

```bash
python ai_classifier.py train /absolute/path/M1_pair \
  --labels /absolute/path/reference_labels.tif \
  --classes /absolute/path/classes.json \
  --out /absolute/path/T06_model \
  --polarization VV --group-pixels 64
```

Outputs: `t06-random-forest.joblib`, `model-metadata.json` (model digest, class dictionary, spatial group holdout confusion matrix and precision/recall/F1). Training refuses insufficient data, classes missing in split, or poor geographic label distribution. A single spatial holdout is **not** independent field validation.

## Inference — exploratory until registration is certified

```bash
python ai_classifier.py infer /absolute/path/M1_pair \
  --model-dir /absolute/path/T06_model \
  --out /absolute/path/T06_output \
  --polarization VV --tile-size 512 \
  --allow-unverified-registration
```

Outputs: `class_map.tif` (IDs 1..254, nodata 255), `uncalibrated_max_probability.tif` (not scientific confidence), `classification-summary.json`. The exit code 2 is intentionally exploratory. T07 will handle proper confidence/uncertainty. T04 subpixel QA and external event-site validation are required before deployment.

### Security

**Only load a model produced by your own trusted training process.** Joblib/pickle deserialization can execute code; comparing a hash from an untrusted JSON alongside it is not a security guarantee. Keep model files private and provenance-verified. Do not make emergency decisions from unvalidated maps.
