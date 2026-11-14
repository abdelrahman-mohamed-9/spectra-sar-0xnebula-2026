"""M2-T07: uncertainty diagnostics, NOT calibrated scientific confidence.

Consumes T06 class_probabilities.tif and class_map.tif, and the M1 quality
masks via the manifest. Outputs diagnostic GeoTIFFs and a JSON summary.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import numpy as np
import rasterio
from rasterio.windows import Window
from ai_classifier import _inputs, _check_grid

NODATA = -9999.0

def uncertainty_from_probabilities(probs, valid, *, low_confidence_threshold=.60):
    """Convert CxHxW probability scores into uncalibrated diagnostics.

    Returns normalized entropy (0..1), top-two margin (0..1), top score,
    and review-required mask (0 or 1; 255=invalid).
    """
    pr=np.asarray(probs,dtype='float64')
    v=np.asarray(valid,dtype=bool)
    if pr.ndim!=3 or pr.shape[0]<2 or pr.shape[1:]!=v.shape:
        raise ValueError('Expected >=2 probability bands and matching 2D valid mask')
    if not 0 < low_confidence_threshold < 1:
        raise ValueError('Threshold must be within (0,1)')
    values=pr[:,v]
    if values.size and (not np.isfinite(values).all() or
        (values < -1e-6).any() or (values > 1+1e-6).any() or
        not np.allclose(values.sum(axis=0),1,atol=1e-3)):
        raise ValueError('Probability vectors must be finite, within [0,1], and sum to 1')
    h,w=v.shape
    entropy=np.full((h,w),NODATA,dtype='float32')
    margin=np.full((h,w),NODATA,dtype='float32')
    maximum=np.full((h,w),NODATA,dtype='float32')
    review=np.full((h,w),255,dtype='uint8')
    if values.size:
        sorted_probs=np.sort(values,axis=0)
        top=sorted_probs[-1];second=sorted_probs[-2]
        ent=-(np.where(values>0, values*np.log(np.maximum(values,1e-300)), 0).sum(axis=0))/np.log(pr.shape[0])
        entropy[v]=np.clip(ent,0,1).astype('float32')
        margin[v]=np.clip(top-second,0,1).astype('float32')
        maximum[v]=top.astype('float32')
        review[v]=(top < low_confidence_threshold).astype('uint8')
    return {'normalized_entropy':entropy,'top_two_margin':margin,
            'uncalibrated_max_probability':maximum,'review_required':review}

def run(pair_dir, classification_dir, output_dir, *, polarization='VV', tile_size=512,
        low_confidence_threshold=.60, allow_unverified_registration=False):
    if not allow_unverified_registration:
        raise ValueError('T04 subpixel registration not certified; explicit exploratory bypass required')
    if tile_size<16: raise ValueError('tile_size must be >=16')
    manifest, qa, paths=_inputs(pair_dir,polarization)
    source=Path(classification_dir).resolve();output=Path(output_dir).resolve()
    if output==source or output in source.parents or source in output.parents:
        raise ValueError('Output must be separate from classification input')
    if output==Path(pair_dir).resolve() or output in Path(pair_dir).resolve().parents or Path(pair_dir).resolve() in output.parents:
        raise ValueError('Output and SAR pair must be separate')
    summary=json.loads((source/'classification-summary.json').read_text(encoding='utf-8'))
    if summary['pair_id']!=manifest['pair_id'] or summary['status']!='EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED':
        raise ValueError('T06 summary does not match SAR pair / expected status')
    output.mkdir(parents=True,exist_ok=True)
    with rasterio.open(source/'class_probabilities.tif') as prob, rasterio.open(source/'class_map.tif') as classes, rasterio.open(paths[0]) as before, rasterio.open(paths[2]) as mb, rasterio.open(paths[3]) as ma:
        for obj,name in ((prob,'probability'),(classes,'classes'),(mb,'before valid'),(ma,'after valid')):
            _check_grid(obj,before,name)
        if prob.count<2 or classes.count!=1: raise ValueError('Invalid number of probability/class raster bands')
        ids=json.loads(prob.tags().get('class_ids','null'))
        if not isinstance(ids,list) or len(ids)!=prob.count or len(set(ids))!=len(ids):
            raise ValueError('Missing or inconsistent class ID metadata')
        if set(str(x) for x in ids)!=set(summary['classes']):
            raise ValueError('Class ID metadata does not match T06 summary')
        float_profile=before.profile.copy()
        float_profile.update(driver='GTiff',count=1,dtype='float32',nodata=NODATA,compress='deflate',predictor=3)
        float_profile.pop('blockxsize',None);float_profile.pop('blockysize',None)
        flag_profile={**float_profile,'dtype':'uint8','nodata':255,'predictor':1}
        names=['normalized_entropy','top_two_margin','uncalibrated_max_probability']
        from contextlib import ExitStack
        with ExitStack() as stack:
            dest={n:stack.enter_context(rasterio.open(output/(n+'.tif'),'w',**float_profile)) for n in names}
            dest['review_required']=stack.enter_context(rasterio.open(output/'review_required.tif','w',**flag_profile))
            counts={'valid':0,'invalid':0,'review_required':0}
            for row in range(0,prob.height,tile_size):
                for col in range(0,prob.width,tile_size):
                    win=Window(col,row,min(tile_size,prob.width-col),min(tile_size,prob.height-row))
                    pv=prob.read(window=win)
                    labels=classes.read(1,window=win)
                    valid=(labels!=255)&(mb.read(1,window=win)==1)&(ma.read(1,window=win)==1)
                    valid&=(before.read_masks(1,window=win)>0)
                    valid&=np.isin(labels,ids)
                    # Masked/invalid probability cells must not be treated as scientific evidence
                    computed=uncertainty_from_probabilities(pv,valid,low_confidence_threshold=low_confidence_threshold)
                    # Ensure the label agrees with the highest-scoring class (ties permitted)
                    if valid.any():
                        maxscore=np.max(pv[:,valid],axis=0)
                        match=np.any((np.array(ids)[:,None]==labels[valid][None,:]) & np.isclose(pv[:,valid],maxscore,atol=1e-5),axis=0)
                        if not match.all(): raise ValueError('Class map inconsistent with probability raster')
                    for name,arr in computed.items():dest[name].write(arr,1,window=win)
                    counts['valid']+=int(valid.sum());counts['invalid']+=int((~valid).sum())
                    counts['review_required']+=int((computed['review_required']==1).sum())
            for name,d in dest.items():d.update_tags(interpretation='diagnostic_only_NOT_calibrated_confidence',source='T06 uncalibrated RF probabilities')
    report={'task':'M2-T07','status':'EXPLORATORY_UNCALIBRATED','pair_id':manifest['pair_id'],
            'polarization':polarization,'t02_status':qa['status'],'registration_status':'SUBPIXEL_UNVERIFIED',
            'class_ids':ids,'low_confidence_threshold':low_confidence_threshold,'pixel_counts':counts,
            'calibrated':False,'scientific_confidence_claim':False,
            'caveats':['Entropy and margin indicate model ambiguity only, NOT probability of correctness.',
            'No calibrated probabilities without reliable geographically independent labels.',
            'Input quality, speckle, registration error, and domain shift require separate validation.',
            'Review flag threshold is operational heuristic, not scientifically optimized.']}
    (output/'uncertainty-summary.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description='T07 uncertainty/ambiguity diagnostics on T06 class probabilities')
    parser.add_argument('pair_dir');parser.add_argument('--classification-dir',required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    parser.add_argument('--tile-size',type=int,default=512)
    parser.add_argument('--low-confidence-threshold',type=float,default=.60)
    parser.add_argument('--allow-unverified-registration',action='store_true')
    args=parser.parse_args()
    try:
        print(json.dumps(run(args.pair_dir,args.classification_dir,args.out,polarization=args.polarization,
            tile_size=args.tile_size,low_confidence_threshold=args.low_confidence_threshold,
            allow_unverified_registration=args.allow_unverified_registration),indent=2))
        return 2 # exploratory, not scientific sign-off
    except (OSError,ValueError,KeyError,TypeError,rasterio.errors.RasterioError) as exc:
        print(f'T07 ERROR: {exc}',file=sys.stderr);return 3
if __name__=='__main__': raise SystemExit(main())
