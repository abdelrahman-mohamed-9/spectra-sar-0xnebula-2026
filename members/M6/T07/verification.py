"""Validate scientific metadata before any spatial pixel comparison."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import numpy as np
from scientific_metrics import evaluate_binary, evaluate_probabilities

@dataclass(frozen=True)
class RasterMetadata:
    crs: str
    transform: tuple[float,float,float,float,float,float]
    width: int
    height: int
    reference_source: str
    reference_date: str
    reference_method: str

    @staticmethod
    def from_mapping(value):
        needed=('crs','transform','width','height','reference_source','reference_date','reference_method')
        missing=[k for k in needed if k not in value]
        if missing: raise ValueError(f'missing metadata fields: {missing}')
        if len(value['transform'])!=6: raise ValueError('transform requires 6 affine values')
        out=RasterMetadata(str(value['crs']),tuple(float(x) for x in value['transform']),
                           int(value['width']),int(value['height']),
                           str(value['reference_source']),str(value['reference_date']),str(value['reference_method']))
        if out.width<1 or out.height<1 or not all([out.crs,out.reference_source,out.reference_date,out.reference_method]):
            raise ValueError('metadata fields must be meaningful')
        if not all(np.isfinite(out.transform)): raise ValueError('transform must be finite')
        return out


def verify_alignment(pred_meta, ref_meta):
    """Never silently resample reference labels or assume equal grids by shape."""
    p=RasterMetadata.from_mapping(pred_meta)
    r=RasterMetadata.from_mapping(ref_meta)
    if p.width!=r.width or p.height!=r.height:
        raise ValueError('raster dimensions differ; align with documented reprojection first')
    if p.crs!=r.crs or not np.allclose(p.transform,r.transform,rtol=0,atol=1e-8):
        raise ValueError('CRS/geotransform differ; perform documented coregistration first')
    return p,r


def verify_result(prediction,truth,pred_meta,ref_meta,valid_mask=None,probabilities=None):
    p,r=verify_alignment(pred_meta,ref_meta)
    for a,name in ((prediction,'prediction'),(truth,'truth')):
        if np.asarray(a).shape!=(p.height,p.width):
            raise ValueError(f'{name} array shape differs from metadata')
    metric=evaluate_binary(prediction,truth,valid_mask)
    prob_metric=None
    if probabilities is not None:
        if np.asarray(probabilities).shape!=(p.height,p.width):
            raise ValueError('probability map shape differs from metadata')
        prob_metric=evaluate_probabilities(probabilities,truth,valid_mask)
    return {'status':'EVALUATED_AGAINST_REFERENCE','reference':{
      'source':r.reference_source,'date':r.reference_date,'method':r.reference_method},
      'grid':{'crs':p.crs,'width':p.width,'height':p.height,'transform':list(p.transform)},
      'metrics':metric,'probability_metrics':prob_metric,
      'caveats':['Metrics describe agreement with the provided reference, not ground-truth certainty.',
                 'Only reference-validated pixels are scored; quality depends on reference provenance.']}
