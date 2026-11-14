"""T08 independent scientific validation of georeferenced T05/T06/T07 outputs.

Ground truth must be external, genuinely labelled data. No synthetic benchmark scores.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import Window
from sklearn.metrics import confusion_matrix


def binary_metrics(truth, predicted):
    t=np.asarray(truth, dtype=bool); p=np.asarray(predicted,dtype=bool)
    if t.shape != p.shape: raise ValueError('Shape mismatch')
    tp=int(np.count_nonzero(t & p)); fp=int(np.count_nonzero(~t & p))
    fn=int(np.count_nonzero(t & ~p)); tn=int(np.count_nonzero(~t & ~p))
    precision=tp/(tp+fp) if tp+fp else None
    recall=tp/(tp+fn) if tp+fn else None
    f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None
    iou=tp/(tp+fp+fn) if tp+fp+fn else None
    return {'TP':tp,'FP':fp,'FN':fn,'TN':tn,'precision':precision,'recall':recall,'f1':f1,'iou':iou}


def multiclass_metrics(true, pred, class_ids):
    ids=[int(c) for c in class_ids]
    if not ids or len(ids)!=len(set(ids)): raise ValueError('Invalid class IDs')
    t=np.asarray(true).ravel(); p=np.asarray(pred).ravel()
    if t.shape!=p.shape: raise ValueError('Shape mismatch')
    if not np.isin(t,ids).all() or not np.isin(p,ids).all(): raise ValueError('Labels outside class IDs')
    cm=confusion_matrix(t,p,labels=ids)
    result={}
    for i,c in enumerate(ids):
        tp=int(cm[i,i]); fp=int(cm[:,i].sum()-tp); fn=int(cm[i,:].sum()-tp)
        result[str(c)]={'support':int(cm[i,:].sum()), 'precision':tp/(tp+fp) if tp+fp else None,
                        'recall':tp/(tp+fn) if tp+fn else None,
                        'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                        'iou':tp/(tp+fp+fn) if tp+fp+fn else None}
    return {'class_ids':ids,'confusion_matrix':cm.tolist(), 'accuracy':float(np.mean(t==p)) if len(t) else None,
            'per_class':result,'macro_f1':float(np.mean([x['f1'] for x in result.values() if x['f1'] is not None])) if any(x['f1'] is not None for x in result.values()) else None}


def reliability_bins(correct, confidence, n_bins=10):
    c=np.asarray(correct,dtype=bool).ravel(); p=np.asarray(confidence,dtype=float).ravel()
    if c.shape!=p.shape: raise ValueError('Confidence/label shape mismatch')
    if n_bins < 2 or not np.isfinite(p).all() or ((p<0)|(p>1)).any(): raise ValueError('Invalid probabilities')
    result=[]; total=len(p); ece=0.
    for i in range(n_bins):
        lo=i/n_bins; hi=(i+1)/n_bins
        selected=(p>=lo)&(p<=hi if i==n_bins-1 else p<hi)
        n=int(selected.sum()); acc=float(c[selected].mean()) if n else None
        avg=float(p[selected].mean()) if n else None
        if n: ece+=n/total*abs(acc-avg)
        result.append({'range':[lo,hi], 'count':n,'empirical_accuracy':acc,'mean_score':avg})
    return {'ece_diagnostic':ece if total else None,'bins':result,'warning':'ECE is diagnostic only; these are uncalibrated model scores'}


def split_check(provenance):
    """Verify declared separation, not independently certify dataset lineage."""
    for key in ('train_region_ids','validation_region_ids','test_region_ids'):
        if key not in provenance or not isinstance(provenance[key],list) or not provenance[key]:
            raise ValueError('Must supply nonempty '+key)
    lists=[provenance[k] for k in ('train_region_ids','validation_region_ids','test_region_ids')]
    sets=[set(x) for x in lists]
    if any(len(s)!=len(x) for s,x in zip(sets,lists)) or any(a&b for a,b in ((sets[0],sets[1]),(sets[0],sets[2]),(sets[1],sets[2]))):
        raise ValueError('Train/validation/test region IDs overlap or repeat')
    if not provenance.get('reference_source') or not provenance.get('model_identifier'):
        raise ValueError('Reference and model provenance required')
    return {'declared_spatial_separation':True,'verified_external_lineage':False,
            'caveat':'Only region-ID disjointness checked; independent audit of geography, dates, sources, and sampling still required'}


def _open_aligned(path, reference):
    ds=rasterio.open(path)
    if (ds.crs!=reference.crs or ds.width!=reference.width or ds.height!=reference.height or
        not ds.transform.almost_equals(reference.transform)):
        ds.close(); raise ValueError('Raster grid mismatch: '+str(path))
    return ds


def evaluate(reference_path, prediction_path, valid_mask_path, output_path, *, mode, class_ids=None,
             score_path=None, provenance_path=None, allow_exploratory=False):
    provenance=json.loads(Path(provenance_path).read_text()) if provenance_path else None
    independence=split_check(provenance) if provenance is not None else None
    if not independence and not allow_exploratory:
        raise ValueError('Independent evaluation requires --provenance with declared disjoint region IDs; use --exploratory for diagnostic only')
    if mode=='multiclass' and not class_ids: raise ValueError('Class IDs required')
    with rasterio.open(reference_path) as ref, _open_aligned(prediction_path,ref) as pred, _open_aligned(valid_mask_path,ref) as mask:
        if ref.count!=1 or pred.count!=1 or mask.count!=1: raise ValueError('Expected single-band labels and mask')
        score_ds=_open_aligned(score_path,ref) if score_path else None
        if score_ds is not None and score_ds.count!=1: raise ValueError('Expected single-band model score')
        try:
            trues=[]; preds=[]; scores=[]
            for _, win in ref.block_windows(1):
                t=ref.read(1,window=win); p=pred.read(1,window=win); m=mask.read(1,window=win)
                valid=(m==1)&np.isfinite(t)&np.isfinite(p)
                if ref.nodata is not None: valid &= t!=ref.nodata
                if pred.nodata is not None: valid &= p!=pred.nodata
                if mode=='binary': valid &= np.isin(t,[0,1])&np.isin(p,[0,1])
                else: valid &= np.isin(t,class_ids)&np.isin(p,class_ids)
                if score_ds is not None:
                    sc=score_ds.read(1,window=win)
                    valid &= np.isfinite(sc)&(sc>=0)&(sc<=1)
                    if score_ds.nodata is not None: valid &= sc!=score_ds.nodata
                    scores.append(sc[valid])
                trues.append(t[valid]); preds.append(p[valid])
            truth=np.concatenate(trues); predicted=np.concatenate(preds)
            if len(truth)==0: raise ValueError('No valid labelled evaluation pixels')
            metrics=binary_metrics(truth==1,predicted==1) if mode=='binary' else multiclass_metrics(truth,predicted,class_ids)
            if score_ds is not None:
                if mode=='multiclass': metrics['reliability']=reliability_bins(truth==predicted,np.concatenate(scores))
                else: metrics['score_note']='Binary score not interpreted as calibrated confidence'
        finally:
            if score_ds is not None: score_ds.close()
    report={'task':'T08','mode':mode,'evaluated_pixels':len(truth),'metrics':metrics,
            'provenance_check':independence,'status':'UNVERIFIED_EXPLORATORY' if not independence else 'PROVISIONAL_REQUIRES_INDEPENDENT_LINEAGE_AUDIT',
            'limitations':['Pixel-wise metrics may inflate apparent certainty due to spatial autocorrelation',
                           'No external audit or scientific sign-off is performed by this software',
                           'Reported metrics depend on accurate, independently sourced ground-truth labels'],
            'files':{'reference':str(reference_path),'prediction':str(prediction_path),'valid_mask':str(valid_mask_path)}}
    target=Path(output_path); target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description='T08 SAR evaluation; never invents scores or reference labels')
    p.add_argument('--reference',required=True);p.add_argument('--prediction',required=True)
    p.add_argument('--valid-mask',required=True);p.add_argument('--out',required=True)
    p.add_argument('--mode',choices=['binary','multiclass'],required=True)
    p.add_argument('--class-ids',nargs='+',type=int)
    p.add_argument('--score');p.add_argument('--provenance');p.add_argument('--exploratory',action='store_true')
    args=p.parse_args()
    report=evaluate(args.reference,args.prediction,args.valid_mask,args.out,mode=args.mode,class_ids=args.class_ids,
                    score_path=args.score,provenance_path=args.provenance,allow_exploratory=args.exploratory)
    print(json.dumps({'status':report['status'],'evaluated_pixels':report['evaluated_pixels'],'output':args.out}))
if __name__=='__main__':main()
