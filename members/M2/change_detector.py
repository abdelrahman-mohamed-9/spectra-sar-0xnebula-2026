"""T05: reproducible SAR RTC log-ratio change candidate detector.

This is a *radiometric change screen*, NOT semantic event classification.
Input: paired M1 RTC gamma0 linear-power images, same pixel grid.
No subpixel registration correction is performed here.
"""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import sys
import numpy as np
import rasterio
from data_loader import load_manifest, safe_pair_file, iter_pair_tiles
from input_validator import inspect_pair

NODATA_SCORE = -9999.0
NODATA_MASK = 255


def log_ratio_db(before, after, valid):
    """10 log10(after/before) (power ratio), retaining sign; nan at invalid pixels."""
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    v = np.asarray(valid, dtype=bool)
    if b.shape != a.shape or a.shape != v.shape:
        raise ValueError('Shape mismatch')
    ok = v & np.isfinite(b) & np.isfinite(a) & (b > 0) & (a > 0)
    score = np.full(b.shape, np.nan, dtype=np.float32)
    # subtraction of log values reduces risk of overflow in ratio
    with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
        score[ok] = (10.0 / math.log(10.0) * (np.log(a[ok]) - np.log(b[ok]))).astype(np.float32)
    return score


def classify_ratio(score, threshold_db=3.0):
    """0 no candidate, 1 decrease, 2 increase, 255 invalid."""
    if not math.isfinite(threshold_db) or threshold_db <= 0:
        raise ValueError('threshold_db must be finite and > 0')
    s = np.asarray(score)
    labels = np.full(s.shape, NODATA_MASK, dtype=np.uint8)
    finite = np.isfinite(s)
    labels[finite] = 0
    labels[finite & (s <= -threshold_db)] = 1
    labels[finite & (s >= threshold_db)] = 2
    return labels


def _profile(src, dtype, nodata, *, compress='deflate'):
    profile = src.profile.copy()
    profile.update(driver='GTiff', count=1, dtype=dtype, nodata=nodata,
                   compress=compress, predictor=3 if dtype == 'float32' else 1,
                   tiled=src.width>=16 and src.height>=16)
    if src.width < 16 or src.height < 16:
        profile.pop('blockxsize',None); profile.pop('blockysize',None)
    else:
        # Some source profiles may have non-16-aligned blocks; let GDAL pick stable ones.
        profile['blockxsize'] = 256
        profile['blockysize'] = 256
    return profile


def run_detection(pair_dir, output_dir, *, polarization='VV', threshold_db=3.0,
                  tile_size=512, allow_unverified_registration=False):
    """Run after T02 validation. Explicitly mark registration as unverified if bypassed.

    Returns structured summary. Does not use synthetic input in production.
    """
    if polarization not in ('VV','VH','HHHH'):
        raise ValueError('Unsupported polarization')
    if tile_size <= 0 or not math.isfinite(threshold_db) or threshold_db <= 0:
        raise ValueError('Invalid tile/threshold')
    root=Path(pair_dir).resolve(); out=Path(output_dir).resolve()
    if out == root or root in out.parents or out in root.parents:
        raise ValueError('Output must be separate from input directory hierarchy')
    qa=inspect_pair(root)
    if qa['status']=='REJECT':
        raise ValueError('T02 REJECT: '+'; '.join(qa['errors']))
    if not allow_unverified_registration:
        raise ValueError('T04 subpixel registration is unverified; use --allow-unverified-registration only for exploratory output, not scientific approval')
    manifest=load_manifest(root)
    if polarization not in manifest['polarizations']:
        raise ValueError(f'{polarization} is not available in manifest')
    before_path=safe_pair_file(root,manifest['before']['raster_files'][polarization]);
    out.mkdir(parents=True,exist_ok=True)
    names={'score':f'change_score_db_{polarization}.tif',
           'mask':f'change_mask_{polarization}.tif',
           'valid':f'valid_mask_{polarization}.tif'}
    with ExitStack() as stack:
        src=stack.enter_context(rasterio.open(before_path))
        score_dst=stack.enter_context(rasterio.open(out/names['score'],'w',**_profile(src,'float32',NODATA_SCORE)))
        mask_dst=stack.enter_context(rasterio.open(out/names['mask'],'w',**_profile(src,'uint8',NODATA_MASK)))
        valid_dst=stack.enter_context(rasterio.open(out/names['valid'],'w',**_profile(src,'uint8',0)))
        counts={'valid_pixels':0,'decrease_pixels':0,'increase_pixels':0,'unchanged_pixels':0,'invalid_pixels':0}
        for tile in iter_pair_tiles(root,polarization=polarization,tile_size=tile_size):
            score=log_ratio_db(tile.before,tile.after,tile.valid)
            labels=classify_ratio(score,threshold_db)
            valid=np.isfinite(score)
            counts['valid_pixels']+=int(np.count_nonzero(valid))
            counts['decrease_pixels']+=int(np.count_nonzero(labels==1))
            counts['increase_pixels']+=int(np.count_nonzero(labels==2))
            counts['unchanged_pixels']+=int(np.count_nonzero(labels==0))
            counts['invalid_pixels']+=int(np.count_nonzero(labels==255))
            score_dst.write(np.where(valid,score,NODATA_SCORE).astype('float32'),1,window=tile.window)
            mask_dst.write(labels,1,window=tile.window)
            valid_dst.write(valid.astype('uint8'),1,window=tile.window)
        score_dst.update_tags(units='dB', quantity='10log10(after_gamma0/before_gamma0)',
                              interpretation='signed_radiometric_change_not_event_classification')
        mask_dst.update_tags(classes='0:no_candidate;1:backscatter_decrease;2:backscatter_increase;255:invalid')
    px=abs(float(src.transform.a)*float(src.transform.e))
    area=px/1e6
    result={'task':'M2-T05','schema_version':'1.0','pair_id':manifest['pair_id'],
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'status':'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED',
        'method':'signed_log_ratio_db_threshold', 'threshold_db':threshold_db,
        'polarization':polarization,'input_radiometry':('nisar_gcov_diagonal_linear_power' if manifest.get('sensor')=='NISAR' else 'gamma0_terrain_linear_power'),
        'registration_status':'UNVERIFIED_SUBPIXEL','t02_status':qa['status'],
        't02_warnings':qa['warnings'],
        'counts':counts,'pixel_area_m2':px,
        'candidate_change_area_km2':round((counts['decrease_pixels']+counts['increase_pixels'])*area,6),
        'estimated_area_not_ground_truth':True,
        'files':names,
        'caveats':['Threshold is a heuristic, not a calibrated false-alarm probability.',
                   'Backscatter difference can be caused by rain, soil moisture, vegetation, viewing geometry, and residual alignment.',
                   'M2 T04 integer-pixel checks do not certify <=0.5 pixel residual; subpixel QA still required.',
                   'Area represents candidate pixels only; no flood/fire/damage labels are inferred.',
                   'No training dataset, validation accuracy, or calibrated confidence is asserted.']}
    (out/'change-summary.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='T05 change candidates from real matched M1 Sentinel-1 RTC rasters')
    p.add_argument('pair_dir');p.add_argument('--out',required=True)
    p.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    p.add_argument('--threshold-db',type=float,default=3.0)
    p.add_argument('--tile-size',type=int,default=512)
    p.add_argument('--allow-unverified-registration',action='store_true')
    args=p.parse_args()
    try:
        result=run_detection(args.pair_dir,args.out,polarization=args.polarization,
                             threshold_db=args.threshold_db,tile_size=args.tile_size,
                             allow_unverified_registration=args.allow_unverified_registration)
    except (ValueError,RuntimeError,OSError,rasterio.errors.RasterioError) as e:
        print(f'T05 ERROR: {e}',file=sys.stderr);return 3
    print(json.dumps({'status':result['status'],'output':str(Path(args.out).resolve()),'counts':result['counts']}))
    return 2 # Explicitly exploratory, not scientific PASS

if __name__=='__main__': raise SystemExit(main())
