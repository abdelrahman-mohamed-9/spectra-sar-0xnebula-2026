"""M2 T04: conservative window-based residual SAR image alignment QA.

This tool verifies *residual* shifts. It does NOT geometrically align or warp imagery.
Inputs are M1 RTC GeoTIFFs on identical grids, checked through T02.
Results are diagnostic, not an independently proven geometric accuracy measurement.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from scipy.ndimage import gaussian_filter, sobel
from data_loader import load_manifest, iter_pair_tiles
from input_validator import inspect_pair


def estimate_shift(before: np.ndarray, after: np.ndarray, valid: np.ndarray, *, min_valid=0.8):
    """Integer-pixel phase-correlation shift of AFTER relative to BEFORE.

    Returns (dy, dx, peak_score), with positive dy/dx indicating displacement
    of content in AFTER; apply negative displacement to AFTER to register.
    Only accepts textured patches and clear correlation peaks.
    """
    b=np.asarray(before, dtype=np.float64); a=np.asarray(after, dtype=np.float64)
    m=np.asarray(valid, dtype=bool) & np.isfinite(b) & np.isfinite(a) & (b>0) & (a>0)
    if b.shape!=a.shape or m.shape!=b.shape or b.ndim!=2 or min(b.shape)<32:
        return None
    if m.mean()<min_valid: return None
    # Log-domain normalizes multiplicative radiometric changes; smooth speckle.
    x=gaussian_filter(np.where(m,np.log(np.maximum(b,1e-20)),np.nanmedian(np.log(b[m]))),1.4)
    y=gaussian_filter(np.where(m,np.log(np.maximum(a,1e-20)),np.nanmedian(np.log(a[m]))),1.4)
    # Gradient magnitude focuses on spatial structures rather than absolute backscatter.
    x=np.hypot(sobel(x,axis=0),sobel(x,axis=1))
    y=np.hypot(sobel(y,axis=0),sobel(y,axis=1))
    if min(np.std(x),np.std(y))<1e-4: return None
    h,w=b.shape
    hann=np.outer(np.hanning(h),np.hanning(w))
    x=(x-x.mean())*hann; y=(y-y.mean())*hann
    fb=np.fft.fft2(x); fa=np.fft.fft2(y)
    cross=fa*np.conj(fb)
    amp=np.abs(cross)
    corr=np.fft.ifft2(np.divide(cross,amp,out=np.zeros_like(cross),where=amp>1e-12)).real
    peak=np.unravel_index(np.argmax(corr),corr.shape)
    dy=int(peak[0] if peak[0]<=h//2 else peak[0]-h)
    dx=int(peak[1] if peak[1]<=w//2 else peak[1]-w)
    peak_val=float(corr[peak]); corr[peak]=0
    # avoid trivial aliasing; compare peak to next strongest separated local maximum
    score=peak_val/(float(np.max(np.abs(corr)))+1e-12)
    if abs(dy)>min(8,h//8) or abs(dx)>min(8,w//8) or score<1.08:
        return None
    return dy,dx,score


def inspect_registration(pair_dir, *, polarization='VV', patch=256,
                         max_patches=48, max_residual_pixels=0.5,
                         allow_warning=False):
    if patch<32 or max_patches<1 or max_residual_pixels<0:
        raise ValueError('invalid T04 settings')
    root=Path(pair_dir).resolve()
    qa=inspect_pair(root)
    report={'task':'M2-T04','schema_version':'1.0','pair_id':None,
            'method':'integer_pixel_patch_phase_correlation_gradient_magnitude',
            'precision':'integer pixel only; no subpixel accuracy certification',
            'threshold_pixels':max_residual_pixels,
            't02_status':qa['status'],'t02_errors':qa['errors'],'t02_warnings':qa['warnings'],
            'samples':[],'status':'WARNING','notes':[]}
    if qa['status']=='REJECT':
        report['status']='REJECT';report['notes'].append('T02 rejected inputs; no alignment assessment performed')
        return report
    if qa['status']=='WARNING' and not allow_warning:
        report['notes'].append('T02 WARNING requires explicit --allow-warning to proceed')
        return report
    manifest=load_manifest(root)
    report['pair_id']=manifest['pair_id']
    if polarization not in manifest['polarizations']:
        report['status']='REJECT'; report['notes'].append(f'Missing polarization {polarization}')
        return report
    samples=[]
    for tile in iter_pair_tiles(root,polarization=polarization,tile_size=patch):
        if len(samples)>=max_patches: break
        result=estimate_shift(tile.before,tile.after,tile.valid)
        if result is not None:
            dy,dx,score=result
            samples.append({'row':int(tile.window.row_off),'col':int(tile.window.col_off),
                            'dy_pixels':dy,'dx_pixels':dx,'peak_ratio':round(score,3),
                            'magnitude_pixels':round(float(np.hypot(dy,dx)),3)})
    report['samples']=samples
    report['valid_patch_count']=len(samples)
    if len(samples)<3:
        report['status']='WARNING'
        report['notes'].append('Insufficient reliable textured patches; registration inconclusive')
        return report
    shifts=np.array([[s['dy_pixels'],s['dx_pixels']] for s in samples])
    med=np.median(shifts,axis=0)
    distances=np.linalg.norm(shifts-med,axis=1)
    consensus=float(np.mean(distances<=1.0))
    magnitude=float(np.linalg.norm(med))
    report.update(median_dy_pixels=float(med[0]),median_dx_pixels=float(med[1]),
                  median_shift_magnitude_pixels=round(magnitude,3),
                  consensus_fraction=round(consensus,3))
    if consensus<0.7:
        report['status']='WARNING'
        report['notes'].append('Inconsistent patch shifts: changes, noise or misregistration possible; manual QA required')
    elif magnitude>max_residual_pixels:
        report['status']='REJECT'
        report['notes'].append('Detected residual integer-pixel shift exceeds threshold; request M1 re-registration')
    else:
        report['status']='WARNING'
        report['notes'].append('No integer-pixel shift detected; subpixel <=0.5px NOT demonstrated; perform independent subpixel/feature-tie-point QA before scientific PASS')
    return report


def main():
    p=argparse.ArgumentParser(description='M2 T04 residual alignment diagnostics, no warping')
    p.add_argument('pair_dir');p.add_argument('--output',default='registration-report.json')
    p.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    p.add_argument('--patch',type=int,default=256)
    p.add_argument('--max-patches',type=int,default=48)
    p.add_argument('--allow-warning',action='store_true')
    args=p.parse_args()
    result=inspect_registration(args.pair_dir,polarization=args.polarization,patch=args.patch,
                                max_patches=args.max_patches,allow_warning=args.allow_warning)
    result['generated_at_utc']=datetime.now(timezone.utc).isoformat()
    out=Path(args.output).resolve()
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'report':str(out),'valid_patches':result.get('valid_patch_count',0)}))
    return {'PASS':0,'WARNING':2,'REJECT':3}[result['status']]

if __name__=='__main__': raise SystemExit(main())
