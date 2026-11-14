#!/usr/bin/env python3
"""M3 Phase 1 pipeline orchestration. Does not download or fabricate live data."""
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

BASE=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''):h.update(chunk)
    return h.hexdigest()

def run_stage(label,args,folder):
    r=subprocess.run([sys.executable,*map(str,args)],cwd=str(folder),capture_output=True,text=True)
    if r.returncode:
        raise RuntimeError(f'{label} failed (exit {r.returncode}): {(r.stderr or r.stdout)[-2500:]}')
    return {'stage':label,'result':'PASS','stdout':r.stdout.strip()[-1200:]}

def verify_stage(path,expected):
    doc=json.loads(Path(path).read_text(encoding='utf8'))
    if doc.get('module')!=expected or doc.get('schema_version')!='1.0.0':
        raise ValueError(f'Invalid module/schema in {path}: {doc.get("module")}')
    return doc

def execute(cfg, output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    manifest=[]
    raw={k:Path(cfg[k]).resolve() for k in ('aoi','osm','population','hazard')}
    for k,v in raw.items():
        if not v.is_file():raise FileNotFoundError(f'{k}: {v}')
    for k in ('hazard_provenance','population_provenance'):
        if not isinstance(cfg.get(k),str) or not cfg[k].strip():raise ValueError(f'{k} required')
    pop_unit=cfg.get('population_unit')
    if pop_unit not in ('count_per_pixel','density_per_km2'):raise ValueError('population_unit required and explicit')
    qa=output/'qa_report.json'
    cmd=['geo_validator.py','--aoi',raw['aoi'],'--osm',raw['osm'],'--population',raw['population'],'--report',qa]
    if cfg.get('source_manifest'):cmd+=['--manifest',Path(cfg['source_manifest']).resolve()]
    manifest.append(run_stage('T03',cmd,BASE/'modules/T03'))
    qa_obj=json.loads(qa.read_text())
    if qa_obj['overall_status']=='WARNING' and not cfg.get('approve_qa_warning',False):
        raise ValueError('T03 WARNING requires explicit documented analyst approval')
    spatial=output/'spatial_metrics.json';clipped=output/'clipped_hazard.geojson'
    cmd=['spatial_engine.py','--aoi',raw['aoi'],'--hazard',raw['hazard'],'--osm',raw['osm'],
         '--qa-report',qa,'--hazard-provenance',cfg['hazard_provenance'],'--out',spatial,'--clipped-hazard-out',clipped]
    if cfg.get('approve_qa_warning'):cmd+=['--approve-qa-warning']
    manifest.append(run_stage('T04',cmd,BASE/'modules/T04'))
    verify_stage(spatial,'SPECTRA-SAR/M3/T04')
    exposure=output/'exposure_metrics.json'
    cmd=['exposure_engine.py','--t04-metrics',spatial,'--clipped-hazard',clipped,'--population',raw['population'],
         '--qa-report',qa,'--population-provenance',cfg['population_provenance'],
         '--population-unit',pop_unit,'--out',exposure]
    if cfg.get('approve_qa_warning'):cmd+=['--approve-qa-warning']
    manifest.append(run_stage('T05',cmd,BASE/'modules/T05'))
    verify_stage(exposure,'SPECTRA-SAR/M3/T05')
    risk=output/'risk_assessment.json'
    cmd=['risk_engine.py','--t05-exposure',exposure,'--config',BASE/'modules/T06/risk_config.yaml',
         '--hazard-type',cfg.get('hazard_type','unknown'),'--evidence-status',cfg.get('evidence_status','UNVERIFIED'),
         '--out',risk]
    if cfg.get('sar_confidence') is not None:cmd+=['--sar-confidence',str(cfg['sar_confidence'])]
    manifest.append(run_stage('T06',cmd,BASE/'modules/T06'))
    verify_stage(risk,'SPECTRA-SAR/M3/T06')
    stats=output/'impact_statistics.json'
    manifest.append(run_stage('T07',['impact_metrics.py','--t05',exposure,'--t06',risk,'--t04',spatial,'--out',stats],BASE/'modules/T07'))
    verify_stage(stats,'SPECTRA-SAR/M3/T07')
    decisions=output/'decision_recommendations.json'
    manifest.append(run_stage('T08',['decision_engine.py','--t07',stats,'--t06',risk,
         '--rules',BASE/'modules/T08/recommendation_rules.yaml','--out',decisions],BASE/'modules/T08'))
    verify_stage(decisions,'SPECTRA-SAR/M3/T08')
    output_files={'t03_qa':qa,'t04_spatial':spatial,'t04_hazard':clipped,
                  't05_exposure':exposure,'t06_risk':risk,'t07_stats':stats,'t08_decisions':decisions}
    result={'schema_version':'1.0.0','module':'SPECTRA-SAR/M3/T09','generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'status':'PIPELINE_EXECUTED','live_data_verified':False,
            'note':'Execution does not establish that source data, hazard identification, confidence, or scientific model is independently validated.',
            'steps':manifest,'inputs':{k:{'path':str(v),'sha256':sha(v)} for k,v in raw.items()},
            'outputs':{k:{'path':str(v),'sha256':sha(v)} for k,v in output_files.items()},
            'risk_status':json.loads(risk.read_text())['decision']['status']}
    (output/'run_manifest.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    return result

def main():
    p=argparse.ArgumentParser(description='M3 pipeline T03-T08; input data is NEVER automatically synthesized')
    p.add_argument('--config',required=True,help='JSON config with paths and provenance');p.add_argument('--out',required=True)
    args=p.parse_args()
    try:
        cfg=json.loads(Path(args.config).read_text(encoding='utf8'))
        result=execute(cfg,args.out)
        print(json.dumps({'status':result['status'],'risk_status':result['risk_status'],'manifest':str(Path(args.out).resolve()/'run_manifest.json')},indent=2))
    except (OSError,KeyError,ValueError,RuntimeError,TypeError) as e:
        p.exit(2,f'PIPELINE FAILED: {e}\n')
if __name__=='__main__':main()
