"""SPECTRA-SAR M3/T03: read real GeoJSON and GeoTIFF without altering content."""
from __future__ import annotations
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any
import rasterio
from shapely.geometry import shape

class GeoDataError(ValueError):
    pass

@dataclass(frozen=True)
class VectorDataset:
    path: Path
    features: list[dict[str, Any]]
    crs: str

@dataclass(frozen=True)
class RasterDataset:
    path: Path
    metadata: dict[str, Any]


def load_geojson(path: str | Path, max_bytes: int = 100_000_000) -> VectorDataset:
    p = Path(path)
    if not p.is_file(): raise GeoDataError(f'Missing GeoJSON: {p}')
    if p.stat().st_size > max_bytes: raise GeoDataError('GeoJSON too large')
    try: raw = json.loads(p.read_text(encoding='utf-8'))
    except (UnicodeError, json.JSONDecodeError) as e: raise GeoDataError(f'Invalid GeoJSON JSON: {e}') from e
    if not isinstance(raw, dict): raise GeoDataError('GeoJSON root must be an object')
    declared_crs = raw.get('crs')
    if declared_crs is not None:
        # RFC7946 GeoJSON coordinates are WGS84 long/lat; reject legacy CRS declarations
        crs_name = (declared_crs.get('properties', {}).get('name', '') if isinstance(declared_crs, dict) else '')
        if crs_name.upper() not in ('EPSG:4326','URN:OGC:DEF:CRS:OGC:1.3:CRS84'):
            raise GeoDataError(f'Unsupported GeoJSON CRS: {crs_name!r}')
    if raw.get('type') == 'FeatureCollection':
        features = raw.get('features')
        if not isinstance(features, list): raise GeoDataError('FeatureCollection.features must be a list')
    elif raw.get('type') == 'Feature': features = [raw]
    elif raw.get('type') in ('Polygon', 'MultiPolygon'): features = [{'type':'Feature','properties':{},'geometry':raw}]
    else: raise GeoDataError('Expected FeatureCollection, Feature, or Polygon/MultiPolygon')
    return VectorDataset(p, features, 'EPSG:4326')


def load_geotiff(path: str | Path) -> RasterDataset:
    p = Path(path)
    if not p.is_file(): raise GeoDataError(f'Missing raster: {p}')
    try:
        with rasterio.open(p) as ds:
            meta = {'driver':ds.driver,'crs':str(ds.crs) if ds.crs else None,
                    'width':ds.width,'height':ds.height,'count':ds.count,
                    'dtype':list(ds.dtypes),'nodata':ds.nodata,
                    'transform':list(ds.transform)[:6],
                    'bounds':list(ds.bounds),'pixel_size':list(ds.res),
                    'units':list(ds.units)}
    except rasterio.errors.RasterioIOError as e: raise GeoDataError(f'Raster cannot be opened: {e}') from e
    return RasterDataset(p,meta)
