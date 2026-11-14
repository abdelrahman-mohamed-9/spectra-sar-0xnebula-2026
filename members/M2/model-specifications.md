# SPECTRA-SAR — M2 Model & Algorithm Specifications

**Workstream:** Member 2 — AI & Scientific Intelligence  
**Phase:** 01 / 09 | **Task:** T01 (second deliverable)  
**Status:** Design specification — models not yet trained, tuned, or validated  
**Version:** 1.0 | **Date:** 2026-11-13

## 1. Architecture and stages
```text
M1 real Sentinel-1 RTC GeoTIFF + manifest + quality masks
    ↓
T02 input_loader → metadata/unit validation → geometry/overlap checks
    ↓
T03 optional speckle processing (preserve raw input)
    ↓
T04 residual co-registration and quality verification
    ↓
T05 deterministic backscatter change detection (scientific baseline)
    ↓
T06 optional hazard-specific classification (only if trained/validated)
    ↓
T07 per-pixel quality and uncertainty representation
    ↓
T08 independent evaluation + run provenance
    ↓
T09 geo-products and JSON contract → M3
```
**Ordering note:** Initial geometry validation precedes filtering, but residual co-registration accuracy must be checked again immediately before differencing. Alignment may need to be performed before filtering to ensure matched spatial sampling; do not assume the diagram mandates a fixed filter-before-registration order.

## 2. Supported inputs / mathematical units
- Real Sentinel-1 IW RTC, dual-pol VV/VH when available; VV-only permitted.
- Raster data: float32/float64 calibrated **linear power** gamma0 terrain (preferred) or another *explicit and matched* backscatter coefficient.
- For strictly positive linear power `P`, `dB = 10 log10(P)`; handle nonpositive/nodata through masks and an explicitly reported floor **used only for numerical stability**, never misrepresent zero/nodata as valid signal.
- If already in dB, do **not** apply `log10` again; dB bands are not linear-power arrays.
- Both date inputs need a shared grid and sensor geometry reasonably consistent; compare relative orbits, directions, polarization, incidence-angle distributions and processing histories.
- Outputs: EPSG/CRS + affine transform, valid region, provenance; mask shadows/layover where available.

## 3. T03 — speckle filtering candidates

### Baseline A: identity/no additional filter
- Mandatory benchmark; many RTC feeds are already filtered or multilooked.
- Avoid double-filtering, which may smooth actual land-cover boundaries and small changes.

### Baseline B: Lee local adaptive filter in linear domain
Concept: `I_filtered = local_mean + W * (I - local_mean)` where `W` varies with local signal/noise variance and is clamped to [0,1]. Exact formula depends on Lee implementation and noise-variance estimation. Specify/record number-of-looks assumption or empirical equivalent, moving-window size (initial experiments 3×3/5×5/7×7), edge treatment and mask-aware statistics.
- Never filter in dB as though the values were linear power.
- Compare filtered vs identity using homogeneous-area coefficient of variation and edge preservation, not just visually smoother results.
- More sophisticated alternatives (Refined Lee, Lee Sigma, non-local SAR filters) are **research candidates**, not promised implemented features.

## 4. T04 — alignment quality
- Exact-grid agreement tests: CRS, geotransform, shape, valid overlap.
- Optional subpixel registration after geocoding, based on stable landmarks or suitable intensity matching, with robust feature rejection.
- Initial **engineering QA target**, to verify empirically: residual displacement ≤0.5 output pixels over a representative set of stable patches. This is not a claimed achieved accuracy or a universal threshold.
- If quality assessment fails, mark pair `REJECTED_ALIGNMENT` and block high-confidence map generation.
- Do not resample the binary validity mask bilinearly; use nearest-neighbor mask resampling. Record interpolation for intensity rasters.

## 5. T05 — deterministic change detection baseline
Let `P_pre(x)` and `P_post(x)` be comparable calibrated linear backscatter intensities at valid co-registered pixel `x`.

**Signed change in dB**:
```text
D(x) = 10 log10(P_post(x)) - 10 log10(P_pre(x))
     = 10 log10(P_post(x) / P_pre(x))
```
**Magnitude**: `A(x) = |D(x)|`.
**Positive-change candidate**: `D > T_pos`; **negative-change candidate**: `D < -T_neg`.
**Any-change mask**: `A > T_any` on the shared valid region.
- Keep signed maps; a change to lower radar backscatter may correspond to open water in some environments, but is **not sufficient evidence of flooding**.
- Initial thresholds **must be selected using a stable reference distribution and sensitivity analysis**; do not impose a fabricated universal 2/3/5 dB detection guarantee.
- Candidate methods for comparison: absolute dB difference, log-ratio plus adaptive threshold, robust background median/MAD, Otsu where histogram assumptions plausibly hold.
- Optional multitemporal references reduce false positives from wet soil, seasonal land cover and speckle.
- Mask co-registration edge buffers, RTC shadow/layover, nodata and bad-quality pixels.

## 6. T06 — event-aware interpretation

| Event | Phase 1 inference | Extra data needed for stronger inference | Major limitation |
|---|---|---|---|
| Flood / inundation | Change candidates + post-event low-backscatter water mask; contextual pre-event water exclusion | independent flood maps, DEM, land cover and optical reference where available | wind/rough surfaces, dense vegetation and buildings may break dark-water assumption |
| Wildfire / burned land | Generic radar change candidates only | active fire / burn severity ground truth, multispectral data and seasonal context | C-band backscatter is not a unique fire signal |
| Glacier displacement | **Not measured from amplitude differencing alone** | offset tracking of appropriately processed images; glacier reference data | change score ≠ velocity or displacement |
| Land subsidence | **Not measured by GRD/RTC amplitude differencing** | Sentinel-1 **SLC phase**, orbit precision, DEM, atmospheric corrections, InSAR stack | requires separate InSAR architecture and validation |

**M2 Phase 1 acceptance claims must stay at `candidate_backscatter_change` level until independently labeled and evaluated.**

## 7. T06 future ML/DL track — design, not current deliverable
- **First scientific baseline**: deterministic approach above, run on actual Sentinel-1 RTC imagery.
- **Supervised model option:** U-Net style segmentation with separate channels for before/after VV, optional VH, ΔdB, validity/quality. Input must be normalized using training-only statistics, preserve geographic partitioning, and include region/date/domain shifts.
- **Alternative:** shallow Random Forest / gradient-boosted trees on change features and land-cover context (useful interpretable comparator).
- **Data requirements:** real georeferenced pairs, provenance, independently sourced pixel or polygon labels, explicit label uncertainty and held-out geographically separated scenes.
- **Train/validation/test:** partition by event/geographic area (not adjacent pixel samples from same scene); avoid train/test leakage through overlapping tiles and dates.
- **No phantom weights:** `model_weights` and AI performance remain **not available** until actually trained and verified. For no-label stage, use baseline only.

## 8. T07 — confidence and uncertainty semantics
Represent distinct quality concepts separately:
1. `valid_mask`: observed and correctly masked pixels.
2. `quality_flags`: nodata, shadow/layover, low overlap, co-registration concerns, atypical geometry and possible double-filtering.
3. `change_score`: observed radar backscatter change, not probability.
4. `confidence`: **null / unavailable by default**. A calibrated detection probability requires appropriate labeled data, calibration and reliability assessment. Unsupervised heuristic stability scores may be exported only with explicit `confidence_kind=heuristic_quality_score` and cannot be called probabilities.
5. `event_class`: `unknown` unless a hazard-specific validated model or external confirmatory dataset supports classification.

## 9. T08 — metrics, benchmarks, and evaluation
**Without labels:** report number of valid pixels, coverage and overlap fraction, residual registration error, background score distribution, filtered vs original noise measures, candidate change fraction and area where geodetic calculation permits. These measure *pipeline quality*, not correctness of event detections.

**With trustworthy independent labels:**
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2PR / (P + R)
- IoU = TP / (TP + FP + FN)
- Confusion matrix with exclusion of ignored/nodata zones.
- Calibration metrics such as Brier score/ECE only for bona fide predicted probabilities.
- Evaluate separately for geography, season, polarization, incidence geometry and land-cover types.

**Acceptance targets:** Set numeric accuracy goals only after data profiling and baseline measurement; no measured performance is asserted in T01. Suggested *engineering gates* (not reported results): no unrecorded missing metadata, valid output grid match, deterministic rerun and zero unmasked nodata pixels in evaluation.

## 10. Implementation stack / module interfaces

| Module | Purpose | Proposed public callable |
|---|---|---|
| `data_loader.py` | Load GeoTIFF and metadata from M1 | `load_pair(manifest_path)` |
| `input_validator.py` | Enforce contract and geometry rules | `validate_pair(pair)` |
| `filters.py` | Identity/Lee speckle filtering | `filter_backscatter(arr, valid_mask, method, params)` |
| `registration.py` | Compare/adjust spatial alignment | `assess_registration(before, after, grid)` |
| `change_detector.py` | Signed ΔdB and masks | `detect_changes(pre, post, valid_mask, config)` |
| `ai_classifier.py` | Optional validated event model | `classify_change(features, model)` |
| `confidence.py` | Quality flags and calibrated confidence when available | `estimate_quality(context)` |
| `evaluation.py` | Independent validation | `evaluate(prediction, reference, ignore_mask)` |
| `pipeline.py` | Reproducible end-to-end orchestration | `run_pipeline(manifest_path, config_path)` |

**Dependencies proposed, not installed or tested:** Python 3.11+; NumPy, Rasterio/GDAL, SciPy, scikit-image, pytest, Pydantic; optionally scikit-learn/PyTorch for supervised experiments. Freeze versions in an actual implementation lockfile.

## 11. Reproducibility and output artifacts
- Unfiltered and optionally filtered real backscatter GeoTIFFs.
- `change_score_db.tif`, `change_mask.tif`, `valid_mask.tif`, `quality_flags.tif` with matching grid.
- `result.json`, `run_config.yaml`, `provenance.json`, `evaluation.json` (with `metrics=null` when unlabeled).
- Before/after figures use same display stretch, grid, dates, units and scale bar; visualizations are **derived from real source imagery** and clearly labeled.
- Record deterministic seed for any randomized component, source product hashes and relevant software versions.

## 12. Scientific blockers and decisions awaiting evidence
- Which real M1 scene pair and AOI will be the first acceptance test?
- Does M1 supply already despeckled RTC? (Determines identity vs additional filter.)
- Does M1 preserve full per-scene orbit/look metadata rather than only `common` fields?
- Which independent event reference or manually audited geographic validation sample can be used?
- Which event type is the target for early hazard-specific validation (recommended: flood first; do not promise generic multi-hazard accuracy)?

## 13. Definition of Done — specification
- [x] Specify baseline change model and equations.
- [x] Specify speckle and alignment methodology.
- [x] Clearly separate radar change from hazard attribution / movement / subsidence.
- [x] Define uncertainty, outputs and evaluation.
- [ ] Confirm feasible real-scene parameters with M1 and M3.
- [ ] Implement and empirically evaluate modules in subsequent tasks.

## References
1. Copernicus Sentinel-1 GRD and processing options: https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S1GRD.html
2. Copernicus Sentinel-1 catalog/products: https://documentation.dataspace.copernicus.eu/Data/Sentinel1.html
3. ASF HyP3 RTC guide: https://hyp3-docs.asf.alaska.edu/hyp3-docs/guides/rtc_product_guide/
4. Digital Earth Africa Sentinel-1 NRB specifications: https://docs.digitalearthafrica.org/en/latest/data_specs/Sentinel-1_specs.html


## Integration contract decision (v1.1)
The team integration baseline is defined in `interface-contract-v1.md` and illustrated by `manifest-template.json`. It selects Sentinel-1 IW RTC terrain gamma0 in linear power, Float32 GeoTIFF, VV mandatory with optional paired VH, UTM shared grids, real scene provenance, explicit masks and a georeferenced M2→M3 output contract. These are design decisions awaiting implementation and three-member interface sign-off; they do not assert that real scenes have been processed or science validated.
