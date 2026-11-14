"""SPECTRA-SAR M3/T06 - transparent, *uncalibrated* exposure-priority screening.

Not a physical disaster-risk model, harm estimate, or emergency alert system.
Consumes genuine T05 JSON at runtime. Test data must not be presented as observations.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml

class RiskInputError(ValueError):
    pass


def load_json(path: str | Path) -> dict:
    obj = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(obj, dict):
        raise RiskInputError('Expected JSON object')
    return obj


def digest(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(obj: dict, key: str, *, maximum: float | None = None) -> float:
    val = obj.get(key)
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0:
        raise RiskInputError(f'{key} must be a finite non-negative number')
    if maximum is not None and val > maximum:
        raise RiskInputError(f'{key} must be <= {maximum}')
    return float(val)


def config_validate(cfg: dict) -> None:
    if cfg.get('schema_version') != '1.0.0' or not isinstance(cfg.get('model_id'), str) or not cfg['model_id'].strip():
        raise RiskInputError('Unsupported config schema or missing model_id')
    expected={'population','buildings','roads'}
    w=cfg.get('weights',{})
    if set(w)!=expected: raise RiskInputError('weights must contain population/buildings/roads exactly')
    for key in expected: number(w,key,maximum=1)
    if abs(sum(w.values())-1)>1e-9:raise RiskInputError('weights must sum to exactly 1')
    scales=cfg.get('reference_scales',{})
    if set(scales)!={'population_people','building_count','road_length_m'}:
        raise RiskInputError('Missing or extra reference scales')
    for key in scales:
        if number(scales,key)<=0:raise RiskInputError(f'{key} must be positive')
    q=cfg.get('quality',{})
    for key in ('minimum_population_coverage','maximum_outside_raster_fraction','minimum_sar_confidence'):
        number(q,key,maximum=1)
    classes=cfg.get('classes')
    if not isinstance(classes,list) or not classes or classes[0].get('min_score')!=0:
        raise RiskInputError('Classes must start at score zero')
    prev=-1
    for entry in classes:
        if not isinstance(entry,dict) or not isinstance(entry.get('name'),str) or not entry['name'].strip():
            raise RiskInputError('Invalid score class')
        val=number(entry,'min_score',maximum=100)
        if val<=prev:raise RiskInputError('Class scores must strictly increase')
        prev=val
    if len({x['name'] for x in classes})!=len(classes):raise RiskInputError('Duplicate class name')


def score_exposure(exposure: dict, cfg: dict, *, hazard_type: str | None,
                   evidence_status: str, sar_confidence: float | None) -> dict[str, Any]:
    """Returns a conservative screening decision. No score if evidence or completeness fails."""
    config_validate(cfg)
    if exposure.get('module')!='SPECTRA-SAR/M3/T05' or exposure.get('schema_version')!='1.0.0':
        raise RiskInputError('Requires original T05 module and schema_version 1.0.0')
    stats=exposure.get('statistics')
    if not isinstance(stats,dict):raise RiskInputError('Missing T05 statistics')
    pop=number(stats,'exposed_population_estimate')
    buildings=number(stats,'potentially_exposed_buildings')
    roads=number(stats,'road_length_overlap_m')
    area=number(stats,'hazard_area_within_aoi_m2')
    coverage=number(stats,'population_cell_coverage_fraction',maximum=1)
    outside=number(stats,'population_outside_raster_fraction',maximum=1)
    if stats.get('population_result_status') not in ('COMPLETE_WITHIN_RASTER','PARTIAL'):
        raise RiskInputError('Unrecognized T05 population status')
    if isinstance(stats.get('population_cells_missing'),bool) or not isinstance(stats.get('population_cells_missing'),int) or stats['population_cells_missing']<0:
        raise RiskInputError('Invalid missing population cells')
    notes=[]
    if area==0 and (pop>0 or buildings>0 or roads>0):
        raise RiskInputError('Nonzero exposure with zero hazard area')
    if area==0:
        notes.append('No change footprint within AOI; no hazard inference possible.')
    if hazard_type not in ('flood','wildfire'):
        notes.append('Hazard type not independently verified as flood or wildfire.')
    if evidence_status!='VERIFIED':
        notes.append('Event evidence must be independently verified; a SAR change mask alone is insufficient.')
    if stats['population_result_status']!='COMPLETE_WITHIN_RASTER' or stats['population_cells_missing']>0:
        notes.append('Partial population raster coverage prevents reliable screening.')
    qual=cfg['quality']
    if coverage < qual['minimum_population_coverage'] or outside > qual['maximum_outside_raster_fraction']:
        notes.append('Population coverage below configured data-quality thresholds.')
    if sar_confidence is None or isinstance(sar_confidence,bool) or not isinstance(sar_confidence,(float,int)) or not math.isfinite(sar_confidence) or not 0<=sar_confidence<=1:
        notes.append('Missing or invalid calibrated SAR evidence confidence.')
    elif sar_confidence < qual['minimum_sar_confidence']:
        notes.append('SAR evidence confidence below configured gate.')
    if notes:
        return {'status':'REVIEW_REQUIRED','priority_score':None,'priority_class':None,
                'reasons':notes,'metrics':{'population_estimate':pop,'buildings':buildings,
                                          'roads_m':roads,'hazard_area_m2':area},
                'interpretation':'Insufficient verified evidence for exposure-based prioritization.'}
    scales=cfg['reference_scales']; weights=cfg['weights']
    # Saturating linear component scales are purely configurable normalization anchors.
    terms={'population':min(1.,pop/scales['population_people']),
           'buildings':min(1.,buildings/scales['building_count']),
           'roads':min(1.,roads/scales['road_length_m'])}
    contributions={k:round(100*weights[k]*v,6) for k,v in terms.items()}
    total=round(100*sum(weights[k]*v for k,v in terms.items()),4)
    cls=max((entry['name'] for entry in cfg['classes'] if total>=entry['min_score']),
            key=lambda name:next(x['min_score'] for x in cfg['classes'] if x['name']==name))
    return {'status':'SCREENED','priority_score':total,'priority_class':cls,
            'components_normalized':terms,'contributions':contributions,
            'metrics':{'population_estimate':pop,'buildings':buildings,'roads_m':roads,'hazard_area_m2':area},
            'reasons':['Scores reflect relative potential exposure under configured thresholds only.'],
            'interpretation':'Uncalibrated exposure-priority index; not disaster likelihood, severity, vulnerability, fatalities, losses or confirmed impact.'}


def analyze(t05_path: str | Path, config_path: str | Path, *, hazard_type: str | None,
            evidence_status: str, sar_confidence: float | None) -> dict:
    exposure=load_json(t05_path)
    cfg=yaml.safe_load(Path(config_path).read_text(encoding='utf-8'))
    if not isinstance(cfg,dict):raise RiskInputError('Config YAML must be a mapping')
    decision=score_exposure(exposure,cfg,hazard_type=hazard_type,
                            evidence_status=evidence_status,sar_confidence=sar_confidence)
    return {'schema_version':'1.0.0','module':'SPECTRA-SAR/M3/T06',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'model_id':cfg['model_id'],
            'inputs':{'t05_exposure_file':str(t05_path),'t05_sha256':digest(t05_path),
                      'config_file':str(config_path),'config_sha256':digest(config_path),
                      'hazard_type':hazard_type,'evidence_status':evidence_status,
                      'sar_confidence':sar_confidence},
            'decision':decision,
            'scientific_limitations':['Not a validated risk model; no vulnerability, capacity, frequency, or physical hazard intensity.',
                                      'A SAR change footprint is not automatically a flood or fire footprint.',
                                      'Configured thresholds and model confidence require external calibration.',
                                      'Never use this output alone for emergency or evacuation decisions.']}


def main():
    p=argparse.ArgumentParser(description='SPECTRA-SAR M3/T06 exposure-priority screening; NOT validated disaster risk')
    p.add_argument('--t05-exposure',required=True)
    p.add_argument('--config',default='risk_config.yaml')
    p.add_argument('--hazard-type',choices=['flood','wildfire','unknown'],default='unknown')
    p.add_argument('--evidence-status',choices=['VERIFIED','UNVERIFIED'],default='UNVERIFIED')
    p.add_argument('--sar-confidence',type=float,default=None,help='Only provide if externally evaluated/calibrated; not fabricated')
    p.add_argument('--out',default='data/risk/risk_assessment.json')
    a=p.parse_args()
    try:
        result=analyze(a.t05_exposure,a.config,hazard_type=a.hazard_type,
                       evidence_status=a.evidence_status,sar_confidence=a.sar_confidence)
        out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({'status':result['decision']['status'],'out':str(out),
                          'decision':result['decision']},indent=2,ensure_ascii=False))
    except (RiskInputError,ValueError,FileNotFoundError,KeyError,yaml.YAMLError) as exc:
        p.exit(2,f'REJECT: {exc}\n')

if __name__=='__main__':main()
