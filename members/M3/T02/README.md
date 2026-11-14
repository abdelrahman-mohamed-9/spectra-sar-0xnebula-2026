# SPECTRA-SAR — M3 / Phase 1 / T02: Geospatial Data Sources Integration

**Status:** Implementation and offline unit tests supplied. **No live downloads performed or verified in this delivery.**

## What the code really does

- `geo_sources.py`: loads real user-supplied EPSG:4326 AOI GeoJSON and constructs Overpass QL queries for OSM buildings, roads and selected facilities.
- `data_fetcher.py`: POSTs to Overpass for source OSM elements, exports candidate points/lines/polygons as GeoJSON; POSTs AOI/year to WorldPop API v3 raster for a genuine population-count GeoTIFF. Saves SHA-256, timestamp, URLs and source provenance.
- **No fabricated satellite data, population or exposure metrics.** No API authentication needed for normal WorldPop v3 limits. Requests can fail due to service restrictions/network. Fails visibly, not silently.

## Installation

```bash
cd M3_Phase1_T02
python -m venv .venv
source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Create your **real** AOI polygon (or a single GeoJSON Feature) at `data/my_aoi.geojson`, EPSG:4326, coordinates **[longitude, latitude]**. Use your selected real project location; this repository intentionally includes no invented event outline.

```bash
python data_fetcher.py --aoi data/my_aoi.geojson --year 2025 --resolution 100m --out data/raw
# or one source at a time:
python data_fetcher.py --aoi data/my_aoi.geojson --year 2025 --source osm
python -m unittest discover -s tests -v
```

Outputs: `osm_overpass_raw.json`, `osm_features.geojson`, `worldpop_population_2025_100m.tif`, `source_manifest.json` (only source files from successful downloads are created).

## Important limitations and next tasks

- Overpass query uses the AOI **bounding box**. Returned OSM ways can cross its boundary. **T04 must clip to actual polygon** before impact counts; do not call these `affected` or `exposed` structures yet. OSM relations are not resolved and OSM data can be incomplete.
- Some `way` polygons (e.g. multipolygon relations or unusual tagging) are not converted. T03/T04 should use an OSM-aware geometry library for final analysis and perform topology validation.
- AOI parser checks basic coordinate/ring format but not polygon self-intersections; T03 must run Shapely validity checks. It does not handle antimeridian crossing.
- Downloaded TIFF is signature-checked, but **T03 must inspect its georeferencing, actual NoData, dimensions, extent, coverage and units** via rasterio; it is not evidence of any real disaster.
- WorldPop is modelled resident population for the specified year, not real-time people present during a disaster. Select year aligned with the event date.
- Do not count generic SAR differences as floods/fires: the validated M2 hazard footprint is required for downstream exposure statistics.
- Overpass public servers have load policies: keep AOIs moderate, avoid rapid automated requests, use an approved own instance/extract for heavy production work. Set a project-specific User-Agent contact before deployment.
- Source licenses: OpenStreetMap ODbL 1.0 (attribution and potential share-alike), WorldPop Global2 CC BY 4.0; verify precise redistribution and attribution requirements before publishing.
- Do not treat a successful unit test as proof that external providers respond successfully. Run the CLI against a real AOI to validate live integration.

## References

- WorldPop v3 API: https://api.worldpop.org/v3/documentation
- WorldPop licensing: https://api.worldpop.org/v3/about
- Overpass API: https://wiki.openstreetmap.org/wiki/Overpass_API
- OSM copyright: https://www.openstreetmap.org/copyright
