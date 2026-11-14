# T04 — SAR Co-registration Verification

## What this does

Checks exact shared geospatial grids through T02, and independently searches for **integer-pixel residual shifts** in several textured patches using phase correlation of smoothed log-power image gradients. Writes `registration-report.json` with shifts, consistency, warnings and reasons.

**It does not warp data, align imagery, estimate subpixel displacement or certify the target 0.5 px residual accuracy.** An undetected integer shift is not proof that subpixel alignment is sufficient. SAR scenes affected by flood/land change, low texture or decorrelation can yield inconclusive estimates. M1 must supply appropriate tie-point/registration evidence or an independent subpixel estimator before T04 scientific approval.

## Run

```bash
pip install -r requirements.txt
python -m pytest tests/ -q
python registration.py /path/to/M1_pair --output registration-report.json --patch 256 --allow-warning
```

Exit status `0=PASS`, `2=WARNING`, `3=REJECT` (with current conservative T04 design, results requiring subpixel certification stay WARNING). M1 should correct misalignments and rerun T02/T03/T04. Do not interpret WARNING as a validated input for scientific change detection.

## Inputs

The same `manifest.json` and `before_VV.tif`, `after_VV.tif`, masks from T02. All input data must be real Sentinel-1 RTC products from M1 for scientific evaluation. Tests below generate synthetic raster patterns strictly as software QA fixtures.

## Caveat

This algorithm is deliberately a **screening method**: tile-based integer shift estimation only; its detected shifts can reflect true scene change and cannot by itself demonstrate precise SAR coregistration. Texture bias may require specialist tie-point methods. Scientific acceptance criterion is <=0.5 pixel residual supported by proper subpixel validation, not just this tool's warning status.
