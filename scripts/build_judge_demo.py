"""Build an offline, evidence-backed judge experience from bundled real Sentinel-1 tiles.

Not a hazard forecast: flood benchmark labels are used for *retrospective evaluation*
and are never used in detection or priority sorting.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image
from pyproj import Geod
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[1]
CHIP = ROOT / 'data/benchmark/Spain_1167260'
OUTPUT = ROOT / 'judge-demo'
GEOD = Geod(ellps='WGS84')


def checksum(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inputs(root: Path = ROOT):
    paths = {key: root / 'data/benchmark/Spain_1167260' / (key+'.tif') for key in ('before','after','labels')}
    paths['prediction'] = root / 'results-phase3/external-ml-prediction.tif'
    paths['benchmark_source'] = root / 'data/benchmark-source.json'
    paths['evaluation'] = root / 'results-phase3/external-evaluation.json'
    return paths


def read_original(paths):
    arrays = {}
    with rasterio.open(paths['before']) as ds:
        base_crs, base_transform, shape = ds.crs, ds.transform, ds.shape
        bounds = ds.bounds
    for key in ('before','after','labels','prediction'):
        with rasterio.open(paths[key]) as ds:
            if ds.crs != base_crs or ds.shape != shape or not ds.transform.almost_equals(base_transform):
                raise ValueError(f'{key} is NOT aligned with the reference tile; refusing silent resampling')
            if ds.count < 1: raise ValueError(key + ' raster has no bands')
            arrays[key] = ds.read(1, masked=True).astype('float64').filled(np.nan)
    return arrays, bounds, base_transform


def score_metrics(truth: np.ndarray, pred: np.ndarray, valid: np.ndarray):
    evaluation_mask = np.isin(truth, (0,1)) & valid & np.isin(pred,(0,1))
    y = truth[evaluation_mask] == 1
    p = pred[evaluation_mask] == 1
    tp, fp, tn, fn = (int(np.count_nonzero(k)) for k in (y&p,~y&p,~y&~p,y&~p))
    return {'tp':tp,'fp':fp,'tn':tn,'fn':fn, 'n':int(len(y)),
            'precision':tp/(tp+fp) if tp+fp else None,
            'recall':tp/(tp+fn) if tp+fn else None,
            'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
            'iou':tp/(tp+fp+fn) if tp+fp+fn else None}


def latitude_pixel_area(lat_center, lon_w, lon_e, dlat):
    area, _ = GEOD.polygon_area_perimeter([lon_w,lon_e,lon_e,lon_w],
                                          [lat_center-dlat/2,lat_center-dlat/2,lat_center+dlat/2,lat_center+dlat/2])
    return abs(area)


def regions(pred, delta, transform, limit=25):
    binary = pred == 1
    comps, n = ndimage.label(binary, structure=np.ones((3,3),dtype='uint8'))
    sizes = np.bincount(comps.ravel())
    indices = sorted((i for i in range(1,n+1) if sizes[i]>=9), key=lambda i:(-sizes[i],i))[:limit]
    coords = ndimage.find_objects(comps)
    pix_height = abs(transform.e)
    meter_x = abs(transform.a)*111320*math.cos(math.radians(38.15))
    meter_y = pix_height*111132
    zones = []
    for rank, idx in enumerate(indices,1):
        rs, cs = coords[idx-1]
        local = comps[rs,cs] == idx
        rr, cc = np.where(local)
        r0, c0 = rs.start, cs.start
        rmin,rmax = int(r0+rr.min()),int(r0+rr.max()+1)
        cmin,cmax = int(c0+cc.min()),int(c0+cc.max()+1)
        centroid_r = float(r0+rr.mean()+.5)
        centroid_c = float(c0+cc.mean()+.5)
        longitude, latitude = transform*(centroid_c,centroid_r)
        strength = float(np.nanmedian(abs(delta[rs,cs][local])))
        area_m2 = latitude_pixel_area(latitude,longitude-transform.a/2,longitude+transform.a/2,pix_height)*int(sizes[idx])
        distances = {}
        # Approximate union of a dilation of this contiguous footprint on the native tile grid.
        for meters in (0,50,150,300):
            padding = int(math.ceil(meters/min(meter_x,meter_y)))+2
            p0,p1 = max(0,rmin-padding),min(pred.shape[0],rmax+padding)
            q0,q1 = max(0,cmin-padding),min(pred.shape[1],cmax+padding)
            zone_mask = comps[p0:p1,q0:q1] == idx
            if meters:
                distance = ndimage.distance_transform_edt(~zone_mask, sampling=(meter_y,meter_x))
                dilated=distance<=meters
            else:dilated=zone_mask
            distances[str(meters)] = int(np.count_nonzero(dilated))
        zones.append({
            'id':f'{rank:02d}', 'rank':rank,'pixels':int(sizes[idx]), 'area_m2':round(area_m2,1),
            'median_change_magnitude_db':round(strength,2),
            'center':{'lat':round(float(latitude),6),'lon':round(float(longitude),6)},
            'bbox_px':[cmin,rmin,cmax,rmax],
            'bbox_normalized':[round(cmin/pred.shape[1],6),round(rmin/pred.shape[0],6),round((cmax-cmin)/pred.shape[1],6),round((rmax-rmin)/pred.shape[0],6)],
            'buffer_pixels':distances,
            'priority_reason':'Large, contiguous radar response; inspect before escalating. Not a measured hazard likelihood.',
            'evidence':['data/benchmark/Spain_1167260/before.tif','data/benchmark/Spain_1167260/after.tif','results-phase3/external-ml-prediction.tif']})
    return zones


def image_gray(data, vmin, vmax):
    norm = np.clip((np.nan_to_num(data,nan=vmin)-vmin)/(vmax-vmin),0,1)
    vals = (255*np.power(norm,0.72)).astype('uint8')
    return Image.fromarray(np.stack([vals]*3,axis=-1),'RGB')


def output_images(output, arr, valid, methods):
    p_low,p_high=np.nanpercentile(np.concatenate([arr['before'][valid],arr['after'][valid]]),(2,98))
    for key in ('before','after'):
        image_gray(arr[key],p_low,p_high).save(output/(key+'.png'),optimize=True)
    base=np.asarray(image_gray(arr['after'],p_low,p_high)).copy()
    for key,pred in methods.items():
        img=base.copy()
        mask=pred==1
        img[mask] = (.35*img[mask]+.65*np.array([247,140,58])).astype('uint8')
        Image.fromarray(img).save(output/(key+'-overlay.png'),optimize=True)
    img=base.copy()
    truth=(arr['labels']==1) & valid
    img[truth] = (.3*img[truth]+.7*np.array([49,217,167])).astype('uint8')
    Image.fromarray(img).save(output/'reference-overlay.png',optimize=True)
    diff=arr['after']-arr['before']
    norm=np.clip(diff/7,-1,1)
    positive=np.clip(norm,0,1)[...,None]
    negative=np.clip(-norm,0,1)[...,None]
    rgb=np.clip(np.asarray(base,dtype=float)*.65+negative*np.array([47,123,244])+positive*np.array([246,124,94]),0,255).astype('uint8')
    Image.fromarray(rgb).save(output/'delta.png',optimize=True)


def candidate_footprint(mask, affine, equal_crs):
    """Vectorize observed candidate pixels; never vectorize reference labels."""
    from pyproj import Transformer
    from rasterio.features import shapes
    from shapely import transform as shapely_transform
    from shapely.geometry import shape
    from shapely.ops import unary_union
    coordinate_transform = Transformer.from_crs('EPSG:4326', equal_crs, always_xy=True)
    features = [shapely_transform(shape(geom), coordinate_transform.transform, interleaved=False)
                for geom, value in shapes(mask.astype('uint8'), mask=mask, transform=affine, connectivity=8)
                if int(value)==1]
    return unary_union(features)


def attach_population(data, arrays, methods, affine, bounds, population_file, population_source, year):
    """Area-weighted (not confirmed) modeled resident counts, only for a supplied real count raster.

    The supplied file must contain people PER CELL, not persons/km². Missing source coverage
    is never represented as a zero count. Reference labels are never accessed here.
    """
    from pyproj import Transformer
    from shapely import transform as shapely_transform
    from shapely.geometry import Polygon
    import sys
    if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
    from phase2.impact import population_screen
    if not population_file.is_file() or not population_source.strip() or year<1900 or year>2100:
        raise ValueError('Population input requires existing count GeoTIFF, verified publisher/source and valid year')
    center_lat=(bounds.bottom+bounds.top)/2
    center_lon=(bounds.left+bounds.right)/2
    equal_crs=f'+proj=laea +lat_0={center_lat:.8f} +lon_0={center_lon:.8f} +datum=WGS84 +units=m +no_defs'
    transformer=Transformer.from_crs('EPSG:4326',equal_crs, always_xy=True)
    outline=Polygon([affine*pt for pt in ((0,0),(arrays['before'].shape[1],0),
                     (arrays['before'].shape[1],arrays['before'].shape[0]),(0,arrays['before'].shape[0]))])
    study=population_screen(population_file,shapely_transform(outline,transformer.transform,interleaved=False),equal_crs)
    results={}
    from scipy.ndimage import label
    for method,pred in methods.items():
        footprint=candidate_footprint(pred==1,affine,equal_crs)
        results[method]=population_screen(population_file,footprint,equal_crs)
        components,n=label(pred==1,structure=np.ones((3,3),dtype='uint8'))
        sizes=np.bincount(components.ravel())
        kept=sorted((idx for idx in range(1,n+1) if sizes[idx]>=9),key=lambda idx:(-sizes[idx],idx))[:25]
        assert len(kept)==len(data['zones'][method])
        for zone,idx in zip(data['zones'][method],kept):
            geometry=candidate_footprint(components==idx,affine,equal_crs)
            zone['population_by_radius']={}
            for meters in (0,50,150,300):
                region=geometry.buffer(meters) if meters else geometry
                screen=population_screen(population_file,region,equal_crs)
                zone['population_by_radius'][str(meters)]=screen
    status='AREA_WEIGHTED_MODEL_ESTIMATE' if (study['estimated_residents'] is not None and
                      all(v['estimated_residents'] is not None for v in results.values())) else 'INCOMPLETE_SPATIAL_COVERAGE'
    data['population']={
      'status':status,'estimate':results['ml']['estimated_residents'],
      'study_area_estimate':study['estimated_residents'],
      'by_method':results,
      'provenance':{'source':population_source,'year':year,'units':'people_per_cell',
                    'original_filename':population_file.name,'sha256':checksum(population_file)},
      'reason':'Modeled population uniformly distributed inside source cells. Overlap is potential proximity to candidate radar signal, NOT confirmed affected people.'}
    data['limits'].append('Population counts are area-weighted model estimates conditional on source cell uniformity and coverage. Not observed/confirmed affected residents.')
    return data['population']

def build(root=ROOT,output=OUTPUT, population_file=None, population_source=None, population_year=None):
    from string import Template
    root, output = Path(root),Path(output)
    output.mkdir(parents=True,exist_ok=True)
    p=inputs(root)
    for key,value in p.items():
        if not value.is_file():raise FileNotFoundError(f'Missing required {key}: {value}')
    arr,bounds,transform=read_original(p)
    valid=np.isfinite(arr['before'])&np.isfinite(arr['after'])
    delta=arr['after']-arr['before']
    # The fixed screen is the original published project's threshold-only darkening,
    # not retraining on Spain. ML is an already-bundled prediction trained on Ghana/USA.
    baseline=np.where(valid & (delta<=-3.0),1,0).astype('uint8')
    ml=np.where(valid,arr['prediction'],255).astype('uint8')
    if not np.isin(ml, [0,1,255]).all():raise ValueError('ML prediction must be 0/1/255')
    methods={'baseline':baseline,'ml':ml}
    truth=arr['labels']
    scores={key:score_metrics(truth,pred,valid) for key,pred in methods.items()}
    original=json.loads(p['evaluation'].read_text())
    for key,original_key in [('baseline','fixed_darkening'),('ml','spatial_ml_tuned')]:
        expected=original['evaluation'][original_key]
        for metric in ('tp','fp','tn','fn'):
            if scores[key][metric]!=expected[metric]:
                raise ValueError(f'Benchmark metric mismatch: {key}:{metric}, computed {scores[key][metric]} vs original {expected[metric]}')
    output_images(output,arr,valid,methods)
    zones={key:regions(pred,delta,transform) for key,pred in methods.items()}
    data={'version':'3.4','case_id':'Spain_1167260','name':'Spain · Sentinel-1 holdout','coordinates':{'west':bounds.left,'south':bounds.bottom,'east':bounds.right,'north':bounds.top},
          'source':'https://doi.org/10.5281/zenodo.7946594','license':'CC BY 4.0','creator':'Ritu Yadav',
          'sensor':'Sentinel-1 / first radar band / VV (dB)',
          'acquisition_dates':'Not verified in supplied chip metadata',
          'study_area_note':'The benchmark tile covers approximately 4 × 5 km in southeastern Spain. This is not the Alaska NISAR pair.',
          'population':{'status':'UNAVAILABLE','estimate':None,'reason':'A georeferenced population count layer for this exact Spain tile was not bundled. Do not reuse the zero-valued Alaska crop or assert people affected.'},
          'methods':{'baseline':{'label':'Fixed 3 dB darkening','description':'Unfiltered darkening threshold. No training or labels used.'},
                     'ml':{'label':'Spatial ML (experimental)','description':'Precomputed model trained on Ghana and USA; Spain is a held-out evaluation chip. Not a flood forecast.'}},
          'metrics':scores,'zones':zones,'images':{'before':'before.png','after':'after.png','baseline':'baseline-overlay.png','ml':'ml-overlay.png','reference':'reference-overlay.png','delta':'delta.png'},
          'metrics_scope':'Water/flood-label benchmark, retrospective. Reference labels must not be treated as independent flood/damage verification for unrelated scenes.',
          'priority_policy':'Sort contiguous detected raster regions by size only; boundaries computed from model output without consulting reference labels.',
          'limits':['Sensor images and predictions are real research dataset artifacts; no simulated observations are shown.',
                    'Detected areas are candidate radar responses, not confirmed damaged/flooded areas.',
                    'ML held-out evaluation is one tile, not a scientific generalization claim.',
                    'Population exposure and confirmed casualties/damage are not available from these source files.',
                    'Spatial buffer slider visualizes inspection extent; it is not a population estimate.']}
    if population_file is not None:
        if not population_source or population_year is None:
            raise ValueError('Supply both --population-source and --population-year with --population-raster')
        attach_population(data,arr,methods,transform,bounds,Path(population_file),population_source,int(population_year))
    (output/'mission-data.json').write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    source_hashes={str(file.relative_to(root)):checksum(file) for file in p.values()}
    if population_file is not None:source_hashes['external:population-raster:'+Path(population_file).name]=checksum(Path(population_file))
    delivered={file.name:checksum(file) for file in output.glob('*.png')}
    delivered['mission-data.json']=checksum(output/'mission-data.json')
    (output/'evidence-manifest.json').write_text(json.dumps({'build':'SPECTRA 3.4 offline judge demo','algorithm':'SHA-256',
         'original_source_files':source_hashes,'derived_demo_files':delivered,
         'note':'Local checksums attest content equality, not an independent provider signature. No internet needed after distribution.'},indent=2)+'\n',encoding='utf-8')
    html_template=(root/'scripts/judge_template.html').read_text(encoding='utf-8')
    json_blob=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    # Embedded payload lets the file open on file:// without fetch or a local service.
    html=html_template.replace('/*__MISSION_DATA__*/',json_blob)
    (output/'index.html').write_text(html,encoding='utf-8')
    report={'data_status':'REAL_BENCHMARK_IMAGERY','population':data['population']['status'],
            'baseline':scores['baseline'],'spatial_ml':scores['ml'],
            'review_regions':{key:len(value) for key,value in zones.items()},'output':str(output)}
    return report


if __name__=='__main__':
    args=argparse.ArgumentParser(description=__doc__)
    args.add_argument('--output',type=Path,default=OUTPUT)
    args.add_argument('--population-raster',type=Path,help='Verified GeoTIFF with persons per original source cell, not density')
    args.add_argument('--population-source',help='Publication URL/provider for the modeled population data')
    args.add_argument('--population-year',type=int,help='Population dataset reference year')
    ns=args.parse_args()
    print(json.dumps(build(output=ns.output,population_file=ns.population_raster,
                           population_source=ns.population_source,population_year=ns.population_year),indent=2))
