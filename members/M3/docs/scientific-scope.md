# SPECTRA-SAR — M3 / Phase 1 / T01
## Scientific Scope & Impact Assessment Methods

**Document ID:** SPECTRA-M3-P1-T01-SCI  
**Version:** 1.0 — 2026-11-13  
**Owner:** Member 3 — Geospatial & Decision Intelligence  
**Status:** Proposed methods; not yet validated with real event datasets

## 1. Research question
Given a **validated georeferenced hazard footprint** from M2, which areas and mapped human assets are **potentially exposed**, and how much uncertainty comes from hazard mapping, spatial datasets and population models?

This is **exposure screening** and spatial decision support, **not proof of physical damage or injury**, nor an authoritative emergency forecast.

## 2. Hazard-specific interpretation
### Flood (primary)
M2 must define a flood/inundation mask (ideally distinguish *newly inundated* water from permanent water). SAR dark-water detection is imperfect due to wind, rough water, vegetation, shadow, buildings, incidence angle, seasonality, and misregistration. Geographic overlap with the mask is **possible flood exposure**, not flood depth or property damage.

### Wildfire/burn scar (secondary)
Only accept burned-area extent from a method validated for this hazard, potentially with optical indices/authoritative burn maps. **A generic SAR pre/post change mask does not identify burned land reliably by itself.** Overlay can show burned-area exposure but cannot infer severity of damage to individual structures or health impacts.

### Not supported in T01
Glacier displacement and land subsidence need dedicated interferometric/time-series displacement products with units, coherence, temporal assumptions, and uncertainty. They are **not interchangeable** with flood/burn classification masks. Add separate scientific scopes later if those hazards are selected.

## 3. Coordinate reference systems and measurement
1. Receive AOI in EPSG:4326 GeoJSON; validate topology, extent, acquisition timestamps and georeferencing.
2. Reproject for local spatial analysis into a suitable meter-based CRS (local UTM where appropriate), or compute geodesic areas/lengths; handle zone boundaries and special regions carefully.
3. Align rasters consistently: nearest-neighbor for hazard classes; use conservative summation or properly weighted area intersection for extensive quantities (people counts).
4. Exclude NoData from known valid area and report: `valid_hazard_coverage_fraction`, `population_coverage_fraction`.
5. Prevent double-counting from overlapping geometries by unioning hazard polygons and deduplicating OSM IDs.

## 4. Core scientific indicators

### A. Hazard area
For a binary classified hazard footprint H clipped to AOI A:

`Affected area (km²) = Area(H ∩ A) / 1,000,000`

Compute using an appropriate projected equal-area method or geodesic polygon area. Report minimum mapping unit / pixel scale. **NoData is unknown, not unaffected.**

### B. Potential population exposure
Use a **population count** raster (people per cell) rather than population density unless density is multiplied by cell area correctly.

For grid cells Cᵢ with estimated people Pᵢ and area fraction fᵢ = area(Cᵢ ∩ H) / area(Cᵢ), estimate:

`P_exposed ≈ Σ Pᵢ × fᵢ`

This assumes population is uniformly distributed within each cell; it is **an approximation**, especially with 100m/1km cells. Alternative conservative cell-inclusive estimates can give a sensitivity band; this is **not** a calibrated confidence interval. Use the population vintage nearest the event when possible, and record differences. Report e.g. `estimated_people_within_footprint`, not `people_harmed`.

### C. Buildings and critical facilities
- Count **unique mapped building footprints intersecting** the hazard footprint; also report centroid-inside counts separately.
- Count mapped facilities by OSM tag: healthcare, schools, emergency services; verify tag rules in code, avoid inferring missing facilities.
- For polygon overlap, optionally report `intersected_building_footprint_area_m2`; **not** verified damaged floor area.
- Distinguish **mapped building objects** from all real-world buildings.

### D. Transport exposure
For road centerlines Rⱼ with classification tags:

`Roads intersecting hazard (km) = Σ Length(Rⱼ ∩ H) / 1,000`

Deduplicate road segments where needed; classify by OSM highway tags. This is potential spatial exposure, **not confirmation of road closure or unsafe passage**.

### E. Descriptive risk screening
Risk is multi-dimensional: hazard extent/intensity, exposure, vulnerability and capacity. Without independent vulnerability and hazard intensity, **do not call an exposure-only score a validated risk probability**.

T01 permits configurable **screening tiers** (`LOW`, `MODERATE`, `HIGH`, `UNKNOWN`) based on documented local decision rules (e.g., affected-population ranges and critical-facility intersections). Thresholds are **design placeholders**, cannot be asserted as scientifically validated before review. `UNKNOWN` is mandatory when inputs or coverage are insufficient. No fabricated numeric 0–100 'AI confidence' or casualty risk.

## 5. Uncertainty and confidence
Maintain separable quality dimensions:

| Dimension | Evidence | Output guidance |
|---|---|---|
| Hazard classification | Validation metrics, confidence raster, model/source revision, SAR artifacts | Report unvalidated if no independent labels |
| Spatial registration | Pixel size, co-registration error, geometry alignment | Flag if footprints/asset geometry may be offset |
| Population model | WorldPop product/year/resolution, census recency | Estimated exposure, not enumerated people |
| OSM completeness | Local map coverage and tag consistency | `mapped_*` counters; unknown missing inventory |
| Temporal mismatch | Before/after dates, population vintage, OSM snapshot date | Report staleness |
| Source coverage | Missing tiles, API failures, AOI gaps | Coverage fractions, partial results |

Do not manufacture a calibrated uncertainty interval. When possible, estimate method sensitivity by repeating overlays with pixel-scale boundary perturbations and alternative footprint thresholds, clearly labeling **scenario range**, not statistical confidence.

## 6. Validation plan (later implementation in T09)
- Compare flood/burn hazard maps to **independent** event-specific reference polygons/images where data and dates align; compute IoU, precision, recall and document label quality.
- Spatial sanity: identical CRS result independent of representation, geometry union avoids duplicate area, intersections fully inside AOI, correct handling of empty/NoData.
- Population sanity: reaggregation of raster cells is numerically stable; partial-cell calculations preserve people counts within tolerance; estimate never exceeds total population under correctly harmonized coverage.
- Roads and facilities: spot-check geographically diverse randomly sampled matches against original OSM geometries; report missing tags.
- Cross-check against CEMS rapid mapping when accessible, **without assuming every CEMS product is a perfect truth layer**.
- Real-data demonstration must include source file IDs, access date, checksums, maps, measured metrics and methodological caveats. **No real demonstration is claimed in T01.**

## 7. Example interpretation (illustrative wording only)
> The classified flood footprint intersects an estimated number of residents and mapped roads. These are potential exposure estimates derived from remote-sensing and reference spatial datasets; on-the-ground impacts and building damage have not been independently verified.

Do not populate numeric values until genuine source data have been ingested and computed.

## 8. Scientific reproducibility checklist
- [ ] Verified real SAR products, event date, study AOI, M2 mask semantics.
- [ ] Recorded hazard classification validation and NoData handling.
- [ ] Fixed raster/vector alignment strategy and area/length units.
- [ ] Chosen population edition/year/cell semantics and coverage.
- [ ] Recorded OSM snapshot, license/attribution and local completeness.
- [ ] Explicitly separated `exposure` from `damage`, `risk`, and `casualty`.
- [ ] Captured source links/checksums and all analysis parameters.
- [ ] Compared independent event reference data where available.

## 9. References
1. NASA ARSET — *Measuring Floods, Subsidence, and Sea Ice with SAR*, SAR flood detection limitations: https://disasters.nasa.gov/sites/default/files/2023-11/SAR_Part3.pdf
2. WorldPop — Population Counts and data selection: https://hub.worldpop.org/project/categories?id=3
3. WorldPop — Dataset interpretation and population modelling limitations: https://www.worldpop.org/methods/populations/
4. WorldPop API v3 — Count raster and aggregation documentation: https://api.worldpop.org/v3/documentation
5. OpenStreetMap — Licensing/attribution: https://www.openstreetmap.org/copyright
6. Copernicus EMS — Mapping, exposure mapping and available products: https://emergency.copernicus.eu/data/
7. Copernicus EMS — Rapid Mapping definitions: https://mapping.emergency.copernicus.eu/about/
