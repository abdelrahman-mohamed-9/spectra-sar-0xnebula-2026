"""Scientific quality metrics for binary SAR change maps (not a trained model)."""
from __future__ import annotations
import numpy as np


def _pair(prediction, truth, valid_mask=None):
    pred = np.asarray(prediction)
    ref = np.asarray(truth)
    if pred.shape != ref.shape or pred.ndim != 2:
        raise ValueError('prediction and truth must be same-shaped 2-D arrays')
    if pred.size == 0:
        raise ValueError('empty images are invalid')
    valid = np.ones(pred.shape, dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    if valid.shape != pred.shape or valid.dtype != np.bool_:
        raise ValueError('valid_mask must be a boolean 2-D array of matching shape')
    if not np.any(valid):
        raise ValueError('no valid reference pixels')
    for value, name in ((pred, 'prediction'), (ref, 'truth')):
        if not np.all(np.isin(value[valid], [0, 1])):
            raise ValueError(f'{name} must contain only 0 or 1 in valid pixels')
    return pred[valid].astype(bool), ref[valid].astype(bool), int(valid.sum()), int(valid.size)


def evaluate_binary(prediction, truth, valid_mask=None):
    """Undefined precision/recall/F1/IoU are None (never silently claim perfect)."""
    pred, ref, n, total = _pair(prediction, truth, valid_mask)
    tp = int(np.count_nonzero(pred & ref))
    fp = int(np.count_nonzero(pred & ~ref))
    fn = int(np.count_nonzero(~pred & ref))
    tn = int(np.count_nonzero(~pred & ~ref))
    div = lambda a,b: None if b == 0 else a/b
    precision=div(tp,tp+fp);recall=div(tp,tp+fn)
    return {
      'tp':tp,'fp':fp,'fn':fn,'tn':tn,'valid_pixels':n,'total_pixels':total,
      'valid_fraction':n/total,'accuracy':(tp+tn)/n,
      'precision':precision,'recall':recall,
      'f1':div(2*tp,2*tp+fp+fn), 'iou':div(tp,tp+fp+fn),
      'balanced_accuracy': None if (tp+fn)==0 or (tn+fp)==0 else ((tp/(tp+fn))+(tn/(tn+fp)))/2,
      'positive_prevalence':(tp+fn)/n,
    }


def evaluate_probabilities(probabilities, truth, valid_mask=None, bins=10):
    """Binary Brier score and ECE for *validated* reference pixels."""
    probs=np.asarray(probabilities,dtype=float)
    labels=np.asarray(truth)
    if probs.shape != labels.shape or probs.ndim!=2:
        raise ValueError('probabilities and truth must be same-shaped 2-D arrays')
    mask=np.ones(probs.shape,dtype=bool) if valid_mask is None else np.asarray(valid_mask)
    if mask.shape!=probs.shape or mask.dtype!=np.bool_ or not np.any(mask):
        raise ValueError('invalid or empty boolean valid_mask')
    pp=probs[mask]; yy=labels[mask]
    if not np.isfinite(pp).all() or np.any(pp<0) or np.any(pp>1):
        raise ValueError('probabilities must be finite in [0,1]')
    if not np.isin(yy,[0,1]).all():
        raise ValueError('truth must be binary')
    if not isinstance(bins,int) or bins<1: raise ValueError('bins must be positive integer')
    # Expected calibration error on predicted CHANGE likelihood, not classification confidence.
    ids=np.minimum((pp*bins).astype(int),bins-1)
    ece=0.0
    for i in range(bins):
        sel=ids==i
        if sel.any(): ece += float(sel.mean()) * abs(float(pp[sel].mean())-float(yy[sel].mean()))
    return {'brier_score':float(np.mean((pp-yy)**2)),'ece_change_probability':ece,
            'valid_pixels':int(mask.sum()),'bins':bins}
