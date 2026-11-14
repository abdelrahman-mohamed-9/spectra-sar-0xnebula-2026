#!/usr/bin/env python3
"""Submit two exact real NISAR GCOV granules to NASA Harmony for cropped HHHH COGs.

- Uses recorded CMR source IDs, not a fabricated dataset.
- Doesn't store secrets. Prompts for EDL creds only in local terminal as needed.
- Never reports scientific flooding based on download alone.
"""
from __future__ import annotations
import argparse
import datetime as dt
import getpass
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'inputs'/'selected-scenes.json'
OUTPUT=ROOT/'data'
REPORTS=ROOT/'reports'
VARIABLE='/science/LSAR/GCOV/grids/frequencyA/HHHH'
BBOX=(-134.70, 58.33, -134.40, 58.55)


def load_selection():
    content=json.loads(SOURCE.read_text())
    gcov=content['flood_gcOV_primary']
    return {
       'before':{'source':gcov['before'],'date':'20260920'},
       'after':{'source':gcov['during_event'],'date':'20261002'}
    }


def validate_configuration(selected):
    first=selected['before']['source']
    last=selected['after']['source']
    check_keys=['track','direction','frame','mode','polarization_code']
    assert all(first['name_metadata'][k]==last['name_metadata'][k] for k in check_keys), 'CMR metadata mismatch'
    assert first['collection_concept_id']==last['collection_concept_id'], 'Different CMR collections'
    for role, row in selected.items():
       assert row['source']['product']=='GCOV', role+' not GCOV'
       assert row['date'] in row['source']['granule_id'], 'Unexpected acquisition date'
       assert row['source']['cmr_concept_id'].startswith('G')
    return first['collection_concept_id']


def credentials_client():
    try:
        from harmony import Client
    except ImportError as exc:
        raise RuntimeError('Missing harmony-py. Run: python3 -m pip install harmony-py') from exc
    token=os.environ.get('EDL_TOKEN','').strip()
    if token:
        print('Using EDL_TOKEN from local environment (value not displayed).')
        return Client(token=token)
    from netrc import netrc
    netrc_credentials=None
    try:
        netrc_credentials=netrc().authenticators('urs.earthdata.nasa.gov')
    except (FileNotFoundError, OSError, Exception) as exc:
        # Ignore absent or invalid local .netrc and allow interactive login.
        pass
    if netrc_credentials:
        print('Using local ~/.netrc Earthdata credentials (not displayed).')
        return Client()
    print('NASA Earthdata login required. Enter credentials ONLY in your local Mac Terminal.')
    username=input('Earthdata username: ').strip()
    password=getpass.getpass('Earthdata password (hidden; not saved): ')
    if not username or not password:
        raise RuntimeError('No credentials. Or use browser fallback described in README.md.')
    # Password lives only in local process memory and isn't written to ZIP, logs, or reports.
    return Client(auth=(username,password))


def build_request(role, row, collection_id):
    from harmony import BBox, Collection, Request
    return Request(collection=Collection(id=collection_id),
                   granule_id=[row['source']['cmr_concept_id']],
                   spatial=BBox(*BBOX),
                   variables=[VARIABLE],
                   format='image/tiff',
                   max_results=1)


def save_json(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str)+'\n',encoding='utf-8')


def handle_role(client, role, row, collection_id, new_job=False):
    role_dir=OUTPUT/role
    role_dir.mkdir(parents=True,exist_ok=True)
    target=OUTPUT/f"{role}_HHHH_{row['date']}.tif"
    manifest=REPORTS/f'{role}-harmony-job.json'
    if target.is_file() and target.stat().st_size>1024:
        print(f'[{role}] Existing candidate {target.name}; will be independently re-verified against its job manifest.')
        return target
    req=build_request(role,row,collection_id)
    if hasattr(req,'is_valid') and not req.is_valid():
        raise ValueError(f'Invalid Harmony request for {role}')
    record={'source':'NASA Harmony','role':role,'collection_concept_id':collection_id,
            'cmr_granule_concept_id':row['source']['cmr_concept_id'],
            'granule_id':row['source']['granule_id'],
            'source_acquisition_utc':row['source']['acquisition_start_utc'],
            'variable_requested':VARIABLE,'bbox_lonlat':list(BBOX),
            'utc_recorded':dt.datetime.now(dt.timezone.utc).isoformat(),
            'status':'SUBMITTING'}
    previous=json.loads(manifest.read_text()) if manifest.is_file() else {}
    if previous.get('job_id') and not new_job:
        for key in ('cmr_granule_concept_id','granule_id','variable_requested','bbox_lonlat'):
            if previous.get(key)!=record.get(key):raise ValueError('Existing job source mismatch: '+key)
        record=previous
    else:
        if previous.get('job_id'):
            archive=REPORTS/(role+'-previous-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')+'.json')
            save_json(archive,previous)
        record['request_url']=client.request_as_url(req)
        record['job_id']=str(client.submit(req))
        record['status']='PROCESSING'
        save_json(manifest,record)
    try:
        print(f'[{role}] Harmony job: {record["job_id"]}')
        # The Harmony library polls job completion before returning download futures.
        futures=list(client.download_all(record['job_id'],directory=str(role_dir),overwrite=False))
        downloaded=[Path(f.result()) for f in futures]
        geotiffs=[p for p in downloaded if p.suffix.lower() in ('.tif','.tiff') and p.is_file()]
        record['downloaded_filenames']=[p.name for p in downloaded]
        if len(geotiffs)!=1:
            raise RuntimeError(f'Expected 1 GCOV GeoTIFF, got {len(geotiffs)}; inspect downloads and variable selection')
        file=geotiffs[0]
        if file.stat().st_size<1024:
            raise RuntimeError('Downloaded file is suspiciously small')
        if 'HHHH' not in file.name.upper():
            raise RuntimeError('Downloaded GeoTIFF filename does not identify HHHH; manual variable verification required')
        shutil.copyfile(file,target)
        h=hashlib.sha256()
        with open(target,'rb') as inp:
            for chunk in iter(lambda: inp.read(1024*1024),b''):
                h.update(chunk)
        record['sha256']=h.hexdigest()
        record['original_geotiff_filename']=file.name
        record['normalized_geotiff']=target.name
        record['size_bytes']=target.stat().st_size
        record['status']='DOWNLOADED_NOT_SCIENCE_VALIDATED'
        save_json(manifest,record)
        print(f'[{role}] Downloaded {target.name} ({target.stat().st_size:,} bytes).')
        return target
    except Exception as exc:
        record.update(status='FAILED',error=type(exc).__name__)
        save_json(manifest,record)
        raise


def main():
    p=argparse.ArgumentParser(description='NASA Harmony NISAR GCOV Mendenhall cropped raster downloader')
    p.add_argument('--new-job',action='store_true',help='Submit a new job if the recorded Harmony job expired; preserve old receipt')
    p.add_argument('--dry-run',action='store_true',help='Only print NASA CMR IDs, dates and intended request; no network or login')
    p.add_argument('--skip-qa',action='store_true',help='Do not run raster verification after downloading')
    p.add_argument('--verify-only',action='store_true',help='Verify existing data/before_...tif and data/after_...tif without NASA login or download')
    args=p.parse_args()
    rows=load_selection()
    collection_id=validate_configuration(rows)
    print('NASA source collection:',collection_id)
    print('Variable:',VARIABLE)
    print('AOI bbox:',BBOX)
    for name, row in rows.items():
        print(name+':',row['source']['cmr_concept_id'],row['source']['acquisition_start_utc'])
    if args.dry_run:
        print('DRY RUN: No download occurred. Scientific/data-access status is unchanged.')
        return 0
    OUTPUT.mkdir(exist_ok=True)
    REPORTS.mkdir(exist_ok=True)
    if args.verify_only:
        before=OUTPUT/'before_HHHH_20260920.tif'
        after=OUTPUT/'after_HHHH_20261002.tif'
        return subprocess.call([sys.executable,str(ROOT/'verify_real_rasters.py'),'--before',str(before),'--after',str(after)],cwd=str(ROOT))
    try:
        client=credentials_client()
    except Exception as exc:
        print(f'LOGIN_OR_SETUP_ERROR: {type(exc).__name__}: {exc}')
        print('Fallback: Open NASA Earthdata Search, add the 2 exact granules, use Customize Download.')
        return 2
    downloaded={}
    for name, row in rows.items():
        try:
            downloaded[name]=handle_role(client,name,row,collection_id,new_job=args.new_job)
        except Exception as exc:
            print(f'{name.upper()}_DOWNLOAD_ERROR: {type(exc).__name__}: {exc}')
            print(f'Diagnostic details (without passwords) in reports/{name}-harmony-job.json')
    if len(downloaded)!=2:
        print('T05_DOWNLOAD_INCOMPLETE: Real pair NOT ready. Use browser fallback from README.md.')
        return 3
    if args.skip_qa:
        print('Both files downloaded. Run verify_real_rasters.py before M2.')
        return 0
    try:
        code=subprocess.call([sys.executable,str(ROOT/'verify_real_rasters.py'),
                '--before',str(downloaded['before']), '--after',str(downloaded['after'])],cwd=str(ROOT))
        if code!=0:
            print('Raster QA not green. Inspect output/t05-real-data-qa.json; files still available.')
        return code
    except Exception as exc:
        print('QA_EXECUTION_ERROR:',str(exc))
        print('Run python3 -m pip install rasterio numpy pillow, then run verify_real_rasters.py.')
        return 4

if __name__=='__main__':
    raise SystemExit(main())
