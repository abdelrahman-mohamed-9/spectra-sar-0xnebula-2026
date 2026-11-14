"""Deterministic raster previews; colors visualize candidates, not confirmed damage."""
import json
import numpy as np
import rasterio
from PIL import Image
from rasterio.warp import transform_bounds

from .run_m2 import write_json


def render(root, original, candidate_mode):
    out=root/'preview';out.mkdir()
    pol=original['polarizations'][0]
    arrays=[]
    for side in ('before','after'):
        with rasterio.open(root/'M1'/f'{side}_{pol}.tif') as ds:
            values=ds.read(1,masked=True).astype('float64').filled(np.nan)
            values=np.where(values>0,10*np.log10(np.maximum(values,1e-30)),np.nan)
            arrays.append(values)
            bounds=transform_bounds(ds.crs,'EPSG:4326',*ds.bounds)
    finite=np.concatenate([v[np.isfinite(v)] for v in arrays])
    low, high=np.percentile(finite,[2,98])
    def gray(a):
        v=np.nan_to_num(np.clip((a-low)/max(high-low,1e-9),0,1))
        rgba=np.stack([v*255,v*255,v*255,np.where(np.isfinite(a),255,0)],axis=-1).astype('uint8')
        return rgba
    def save(name, data):
        Image.fromarray(data).save(out/name)
    for side,a in zip(('before','after'),arrays): save(side+'.png',gray(a))
    for mode,filename in [('conservative','adaptive_change_mask.tif'),('review','review_change_mask.tif')]:
        with rasterio.open(root/'M2'/filename) as ds: labels=ds.read(1)
        rgba=gray(arrays[1]);rgba[labels==1]=[45,212,191,255];rgba[labels==2]=[251,146,60,255]
        rgba[labels==255,3]=0
        save(mode+'.png',rgba)
    with rasterio.open(root/'M3/review-priority.tif') as ds: priority=ds.read(1)
    rgba=gray(arrays[1]);rgba[priority==1]=[250,204,21,255];rgba[priority==2]=[167,139,250,255]
    save('priority.png',rgba)
    write_json(out/'metadata.json',{'bounds_wgs84':list(bounds), 'width':arrays[0].shape[1], 'height':arrays[0].shape[0],
        'shared_display_stretch_db':[float(low),float(high)], 'candidate_mode_for_impact':candidate_mode,
        'legend':{'decrease':'#2dd4bf','increase':'#fb923c','threshold_sensitive':'#facc15','threshold_stable':'#a78bfa'},
        'interpretation':'Radar backscatter candidates only; no confirmed event, hazard or damage classification.'})
    return ['preview/'+p.name for p in out.iterdir()]


def report_markdown(root, summary, science, impact, external):
    lines=['# SPECTRA Phase 2 — execution report','',
        f"Pair: `{summary['pair_id']}`. Status: `{summary['status']}`.",
        '**Scientific approval: false.** Candidate changes are not confirmed events or damage.','',
        '## Processing',f"- M1 jointly valid cells: {summary['m1']['joint_valid']:,}.",
        f"- M2 conservative candidates: {summary['m2']['conservative_pixels']:,}.",
        f"- M2 broader-review candidates: {summary['m2']['review_pixels']:,}.",
        f"- M3 selected candidate mode: {summary['m2']['candidate_mode']}.",
        f"- Candidate footprint area: {impact['candidate_area_m2']:,.2f} m².",
        f"- Independently labeled pair evaluation: {science['independent_evaluation']['status']}.",
        f"- Residents potentially exposed: {impact['estimated_residents_exposed'] if impact['estimated_residents_exposed'] is not None else 'UNAVAILABLE; not zero'}.",
        '', '## External Sentinel-1 comparison',
        'Flood/water labels on Spain; not an accuracy estimate for NISAR Alaska.']
    if external.get('evaluation'):
        lines += ['', '| Method | Precision | Recall | F1 |', '|---|---:|---:|---:|']
        for method, m in external['evaluation'].items():
            lines += [f"| {method} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |"]
        lines += ['', 'Additional spatial ML is experimental. Its held-out result may be worse than the original logistic baseline; it is not promoted to NISAR production inference.']
    else: lines += ['Not run for this imported dataset.']
    lines += ['', '## Outstanding evidence', *['- '+x for x in summary['acceptance_gaps']],
        '', '## Integrity', 'Source, intermediate and final artifacts are hashed. The SQLite receipt gates downloads. Local hashes establish byte integrity, not provider authenticity.',
        '', '## Interpretation', 'Threshold stability is not a calibrated probability. Small changes can be removed by component filtering. Empty asset queries do not prove absence. Population averages cannot locate individual residents.']
    (root/'REPORT.md').write_text('\n'.join(lines)+'\n')
