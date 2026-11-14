"""M5 Celery adapter: complete local pipeline → private MinIO → M5 DB.

Requires an existing real project, scene pair and queued `other` job whose
input_parameters are {"pipeline":"phase1","config_name":"local.json"}.
No other member's competing database migrations are used.
"""
import os
import re
from pathlib import Path
from uuid import uuid4
from fastapi import UploadFile
from phase1.common import ROOT, load, safe, sha, command
from phase1.configuration import resolve_config
from phase1.pipeline import run

def handle(db,job):
    from spectra.persistence.models import ScenePair,SarScene,Artifact,ChangeResult,ImpactAssessment,AuditEvent
    from spectra.storage.storage_service import upload_artifact,delete_managed
    parameters=job.input_parameters or {}
    if parameters.get('pipeline')!='phase1': raise ValueError('Expected pipeline=phase1')
    config_name=parameters.get('config_name','local.json')
    if not re.fullmatch(r'[A-Za-z0-9_-]+\.json',config_name): raise ValueError('Invalid config name')
    pair=db.get(ScenePair,job.scene_pair_id)
    if pair is None or pair.project_id!=job.project_id:raise ValueError('Job needs matching project scene pair')
    scenes=[db.get(SarScene,pair.before_scene_id),db.get(SarScene,pair.after_scene_id)]
    if not all(scenes):raise ValueError('Scene metadata is missing')
    root=Path(os.getenv('SPECTRA_RUNS_DIR',str(ROOT/'runs')))
    out=root/str(job.id)
    if out.exists():
        result=load(out/'run.json')
    else:
        result=run(resolve_config(load(safe(ROOT/'config',config_name))),out)
    if result['status']!='COMPLETED_EXPLORATORY':
        raise RuntimeError('Phase1 incomplete; inspect local run report before creating a new job')
    manifest=load(out/'M1/input-manifest.json')
    if [s.provider_item_id for s in scenes] != [manifest[k]['scene_id'] for k in ('before','after')]:
        raise ValueError('Run scene IDs differ from the database scene pair')
    command(['-m','phase1.worker','verify',out],out/'logs/distributed-verify.log')
    delivery=load(out/'M2/m3-delivery.json')
    mask='M2/'+delivery['artifacts']['mask']['path']
    objects={};uploaded=[]
    try:
        entries=list(load(out/'M6/provenance.json')['artifacts'])
        for rel in ('M6/provenance.json','M6/verification.json','run.json'):
            entries.append({'storage_uri':'file://'+rel,'sha256':sha(out/rel)})
        for artifact in entries:
            rel=artifact['storage_uri'].removeprefix('file://')
            path=safe(out,rel)
            if sha(path)!=artifact['sha256']:raise ValueError('Artifact changed before publication')
            # Store all analysis/evidence JSON and TIFFs; logs remain local.
            if path.suffix not in ('.json','.geojson','.tif','.tiff','.png'):continue
            with path.open('rb') as stream:
                saved=upload_artifact(UploadFile(filename=path.name,file=stream),job.project_id)
            uploaded.append(saved.uri)
            if saved.sha256!=artifact['sha256']:raise ValueError('Upload snapshot differs from evidence')
            obj=Artifact(id=uuid4(),project_id=job.project_id,kind='change_mask' if rel==mask else 'other',
                         storage_uri=saved.uri,media_type=saved.media_type,size_bytes=saved.size_bytes,
                         sha256=saved.sha256,metadata_json={'relative_path':rel,'run_id':str(job.id),
                                                           'scientific_approval':False})
            db.add(obj);objects[rel]=obj
        change=ChangeResult(id=uuid4(),job_id=job.id,scene_pair_id=pair.id,
                           change_mask_artifact_id=objects[mask].id,
                           algorithm=str(delivery['change_detection']['method'])[:100],algorithm_version='M2-T09',
                           mean_confidence=None,changed_area_m2=None,
                           evaluation_metrics={'scientific_approval':False,
                               'candidate_change_area_km2':delivery['change_detection']['candidate_change_area_km2'],
                               'delivery_status':delivery['delivery_status']})
        db.add(change)
        risk=out/'M3/impact/risk_assessment.json'
        if risk.exists():
            risk_doc=load(risk)
            db.add(ImpactAssessment(id=uuid4(),change_result_id=change.id,job_id=job.id,
                assessment_type='exploratory_geospatial_exposure',risk_level='unknown',population_estimate=None,
                risk_artifact_id=objects['M3/impact/risk_assessment.json'].id,
                findings={'decision':risk_doc['decision'],'scientific_approval':False},
                methods_and_sources={'m3_manifest':load(out/'M3/impact/run_manifest.json')}))
        db.add(AuditEvent(id=uuid4(),project_id=job.project_id,actor_id='phase1-worker',
                         action='phase1.exploratory_completed',entity_type='processing_job',entity_id=job.id,
                         event_details={'run_id':str(job.id),'artifacts':len(objects),'scientific_approval':False}))
        db.flush()
    except Exception:
        # Database transaction is rolled back by the existing M5 task runner.
        for uri in reversed(uploaded):
            try:delete_managed(uri)
            except Exception:pass  # Object store reconciliation may be required after outages.
        raise
