# SPECTRA-SAR — M1 ⇄ M2 ⇄ M3 Data Interface Contract

**Version:** 1.0 | **Date:** 2026-11-13 | **Status:** Proposed team baseline, implementation not yet verified
**Owner:** M2, requires M1 producer and M3 consumer agreement.

## 1. Decision and rationale

Primary source: real ESA Sentinel-1 IW images converted by M1 to a common geocoded radiometric-terrain-corrected (RTC) product. **Preferred:** gamma0 terrain, linear power, float32, in UTM GeoTIFF. VV is mandatory in the baseline; VH is optional only when both scenes contain it. Do not mix radiometric coefficients, linear/dB units or polarization across time. Use actual scene IDs, dates and processing provenance. No synthetic imagery for scientific demonstration.

A nominal output grid of 10 m may be used where a compatible product supports it; 30 m is also supported. Pixel spacing is NOT the actual sensor spatial resolution. Set and retain one CRS, transform, bounds, dimensions and pixel spacing per pair. The same exact grids must be enforced before comparison; supplying both images with the same width/height is insufficient.

## 2. M1 → M2 input folder

```
input_pair/<pair_id>/
  before_VV.tif
  after_VV.tif
  before_VH.tif               # optional, only with after_VH.tif
  after_VH.tif                # optional, only with before_VH.tif
  before_valid_mask.tif      # uint8, 1 valid, 0 invalid
  after_valid_mask.tif       # uint8, 1 valid, 0 invalid
  before_layover_shadow.tif  # optional; 1 affected, 0 unaffected
  after_layover_shadow.tif   # optional; 1 affected, 0 unaffected
  manifest.json
```

Manifest fields: `schema_version`, `pair_id`, `source_provider`, `processing_software`, `processing_version`, `radiometry` (`gamma0_terrain`), `units` (`linear_power`), `product_type` (`RTC`), `acquisition_mode` (`IW`), `polarizations`, `grid` (`crs`, `pixel_size_m`, `width`, `height`), and for `before`/`after`: `scene_id`, `acquired_utc`, `relative_orbit`, `orbit_direction`, `incidence_angle_deg_summary`, `raster_files`, `valid_mask_file`, optional `layover_shadow_mask_file`. Every path relative to the pair directory; external references may be recorded separately in provenance. The manifest is metadata; it is NOT proof that the rasters have matching geotransforms. Validate files themselves.

## 3. Acceptance / rejection policy

**Hard reject** when files unreadable; missing required VV/valid mask; missing scene IDs/dates; missing or contradictory radiometry/units; mismatched VV polarization, orbit direction, relative orbit, acquisition mode; one VH without its pair; invalid GeoTIFF grids; non-overlapping/unsuccessfully aligned rasters; or no usable shared valid area. `gamma0_terrain` input must have physically plausible finite nonnegative power; zeros must be handled by documented mask/floor policy, not silently logarithmed.

**Review / warning** for incidence angle difference > 2 degrees (project heuristic; not universal scientific cutoff), substantial missing-data fraction, acquisition seasonal inconsistency, filtering history mismatch, or uncertain alignment. Warning data must not be automatically passed as high-confidence results.

**Alignment QA target:** measured residual shift <= 0.5 output pixels on stable patches. Target, NOT a guaranteed achieved accuracy. M2 verifies geometry and may explicitly co-register/warp with recorded resampling; never silently assume registration.

## 4. M2 processing boundaries

1. T02 validate raster metadata, provenance, units, masks and pair geometry.
2. T03 preserve original; compare no-filter baseline with mask-aware Lee-family linear-power filter, avoiding double filtering.
3. T04 verify/repair alignment before pixelwise difference, with a final QA pass.
4. T05 produce signed dB change (`10*log10(after/before)` for positive valid linear power), absolute magnitude and candidate threshold mask. Threshold is calibrated per target case, never treated as a universal constant.
5. T06 allow hazard classification only with validated independent labeled data. Amplitude change alone does NOT prove flood, fire, subsidence, or glacier speed.
6. T07 provide validity/QA and a documented confidence/uncertainty measure; do NOT represent an uncalibrated score as a probability.
7. T08 evaluate against independent real reference labels, where available, with confusion matrix, F1 and IoU, noting limitations.
8. T09 export outputs and run manifest for M3.

## 5. M2 → M3 output folder

```
output_pair/<pair_id>/
  change_signed_db.tif           # float32, nodata where invalid
  change_magnitude_db.tif        # float32 >=0, nodata where invalid
  candidate_change_mask.tif     # uint8: 0 no change, 1 candidate, 255 nodata
  valid_mask.tif                # uint8: 0 invalid, 1 valid
  quality_score.tif             # float32 0..1, NaN/nodata invalid; NOT probability
  change_polygons.geojson       # optional vectorization, georeferenced
  summary.json
```

All raster layers must share CRS, affine transform, shape and pixel grid; polygon coordinates MUST follow GeoJSON WGS84 longitude/latitude conventions. The summary records `pair_id`, source scene IDs/times, parameter/version hashes, status (`PASS`, `WARNING`, `REJECT`), quality flags, pixel_area_m2, valid_area_m2, candidate_change_area_m2, threshold_db, model_training_status, confidence_semantics and relative output paths. Area is measured in a suitable projected/equal-area CRS; don't compute m² from latitude/longitude degree pixels. `candidate_change_area_m2` is a radar-change footprint, not verified damage or disaster area.

## 6. Cross-team handoff / acceptance tests

- M1 provides one REAL pair and raster metadata; M2 verifies manifest values against actual rasters.
- Pair has documented source provider and scene IDs; metadata reflects real acquisitions.
- M2 tests aligned pair, misaligned pair, missing mask, orbit mismatch, polarization mismatch, missing VH counterpart and empty valid intersection.
- M2 saves deterministic baseline products, timestamps, parameters and QA report.
- M3 loads all M2 outputs and can resolve coordinates/areas; does NOT infer actual damage from candidate change alone.
- M1/M2/M3 explicitly approve the interface before freezing v1.0. If any changes are needed, bump schema version and retain backward-compatible parser or migration.

## 7. Real data and limitations

No actual scene downloads, processing success, model training or ground truth collection is implied by this specification. For **land subsidence**, Sentinel-1 GRD/RTC amplitude cannot supply phase-based deformation estimates: separate SLC/InSAR branch required. For **glacier motion**, implement dedicated validated offset tracking/InSAR where appropriate. For **floods**, radar intensity changes are candidate indicators, impacted by wind, soil moisture, roughness, urban geometry and look geometry.

## References
- ASF HyP3 Sentinel-1 RTC product guide: https://hyp3-docs.asf.alaska.edu/guides/rtc_product_guide/
- ASF RTC algorithm theoretical basis: https://hyp3-docs.asf.alaska.edu/guides/Sentinel_RTC_ATBD_v3.1.pdf
- Digital Earth Africa Sentinel-1 product specs: https://docs.digitalearthafrica.org/en/latest/data_specs/Sentinel-1_specs.html
