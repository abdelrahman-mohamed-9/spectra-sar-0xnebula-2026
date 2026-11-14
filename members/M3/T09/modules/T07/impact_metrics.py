"""SPECTRA-SAR M3 T07: evidence-preserving impact statistics dashboard export.

Reports potential EXPOSURE, never confirmed physical damage or casualties.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = '1.0.0'
class MetricsError(ValueError):
    pass

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path, expected):
    doc = json.loads(Path(path).read_text(encoding='utf-8'), parse_constant=lambda x: (_ for _ in ()).throw(MetricsError('Nonfinite JSON number: '+x)))
    if not isinstance(doc, dict) or doc.get('module') != expected or doc.get('schema_version') != SCHEMA:
        raise MetricsError('Expected '+expected+' schema_version '+SCHEMA)
    return doc

def finite_nonnegative(obj, key):
    v=obj.get(key)
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0:
        raise MetricsError('Invalid or missing metric: '+key)
    return v

def fraction(obj,key):
    v=finite_nonnegative(obj,key)
    if v>1: raise MetricsError('Fraction out of range: '+key)
    return v

def build_report(t05_path, t06_path, t04_path=None):
    t05=load(t05_path,'SPECTRA-SAR/M3/T05')
    t06=load(t06_path,'SPECTRA-SAR/M3/T06')
    if t06.get('inputs',{}).get('t05_sha256') != digest(t05_path):
        raise MetricsError('T06 does not reference the exact T05 file; refuse mismatched event')
    s=t05.get('statistics')
    if not isinstance(s,dict): raise MetricsError('Missing T05 statistics')
    pop=finite_nonnegative(s,'exposed_population_estimate')
    buildings=finite_nonnegative(s,'potentially_exposed_buildings')
    if int(buildings)!=buildings: raise MetricsError('Building count must be integral')
    roads=finite_nonnegative(s,'road_length_overlap_m')
    area=finite_nonnegative(s,'hazard_area_within_aoi_m2')
    footprint=finite_nonnegative(s,'building_footprint_overlap_m2')
    coverage=fraction(s,'population_cell_coverage_fraction')
    outside=fraction(s,'population_outside_raster_fraction')
    missing=s.get('population_cells_missing')
    if isinstance(missing,bool) or not isinstance(missing,int) or missing<0:
        raise MetricsError('Invalid population_cells_missing')
    status=s.get('population_result_status')
    if status not in ('COMPLETE_WITHIN_RASTER','PARTIAL'):
        raise MetricsError('Unrecognized population_result_status')
    incomplete=(status=='PARTIAL' or missing>0 or outside>1e-8 or coverage<1-1e-8)
    if status=='COMPLETE_WITHIN_RASTER' and incomplete:
        raise MetricsError('Complete population status contradicts incomplete coverage')
    if area==0 and (pop>0 or buildings>0 or roads>0 or footprint>0):
        raise MetricsError('Nonzero exposure but zero change footprint')
    d=t06.get('decision')
    if not isinstance(d,dict): raise MetricsError('Missing T06 decision')
    decision_status=d.get('status')
    if decision_status not in ('SCREENED','REVIEW_REQUIRED'):
        raise MetricsError('Unsupported T06 decision status')
    if decision_status=='SCREENED':
        score=d.get('priority_score')
        if isinstance(score,bool) or not isinstance(score,(float,int)) or not math.isfinite(score) or not 0<=score<=100:
            raise MetricsError('Invalid priority score')
        if d.get('priority_class') not in ('LOW','MODERATE','HIGH','VERY_HIGH'):
            raise MetricsError('Invalid priority class')
        if incomplete: raise MetricsError('Scored T06 conflicts with partial population data')
    else:
        if d.get('priority_score') is not None or d.get('priority_class') is not None:
            raise MetricsError('REVIEW_REQUIRED must not include score or class')
    result={
        'schema_version':SCHEMA,'module':'SPECTRA-SAR/M3/T07',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'inputs':{'t05_sha256':digest(t05_path),'t06_sha256':digest(t06_path),
                  'population_provenance':t05.get('inputs',{}).get('population_provenance'),
                  'hazard_provenance':t05.get('inputs',{}).get('hazard_provenance')},
        'summary':{'change_footprint_area_km2':round(area/1e6,6),
                   'potentially_exposed_population_estimate':round(pop,3),
                   'population_estimate_is_complete':not incomplete,
                   'potentially_exposed_buildings':int(buildings),
                   'building_footprint_overlap_km2':round(footprint/1e6,6),
                   'road_overlap_km':round(roads/1000,6),
                   'exposure_priority_status':decision_status,
                   'exposure_priority_index':d.get('priority_score') if decision_status=='SCREENED' else None,
                   'exposure_priority_class':d.get('priority_class') if decision_status=='SCREENED' else None},
        'data_quality':{'population_result_status':status,
                        'population_cell_coverage_fraction':coverage,
                        'population_outside_raster_fraction':outside,
                        'population_cells_missing':missing,
                        'priority_review_reasons':d.get('reasons',[]) if decision_status=='REVIEW_REQUIRED' else []},
        'dashboard_cards':[
          {'id':'change_area','title':'Observed change footprint','value':round(area/1e6,6),'unit':'km²','interpretation':'SAR-derived spatial change, not confirmed hazard damage'},
          {'id':'population','title':'Potentially exposed population','value':round(pop,3),'unit':'estimated people','status':'PARTIAL' if incomplete else 'COMPLETE_WITHIN_RASTER', 'interpretation':'Model-based geospatial estimate, not counted harmed people'},
          {'id':'buildings','title':'Intersecting OSM buildings','value':int(buildings),'unit':'features','interpretation':'Mapped buildings intersecting change footprint, not destroyed structures'},
          {'id':'roads','title':'Intersecting road length','value':round(roads/1000,6),'unit':'km','interpretation':'Geospatial road overlap, not damaged roads'},
          {'id':'priority','title':'Relative exposure priority','value':d.get('priority_score') if decision_status=='SCREENED' else None,'unit':'index 0–100','status':decision_status,'interpretation':'Uncalibrated relative prioritization; not disaster risk or emergency guidance'}
        ],
        'warnings':list(dict.fromkeys((t05.get('warnings') or []) + [
          'No casualty, confirmed damage, displacement or economic-loss figures are inferred.',
          'Never use this report alone for evacuation or emergency response.'])),
    }
    if t04_path is not None:
        t04=load(t04_path,'SPECTRA-SAR/M3/T04')
        if t05.get('inputs',{}).get('t04_metrics_sha256')!=digest(t04_path):
            raise MetricsError('T05 does not reference the exact T04 report')
        s4=t04.get('statistics',{})
        aoi=finite_nonnegative(s4,'aoi_area_m2')
        if aoi<=0 or area>aoi+1e-3: raise MetricsError('Invalid AOI area')
        if abs(finite_nonnegative(s4,'hazard_area_within_aoi_m2')-area)>1e-3:
            raise MetricsError('T04 and T05 hazard areas disagree')
        if abs(finite_nonnegative(s4,'road_length_overlap_m')-roads)>1e-3 or finite_nonnegative(s4,'potentially_exposed_buildings')!=buildings:
            raise MetricsError('T04 and T05 asset statistics disagree')
        result['inputs']['t04_sha256']=digest(t04_path)
        result['summary']['aoi_area_km2']=round(aoi/1e6,6)
        result['summary']['change_footprint_percent_of_aoi']=round(100*area/aoi,5)
    return result

def main():
    p=argparse.ArgumentParser(description='Generate M3/T07 dashboard report from real, matching T05 + T06 JSON')
    p.add_argument('--t05',required=True);p.add_argument('--t06',required=True)
    p.add_argument('--t04');p.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        report=build_report(args.t05,args.t06,args.t04)
        out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({'status':'PASS','out':str(out),'summary':report['summary']},indent=2))
    except (MetricsError,OSError,ValueError,KeyError) as exc:
        p.exit(2,'ERROR: '+str(exc)+'\n')

if __name__=='__main__': main()
