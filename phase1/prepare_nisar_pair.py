"""Package REAL NASA NISAR GCOV diagonal HHHH pair for M2, with no synthetic observations.
Fail closed on geospatial incompatibility; M1 must regrid if differing grids.
Validity masks are *derived from the actual TIFFs*, not fabricated evidence.
"""
from __future__ import annotations
from pathlib import Path
import hashlib,json,shutil
from datetime import datetime,timezone
from contextlib import ExitStack
import rasterio
import numpy as np

HERE=Path(__file__).resolve().parents[1]
M1=HERE/'members/M1'
BEFORE=M1/'data/before_HHHH_20260920.tif'
AFTER=M1/'data/after_HHHH_20261002.tif'

def hash_file(path):
 d=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(2**20),b''):d.update(chunk)
 return d.hexdigest()

def copy_or_link(src,dst):
 if dst.exists():raise FileExistsError(dst)
 try:dst.hardlink_to(src)
 except OSError:shutil.copy2(src,dst)

def prepare(out:Path,before:Path=BEFORE,after:Path=AFTER):
 out,before,after=map(lambda x:Path(x).resolve(),(out,before,after))
 if out.exists():raise ValueError('Pair output exists; choose a new directory')
 if not before.is_file() or not after.is_file():raise FileNotFoundError('A REAL before + after NISAR TIFF pair is required (After is not yet included in uploaded files)')
 if hash_file(before)==hash_file(after):raise ValueError('Before and After are identical bytes; cannot use a copied Before as After')
 bmeta=json.loads((M1/'reports/before-harmony-job.json').read_text())
 ameta=json.loads((M1/'reports/after-harmony-job.json').read_text())
 if ameta.get('sha256') and hash_file(after)!=ameta['sha256']:raise ValueError('After SHA256 mismatch with supplied download receipt')
 if hash_file(before)!=bmeta['sha256']:raise ValueError('Known real Before source SHA256 mismatch; do not continue')
 with ExitStack() as stack:
  b=stack.enter_context(rasterio.open(before));a=stack.enter_context(rasterio.open(after))
  for ds in (b,a):
   if ds.driver!='GTiff' or ds.count!=1 or ds.dtypes[0]!='float32' or ds.crs is None or not ds.crs.is_projected:
    raise ValueError('Both files must be single band float32 projected GeoTIFF power')
   if ds.tags().get('mission_name','').upper()!='NISAR':
    raise ValueError('Missing NISAR mission tag; refusing generic unverified raster')
  if (b.crs,b.transform,b.width,b.height)!=(a.crs,a.transform,a.width,a.height):
   raise ValueError('M1 must co-register both NISAR files on IDENTICAL projected pixel grid; no silent resampling')
  if b.transform.b!=0 or b.transform.d!=0 or b.transform.a<=0 or b.transform.e>=0:
   raise ValueError('Unsupported rotated / south-up raster')
  if abs(b.transform.a-abs(b.transform.e))>0.00001:raise ValueError('Rectangular pixel not yet supported')
  if b.crs.linear_units.lower() not in ('metre','meter','metres','meters'):raise ValueError('Pixel units must be metric')
  if b.width*b.height>120_000_000:raise ValueError('Raster unexpectedly large for local integration')
  out.mkdir(parents=True)
  shutil.copy2(before,out/'before_HHHH.tif');shutil.copy2(after,out/'after_HHHH.tif')
  masks={}
  for role,src in [('before',b),('after',a)]:
   profile=src.profile.copy();profile.update(driver='GTiff',dtype='uint8',count=1,nodata=None,compress='deflate',predictor=1)
   dest=out/f'{role}_valid_mask.tif'
   total=ok=0
   with rasterio.open(dest,'w',**profile) as dst:
    for _,window in src.block_windows(1):
     block=src.read(1,window=window)
     mask=((src.read_masks(1,window=window)>0)&np.isfinite(block)&(block>0)).astype('uint8')
     dst.write(mask,1,window=window);total+=mask.size;ok+=int(mask.sum())
   masks[role]={'valid':ok,'total':total,'fraction':round(ok/max(1,total),5)}
  scenes=json.loads((M1/'inputs/selected-scenes.json').read_text())['flood_gcOV_primary']
  manifest={'schema_version':'1.0','sensor':'NISAR','pair_id':'NISAR_GCOV_MENDENHALL_20260920_20261002',
   'source_provider':'NASA Harmony / ASF NISAR GCOV, PROVISIONAL',
   'processing_software':'NASA Harmony GDAL subset + M2 bridge real-mask derivation',
   'processing_version':'M2 integration 1.0', 'product_type':'GCOV',
   'acquisition_mode':'4005','radiometry':'nisar_gcov_diagonal','units':'linear_power',
   'polarizations':['HHHH'], 'grid':{'crs':str(b.crs),'pixel_size_m':float(b.res[0]),'width':b.width,'height':b.height},
   'source_ids':{'before':bmeta['cmr_granule_concept_id'],'after':ameta['cmr_granule_concept_id']},
   'data_limitations':['NISAR L-band HHHH diagonal covariance; NOT Sentinel-1 VV.',
      'Uncalibrated relative changes; source product and incidence angle verification remain.',
      'Masks are derived from valid positive pixels, NOT independent terrain/shadow masks.',
      'Subpixel co-registration accuracy NOT established.'],
  }
  for role,meta in [('before',bmeta),('after',ameta)]:
   rec=scenes[role if role=='before' else 'during_event']
   manifest[role]={'scene_id':meta['granule_id'],'acquired_utc':meta['source_acquisition_utc'],
    'relative_orbit':int(rec['name_metadata']['track']),'orbit_direction':'ASCENDING' if rec['name_metadata']['direction']=='A' else 'DESCENDING',
    'incidence_angle_deg_summary':None,'raster_files':{'HHHH':f'{role}_HHHH.tif'},'valid_mask_file':f'{role}_valid_mask.tif','source_url':meta['request_url']}
  (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
  receipt={'created_utc':datetime.now(timezone.utc).isoformat(),'source_before_sha256':hash_file(before),
    'source_after_sha256':hash_file(after),'validity_masks':masks,'status':'SOURCE_IMAGERY_NOT_SCIENCE_APPROVED',
    'external_evidence_needed':['Harmony job identity/After download receipt','NISAR GCOV radiometry metadata','subpixel QA','independent event labels']}
  (out/'pair-build-evidence.json').write_text(json.dumps(receipt,indent=2)+'\n')
  return out

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--before',type=Path,default=BEFORE);p.add_argument('--after',type=Path,default=AFTER)
 a=p.parse_args();print(prepare(a.out,a.before,a.after))
