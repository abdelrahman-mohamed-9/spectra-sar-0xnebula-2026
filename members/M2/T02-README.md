# T02 — Real SAR Data Input & Validation (M2)

## Deliverables
- `data_loader.py`: memory-bounded windowed GeoTIFF loader yielding arrays and joint validity masks
- `input_validator.py`: manifest / geometry / signal preflight, machine-readable QA report
- `tests/test_t02.py`: automated **software** tests with generated tiny fixtures (not scientific demonstration)
- `requirements.txt`, this README, T01 specs and manifest template

## Install and execute
```bash
cd SPECTRA-SAR/M2/phase-01
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
python -m pip install -r requirements.txt
python -m pytest tests/ -q
python input_validator.py /absolute/path/to/input_pair/REAL_PAIR_ID --output qa-report.json
```
Validator exit codes: `0 PASS`, `2 WARNING`, `3 REJECT`. Under the present contract **even usable data receives WARNING** until residual alignment has been independently measured in T04. This is intentional, not a test failure. `WARNING` requires QA review, not silent acceptance as high confidence.

For a downstream loop (AFTER validating):
```python
from data_loader import iter_pair_tiles
for tile in iter_pair_tiles('/absolute/path/to/input_pair/REAL_PAIR_ID'):
    # tile.before / tile.after: float32 linear power arrays
    # tile.valid: boolean mask, includes power>0 & both masks & layover exclusion
    print(tile.window, tile.valid.sum())
```

## M1 → M2 delivery instructions
1. Acquire **real** matched Sentinel-1 IW acquisitions (same relative orbit, direction, polarization) and process via ASF HyP3 RTC or rigorously equivalent chain. Choose gamma0 **power** (linear) and no speckle filtering if T03 will compare filters.
2. Align both scenes to an **identical** projected north-up grid, including pixel origin, dimensions and affine transform. T02 does not warp images.
3. Export `before_VV.tif`, `after_VV.tif` (float32); `before_valid_mask.tif`, `after_valid_mask.tif` (uint8 exactly 0/1). Where possible provide layover/shadow rasters (uint8 1 affected, 0 otherwise). VH may be added if both scenes have VH. File naming is controlled by manifest, not hardcoded.
4. Copy `manifest-template.json` to `manifest.json`, replace ALL placeholders with real provenance and verified values. Use real Sentinel-1 acquisition UTC timestamps, scene IDs, relative orbit 1..175 and accurate grid metadata. A manifest claim alone does not prove source authenticity.
5. Run validator, give M2 pair folder and QA JSON. Fix REJECT before using; review WARNING. T04 must evaluate real subpixel co-registration before change detection.

## Scientific safety and limitations
- Reading and validating successful GeoTIFFs **does not** establish true radiometric calibration, original ESA provenance or subpixel registration. Cross-check HyP3 product metadata/readmes and scene identifiers externally.
- Invalid and zero backscatter values are masked; no logarithms or filtering implemented in T02.
- Missing incidence angles are warnings (not fabricated). >2° difference is a team heuristic requiring review, not an ESA mandated threshold.
- T02 outputs **no** flood, fire, glacier velocity, or land subsidence assertions. InSAR deformation needs SLC phase processing, not these GRD/RTC intensity rasters.
- 10/30 metres describe output *pixel spacing*, not true spatial resolution.

## Sources
- https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
- https://rasterio.readthedocs.io/en/stable/topics/masks.html
