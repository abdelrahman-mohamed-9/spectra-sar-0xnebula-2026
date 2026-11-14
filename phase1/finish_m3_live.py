#!/usr/bin/env python3
"""Run real M3 T02-T09 then rerun M1-M6 using actual NISAR snapshots.

No generated/synthetic population, building data, or claims of confirmed hazard.
Data acquisition occurs only on user's machine with working internet.
"""
from __future__ import annotations
import argparse, datetime, hashlib, json, os, shutil, subprocess, sys, traceback
from pathlib import Path
from phase1.common import ROOT
from phase1.pipeline import fresh_run
from phase1.population_gap import is_only_population_nodata, request_worldpop_aggregate, create_population_gap_report

AOI_BOUNDS=(-153.12,64.63,-153.07,64.65)  # explicitly user-chosen *experimental* ROI, NOT Mendenhall Valley
EXPECTED_PAIR='NISAR_GCOV_073_055_20261017_20261029_REAL'
ALLOWED_WARNING_CODES={'NOT_CLIPPED','POPULATION_UNITS','EMPTY_VECTOR','PARTIAL_COVERAGE','NO_AOI_OVERLAP'}

def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def save(p,data):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(data,indent=2,ensure_ascii=False,default=str)+'\n',encoding='utf-8')
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def execute(args,cwd=None):
    command=[str(x) for x in args]
    print('RUN:', ' '.join(command),flush=True)
    return subprocess.run(command, cwd=cwd,check=True)

def existing_run_pair():
    # Prefer user's existing verified M1 import, preserving original input image bytes.
    candidates=[]
    for p in (ROOT/'data/real-nisar-oct2026-pair', Path.home()/'Downloads/SPECTRA-PHASE1-REAL-DATA-INTEGRATED/data/real-nisar-oct2026-pair'):
        if (p/'manifest.json').is_file():candidates.append(p)
    for candidate in candidates:
        manifest=load(candidate/'manifest.json')
        if manifest.get('pair_id') != EXPECTED_PAIR: continue
        paths=[]
        for side in ('before','after'):
            rec=manifest[side]
            paths += [candidate/p for p in rec['raster_files'].values()]
            paths += [candidate/rec['valid_mask_file']]
        if all(p.is_file() and p.stat().st_size>0 for p in paths):return candidate
    return None

def create_real_pair():
    p=existing_run_pair()
    if p:return p
    sources=Path(os.environ.get('SPECTRA_REAL_DATA_DIR',str(Path.home()/'Desktop/SPECTRA-SAR/data')))
    if not all((sources/n).is_file() for n in ('before.tif','after.tif')):
        raise RuntimeError(f'Missing actual before.tif and after.tif in {sources}; cannot build real-data pair')
    p=ROOT/'data/real-nisar-oct2026-pair'
    execute([sys.executable,'-m','phase1.import_real_nisar','--data',sources,'--output',p],cwd=ROOT)
    return p

def validate_original_handoff():
    folder=ROOT/'data/M3_UPLOADED_HANDOFF'
    paths=['run.json','M1/input-manifest.json','M2/m3-delivery.json','M3/candidate-change.geojson','M3/candidate-union.geojson','M3/candidate-summary.json']
    for name in paths:
        if not (folder/name).is_file():raise RuntimeError(f'Missing uploaded evidence file: {folder/name}')
    manifest=load(folder/'M1/input-manifest.json'); delivery=load(folder/'M2/m3-delivery.json'); run=load(folder/'run.json')
    if manifest['pair_id']!=EXPECTED_PAIR or delivery['pair_id']!=EXPECTED_PAIR:
        raise RuntimeError('Source data do not match selected 17/29 October NISAR pair')
    if run['stages']['M3']['status']!='BLOCKED':
        raise RuntimeError('Unexpected uploaded handoff M3 state')
    return {'pair_id':EXPECTED_PAIR,'uploaded_run_id':run['run_id'],'qa_approved':False,'uploaded_candidate_count':load(folder/'M3/candidate-summary.json')['output_polygons']}

def create_aoi(output):
    w,s,e,n=AOI_BOUNDS
    f={'type':'FeatureCollection','features':[{'type':'Feature','geometry':{
        'type':'Polygon','coordinates':[[[w,s],[e,s],[e,n],[w,n],[w,s]]]},'properties':{
        'label':'EXPERIMENTAL ROI; NOT Mendenhall Valley',
        'science_scope':'radar change candidates only',
        'source':'User-selected AOI coordinates in project chat'}}]}
    save(output,f)

def verify_sources(dir):
    manifest=load(dir/'source_manifest.json')
    for source in ('osm','worldpop'):
        record=manifest['sources'].get(source,{})
        if record.get('status')!='downloaded':raise RuntimeError(f'{source} acquisition failed: {record.get("error")}')
        meta=record.get('metadata',{})
        if not meta.get('sha256'):raise RuntimeError(f'Missing {source} source fingerprint')
        files=record['files']
        match=next((Path(p) for p in files if (p.endswith('osm_overpass_raw.json') if source=='osm' else p.endswith('.tif'))),None)
        if not match or not match.is_file():raise RuntimeError(f'Missing {source} source data')
        h=hashlib.sha256(match.read_bytes()).hexdigest()
        if h!=meta['sha256']:raise RuntimeError(f'{source} source checksum mismatched')
    return manifest

def check_qa(qa):
    if qa.get('overall_status')=='REJECT':raise RuntimeError('M3 T03 rejected real input: examine T03-QA.json')
    codes={i['code'] for r in qa['reports'].values() for i in r.get('issues',[])}
    unknown=codes-ALLOWED_WARNING_CODES
    if unknown:raise RuntimeError(f'Unexpected real-data QA warnings require analyst review: {sorted(unknown)}')
    # The approval flag only permits software processing under known exploratory
    # warnings. This is not scientific acceptance or source completeness validation.
    return sorted(codes)

def create_handoff_zip(run_dir, source_dir, qa_path, report_path):
    import zipfile
    output=ROOT/'SPECTRA-M3-LIVE-EXPLORATORY-HANDOFF.zip'
    include=[]
    for rel in ['run.json','M1/input-manifest.json','M2/m3-delivery.json','M3/candidate-change.geojson',
                'M3/candidate-union.geojson','M3/candidate-summary.json','M3/population-data-gap.json','M3/impact/qa_report.json',
                'M3/impact/spatial_metrics.json','M3/impact/exposure_metrics.json','M3/impact/risk_assessment.json',
                'M3/impact/impact_statistics.json','M3/impact/decision_recommendations.json',
                'M3/impact/run_manifest.json','M4/evidence.json','M5/run-contract.json','M6/verification.json']:
        p=run_dir/rel
        if p.is_file():include.append((p,'run/'+rel))
    for rel in ['source_manifest.json','osm_features.geojson','osm_overpass_raw.json']:
        p=source_dir/rel
        if p.is_file(): include.append((p,'sources/'+rel))
    for p,rel in [(qa_path,'qa-preview.json'),(report_path,'M3-LIVE-EXECUTION-REPORT.json')]:
        if p.is_file():include.append((p,rel))
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as z:
        for p,rel in include:z.write(p,rel)
    return output

def main():
    output=ROOT/'M3-LIVE-EXECUTION-REPORT.json'
    report={'created_at':now(),'status':'STARTING','scientifically_approved':False,'original_handoff':None,
            'real_sources_downloaded':False,'run_dir':None,'qa_warnings':[],
            'limitations':['Radar backscatter differences are not confirmed flooding or damage.',
                           'Experimental AOI is not Mendenhall Valley.',
                           'PROVISIONAL P05023 and VALIDATED P05036 are mixed; correction/registration not certified.',
                           'OSM map completeness is unknown; WorldPop is modeled resident population.']}
    try:
        report['original_handoff']=validate_original_handoff()
        pair=create_real_pair();report['pair_directory']=str(pair)
        aoi=ROOT/'data/real-m3-impact/aoi_experimental.geojson';create_aoi(aoi)
        sources=ROOT/'data/real-m3-impact/sources';sources.mkdir(parents=True,exist_ok=True)
        manifest_file=sources/'source_manifest.json'
        if manifest_file.is_file():
            try:
                verify_sources(sources)
                print('Using previously downloaded, SHA256-verified OSM + WorldPop inputs.',flush=True)
            except Exception:
                print('Existing sources incomplete; reacquiring from official services.',flush=True)
                execute([sys.executable, ROOT/'members/M3/T02/data_fetcher.py','--aoi',aoi,'--out',sources,
                         '--year','2026','--resolution','100m','--source','all'],cwd=ROOT)
        else:
            execute([sys.executable, ROOT/'members/M3/T02/data_fetcher.py','--aoi',aoi,'--out',sources,
                     '--year','2026','--resolution','100m','--source','all'],cwd=ROOT)
        downloaded=verify_sources(sources);report['real_sources_downloaded']=True
        pop=sources/'worldpop_population_2026_100m.tif';osm=sources/'osm_features.geojson'
        qa_path=ROOT/'data/real-m3-impact/T03-QA.json'
        validate_call=[sys.executable,ROOT/'members/M3/T09/modules/T03/geo_validator.py',
                 '--aoi',aoi,'--osm',osm,'--population',pop,'--manifest',manifest_file,'--report',qa_path]
        validation=subprocess.run([str(x) for x in validate_call],cwd=ROOT,check=False)
        if not qa_path.is_file(): raise RuntimeError('T03 QA report missing')
        qa=load(qa_path);report['qa_status']=qa['overall_status']
        population_gap=is_only_population_nodata(qa)
        if not population_gap:
            report['qa_warnings']=check_qa(qa)  # rejects all other ERROR codes
            if validation.returncode!=0: raise RuntimeError('T03 failed unexpectedly despite non-REJECT QA')
        else:
            aggregate=request_worldpop_aggregate(aoi,year=2026)
            aggregate_path=ROOT/'data/real-m3-impact/worldpop-aggregate-response.json'
            save(aggregate_path,aggregate)
            gap_path=ROOT/'data/real-m3-impact/M3-POPULATION-DATA-GAP.json'
            gap_info=create_population_gap_report(aoi,pop,qa_path,gap_path,aggregate,manifest_file)
            report['population_gap']=gap_info
            report['limitations'].append('Population raster is ALL_NODATA: never substitute modeled AOI aggregate as per-pixel exposure or as a validated zero-population raster.')
            report['limitations'].append('M3 spatial exposure and infrastructure impact remain scientifically unavailable; radar candidates and downstream integrity processing still run.')
            print('M3/T03: isolated ALL_NODATA population raster. Proceeding with documented partial workflow; not claiming T03 PASS.',flush=True)
        # Warnings are included in report; auto-allow only known T03 exploratory warnings.
        if 'EMPTY_VECTOR' in report['qa_warnings'] or 'NO_AOI_OVERLAP' in report['qa_warnings']:
            report['limitations'].append('OSM returned no mapped assets (or none overlapping AOI); zero counts do not imply absence of buildings.')
        if 'PARTIAL_COVERAGE' in report['qa_warnings']:
            report['limitations'].append('Population raster does not cover full AOI; exposure may be a lower bound.')
        cfg={'pair_dir':str(pair),'exploratory':True,'threshold_db':3.0,'min_pixels':9,
             'data_kind':'USER_SUPPLIED_REAL_NISAR_UNVERIFIED',
             'impact':{'aoi':str(aoi),'osm':str(osm),'population':str(pop),
                       'source_manifest':str(manifest_file),'population_unit':'count_per_pixel',
                       'population_provenance':'WorldPop Global2 R2025A v1, modeled 2026 resident population, '+
                           '100m count-per-cell, https://api.worldpop.org/v3/raster , CC BY 4.0',
                       'approve_qa_warning':True}}
        if population_gap:
            # Do not pass unusable raster to T04–T08; retain genuine radar candidates.
            cfg.pop('impact')
            cfg['impact_gap']={'report':str(gap_path),'status':'PARTIAL_DATA_GAP'}
        config_path=ROOT/'data/real-m3-impact/config.executed.json';save(config_path,cfg)
        result=fresh_run(cfg)
        run_dir=ROOT/'runs'/result['run_id']
        report['run_dir']=str(run_dir)
        report['stage_results']={k:v['status'] for k,v in result['stages'].items()}
        report['status']=('COMPLETED_EXPLORATORY_WITH_QA_WARNINGS' if result['stages']['M3']['status']=='PASS' else 'COMPLETED_WITH_POPULATION_DATA_GAP' if result['stages']['M3']['status']=='PARTIAL_DATA_GAP' else 'PARTIAL_OR_BLOCKED')
        report['scientifically_approved']=False
        report['m3_stage_detail']=result['stages']['M3']['detail']
        save(output,report)
        archive=create_handoff_zip(run_dir,sources,qa_path,output)
        print('\nFINAL STATUS:',report['status'],flush=True)
        print('M1-M6:',report['stage_results'],flush=True)
        print('QA WARNINGS:',report['qa_warnings'],flush=True)
        print('REPORT:',output,flush=True)
        print('ZIP TO SHARE:',archive,flush=True)
        return 0 if result['stages']['M3']['status'] in ('PASS','PARTIAL_DATA_GAP') else 2
    except Exception as e:
        report['status']='BLOCKED';report['error']=str(e);save(output,report)
        print('\nBLOCKED:',e,flush=True)
        print('REPORT:',output,flush=True)
        traceback.print_exc()
        return 2

if __name__=='__main__':raise SystemExit(main())
