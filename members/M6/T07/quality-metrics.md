# Scientific evaluation protocol — M6/T07

## Scope & scientific boundaries
Evaluate **binary change masks** supplied by M2, NOT raw Sentinel-1 SAR imagery or actual geophysical labels. No claim of flood, landslide, or deforestation accuracy is valid without appropriate independent reference labels and uncertainty analysis. All reported scores must describe their validation geography, dates, labels and sampling.

## Required inputs
- A M2 pixel-aligned binary output raster (`0=no change`, `1=change`).
- An **independent** reference mask covering the same geography/date, labelled with source and generation method. Same predictions must never be used to construct the reference.
- Matching CRS, pixel shape and affine geotransform for both. Explicit geospatial resampling/coregistration must be performed outside T07 and logged before evaluation. Never assume shapes alone establish alignment.
- `valid_mask` excludes unknown regions, missing reference, SAR shadow/layover or otherwise invalid areas (depending on campaign). Do not score masked-out pixels.
- Optionally change probabilities in [0,1], calibrated with Brier score / ECE.

## Metrics & interpretation
- TP predicted change and reference change; FP predicted change without reference change; FN missed reference change; TN agreement on no change.
- Precision = TP/(TP+FP); Recall = TP/(TP+FN); F1 = 2TP/(2TP+FP+FN); IoU = TP/(TP+FP+FN).
- Accuracy and balanced accuracy are supplementary; accuracy can look high when most of the image does not change.
- `null` for undefined metrics: e.g. no positives predicted means precision is undefined; no change in either map makes change IoU undefined. Never label as 100%.
- `valid_fraction` helps identify cherry-picked masks; always report total and valid pixels.
- Brier score and expected calibration error (ECE) require true probability outputs. Do not treat raw uncalibrated SAR intensities as probabilities.

## Acceptance gate (proposed; M2/M3/M6 to agree)
1. Required reference provenance is present and auditable.
2. No CRS/geotransform mismatch; valid pixel count greater than zero.
3. All available metrics derived strictly from reference-validated pixels.
4. Raw counts, masking fraction and source identifiers stored with run ID and file digests (M6 T06).
5. Test geography and acquisition times are held out from tuning/training data where feasible. Inspect leakage, seasonal effects, urban speckle and registration artifacts.
6. For operating thresholds (IoU, recall, false-alarm rates), obtain application-specific thresholds from domain experts and a declared validation dataset, **not** arbitrary default scores.
7. Until actual labelled data is evaluated, label status `UNVALIDATED_SCIENTIFICALLY`; local unit-test pass does not change that status.

## Next validation levels
- Pixel-level verification with independent labels and geospatial metadata.
- Event-level verification: polygons, minimum mapping unit, false alarms per square kilometre, tolerance to boundary offsets.
- Robustness across orbit directions, incidence angles, polarization, seasons and geography (only comparable scenes per M1 gate).
- Confidence intervals via event/region-level bootstrapping (not naive independent pixels).
- Earth-observation interpretation: a SAR intensity change is not automatically a flood or disaster.
