"""Strict RFC 7946 polygon handling for API and PostGIS handoff.

This module validates geometry; it does not infer SAR measurement quality.
Input/output longitude/latitude coordinates are WGS84 (EPSG:4326).
"""
from __future__ import annotations
import json
import math
from typing import Any
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.geometry.base import BaseGeometry
from shapely.validation import explain_validity

MAX_VERTICES = 20_000


class InvalidGeoJSON(ValueError):
    pass


def parse_polygon_geometry(value: dict[str, Any]) -> MultiPolygon:
    if not isinstance(value, dict) or value.get('type') not in ('Polygon', 'MultiPolygon'):
        raise InvalidGeoJSON('Expected GeoJSON Polygon or MultiPolygon')
    if set(value) - {'type', 'coordinates'}:
        raise InvalidGeoJSON('Only geometry type and coordinates are accepted')
    n = 0
    def check_position(pos: Any):
        nonlocal n
        n += 1
        if n > MAX_VERTICES:
            raise InvalidGeoJSON('Too many coordinates')
        if not isinstance(pos, list) or len(pos) != 2:
            raise InvalidGeoJSON('Positions must be exactly [longitude, latitude]')
        if any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in pos):
            raise InvalidGeoJSON('Coordinates must be finite numbers')
        if not (-180 <= pos[0] <= 180 and -90 <= pos[1] <= 90):
            raise InvalidGeoJSON('Coordinates outside WGS84 bounds')

    polygons = [value.get('coordinates')] if value['type'] == 'Polygon' else value.get('coordinates')
    if not isinstance(polygons, list) or not polygons:
        raise InvalidGeoJSON('Nonempty polygon coordinates required')
    for poly in polygons:
        if not isinstance(poly, list) or not poly:
            raise InvalidGeoJSON('Polygon requires at least one ring')
        for ring in poly:
            if not isinstance(ring, list) or len(ring) < 4:
                raise InvalidGeoJSON('Ring must have at least four positions')
            for position in ring:
                check_position(position)
            if ring[0] != ring[-1]:
                raise InvalidGeoJSON('Ring is not closed')
    try:
        geom = shape(value)
    except (ValueError, TypeError, IndexError, KeyError) as exc:
        raise InvalidGeoJSON('Malformed GeoJSON polygon') from exc
    if geom.is_empty or geom.area <= 0 or not geom.is_valid:
        raise InvalidGeoJSON('Invalid polygon topology: ' + explain_validity(geom))
    if geom.geom_type == 'Polygon':
        return MultiPolygon([geom])
    if geom.geom_type != 'MultiPolygon':
        raise InvalidGeoJSON('Expected polygonal shape')
    return geom


def normalize_multipolygon(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(mapping(parse_polygon_geometry(value))))


def feature_from_postgis(geometry_json: str | dict, *, feature_id: str, properties: dict | None = None) -> dict:
    """Wrap ST_AsGeoJSON output; never fabricate geospatial data."""
    parsed = json.loads(geometry_json) if isinstance(geometry_json, str) else geometry_json
    normalized = normalize_multipolygon(parsed)
    return {'type': 'Feature', 'id': feature_id, 'geometry': normalized, 'properties': properties or {}}
