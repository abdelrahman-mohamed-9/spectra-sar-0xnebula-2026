"""Real network integrations for OSM/Overpass and WorldPop v3 raster.
No fallbacks to fabricated data. Failed downloads raise exceptions.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import time
import requests

from geo_sources import (DataSourceError, OVERPASS_URL, WORLDPOP_RASTER_URL,
                         SOURCES, USER_AGENT, bbox, load_aoi, overpass_query)

MAX_OSM_BYTES = 80 * 1024 * 1024
MAX_TIFF_BYTES = 250 * 1024 * 1024


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def request_with_retry(session, method, url, attempts=3, **kwargs):
    last = None
    for i in range(attempts):
        try:
            response = session.request(method, url, timeout=(15, 120), **kwargs)
            if response.status_code in (429, 502, 503, 504) and i + 1 < attempts:
                wait = response.headers.get('Retry-After', '')
                try:
                    delay = min(30.0, max(0.0, float(wait)))
                except ValueError:
                    delay = min(15.0, 2 ** i + random.random())
                response.close(); time.sleep(delay); continue
            response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError) as exc:
            last = exc
            if i + 1 == attempts: break
            time.sleep(min(15, 2 ** i))
    raise RuntimeError(f'Source request failed: {url}: {last}')


def save_stream(response, target: Path, max_bytes: int, prefix: bytes | None = None):
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + '.part')
    count = 0; hasher = hashlib.sha256(); head = b''
    try:
        with tmp.open('wb') as handle:
            for chunk in response.iter_content(chunk_size=65536):
                if not chunk: continue
                if len(head) < 8: head = (head + chunk)[:8]
                count += len(chunk)
                if count > max_bytes: raise DataSourceError('Source file exceeds configured byte limit')
                handle.write(chunk); hasher.update(chunk)
        if count == 0: raise DataSourceError('Empty source response')
        if prefix is not None and not head.startswith(prefix):
            raise DataSourceError('Response is not expected file format')
        tmp.replace(target)
        return {'sha256': hasher.hexdigest(), 'size_bytes': count}
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def osm_element_to_feature(element: dict):
    tags = element.get('tags', {})
    t = element.get('type')
    if t == 'node':
        geometry = {'type': 'Point', 'coordinates': [element['lon'], element['lat']]}
    elif t == 'way':
        coords = [[p['lon'], p['lat']] for p in element.get('geometry', [])]
        if len(coords) < 2: return None
        # closed building/amenity ways become polygons, roads stay lines
        is_polygon = len(coords) >= 4 and coords[0] == coords[-1] and ('building' in tags or 'amenity' in tags) and 'highway' not in tags
        geometry = {'type': 'Polygon' if is_polygon else 'LineString', 'coordinates': [coords] if is_polygon else coords}
    else:
        return None
    return {'type':'Feature', 'id':f'{t}/{element["id"]}', 'geometry':geometry,
            'properties': {'osm_type': t, 'osm_id': element['id'], **tags}}


def fetch_osm(aoi: dict, outdir: Path, session=None, endpoint=OVERPASS_URL):
    session = session or requests.Session()
    query = overpass_query(aoi)
    response = request_with_retry(session, 'POST', endpoint,
                                  data={'data':query}, headers={'User-Agent': USER_AGENT}, stream=True)
    raw_path = outdir / 'osm_overpass_raw.json'
    try:
        fingerprint = save_stream(response, raw_path, MAX_OSM_BYTES)
    finally:
        response.close()
    try:
        raw = json.loads(raw_path.read_text(encoding='utf-8'))
        if not isinstance(raw.get('elements'), list): raise ValueError('missing elements')
    except (ValueError, UnicodeError) as exc:
        raw_path.unlink(missing_ok=True)
        raise DataSourceError(f'Overpass returned invalid JSON data: {exc}') from exc
    features = [f for item in raw['elements'] if (f := osm_element_to_feature(item))]
    geo_path = outdir / 'osm_features.geojson'
    geo_path.write_text(json.dumps({'type':'FeatureCollection','features':features}, ensure_ascii=False), encoding='utf-8')
    metadata = {**SOURCES['osm'], **fingerprint, 'downloaded_at_utc':utc_now(),
                'observation_year_or_date':raw.get('osm3s', {}).get('timestamp_osm_base'),
                'crs':'EPSG:4326', 'returned_elements':len(raw['elements']), 'exported_features':len(features),
                'aoi_bbox_south_west_north_east':bbox(aoi),
                'note':'Empty OSM results mean no mapped features returned, NOT proven absence of assets.'}
    return {'files':[str(raw_path),str(geo_path)], 'metadata':metadata}


def fetch_worldpop(aoi: dict, outdir: Path, year: int, resolution='100m', session=None, endpoint=WORLDPOP_RASTER_URL):
    if not 2015 <= year <= 2030: raise DataSourceError('WorldPop v3 year must be 2015..2030')
    if resolution not in ('100m','1km'): raise DataSourceError('Resolution must be 100m or 1km')
    session = session or requests.Session()
    response = request_with_retry(session,'POST',endpoint,
       json={'geojson':aoi,'year':year,'resolution':resolution,'layer':'population'},
       headers={'User-Agent':USER_AGENT,'Accept':'image/tiff'}, stream=True)
    target = outdir / f'worldpop_population_{year}_{resolution}.tif'
    try:
        # Accept both little-endian and big-endian TIFF.
        fingerprint = save_stream(response,target,MAX_TIFF_BYTES)
    finally:
        response.close()
    with target.open('rb') as f: signature=f.read(4)
    if signature not in (b'II*\x00',b'MM\x00*',b'II+\x00',b'MM\x00+'):
        target.unlink(missing_ok=True)
        raise DataSourceError('WorldPop response was not a TIFF (possibly JSON error)')
    metadata={**SOURCES['worldpop'], **fingerprint, 'downloaded_at_utc':utc_now(),
              'observation_year_or_date':year, 'spatial_resolution':resolution,
              'crs':'EPSG:4326', 'units':'people per cell', 'nodata':-99999,
              'population_total_header':response.headers.get('X-Total-Population'),
              'aoi_bbox_south_west_north_east':bbox(aoi),
              'note':'Raster CRS/nodata/geotransform must be verified with rasterio in T03. Not yet an exposure result.'}
    return {'files':[str(target)], 'metadata':metadata}


def main():
    parser=argparse.ArgumentParser(description='Download actual OSM and WorldPop data for a real AOI (T02).')
    parser.add_argument('--aoi', required=True, help='Real AOI GeoJSON Polygon or MultiPolygon in EPSG:4326')
    parser.add_argument('--out', default='data/raw', help='Output folder')
    parser.add_argument('--year', type=int, required=True, help='WorldPop population year 2015..2030')
    parser.add_argument('--resolution', choices=['100m','1km'], default='100m')
    parser.add_argument('--source', choices=['all','osm','worldpop'], default='all')
    args=parser.parse_args()
    aoi=load_aoi(args.aoi)
    outdir=Path(args.out); outdir.mkdir(parents=True, exist_ok=True)
    results={}
    for source,fetch in [('osm',lambda:fetch_osm(aoi,outdir)),('worldpop',lambda:fetch_worldpop(aoi,outdir,args.year,args.resolution))]:
        if args.source not in ('all',source): continue
        try:
            results[source]= {'status':'downloaded', **fetch()}
            print(f'{source}: downloaded real data')
        except Exception as exc:
            results[source]={'status':'failed','error':str(exc)}
            print(f'{source}: FAILED: {exc}')
    manifest={'task':'M3-P1-T02','created_at_utc':utc_now(),'aoi_file':str(args.aoi),
              'aoi_sha256':hashlib.sha256(Path(args.aoi).read_bytes()).hexdigest(),
              'sources':results, 'is_real_observation':True,
              'note':'Source files are real fetched data only if status=downloaded. No hazard/exposure metrics computed.'}
    (outdir/'source_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding='utf-8')
    if any(r['status']=='failed' for r in results.values()): raise SystemExit(1)

if __name__=='__main__': main()
