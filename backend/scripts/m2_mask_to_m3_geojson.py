#!/usr/bin/env python3
"""Convert an actual M2 T09 four-class GeoTIFF mask to an M3 EPSG:4326 candidate-change GeoJSON.
No fabricated data, no inference about disaster types, and no scientific validation claim.
"""
import argparse, json, sys
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mask',type=Path,required=True,help='M2 change_mask_VV.tif or change_mask_VH.tif')
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--min-pixels',type=int,default=1,help='Minimum connected-region pixel count; default 1')
    a=ap.parse_args()
    if a.min_pixels != 1:
        ap.error('Only --min-pixels 1 supported currently; filtering would alter area estimates')
    try:
        import numpy as np
        import rasterio
        from rasterio.features import shapes
        from rasterio.warp import transform_geom
    except ImportError as e:
        sys.exit(f'Missing dependency: {e}. Install rasterio numpy.')
    if not a.mask.is_file(): sys.exit(f'Not found: {a.mask}')
    with rasterio.open(a.mask) as ds:
        if ds.count!=1 or ds.crs is None: sys.exit('Mask must have one band and georeferencing CRS')
        arr=ds.read(1)
        distinct=np.unique(arr)
        if not np.isin(distinct,[0,1,2,255]).all():
            sys.exit(f'Unexpected mask values: {distinct.tolist()} (expected only 0,1,2,255)')
        valid=np.isin(arr,[1,2])
        features=[]
        for geom, value in shapes(arr, mask=valid, transform=ds.transform, connectivity=8):
            change_class=int(value)
            if change_class not in (1,2): continue
            geo=transform_geom(ds.crs,'EPSG:4326',geom,precision=8)
            features.append({'type':'Feature','properties':{'change_class':change_class,'change_direction': 'radar_backscatter_decrease' if change_class==1 else 'radar_backscatter_increase','evidence_status':'UNVERIFIED','interpretation':'candidate_radar_change_not_confirmed_hazard'},'geometry':geo})
    collection={'type':'FeatureCollection','name':'candidate_change_footprint','features':features}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(collection,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(a.out),'features':len(features),'crs':'EPSG:4326','scientific_status':'UNVERIFIED'}))

if __name__=='__main__': main()
