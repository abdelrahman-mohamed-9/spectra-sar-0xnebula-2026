# Optional population input — scientific contract

This feature is **disabled by default** because the original 3.3 ZIP does not contain a georeferenced people-per-cell population raster for the Spain benchmark chip. The default judge demo therefore reports **Unavailable**, not zero and not an invented positive figure.

If a real raster from a documented publisher is supplied, regenerate only the judge exhibit:

```bash
# From SPECTRA-Phase3 (after installing the standard project Python dependencies):
python scripts/build_judge_demo.py \
  --population-raster '/absolute/path/to/Spain-population-counts.tif' \
  --population-source 'Publisher name + public product URL or DOI' \
  --population-year 2025
```

The GeoTIFF must be single-band, georeferenced, north-up and contain **counts of modeled people per source cell** (not population density in persons/km²). It must cover the Spain extent. The calculation uses original population-grid cell polygons and area-weighted intersection with SAR-derived footprints; it records fractional spatial coverage. The operation refuses to produce a number for a candidate footprint with incomplete modeled population coverage. It also calculates an approximation for buffers of 0, 50, 150 and 300 meters around candidate regions, subject to complete coverage. These are modeled spatial overlaps, not confirmed affected residents or damage.

Sources for the input must be independently verified: publication link, year, exact product/tile, geographic coverage and people-per-cell units. The CLI *records* the publisher/source string but cannot independently authenticate its truth. Example test rasters used in software tests are not included in this release.

Existing GHSL 2025 layers in the original NISAR Alaska bundle **must not be moved to Spain or used for Spain counts**. Source years and spatial coverage must be clearly stated in the report.
