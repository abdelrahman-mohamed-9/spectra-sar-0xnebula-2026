# Phase 2 data contracts

## Pair

Use a directory produced under the Phase 1 M1 manifest contract. Example structure is the actual `data/nisar/` directory. Preserve truthful acquisition dates, scene IDs, sensor, units, polarization, orbit and processing metadata. The current importer selects the first declared polarization; trim the manifest to the intended common polarization if necessary. NISAR diagonal HHHH and supported Sentinel-1 linear-power inputs are analyzed by the existing Phase 1 validator. dB images must not be labeled linear power.

The registry is local and operator-controlled, not an unauthenticated HTTP upload service. Each imported dataset is copied into `state/datasets/<id>/data`, checked, and pinned in its own `catalog.json`. API calls can only select known IDs. Any later source-byte mismatch fails the job.

The included pair is also copied under `data/real-nisar-oct2026-pair`, so the original Phase 1 local configuration now resolves the same bytes. See `reports/phase1-phase2-source-link.json` for equality with the original import receipt.

## Independent reference

- Single-band uint8 GeoTIFF on the before/common grid, same CRS/transform/shape.
- `0`: independently labeled unchanged; `1`: independently labeled changed; `255`: unlabeled and nodata.
- Include both classes on valid input pixels.
- Companion JSON: `source`, `label_definition`, `labeling_method`, `pair_id`, `sha256`, `independent_of_predictions: true`.
- The declaration must reflect real independence, not model predictions recycled as truth. It is an operator attestation, not independently authenticated by the application.
- Labels are compared against the original baseline, conservative screen and broader-review screen. They are not used to tune either screen.

## Geography

Supply WGS84 FeatureCollections named `population.geojson`, `roads-2.geojson`, `roads-6.geojson`, `roads-8.geojson` and `buildings.geojson`, plus `geography-source.json`. The supplied bundle is an example. Each query must cover the full analysis grid; partial service results flagged by `exceededTransferLimit` are rejected.

Census context properties are `GEOID`, integer `POP100`, `AREALAND` (m²). Buildings use `OBJECTID`; road geometry must be line or multiline. No inference of residents within candidates is made from a block aggregate.

To add a real population raster, extend geography-source.json:

```json
{
  "population_raster": {
    "file": "population-counts.tif",
    "units": "people_per_cell",
    "source": "Actual publisher, dataset, version/year and download reference"
  }
}
```

Keep the existing coverage/source fields as well. The raster must be north-up, one-band, georeferenced, with nonnegative counts and correct nodata. Density values must not be labeled counts. The candidate footprint needs >=99.9% usable population coverage; otherwise the result stays unavailable. Calculations assume uniform population within each source cell. Population inputs are locally cropped and limited to 250,000 intersecting source cells.

Alaska uses EPSG:3338; other regions use a local Lambert azimuthal equal-area projection. Geographic polygons near dateline discontinuities may need preprocessing; this release does not claim global antimeridian handling.

## Results

All jobs have `scientific_approval: false`. `COMPLETED_EXPLORATORY` means the computations, checks and persistence finished. `FAILED` means the worker could not safely complete the analysis. Restart marks interrupted running jobs failed; submit a new job to retry. Source snapshots and output receipts are immutable per run.
