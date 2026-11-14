#!/usr/bin/env python3
"""SPECTRA-SAR M1 T05 finish: check REAL downloaded GCOV HHHH raster pair.

This script NEVER fabricates source observations and NEVER asserts detected flooding.
Needs rasterio + numpy for geospatial QA. Outputs QA and small browse previews.
Do not place Earthdata login credentials in this folder.
"""
from __future__ import annotations
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'output'
EXPECTED = {
    'before': ('20260920', 'G4319985062-ASF'),
    'after': ('20261002', 'G4338819270-ASF'),
}
AOI = (-134.70, 58.33, -134.40, 58.55)

def hash_file(p):
    d = hashlib.sha256()
    with open(p, 'rb') as f:
        for block in iter(lambda: f.read(2 * 1024 * 1024), b''):
            d.update(block)
    return d.hexdigest()

def inspect_tif(path, role, preview=False):
    try:
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
        from rasterio.windows import from_bounds, Window
        from rasterio.enums import Resampling
    except ImportError:
        return {'status': 'NEEDS_RASTERIO', 'reason': 'Run: python3 -m pip install rasterio numpy'}
    p = Path(path).expanduser().resolve()
    data = {'path': str(p), 'exists': p.is_file(), 'expected_date': EXPECTED[role][0],
            'expected_concept_id': EXPECTED[role][1], 'status': 'PENDING'}
    if not p.is_file():
        data['status'] = 'FILE_MISSING'
        return data
    if p.stat().st_size < 100:
        data['status'] = 'EMPTY_OR_ERROR_FILE'
        return data
    data['size_bytes'] = p.stat().st_size
    data['sha256'] = hash_file(p)
    try:
        with rasterio.open(p) as ds:
            data.update({'driver': ds.driver, 'bands': ds.count, 'width': ds.width,
                         'height': ds.height, 'dtype': ds.dtypes[0],
                         'crs': str(ds.crs) if ds.crs else None,
                         'nodata': ds.nodata,
                         'transform': list(ds.transform)[:6],
                         'bounds': [float(q) for q in ds.bounds],
                         'pixel_size': list(ds.res),
                         'band_description': ds.descriptions[0] if ds.descriptions else None})
            tags = {str(k):str(v)[:500] for k,v in ds.tags().items()}
            tags.update({f'BAND1_{k}':str(v)[:500] for k,v in ds.tags(1).items()})
            data['tags'] = tags
            if ds.driver != 'GTiff' or ds.crs is None:
                data['status'] = 'MISSING_GEOTIFF_OR_CRS'
                return data
            # The file's name/tags sometimes identify HHHH; cannot infer it from numeric values.
            # Only embedded tags/descriptions count as raster evidence.
            # Our renamed filename is NOT independent evidence of the HHHH layer.
            context = (str(ds.descriptions) + ' ' + str(tags)).upper()
            data['hhhh_identity_in_export_metadata'] = ('HHHH' in context)
            data['source_date_in_filename'] = EXPECTED[role][0] in p.name
            aoi_crs_bounds = transform_bounds('EPSG:4326', ds.crs, *AOI, densify_pts=21)
            xmin = max(aoi_crs_bounds[0], ds.bounds.left)
            ymin = max(aoi_crs_bounds[1], ds.bounds.bottom)
            xmax = min(aoi_crs_bounds[2], ds.bounds.right)
            ymax = min(aoi_crs_bounds[3], ds.bounds.top)
            data['intersects_flood_aoi'] = (xmin < xmax and ymin < ymax)
            if not data['intersects_flood_aoi']:
                data['status'] = 'AOI_NO_INTERSECTION'
                return data
            full = from_bounds(xmin, ymin, xmax, ymax, transform=ds.transform)
            full = full.round_offsets().round_lengths()
            full = full.intersection(Window(0,0,ds.width,ds.height))
            if full.width <= 0 or full.height <= 0:
                data['status'] = 'EMPTY_AOI_WINDOW';return data
            # Downsample cropped AOI for fast, bounded diagnostic preview and QA.
            scale = min(1.0, 768 / max(full.width,full.height))
            size = (max(1, round(full.height*scale)), max(1, round(full.width*scale)))
            arr = ds.read(1,window=full, masked=True, out_shape=size, resampling=Resampling.nearest)
            vals = np.asarray(arr.data, dtype='float64')
            good = (~np.ma.getmaskarray(arr)) & np.isfinite(vals)
            positive = good & (vals > 0)
            data['aoi_sample_valid_fraction'] = round(float(good.mean()), 6)
            data['aoi_sample_positive_fraction'] = round(float(positive.mean()), 6)
            if positive.any():
                pcts = np.percentile(vals[positive], [2, 50, 98])
                data['aoi_positive_percentiles_linear'] = [round(float(z), 9) for z in pcts]
            else:
                data['aoi_positive_percentiles_linear'] = []
            if preview and positive.any():
                try:
                    from PIL import Image
                    scaled = np.clip(10*np.log10(np.maximum(vals,1e-12)), -35, 5)
                    scaled = np.uint8(np.clip((scaled+35)/40*255, 0, 255))
                    scaled[~positive] = 0
                    Image.fromarray(scaled, 'L').save(OUT / f'{role}_radar_preview.png')
                    data['preview'] = f'{role}_radar_preview.png'
                except ImportError:
                    data['preview'] = 'PIL_NOT_INSTALLED'
            data['status'] = ('BASIC_RASTER_PASS' if data['aoi_sample_positive_fraction'] > 0.05
                              else 'AOI_TOO_FEW_POSITIVE_PIXELS')
            return data
    except Exception as e:
        data.update(status='RASTER_OPEN_ERROR', error=f'{type(e).__name__}: {e}')
        return data

def verify_harmony_manifest(role, raster_record):
    """Bind each file to a specific Harmony job and NASA CMR granule by checksum.

    A filename manually renamed to HHHH is never treated as source evidence.
    """
    manifest_path=ROOT / 'reports' / f'{role}-harmony-job.json'
    result={'verified':False,'manifest_path':str(manifest_path),'reason':'NO_HARMONY_MANIFEST'}
    if not manifest_path.is_file():
        return result
    try:
        record=json.loads(manifest_path.read_text(encoding='utf-8'))
        expected_name=f'{role}_HHHH_{EXPECTED[role][0]}.tif'
        checks={
            'status':record.get('status')=='DOWNLOADED_NOT_SCIENCE_VALIDATED',
            'granule_concept':record.get('cmr_granule_concept_id')==EXPECTED[role][1],
            'variable':record.get('variable_requested')=='/science/LSAR/GCOV/grids/frequencyA/HHHH',
            'normalized_filename':record.get('normalized_geotiff')==expected_name,
            'original_hhhh_filename':'HHHH' in record.get('original_geotiff_filename','').upper(),
            'checksum':bool(raster_record.get('sha256')) and raster_record.get('sha256')==record.get('sha256'),
            'file_basename':Path(raster_record.get('path','')).name==expected_name,
        }
        result.update(verified=all(checks.values()),checks=checks,reason='MATCH' if all(checks.values()) else 'MANIFEST_CHECK_FAILED')
        return result
    except Exception as e:
        result['reason']=f'INVALID_MANIFEST: {type(e).__name__}: {str(e)[:120]}'
        return result

def validate_pair(a, b):
    result={'status':'PENDING', 'science_flood_proven':False, 'matching_hhhh_source_verified':False}
    if a.get('status')!='BASIC_RASTER_PASS' or b.get('status')!='BASIC_RASTER_PASS':
        result['reason']='Actual GeoTIFFs not present, not georeferenced, or no valid AOI samples'
        return result
    import math
    same_crs = a['crs'] == b['crs']
    same_shape = (a['width'],a['height']) == (b['width'],b['height'])
    same_transform = all(math.isclose(float(x),float(y),rel_tol=0,abs_tol=1e-6)
                         for x,y in zip(a['transform'],b['transform']))
    before_manifest=verify_harmony_manifest('before',a)
    after_manifest=verify_harmony_manifest('after',b)
    provenance_pass=before_manifest['verified'] and after_manifest['verified']
    result.update(source_provenance_verified=provenance_pass,
                  before_provenance=before_manifest,after_provenance=after_manifest,
                  same_crs=same_crs, same_shape=same_shape,
                  same_grid=same_crs and same_shape and same_transform,
                  layer_identity_in_metadata_both=bool(a['hhhh_identity_in_export_metadata'] and b['hhhh_identity_in_export_metadata']),
                  source_date_in_filename_both=bool(a['source_date_in_filename'] and b['source_date_in_filename']))
    if not result['same_grid']:
        result.update(status='NEEDS_GEOSPATIAL_ALIGNMENT',reason='Pixel grid/CRS differ; M2 must not directly subtract arrays')
    elif not (result['layer_identity_in_metadata_both'] or provenance_pass):
        result.update(status='NEEDS_LAYER_CONFIRMATION',reason='Neither embedded raster metadata nor verified Harmony manifests establish HHHH identity')
    elif not provenance_pass:
        result.update(status='NEEDS_PROVENANCE_CONFIRMATION',reason='Raster grids usable, but NASA granule-to-file checksum provenance has not been established')
    else:
        result.update(status='BASIC_PAIR_READY_FOR_M2',reason='Grids, AOI coverage, and exported HHHH layer names pass; flood inference still requires science analysis')
    return result

def main():
    p = argparse.ArgumentParser(description='Verify two actual NISAR GCOV GeoTIFF files, not catalog metadata')
    p.add_argument('--before',required=True, help='Sep 20 2026 HHHH GeoTIFF path')
    p.add_argument('--after',required=True, help='Oct 2 2026 HHHH GeoTIFF path')
    args=p.parse_args()
    OUT.mkdir(exist_ok=True)
    b=inspect_tif(args.before,'before',preview=True)
    a=inspect_tif(args.after,'after',preview=True)
    pair=validate_pair(b,a)
    report={ 'task':'M1-T05','timestamp_utc':datetime.now(timezone.utc).isoformat(),
             'sources':'NASA CMR GCOV granules with concept IDs noted per input (not independently authenticated by this script)',
             'data_origin_verified_independently':False,
             'local_harmony_job_trace_verified':bool(pair.get('source_provenance_verified')), 
             'before':b,'after':a,'pair':pair,
             'limitations':['A basic GIS check is not a flood detection validation',
                            'Confirm filename-to-granule association and the Harmony job record before scientific claims',
                            'QA uses a sampled subset of the AOI and does not assess all raster pixels'] }
    target=OUT / 't05-real-data-qa.json'
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    print('BEFORE:',b['status']);print('AFTER:',a['status']);print('PAIR:',pair['status']);print('REPORT:',target)
    if pair['status']=='BASIC_PAIR_READY_FOR_M2':
        print('NEXT: pass verified real raster paths, Harmony manifests, and report to M2. Flood event evidence still requires scientific analysis')
        return 0
    print('NEXT: inspect report and fix missing file/layer/geometric alignment')
    return 2

if __name__=='__main__':
    sys.exit(main())
