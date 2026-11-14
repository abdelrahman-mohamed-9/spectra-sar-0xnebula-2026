"""Geodetic area/length utilities for EPSG:4326 geometries, WGS84 ellipsoid."""
from __future__ import annotations
import math
from pyproj import Geod
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection

GEOD = Geod(ellps='WGS84')

def area_m2(geometry):
    """Unsigned ellipsoidal area; suitable for regions not crossing antimeridian."""
    if geometry.is_empty: return 0.0
    if isinstance(geometry, (Polygon, MultiPolygon)):
        area, _ = GEOD.geometry_area_perimeter(geometry)
        return abs(area)
    if isinstance(geometry, GeometryCollection):
        return sum(area_m2(part) for part in geometry.geoms)
    return 0.0

def length_m(geometry):
    """Ellipsoidal line length; polygons have no road length."""
    if geometry.is_empty: return 0.0
    if isinstance(geometry, LineString):
        x,y=geometry.xy
        return float(GEOD.line_length(x,y))
    if isinstance(geometry, (MultiLineString,GeometryCollection)):
        return sum(length_m(part) for part in geometry.geoms)
    return 0.0

def validate_polygon(geometry, label='polygon'):
    if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in ('Polygon','MultiPolygon'):
        raise ValueError(f'{label}: expected nonempty valid Polygon/MultiPolygon')
    xmin,ymin,xmax,ymax=geometry.bounds
    if not all(math.isfinite(c) for c in geometry.bounds) or xmin < -180 or xmax > 180 or ymin < -90 or ymax > 90:
        raise ValueError(f'{label}: coordinates outside EPSG:4326')
    if xmax-xmin >= 180:
        raise ValueError(f'{label}: antimeridian-spanning geometry not supported')
    if area_m2(geometry) <= 0: raise ValueError(f'{label}: zero geodetic area')
