"""T06: supervised, explicitly trained SAR pixel-level classification.

No pretrained model or semantic label is implied. Only externally supplied
georeferenced reference labels can authorize a semantic classification.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

import joblib  # WARNING: deserializing untrusted joblib/pickle files executes code
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.enums import Resampling
from scipy.ndimage import uniform_filter
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import classification_report, confusion_matrix

from data_loader import load_manifest, safe_pair_file
from input_validator import inspect_pair

FEATURES = ['before_db', 'after_db', 'signed_change_db', 'abs_change_db',
            'local_before_mean_db', 'local_after_mean_db', 'local_change_std_db']
INVALID_CLASS = 255
HALO = 3  # radius of 7x7 neighborhood


def features_from_arrays(before, after, valid, *, size=7):
    """Return HxWx7 features for positive gamma0 linear power in common grid.

    Neighborhood statistics use only valid samples; invalid cells get no weight.
    Apply with a halo at tile borders for seamless inference.
    """
    b = np.asarray(before, dtype=np.float64)
    a = np.asarray(after, dtype=np.float64)
    v = np.asarray(valid, dtype=bool) & np.isfinite(b) & np.isfinite(a) & (b > 0) & (a > 0)
    if b.shape != a.shape or b.shape != v.shape or b.ndim != 2:
        raise ValueError('Expected same-shape 2D arrays')
    if size != 7:
        raise ValueError('This version uses a fixed 7x7 window')
    bdb = np.zeros(b.shape, dtype=np.float64)
    adb = np.zeros(a.shape, dtype=np.float64)
    bdb[v] = 10 * np.log10(b[v]); adb[v] = 10 * np.log10(a[v])
    diff = adb - bdb
    w = v.astype(np.float64)
    n = uniform_filter(w, size=size, mode='constant', cval=0)
    n = np.maximum(n, 1e-12)
    def local_mean(z):
        return uniform_filter(z*w, size=size, mode='constant', cval=0)/n
    bm = local_mean(bdb); am = local_mean(adb)
    dm = local_mean(diff)
    var = np.maximum(local_mean(diff*diff) - dm*dm, 0)
    feat = np.stack((bdb, adb, diff, np.abs(diff), bm, am, np.sqrt(var)), axis=-1).astype('float32')
    feat[~v] = np.nan
    return feat, v


def _check_grid(x, ref, name):
    if (x.width != ref.width or x.height != ref.height or
        x.crs != ref.crs or not x.transform.almost_equals(ref.transform)):
        raise ValueError(f'{name} geospatial grid differs from before raster')


def _inputs(pair_dir, polarization):
    root = Path(pair_dir).resolve()
    qa = inspect_pair(root)
    if qa['status'] == 'REJECT':
        raise ValueError('T02 rejected pair: ' + '; '.join(qa['errors']))
    manifest = load_manifest(root)
    if polarization not in manifest['polarizations']:
        raise ValueError(f'Polarization {polarization} missing')
    b = safe_pair_file(root, manifest['before']['raster_files'][polarization])
    a = safe_pair_file(root, manifest['after']['raster_files'][polarization])
    mb = safe_pair_file(root, manifest['before']['valid_mask_file'])
    ma = safe_pair_file(root, manifest['after']['valid_mask_file'])
    sb = safe_pair_file(root, manifest['before']['layover_shadow_mask_file']) if manifest['before'].get('layover_shadow_mask_file') else None
    sa = safe_pair_file(root, manifest['after']['layover_shadow_mask_file']) if manifest['after'].get('layover_shadow_mask_file') else None
    return manifest, qa, (b, a, mb, ma, sb, sa)


def _read_inputs(paths):
    with rasterio.open(paths[0]) as b, rasterio.open(paths[1]) as a, rasterio.open(paths[2]) as bm, rasterio.open(paths[3]) as am:
        for src, name in [(a,'after'), (bm,'before mask'), (am,'after mask')]:
            _check_grid(src, b, name)
        bv=b.read(1).astype('float64'); av=a.read(1).astype('float64')
        good=(bm.read(1)==1)&(am.read(1)==1)
        good &= (b.read_masks(1)>0)&(a.read_masks(1)>0)
        for extra in paths[4:]:
            if extra is not None:
                with rasterio.open(extra) as shadow:
                    _check_grid(shadow,b,'layover/shadow mask')
                    good &= (shadow.read(1)==0)
        feat, valid=features_from_arrays(bv,av,good)
        return feat,valid,b.profile.copy()


def _label_metadata(label_map):
    if not isinstance(label_map,dict) or len(label_map)<2:
        raise ValueError('Provide >=2 explicitly named semantic classes, e.g. {"1":"flood", "2":"other"}')
    parsed={}
    for k,v in label_map.items():
        i=int(k)
        if i < 1 or i > 254 or str(i)!=str(k) or not isinstance(v,str) or not v.strip():
            raise ValueError('Classes must be unique integer IDs 1..254 and nonempty names')
        parsed[i]=v.strip()
    if len(set(parsed.values()))!=len(parsed):
        raise ValueError('Duplicate class names')
    return parsed


def train(pair_dir, labels_path, classes_path, out_dir, *, polarization='VV', seed=42,
          max_samples=100000, group_pixels=64):
    """Train only on provided reference raster; spatial holdout avoids random-pixel leakage."""
    if max_samples < 100 or group_pixels < 8:
        raise ValueError('max_samples >=100 and group_pixels >=8 required')
    manifest, qa, paths=_inputs(pair_dir,polarization)
    classes=_label_metadata(json.loads(Path(classes_path).read_text(encoding='utf-8')))
    feat,valid,profile=_read_inputs(paths)
    with rasterio.open(labels_path) as src, rasterio.open(paths[0]) as ref:
        _check_grid(src,ref,'reference labels')
        label=src.read(1)
    labeled=valid & np.isin(label,list(classes))
    if np.count_nonzero(labeled)<100:
        raise ValueError('Insufficient labeled valid pixels (minimum 100)')
    yrows,ycols=np.where(labeled)
    groups=(yrows//group_pixels)*((label.shape[1]+group_pixels-1)//group_pixels)+(ycols//group_pixels)
    unique_groups=np.unique(groups)
    if unique_groups.size<3:
        raise ValueError('Need labels spread across at least three spatial groups')
    split=GroupShuffleSplit(n_splits=1,test_size=0.25,random_state=seed)
    tr_idx,te_idx=next(split.split(yrows,groups=groups))
    # Sample TRAIN only, preserving genuine held-out spatial groups
    rng=np.random.default_rng(seed)
    if len(tr_idx)>max_samples:
        tr_idx=rng.choice(tr_idx,size=max_samples,replace=False)
    xtr=feat[yrows[tr_idx],ycols[tr_idx],:]
    ytr=label[yrows[tr_idx],ycols[tr_idx]].astype('int32')
    xte=feat[yrows[te_idx],ycols[te_idx],:]
    yte=label[yrows[te_idx],ycols[te_idx]].astype('int32')
    if len(set(ytr))<len(classes) or len(set(yte))<len(classes):
        raise ValueError('Spatial split lacks some class(es) in train or holdout; collect geographically spread labels')
    clf=RandomForestClassifier(n_estimators=100,min_samples_leaf=3,class_weight='balanced_subsample',
                               max_features='sqrt',random_state=seed,n_jobs=-1)
    clf.fit(xtr,ytr)
    pred=clf.predict(xte)
    ids=sorted(classes)
    evaluation={
        'reference_labels':'USER_PROVIDED_NOT_INDEPENDENTLY_VERIFIED',
        'holdout_method':'single_spatial_group_split_not_independent_external_site',
        'group_pixels':group_pixels,'training_samples':len(tr_idx),'holdout_samples':len(te_idx),
        'train_groups':len(np.unique(groups[tr_idx])),'holdout_groups':len(np.unique(groups[te_idx])),
        'report':classification_report(yte,pred,labels=ids,target_names=[classes[i] for i in ids],zero_division=0,output_dict=True),
        'confusion_matrix':confusion_matrix(yte,pred,labels=ids).tolist(),
        'class_ids':ids,
    }
    dest=Path(out_dir).resolve(); dest.mkdir(parents=True,exist_ok=True)
    modelpath=dest/'t06-random-forest.joblib'
    joblib.dump(clf,modelpath)
    sha=hashlib.sha256(modelpath.read_bytes()).hexdigest()
    metadata={'task':'M2-T06','model_type':'RandomForestClassifier','model_sha256':sha,
              'trained_at_utc':datetime.now(timezone.utc).isoformat(),'pair_id':manifest['pair_id'],
              'polarization':polarization,'features':FEATURES,'classes':{str(k):v for k,v in classes.items()},
              'model_training_status':'TRAINED_ON_SUPPLIED_LABELS_NOT_EXTERNALLY_VALIDATED',
              'registration_status':'SUBPIXEL_UNVERIFIED','t02_status':qa['status'],
              'evaluation':evaluation,'limitations':['Reference-label quality not independently established.',
              'Single spatial holdout is not an independent geographic/temporal test.',
              'Probabilities are uncalibrated. T07 must assess uncertainty.',
              'Joblib model deserialization is unsafe for untrusted model files.']}
    (dest/'model-metadata.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    return metadata


def infer(pair_dir, model_dir, output_dir, *, polarization='VV', tile_size=512,
          allow_unverified_registration=False):
    if not allow_unverified_registration:
        raise ValueError('T04 subpixel registration not certified; exploratory mode requires explicit bypass')
    if tile_size<16: raise ValueError('tile_size must be >=16')
    manifest, qa,paths=_inputs(pair_dir,polarization)
    md=json.loads((Path(model_dir)/'model-metadata.json').read_text(encoding='utf-8'))
    modelpath=Path(model_dir)/'t06-random-forest.joblib'
    if hashlib.sha256(modelpath.read_bytes()).hexdigest()!=md['model_sha256']:
        raise ValueError('Model hash mismatch')
    if md['features']!=FEATURES or md['polarization']!=polarization:
        raise ValueError('Model feature definition / polarization mismatch')
    # Load only personally created / trusted artifacts. Hash alone does not make a pickle safe.
    clf=joblib.load(modelpath)
    if not isinstance(clf,RandomForestClassifier): raise ValueError('Unexpected model type')
    output=Path(output_dir).resolve()
    if output in Path(pair_dir).resolve().parents or output==Path(pair_dir).resolve() or Path(pair_dir).resolve() in output.parents:
        raise ValueError('Output and input must be separate directory trees')
    output.mkdir(parents=True,exist_ok=True)
    with rasterio.open(paths[0]) as b, rasterio.open(paths[1]) as a, rasterio.open(paths[2]) as bm, rasterio.open(paths[3]) as am:
        for src,name in [(a,'after'),(bm,'before mask'),(am,'after mask')]: _check_grid(src,b,name)
        profile=b.profile.copy()
        profile.update(driver='GTiff',count=1,dtype='uint8',nodata=255,compress='deflate',predictor=1)
        profile.pop('blockxsize',None);profile.pop('blockysize',None)
        profile.update(tiled=b.width>=16 and b.height>=16)
        pprob=profile.copy();pprob.update(dtype='float32',nodata=-9999.0,predictor=3)
        with rasterio.open(output/'class_map.tif','w',**profile) as cls, rasterio.open(output/'uncalibrated_max_probability.tif','w',**pprob) as prob, rasterio.open(output/'class_probabilities.tif','w',**{**pprob, 'count':len(clf.classes_)}) as full_probs:
            full_probs.update_tags(interpretation='uncalibrated_model_probabilities_not_calibrated_confidence', class_ids=json.dumps([int(x) for x in clf.classes_]))
            counts={'invalid':0,'valid':0}
            for row in range(0,b.height,tile_size):
                for col in range(0,b.width,tile_size):
                    h=min(tile_size,b.height-row);w=min(tile_size,b.width-col)
                    rr=max(0,row-HALO); cc=max(0,col-HALO)
                    rh=min(b.height,row+h+HALO)-rr; cw=min(b.width,col+w+HALO)-cc
                    win=Window(cc,rr,cw,rh)
                    before=b.read(1,window=win).astype('float64');after=a.read(1,window=win).astype('float64')
                    v=(bm.read(1,window=win)==1)&(am.read(1,window=win)==1)
                    v&=(b.read_masks(1,window=win)>0)&(a.read_masks(1,window=win)>0)
                    for extra in paths[4:]:
                        if extra is not None:
                            with rasterio.open(extra) as shadow:
                                _check_grid(shadow,b,'layover/shadow mask')
                                v &= shadow.read(1,window=win)==0
                    feat,valid=features_from_arrays(before,after,v)
                    r=row-rr;c=col-cc
                    f=feat[r:r+h,c:c+w];good=valid[r:r+h,c:c+w]
                    lab=np.full((h,w),255,dtype='uint8');confidence=np.full((h,w),-9999,dtype='float32')
                    all_probs=np.full((len(clf.classes_),h,w),-9999,dtype='float32')
                    if good.any():
                        xx=f[good]
                        lab[good]=clf.predict(xx).astype('uint8')
                        pr=clf.predict_proba(xx).astype('float32')
                        confidence[good]=pr.max(axis=1)
                        all_probs[:,good]=pr.T
                    dst=Window(col,row,w,h)
                    cls.write(lab,1,window=dst);prob.write(confidence,1,window=dst);full_probs.write(all_probs,window=dst)
                    counts['valid']+=int(good.sum());counts['invalid']+=int((~good).sum())
            cls.update_tags(interpretation='supervised_labels_only_when_user_supplied_reference_and_model')
            prob.update_tags(interpretation='uncalibrated_model_score_not_scientific_confidence')
    result={'task':'M2-T06','status':'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED',
            'pair_id':manifest['pair_id'],'classes':md['classes'],'pixel_counts':counts,
            'model_sha256':md['model_sha256'],'t02_status':qa['status'],
            'registration_status':'SUBPIXEL_UNVERIFIED',
            'note':'Semantic predictions depend entirely on provided reference labels; no flood/damage validity implied. Probabilities uncalibrated.'}
    (output/'classification-summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description='T06 opt-in supervised classifier; no invented AI model')
    sub=p.add_subparsers(dest='command',required=True)
    tr=sub.add_parser('train');tr.add_argument('pair_dir');tr.add_argument('--labels',required=True)
    tr.add_argument('--classes',required=True);tr.add_argument('--out',required=True)
    tr.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    tr.add_argument('--group-pixels',type=int,default=64)
    ins=sub.add_parser('infer');ins.add_argument('pair_dir');ins.add_argument('--model-dir',required=True)
    ins.add_argument('--out',required=True);ins.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV')
    ins.add_argument('--tile-size',type=int,default=512)
    ins.add_argument('--allow-unverified-registration',action='store_true')
    args=p.parse_args()
    try:
        if args.command=='train':
            result=train(args.pair_dir,args.labels,args.classes,args.out,
                         polarization=args.polarization,group_pixels=args.group_pixels)
        else:
            result=infer(args.pair_dir,args.model_dir,args.out,polarization=args.polarization,
                         tile_size=args.tile_size,allow_unverified_registration=args.allow_unverified_registration)
        print(json.dumps({'status':result.get('status',result.get('model_training_status')), 'result':result.get('evaluation',result.get('pixel_counts'))}))
        return 2  # exploratory only
    except (ValueError,OSError,KeyError,rasterio.errors.RasterioError) as exc:
        print(f'T06 ERROR: {exc}',file=sys.stderr);return 3

if __name__=='__main__': raise SystemExit(main())
