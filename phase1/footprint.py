#!/usr/bin/env python3
"""Convert real M2 change-candidate raster into M3 hazard candidate polygons.
Exploratory only. Does NOT assert flood/disaster class or validated confidence.
"""
import argparse, json, hashlib, math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import shapes, sieve
from rasterio.warp import transform_geom


def make_footprint(mask_path, out_path, *, min_pixels=9, max_polygons=100000, delivery_json=None):
    mask_path, out_path = Path(mask_path).resolve(), Path(out_path).resolve()
    if min_pixels < 1 or max_polygons < 1: raise ValueError('min_pixels and max_polygons must be positive')
    with rasterio.open(mask_path) as ds:
        if ds.count != 1 or not ds.crs: raise ValueError('One-band georeferenced raster required')
        if not ds.crs.is_projected or ds.crs.linear_units.lower() not in ('metre','meter','metres','meters'):
            raise ValueError('Projected metric CRS required for area')
        data = ds.read(1)
        if not np.isin(data, [0,1,2,255]).all(): raise ValueError('Unexpected M2 change classes')
        valid = (data != 255)
        candidate = ((data == 1) | (data == 2)).astype('uint8')
        raw_pixels=int(candidate.sum())
        filtered = sieve(candidate, size=min_pixels, connectivity=8, mask=valid.astype('uint8')) if min_pixels>1 else candidate
        filtered = ((filtered == 1) & (candidate == 1)).astype('uint8')
        kept_pixels=int(filtered.sum())
        polygons=[]
        for geom,val in shapes(filtered, mask=(filtered == 1), transform=ds.transform, connectivity=8):
            if int(val)!=1: continue
            if len(polygons)>=max_polygons: raise ValueError('Polygon count exceeds safety limit; change min_pixels or AOI explicitly')
            g = transform_geom(ds.crs, 'EPSG:4326', geom, precision=7)
            polygons.append({'type':'Feature','geometry':g,'properties':{'source':'M2 signed log-ratio candidate mask','hazard_type':'unknown',
                           'evidence_status':'UNVERIFIED','scientific_approval':False,
                           'registration_subpixel_certified':False}})
        info={'raster':str(mask_path),'raw_candidate_pixels':raw_pixels,'kept_candidate_pixels':kept_pixels,
              'excluded_candidate_pixels':raw_pixels-kept_pixels,'min_pixels':min_pixels,'max_polygons':max_polygons,
              'output_polygons':len(polygons),'raster_crs':str(ds.crs),'raster_transform':list(ds.transform)[:6],
              'pixel_area_m2':abs(ds.transform.a*ds.transform.e-ds.transform.b*ds.transform.d),
              'scientific_approval':False,'interpretation':'radiometric_change_candidates_NOT_confirmed_hazard'}
    if delivery_json:
        delivery=json.loads(Path(delivery_json).read_text())
        if delivery.get('scientific_approval') is not False: raise ValueError('M2 exploratory-only guard failed')
        info['m2_delivery_pair_id']=delivery.get('pair_id')
    doc={'type':'FeatureCollection','features':polygons,'metadata':info}
    out_path.parent.mkdir(parents=True,exist_ok=True)
    out_path.write_text(json.dumps(doc,ensure_ascii=False,allow_nan=False)+'\n')
    out_path.with_suffix('.summary.json').write_text(json.dumps(info,indent=2)+'\n')
    return info


def main():
    p=argparse.ArgumentParser(description='M2 candidate GeoTIFF -> M3 EPSG:4326 GeoJSON (UNVERIFIED)')
    p.add_argument('--mask',required=True);p.add_argument('--out',required=True)
    p.add_argument('--min-pixels',type=int,default=9)
    p.add_argument('--delivery-json')
    a=p.parse_args();print(json.dumps(make_footprint(a.mask,a.out,min_pixels=a.min_pixels,delivery_json=a.delivery_json),indent=2))
if __name__=='__main__':main()
