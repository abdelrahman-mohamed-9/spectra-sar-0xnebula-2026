# T07 — Geospatial Data Integration

## Delivered files

- `src/spectra/geospatial/geojson_converter.py`: finite WGS84 coordinate validation; valid Polygon/MultiPolygon topology using Shapely; normalization to MultiPolygon; GeoJSON Feature conversion of geometries returned by PostGIS. Restricts input to 20,000 positions to prevent unbounded geometry validation.
- `src/spectra/geospatial/geo_service.py`: SQLAlchemy/PostGIS-backed footprint reads and bbox intersection queries using `ST_AsGeoJSON`, `ST_Intersects`, and `ST_MakeEnvelope` (SRID 4326); pagination. Impact searches are scoped to an explicit `project_id` using scene-pair joins.
- `src/spectra/api/v1/geospatial.py`: authenticated v1 geo endpoints and WGS84 bbox parameter validation.
- `tests/test_t07.py`: geometry/bbox negative cases, PostGIS SQL compilation checks, HTTP authentication, and endpoint tests.
- `pyproject.toml`: adds Shapely >=2 dependency.

## HTTP contract (internal only, X-API-Key required)

- `GET /api/v1/geospatial/scenes/within?bbox=30,29,33,32&limit=50&offset=0`
- `GET /api/v1/geospatial/impacts/within?project_id=<UUID>&bbox=30,29,33,32`
- `GET /api/v1/geospatial/scenes/<UUID>/footprint`
- `GET /api/v1/geospatial/impacts/<UUID>/footprint`

BBox values are WGS84 decimal degrees in `minLon,minLat,maxLon,maxLat` order. Responses are GeoJSON Feature or FeatureCollection. A missing geometry is returned as HTTP 404 (same as unknown record). Payloads are generated from records, never simulated satellite observations.

## Notes and remaining real-world verification

1. PostGIS spatial queries were compiled and tested with mocked database sessions. They have NOT been executed against a live PostgreSQL/PostGIS database in this environment.
2. The domain schemas from T05 do **structural** coordinate validation, while this new converter performs strict geometric topology validation. For writing new polygons into the DB from upstream, call `normalize_multipolygon()` before the repository insert; database constraints (`ST_IsValid`) should also be introduced in a later migration if production hardening is required.
3. The current feature endpoints produce GeoJSON intended for internal consumers. `X-API-Key` is NOT end-user authorization/RBAC; project-specific user permissions remain required before exposing them to a public frontend.
4. Bboxes crossing the antimeridian are deliberately rejected. Submit two separate bbox searches. Likewise, polygons crossing the antimeridian require special geometry handling not yet implemented.
5. Geodesic area should be calculated with PostGIS `ST_Area(geom::geography)` instead of planar degrees. This task does not compute SAR changed-area metrics.
6. Integration against authentic Sentinel-1 data and real M1/M2/M3 geometries is pending. No synthetic imagery was presented as verified data.

## Verification commands

```bash
cd backend
python -m pip install -e '.[dev]'
python -m pytest -q
# If Docker is available, configure deploy/.env and start real PostGIS:
cd deploy && docker compose up --build -d
```

## Test status

69/69 unit/API/compiler-level tests passed locally, including the pre-existing 39. Live PostGIS / Docker integration not performed.
