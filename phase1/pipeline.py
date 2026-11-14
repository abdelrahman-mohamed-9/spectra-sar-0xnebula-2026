"""Single orchestrator calling original member code, with honest partial states."""
from pathlib import Path
import shutil
import uuid
from phase1.common import ROOT, load, write, sha, now, safe, command

def run(config, output):
    out = Path(output).resolve()
    if out.exists(): raise FileExistsError('Choose a new output directory; existing runs are immutable')
    out.mkdir(parents=True)
    report = {'schema_version':'1.0','run_id':out.name,'created_at':now(),
              'status':'RUNNING','scientific_approval':False,
              'data_kind':config.get('data_kind','USER_SUPPLIED_NOT_INDEPENDENTLY_VERIFIED'),
              'stages':{x:{'status':'PENDING'} for x in ('M1','M2','M3','M4','M5','M6')}}
    def stage(member, status, detail, **extra):
        report['stages'][member] = dict(status=status,detail=detail,**extra)
        write(out/'run.json',report)
    current = 'M1'
    try:
        if config.get('pair_dir'):
            source = Path(config['pair_dir']).resolve()
            if out == source or out.is_relative_to(source) or source.is_relative_to(out):
                raise ValueError('Input/output trees must not overlap')
            manifest = load(source/'manifest.json')
            # Snapshot inputs so later stages cannot race an external edit.
            pair = out/'M1/pair'; pair.mkdir(parents=True)
            for side in ('before','after'):
                scene = manifest[side]
                rels = list(scene['raster_files'].values())
                rels += [scene[k] for k in ('valid_mask_file','layover_shadow_mask_file') if scene.get(k)]
                for rel in rels:
                    src = safe(source,rel); dst = safe(pair,rel)
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copy2(src,dst)
            write(pair/'manifest.json',manifest)
        else:
            from phase1.prepare_nisar_pair import prepare, BEFORE, AFTER
            pair = prepare(out/'M1/pair',Path(config.get('before') or BEFORE),Path(config.get('after') or AFTER))
            manifest = load(pair/'manifest.json')
        write(out/'M1/input-manifest.json',manifest)
        input_receipt = {p.relative_to(pair).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size}
                         for p in sorted(pair.rglob('*')) if p.is_file()}
        write(out/'M1/source-receipt.json',{'files':input_receipt,'provider_authenticated':False})
        stage('M1','PASS','Input snapshot + actual file digests created; scientific QA runs in M2')
        current = 'M2'
        pol = config.get('polarization') or manifest['polarizations'][0]
        args = [ROOT/'members/M2/pipeline.py',pair,'--out',out/'M2','--polarization',pol,
                '--threshold-db',str(config.get('threshold_db',3.0))]
        if config.get('exploratory',False): args.append('--allow-warning')
        for key,flag in [('model_dir','--model-dir'),('reference','--reference'),('provenance','--provenance')]:
            if config.get(key): args += [flag,config[key]]
        command(args,out/'logs/M2.log',allowed=(0,2))
        delivery = load(out/'M2/m3-delivery.json')
        # M5's original validator checks actual raster hashes + classes before conversion.
        command([ROOT/'backend/scripts/spectra_integrate.py','audit','--m2-delivery',out/'M2/m3-delivery.json'],out/'logs/M5-contract.log')
        stage('M2','PASS','Original T02–T05/T09 executed; optional T06–T08 require model/reference',
              classification_available=delivery['classification_available'],
              evaluation_available=delivery['evaluation_available'])
        current = 'M3'
        from phase1.footprint import make_footprint
        from shapely.geometry import shape, mapping
        from shapely.ops import unary_union
        mask = out/'M2'/delivery['artifacts']['mask']['path']
        geo = out/'M3/candidate-change.geojson'
        summary = make_footprint(mask,geo,min_pixels=config.get('min_pixels',9),delivery_json=out/'M2/m3-delivery.json')
        doc = load(geo)
        # M3 accepts one polygonal feature: union all candidates without changing class claims.
        if doc['features']:
            union = unary_union([shape(f['geometry']) for f in doc['features']])
            if not union.is_valid: raise ValueError('Candidate geometry invalid; manual QA needed')
            hazard = out/'M3/candidate-union.geojson'
            write(hazard,{'type':'Feature','geometry':mapping(union),'properties':{
                  'hazard_type':'unknown','evidence_status':'UNVERIFIED','scientific_approval':False}})
        impact = config.get('impact') or {}
        required = ('aoi','osm','population','population_unit','population_provenance')
        missing = [k for k in required if not impact.get(k)]
        write(out/'M3/candidate-summary.json',summary)
        if not doc['features']:
            stage('M3','NO_CANDIDATES','No retained candidate footprint; exposure not computed')
        elif missing:
            # M3 may have a fully authenticated source with NO usable resident-population
            # raster; acknowledge the scientific gap without failing other members.
            gap = config.get('impact_gap')
            if gap:
                gap_src = Path(gap['report']).resolve()
                gap_doc = load(gap_src)
                if gap_doc.get('status')!='PARTIAL_DATA_GAP' or gap_doc.get('estimated_people_exposed_to_radar_change','INVALID') is not None or gap_doc.get('population_spatial_status')!='UNAVAILABLE':
                    raise ValueError('Invalid M3 population-gap evidence; refusing to bypass data QA')
                gap_copy=out/'M3/population-data-gap.json'
                write(gap_copy,gap_doc)
                stage('M3','PARTIAL_DATA_GAP','Real SAR change candidates available; spatial population/infrastructure exposure NOT calculated.',
                      documentation=str(gap_copy.relative_to(out)),missing=missing,
                      aggregate_is_NOT_spatial_exposure=True)
            else:
                stage('M3','BLOCKED','Candidate GeoJSON produced; independent impact inputs missing',missing=missing)
        else:
            cfg = {**impact,'hazard':str(hazard),'hazard_type':'unknown','evidence_status':'UNVERIFIED',
                   'sar_confidence':None,'hazard_provenance':'Unverified M2 radiometric candidates; mask SHA256 '+sha(mask)}
            write(out/'M3/impact-config.json',cfg)
            try:
                command([ROOT/'members/M3/T09/pipeline.py','--config',out/'M3/impact-config.json','--out',out/'M3/impact'],out/'logs/M3.log')
                result = load(out/'M3/impact/run_manifest.json')
                if result['status'] != 'PIPELINE_EXECUTED' or result['risk_status'] != 'REVIEW_REQUIRED':
                    raise ValueError('Unexpected M3 scientific status')
                stage('M3','PASS','Original T03–T08 executed; risk remains REVIEW_REQUIRED')
            except Exception as exc:
                stage('M3','BLOCKED',str(exc))
        current = 'M4'
        command(['-m','phase1.worker','m4',out],out/'logs/M4.log')
        stage('M4','PASS','Original evidence builder + SHA256 verifier executed')
        current = 'M5'
        write(out/'M5/run-contract.json',{'run_id':out.name,'schema_version':'1.0',
              'scientific_approval':False,'m2_delivery':'M2/m3-delivery.json','m4_evidence':'M4/evidence.json',
              'candidate_geojson':'M3/candidate-change.geojson','mode':'LOCAL_FILES',
              'postgres_redis_minio_verified':False,
              'api_resource':'/api/v1/phase1/runs/'+out.name})
        stage('M5','PASS','M5 handoff validated and local API resource prepared; distributed services separate')
        current = 'M6'
        command(['-m','phase1.worker','m6',out],out/'logs/M6.log')
        stage('M6','PASS','Original provenance schema + independent local-byte verifier executed')
        report['status'] = 'PARTIAL' if report['stages']['M3']['status'] in ('BLOCKED','PARTIAL_DATA_GAP') else 'COMPLETED_EXPLORATORY'
    except Exception as exc:
        stage(current,'BLOCKED',str(exc))
        report['status']='BLOCKED'
        for member, record in report['stages'].items():
            if record['status']=='PENDING': stage(member,'BLOCKED',f'Upstream {current} did not complete')
    report['finished_at']=now()
    write(out/'run.json',report)
    return report

def fresh_run(config, runs_root=None):
    root = Path(runs_root or ROOT/'runs')
    return run(config,root/str(uuid.uuid4()))
