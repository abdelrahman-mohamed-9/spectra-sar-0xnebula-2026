"""SPECTRA-SAR M3 T02: source configuration, AOI validation, Overpass QL."""
from __future__ import annotations
import json
import math
from pathlib import Path

OVERPASS_URL = 'https://overpass-api.de/api/interpreter'
WORLDPOP_RASTER_URL = 'https://api.worldpop.org/v3/raster'
USER_AGENT = 'SPECTRA-SAR-M3/0.1 (research; contact: configure-before-production)'

class DataSourceError(ValueError):
    pass


def load_aoi(path: str | Path) -> dict:
    """Read EPSG:4326 Polygon/MultiPolygon or a single-feature GeoJSON."""
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if obj.get('type') == 'Feature':
        obj = obj.get('geometry') or {}
    elif obj.get('type') == 'FeatureCollection':
        features = obj.get('features', [])
        if len(features) != 1:
            raise DataSourceError('Provide one AOI polygon Feature, not a multi-feature collection')
        obj = features[0].get('geometry') or {}
    if obj.get('type') not in {'Polygon', 'MultiPolygon'}:
        raise DataSourceError('AOI must be a GeoJSON Polygon/MultiPolygon in EPSG:4326')
    rings = []
    polygons = [obj['coordinates']] if obj['type'] == 'Polygon' else obj['coordinates']
    for polygon in polygons:
        if not polygon or not polygon[0]:
            raise DataSourceError('Polygon has no exterior ring')
        for ring in polygon:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise DataSourceError('Each ring must be closed with at least 4 coordinates')
            rings.append(ring)
    coords = [p for ring in rings for p in ring]
    if not coords or any(len(p) < 2 or not all(math.isfinite(v) for v in p[:2]) or not (-180 <= p[0] <= 180 and -90 <= p[1] <= 90) for p in coords):
        raise DataSourceError('Invalid longitude/latitude coordinate')
    lon = [p[0] for p in coords]; lat = [p[1] for p in coords]
    if max(lon) - min(lon) >= 180:
        raise DataSourceError('Antimeridian AOIs need splitting first')
    if max(lon) == min(lon) or max(lat) == min(lat):
        raise DataSourceError('AOI bounding box is empty')
    return obj


def bbox(aoi: dict) -> tuple[float, float, float, float]:
    polys = [aoi['coordinates']] if aoi['type'] == 'Polygon' else aoi['coordinates']
    pts = [pt for poly in polys for ring in poly for pt in ring]
    return min(p[1] for p in pts), min(p[0] for p in pts), max(p[1] for p in pts), max(p[0] for p in pts)


def overpass_query(aoi: dict, timeout_seconds: int = 60) -> str:
    """BBox candidate fetch; later spatial engine MUST clip geometry to AOI."""
    s, w, n, e = bbox(aoi)
    bb = ','.join(f'{v:.7f}' for v in (s, w, n, e))
    return (f'[out:json][timeout:{int(timeout_seconds)}];('\
            f'way["building"]({bb});'\
            f'way["highway"]({bb});'\
            f'node["amenity"~"^(hospital|school|fire_station|police)$"]({bb});'\
            f'way["amenity"~"^(hospital|school|fire_station|police)$"]({bb});'\
            f');out geom;')

SOURCES = {
    'osm': {'provider': 'OpenStreetMap contributors', 'dataset_name': 'OpenStreetMap via Overpass API', 'license': 'ODbL 1.0', 'source_url': OVERPASS_URL, 'limitations': 'Coverage incomplete; bbox fetch, not AOI clipping; relations not included.'},
    'worldpop': {'provider': 'WorldPop / University of Southampton', 'dataset_name': 'Global2 R2025A population count', 'dataset_version': 'R2025A v1', 'license': 'CC BY 4.0', 'source_url': WORLDPOP_RASTER_URL, 'limitations': 'Modelled resident population per grid cell, not real-time occupancy.'},
}
