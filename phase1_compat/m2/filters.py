"""SPECTRA-SAR M2 T03: masked, halo-aware Lee speckle filter on linear gamma0 power.

Works on real, M1-prepared RTC GeoTIFF pairs; never downloads or fabricates SAR data.
CLI: python filters.py /path/to/pair --out /path/to/output --window 7 --looks 4
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from scipy.ndimage import uniform_filter

from data_loader import load_manifest, safe_pair_file
from input_validator import inspect_pair


def masked_lee(image: np.ndarray, valid: np.ndarray, *, window: int = 7, looks: float = 4.0, min_count: int = 3) -> np.ndarray:
    """Local-statistics Lee-family intensity filter (not 'Enhanced Lee').

    Noise variance estimated as local_mean**2 / looks; local signal variance
    estimated as max(observed_variance - noise_variance, 0). Filter in LINEAR
    POWER, not dB. Invalid pixels do not influence neighborhoods.
    """
    if image.ndim != 2 or valid.shape != image.shape:
        raise ValueError('image and valid must have matching 2D shapes')
    if window < 3 or window % 2 != 1:
        raise ValueError('window must be odd and >= 3')
    if not np.isfinite(looks) or looks <= 0:
        raise ValueError('looks must be a finite positive value')
    if min_count < 1 or min_count > window * window:
        raise ValueError('min_count out of range')
    x = image.astype('float64', copy=False)
    mask = valid.astype(bool) & np.isfinite(x) & (x > 0)
    safe = np.where(mask, x, 0.0)
    count = uniform_filter(mask.astype('float64'), size=window, mode='constant', cval=0.0) * window**2
    sum_x = uniform_filter(safe, size=window, mode='constant', cval=0.0) * window**2
    sum_sq = uniform_filter(safe * safe, size=window, mode='constant', cval=0.0) * window**2
    mean = np.divide(sum_x, count, out=np.zeros_like(sum_x), where=count > 0)
    var = np.maximum(np.divide(sum_sq, count, out=np.zeros_like(sum_sq), where=count > 0) - mean * mean, 0.0)
    noise_var = mean * mean / looks
    signal_var = np.maximum(var - noise_var, 0.0)
    weight = np.divide(signal_var, signal_var + noise_var, out=np.zeros_like(var), where=(signal_var + noise_var) > 0)
    result = mean + weight * (x - mean)
    # Sparse valid neighborhoods: keep original valid samples unchanged.
    result = np.where(count >= min_count, result, x)
    return np.where(mask, np.maximum(result, np.finfo('float32').tiny), np.nan).astype('float32')


def _windows(height: int, width: int, tile: int):
    for row in range(0, height, tile):
        for col in range(0, width, tile):
            yield Window(col, row, min(tile, width-col), min(tile, height-row))


def _with_halo(w: Window, width: int, height: int, halo: int) -> Window:
    left, top = max(0, int(w.col_off)-halo), max(0, int(w.row_off)-halo)
    right = min(width, int(w.col_off+w.width)+halo)
    bottom = min(height, int(w.row_off+w.height)+halo)
    return Window(left, top, right-left, bottom-top)


def _side_paths(root, side, polarization):
    doc = load_manifest(root)[side]
    return (safe_pair_file(root, doc['raster_files'][polarization]),
            safe_pair_file(root, doc['valid_mask_file']),
            safe_pair_file(root, doc['layover_shadow_mask_file']) if doc.get('layover_shadow_mask_file') else None)


def process_pair(pair_dir: str | Path, output_dir: str | Path, *, polarization: str = 'VV', window: int = 7,
                 looks: float = 4.0, tile: int = 512, allow_warning: bool = False) -> dict:
    if polarization not in ('VV', 'VH', 'HHHH'):
        raise ValueError('polarization must be VV, VH or HHHH')
    if tile < 1:
        raise ValueError('tile must be >= 1')
    if window < 3 or window % 2 != 1 or looks <= 0 or not np.isfinite(looks):
        raise ValueError('invalid filtering settings')
    root = Path(pair_dir).resolve()
    dest = Path(output_dir).resolve()
    if dest == root or dest.is_relative_to(root) or root.is_relative_to(dest):
        raise ValueError('output directory must be separate from input directory')
    qa = inspect_pair(root)
    if qa['status'] == 'REJECT' or (qa['status'] == 'WARNING' and not allow_warning):
        raise ValueError('Preflight did not PASS: ' + json.dumps({'status': qa['status'], 'errors': qa['errors'], 'warnings': qa['warnings']}))
    manifest = load_manifest(root)
    if polarization not in manifest['polarizations']:
        raise ValueError('polarization unavailable in manifest')
    dest.mkdir(parents=True, exist_ok=True)
    summary = {'schema_version':'1.0', 'task':'M2-T03', 'input_pair_id':manifest['pair_id'],
               'polarization': polarization, 'filter':'local_lee_linear_power', 'window':window,
               'assumed_equivalent_looks':looks, 'input_units':('nisar_gcov_diagonal_linear_power' if manifest.get('sensor')=='NISAR' else 'gamma0_linear_power'),
               'qa_status': qa['status'], 'qa_warnings': qa['warnings'], 'images':{}}
    for side in ('before', 'after'):
        image_path, mask_path, shadow_path = _side_paths(root, side, polarization)
        outfile = dest / f'{side}_{polarization}_lee.tif'
        with ExitStack() as stack:
            r = stack.enter_context(rasterio.open(image_path))
            v = stack.enter_context(rasterio.open(mask_path))
            sh = stack.enter_context(rasterio.open(shadow_path)) if shadow_path else None
            if any((z.crs,z.transform,z.width,z.height) != (r.crs,r.transform,r.width,r.height) for z in [v]+([sh] if sh else [])):
                raise ValueError(f'{side} mask grid differs from image')
            profile = r.profile.copy()
            profile.update(driver='GTiff', count=1, dtype='float32', nodata=-9999.0,
                           compress='deflate', predictor=3, tiled=r.width>=16 and r.height>=16)
            if profile['tiled']:
                profile.update(blockxsize=256, blockysize=256)
            else:
                profile.pop('blockxsize',None); profile.pop('blockysize',None)
            valid_count, raw_sum, filtered_sum, tile_count = 0, 0.0, 0.0, 0
            with rasterio.open(outfile, 'w', **profile) as dst:
                dst.update_tags(SPECTRA_FILTER='local_lee', LOOKS_ASSUMED=str(looks), WINDOW=str(window),
                                RADIOMETRY=manifest['radiometry'], UNITS='linear_power', SOURCE_SCENE_ID=manifest[side]['scene_id'])
                for w in _windows(r.height,r.width,tile):
                    hw = _with_halo(w,r.width,r.height,window//2)
                    x = r.read(1,window=hw).astype('float32')
                    valid = ((v.read(1,window=hw)==1) & (r.read_masks(1,window=hw)>0)
                             & np.isfinite(x) & (x>0))
                    if sh is not None:
                        valid &= sh.read(1,window=hw)==0
                    result = masked_lee(x,valid,window=window,looks=looks)
                    rr = int(w.row_off-hw.row_off); cc=int(w.col_off-hw.col_off)
                    h,ww=int(w.height),int(w.width)
                    sub = result[rr:rr+h,cc:cc+ww]
                    original = x[rr:rr+h,cc:cc+ww]
                    good = np.isfinite(sub)
                    valid_count += int(good.sum())
                    raw_sum += float(original[good].sum(dtype='float64'))
                    filtered_sum += float(sub[good].sum(dtype='float64'))
                    dst.write(np.where(good,sub,-9999.0).astype('float32'),1,window=w)
                    tile_count+=1
        summary['images'][side] = {'source':str(image_path), 'filtered':str(outfile), 'valid_pixels':valid_count,
                                    'mean_raw_linear':raw_sum/valid_count if valid_count else None,
                                    'mean_filtered_linear':filtered_sum/valid_count if valid_count else None,
                                    'tiles_processed':tile_count}
    summary['generated_utc']=datetime.now(timezone.utc).isoformat()
    (dest/'filter-report.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return summary


def main():
    p=argparse.ArgumentParser(description='Mask-aware Lee SAR speckle filter: M1 RTC pair -> M2 filtered GeoTIFFs')
    p.add_argument('pair_dir',type=Path); p.add_argument('--out',type=Path,required=True)
    p.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    p.add_argument('--window',type=int,default=7); p.add_argument('--looks',type=float,default=4.0)
    p.add_argument('--tile',type=int,default=512); p.add_argument('--allow-warning',action='store_true')
    a=p.parse_args()
    try:
        report=process_pair(a.pair_dir,a.out,polarization=a.polarization,window=a.window,looks=a.looks,tile=a.tile,allow_warning=a.allow_warning)
    except (ValueError,OSError,KeyError) as exc:
        p.exit(3,f'T03 REJECT: {exc}\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
