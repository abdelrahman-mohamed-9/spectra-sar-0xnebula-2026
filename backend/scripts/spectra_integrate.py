#!/usr/bin/env python3
"""M2→M3→M5 real-data integration CLI. Never fabricates observations or outcomes.

Audit and preparation require real georeferenced M2 files. M3 only runs with
real operator-supplied OSM + population + AOI. Publication requires existing
M5 project, pair and jobs and a private backend service key.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlparse
from uuid import UUID

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
M2 = ROOT.parent / 'members' / 'M2'
M3 = ROOT.parent / 'members' / 'M3' / 'T09'


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(path):
    with Path(path).open('rb') as f:
        h=hashlib.sha256()
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()


def verified_m2(manifest):
    path=Path(manifest).resolve()
    if not path.is_file():raise ValueError(f'M2 delivery not found: {path}')
    doc=load(path)
    if doc.get('schema_version')!='1.0' or doc.get('producer')!='SPECTRA-SAR-M2-T09':
        raise ValueError('Not an M2 T09 delivery')
    if doc.get('scientific_approval') is not False or doc.get('delivery_status')!='EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED':
        raise ValueError('Unrecognized scientific validation status')
    if not doc.get('pair_id') or not doc.get('polarization') in ('VV','VH','HHHH'):
        raise ValueError('Missing M2 pair provenance')
    artifacts=doc.get('artifacts',{})
    # M2 outputs are relative to the directory holding m3-delivery.json.
    for key, item in artifacts.items():
        rel=Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise ValueError(f'Unsafe artifact path for {key}')
        absolute=(path.parent/rel).resolve()
        if not absolute.is_relative_to(path.parent) or not absolute.is_file():
            raise ValueError(f'Missing M2 artifact {key}: {absolute}')
        if digest(absolute)!=item['sha256']:
            raise ValueError(f'Checksum mismatch for {key}')
    mask_key=next((k for k in artifacts if k in ('change_mask','mask','change_class_mask')),None)
    if mask_key is None:
        candidates=[k for k in artifacts if k.startswith('change_mask')]
        if len(candidates)==1:mask_key=candidates[0]
    if mask_key is None:
        raise ValueError('Missing M2 four-class change_mask artifact')
    mask=path.parent / artifacts[mask_key]['path']
    try:
        import rasterio
        import numpy as np
    except ImportError as exc:raise RuntimeError('Install numpy rasterio first') from exc
    with rasterio.open(mask) as ds:
        if ds.count!=1 or ds.crs is None or ds.transform.is_identity:
            raise ValueError('Mask requires a valid single-band geospatial grid')
        for _, window in ds.block_windows(1):
            v=ds.read(1,window=window)
            if not np.isin(v,[0,1,2,255]).all():
                raise ValueError('Mask classes must be 0, 1, 2, 255')
    return doc, mask.resolve()


def command(args, allow_exploratory=False):
    p=subprocess.run(args,check=False)
    if p.returncode==2 and allow_exploratory:
        return
    if p.returncode:raise RuntimeError(f'Process exited {p.returncode}: {args[0]}')


def audit(args):
    if args.m2_delivery:
        doc,mask=verified_m2(args.m2_delivery)
        print(json.dumps({'M2':'VERIFIED_FILES_NOT_SCIENTIFIC_CERTIFICATION','mask':str(mask),
            'pair_id':doc['pair_id'],'artifacts':len(doc['artifacts'])},indent=2))
    else:
        print('M2 source code present; no real m3-delivery.json was supplied')
    print(json.dumps({'M3_source_present':(M3/'pipeline.py').exists(),
                      'M5_backend_present':(ROOT/'src/spectra/main.py').exists()},indent=2))


def m2_run(args):
    if not Path(args.pair_dir).is_dir():raise ValueError('Real M1 pair directory is required')
    out=Path(args.out).resolve()
    if out.exists():raise ValueError('Output already exists; refusing to overwrite')
    command([sys.executable,str(M2/'pipeline.py'),str(Path(args.pair_dir).resolve()),
             '--out',str(out),'--polarization',args.polarization],allow_exploratory=True)
    verified_m2(out/'m3-delivery.json')
    print('M2 verified deliverable:',out/'m3-delivery.json')


def prepare(args):
    doc,mask=verified_m2(args.m2_delivery)
    out=Path(args.out).resolve()
    if out.exists():raise ValueError('Output already exists; refusing to overwrite')
    out.mkdir(parents=True)
    geojson=out/'candidate_change_footprint.geojson'
    command([sys.executable,str(HERE/'m2_mask_to_m3_geojson.py'),'--mask',str(mask),'--out',str(geojson)])
    package={
        'schema_version':'1.0','source':'SPECTRA-SAR-M2-T09',
        'pair_id':doc['pair_id'],'polarization':doc['polarization'],
        'm2_manifest_path':str(Path(args.m2_delivery).resolve()),
        'm2_manifest_sha256':digest(args.m2_delivery),
        'mask_path':str(mask),'mask_sha256':digest(mask),
        'candidate_geojson':str(geojson),'geojson_sha256':digest(geojson),
        'evidence_status':'UNVERIFIED',
        'scientific_approval':False,
        'limitations':doc['limitations']
    }
    (out/'bridge-manifest.json').write_text(json.dumps(package,indent=2)+'\n')
    print('Prepared real M2 → M3 candidate geometry:',geojson)


def verified_bridge(path):
    doc=load(path)
    if doc.get('evidence_status')!='UNVERIFIED' or doc.get('scientific_approval') is not False:
        raise ValueError('Bridge scientific status invalid')
    for name,path_key,hash_key in [('M2 source','m2_manifest_path','m2_manifest_sha256'),
                                   ('mask','mask_path','mask_sha256'),
                                   ('GeoJSON','candidate_geojson','geojson_sha256')]:
        p=Path(doc[path_key]);
        if not p.is_file() or digest(p)!=doc[hash_key]:raise ValueError(f'{name} modified or missing')
    verified_m2(doc['m2_manifest_path'])
    return doc


def m3_run(args):
    bridge=verified_bridge(args.bridge)
    for key in ('aoi','osm','population'):
        if not Path(getattr(args,key)).is_file():
            raise ValueError(f'Real M3 input {key} is missing')
    cfg={'aoi':str(Path(args.aoi).resolve()),
         'osm':str(Path(args.osm).resolve()),
         'population':str(Path(args.population).resolve()),
         'hazard':bridge['candidate_geojson'],
         'hazard_provenance':f"M2 unverified SAR candidate change; sha256={bridge['mask_sha256']}; pair={bridge['pair_id']}",
         'population_provenance':args.population_provenance,
         'population_unit':args.population_unit,
         'hazard_type':'unknown','evidence_status':'UNVERIFIED',
         'sar_confidence':None,'approve_qa_warning':args.approve_qa_warning}
    out=Path(args.out).resolve()
    if out.exists():raise ValueError('Output already exists; refusing to overwrite')
    out.mkdir(parents=True)
    config=out/'integration-config.json'
    config.write_text(json.dumps(cfg,indent=2)+'\n')
    command([sys.executable,str(M3/'pipeline.py'),'--config',str(config),'--out',str(out)])
    report=load(out/'run_manifest.json')
    if report.get('status')!='PIPELINE_EXECUTED':raise ValueError('M3 output did not complete')
    (out/'m5-provenance.json').write_text(json.dumps({'bridge_manifest':str(Path(args.bridge).resolve()),
        'bridge_sha256':digest(args.bridge),'m3_manifest_sha256':digest(out/'run_manifest.json'),
        'scientific_approval':False,'evidence_status':'UNVERIFIED'},indent=2)+'\n')
    print('M3 executed with actual inputs. Scientific status remains UNVERIFIED:',out)


def uuid(value):return str(UUID(str(value)))


def backend_client(args):
    base=args.api_url.rstrip('/')
    u=urlparse(base)
    if u.scheme not in ('http','https') or not u.netloc or u.username or u.password:
        raise ValueError('Invalid backend URL')
    if u.scheme=='http' and u.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('Plain HTTP only allowed for localhost; use HTTPS')
    secret=os.getenv('SPECTRA_INTERNAL_API_KEY','')
    if len(secret)<32:raise ValueError('Set SPECTRA_INTERNAL_API_KEY (>=32 characters)')
    import requests
    return requests.Session(),base,{'X-API-Key':secret}


def publish(args):
    bridge=verified_bridge(args.bridge)
    m3dir=Path(args.m3_output).resolve()
    run=load(m3dir/'run_manifest.json')
    if run.get('module')!='SPECTRA-SAR/M3/T09' or run.get('status')!='PIPELINE_EXECUTED':
        raise ValueError('M3 run manifest invalid')
    for item in run['outputs'].values():
        p=Path(item['path'])
        if not p.is_file() or digest(p)!=item['sha256']:
            raise ValueError(f'M3 output changed or missing: {p}')
    proof=load(m3dir/'m5-provenance.json')
    if proof['bridge_sha256'] != digest(args.bridge) or proof['m3_manifest_sha256']!=digest(m3dir/'run_manifest.json'):
        raise ValueError('M3 outputs and M2 bridge mismatch')
    risk=load(m3dir/'risk_assessment.json')
    metrics=load(m3dir/'impact_statistics.json')
    if risk.get('decision',{}).get('status')!='REVIEW_REQUIRED':
        raise ValueError('Unverified SAR evidence must not be presented as scored risk')
    project, pair, change_job, impact_job=map(uuid,(args.project_id,args.scene_pair_id,args.change_job_id,args.impact_job_id))
    if change_job==impact_job:raise ValueError('Use distinct M2/M3 processing jobs')
    session,base,headers=backend_client(args)
    def api(method,path,**kw):
        r=session.request(method,base+'/api/v1'+path,headers=headers,timeout=180,**kw)
        if not r.ok:raise RuntimeError(f'{method} {path} → HTTP {r.status_code}: {r.text[:500]}')
        return r.json()
    # Authoritative server-side IDs are required; no fabricated foreign keys.
    for kind,pk in [('scene-pairs',pair),('jobs',change_job),('jobs',impact_job)]:
        doc=api('GET',f'/resources/{kind}/{pk}')
        if doc.get('project_id')!=project:
            raise ValueError(f'{kind}/{pk} is not owned by project {project}')
    state_path=Path(args.state).resolve()
    if state_path.exists():
        state=load(state_path)
        if state['bridge_sha256']!=digest(args.bridge) or state['m3_manifest_sha256']!=digest(m3dir/'run_manifest.json'):
            raise ValueError('Existing state belongs to different inputs')
    else:
        state={'bridge_sha256':digest(args.bridge),'m3_manifest_sha256':digest(m3dir/'run_manifest.json'),
               'project_id':project,'scene_pair_id':pair,'change_job_id':change_job,'impact_job_id':impact_job}
    def save():
        state_path.parent.mkdir(parents=True,exist_ok=True)
        state_path.write_text(json.dumps(state,indent=2)+'\n')
    def upload(label,file,kind):
        if label in state:return state[label]
        p=Path(file)
        with p.open('rb') as f:
            obj=api('POST','/storage/artifacts/upload',data={'project_id':project,'kind':kind},
                    files={'file':(p.name,f,'application/octet-stream')})
        state[label]=uuid(obj['id']);save();return state[label]
    maskid=upload('mask_artifact_id',bridge['mask_path'],'change_mask')
    if 'change_result_id' not in state:
        change_doc=load(bridge['m2_manifest_path'])
        candidate_km2=change_doc['change_detection'].get('candidate_change_area_km2')
        payload={'job_id':change_job,'scene_pair_id':pair,'change_mask_artifact_id':maskid,
                 'algorithm':str(change_doc['change_detection']['method'])[:100],
                 'algorithm_version':'M2-T09-v1',
                 'mean_confidence':None,'changed_area_m2':None,
                 'evaluation_metrics':{'candidate_change_area_km2':candidate_km2,
                    'estimated_area_not_ground_truth':True,'scientific_approval':False,
                    'delivery_status':change_doc['delivery_status'],
                    'mask_sha256':bridge['mask_sha256'],'pair_id':bridge['pair_id'],
                    'limitations':bridge['limitations']}}
        obj=api('POST','/resources/change-results',json=payload)
        state['change_result_id']=uuid(obj['id']);save()
    riskid=upload('risk_report_artifact_id',m3dir/'risk_assessment.json','report')
    if 'impact_assessment_id' not in state:
        payload={'change_result_id':state['change_result_id'],'job_id':impact_job,
                 'assessment_type':'exploratory_geospatial_exposure','risk_level':'unknown',
                 'risk_artifact_id':riskid,'population_estimate':None,
                 'findings':{'decision':risk['decision'],'summary':metrics.get('summary',{}),
                             'data_quality':metrics.get('data_quality',{}),
                             'scientific_approval':False,'evidence_status':'UNVERIFIED'},
                 'methods_and_sources':{'m2_bridge_sha256':digest(args.bridge),
                     'm3_manifest_sha256':digest(m3dir/'run_manifest.json'),
                     'm3_provenance':run.get('inputs',{}),
                     'limitations':risk.get('scientific_limitations',[])}}
        obj=api('POST','/resources/impact-assessments',json=payload)
        state['impact_assessment_id']=uuid(obj['id']);save()
    print(json.dumps({'status':'M5_RECORDS_CREATED_NOT_SCIENTIFICALLY_VALIDATED',
                      'ids':state,'state_file':str(state_path)},indent=2))


def parse():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('audit');a.add_argument('--m2-delivery');a.set_defaults(fn=audit)
    a=sub.add_parser('run-m2');a.add_argument('--pair-dir',required=True);a.add_argument('--out',required=True)
    a.add_argument('--polarization',choices=['VV','VH','HHHH'],default='VV');a.set_defaults(fn=m2_run)
    a=sub.add_parser('prepare-m3');a.add_argument('--m2-delivery',required=True);a.add_argument('--out',required=True);a.set_defaults(fn=prepare)
    a=sub.add_parser('run-m3');a.add_argument('--bridge',required=True);a.add_argument('--aoi',required=True)
    a.add_argument('--osm',required=True);a.add_argument('--population',required=True)
    a.add_argument('--population-provenance',required=True)
    a.add_argument('--population-unit',required=True,choices=['count_per_pixel','density_per_km2'])
    a.add_argument('--approve-qa-warning',action='store_true');a.add_argument('--out',required=True);a.set_defaults(fn=m3_run)
    a=sub.add_parser('publish-m5');a.add_argument('--bridge',required=True);a.add_argument('--m3-output',required=True)
    a.add_argument('--project-id',required=True);a.add_argument('--scene-pair-id',required=True)
    a.add_argument('--change-job-id',required=True);a.add_argument('--impact-job-id',required=True)
    a.add_argument('--api-url',default='http://127.0.0.1:8000');a.add_argument('--state',required=True)
    a.set_defaults(fn=publish)
    return p.parse_args()

if __name__=='__main__':
    args=parse()
    try:args.fn(args)
    except Exception as exc:
        print(f'INTEGRATION BLOCKED: {exc}',file=sys.stderr)
        sys.exit(1)
