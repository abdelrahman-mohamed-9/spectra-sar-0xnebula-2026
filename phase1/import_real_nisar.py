"""Import a REAL user-extracted NISAR GCOV HHHH pair into the unified M1→M6 contract.

No fake imagery, resampling, guessed ground truth or certification. Source URLs are
metadata supplied by the ASF GDAL commands, not a provider-issued attestation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import hashlib

import numpy as np
import rasterio

from phase1.common import ROOT

SCENES = {
    'before': {
        'scene_id': 'NISAR_L2_PR_GCOV_033_073_D_055_4005_DHDH_A_20261017T062424_20261017T062502_P05023_N_F_J_001',
        'acquired_utc': '2026-10-17T06:24:24Z',
        'collection': 'NISAR_L2_GCOV_PROVISIONAL_V1',
        'processing_identifier': 'P05023',
        'maturity': 'PROVISIONAL',
    },
    'after': {
        'scene_id': 'NISAR_L2_PR_GCOV_034_073_D_055_4005_DHDH_A_20261029T062425_20261029T062502_P05036_N_F_J_001',
        'acquired_utc': '2026-10-29T06:24:25Z',
        'collection': 'NISAR_L2_GCOV_V1',
        'processing_identifier': 'P05036',
        'maturity': 'VALIDATED',
    },
}
LAYER='//science/LSAR/GCOV/grids/frequencyA/HHHH'

def source_url(rec):
    s=rec['scene_id']; c=rec['collection']
    return f'https://nisar.asf.earthdatacloud.nasa.gov/NISAR/{c}/{s}/{s}.h5'

def digest(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda: f.read(2**20),b''): h.update(block)
    return h.hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,default=Path.home()/'Desktop/SPECTRA-SAR/data',help='Folder holding genuine before.tif and after.tif')
    p.add_argument('--output',type=Path,default=ROOT/'data/real-nisar-oct2026-pair')
    args=p.parse_args()
    source=args.data.expanduser().resolve(); dest=args.output.expanduser().resolve()
    before,after=(source/(x+'.tif') for x in ('before','after'))
    for f in (before,after):
        if not f.is_file() or f.stat().st_size < 1024: raise SystemExit(f'MISSING REAL INPUT: {f}')
    if before.resolve()==after.resolve() or digest(before)==digest(after):
        raise SystemExit('REJECT: identical source images')
    if source==dest or source in dest.parents or dest in source.parents:
        raise SystemExit('REJECT: input and output trees overlap')
    with rasterio.open(before) as b, rasterio.open(after) as a:
        for side,ds in (('before',b),('after',a)):
            if ds.driver!='GTiff' or ds.count!=1 or ds.dtypes[0]!='float32':
                raise SystemExit(f'REJECT: {side} must be single-band Float32 GeoTIFF')
            if ds.crs is None or not ds.crs.is_projected or str(ds.crs.linear_units).lower() not in ('metre','meter','metres','meters'):
                raise SystemExit(f'REJECT: {side} CRS must be projected metric (not degrees)')
            if ds.transform.b!=0 or ds.transform.d!=0 or ds.transform.a<=0 or ds.transform.e>=0:
                raise SystemExit(f'REJECT: {side} must be north-up nonrotated grid')
        if (b.crs,b.transform,b.width,b.height)!=(a.crs,a.transform,a.width,a.height):
            raise SystemExit('REJECT: CRS/grid mismatch; do not silently resample')
        if b.width*b.height>120_000_000:raise SystemExit('REJECT: excessively large local raster')
        if abs(b.transform.a+ b.transform.e)>0.00001:raise SystemExit('REJECT: rectangular pixel grid unsupported')
        if b.width<16 or b.height<16:raise SystemExit('REJECT: tiny raster cannot be analysed')
        stats={}
        for side,ds in (('before',b),('after',a)):
            ok=total=invalid_neg=0
            for _,win in ds.block_windows(1):
                data=ds.read(1,window=win)
                mask=ds.read_masks(1,window=win)>0
                ok+=int(np.count_nonzero(mask & np.isfinite(data) & (data>0)))
                invalid_neg+=int(np.count_nonzero(mask & np.isfinite(data) & (data<0)))
                total+=data.size
            if invalid_neg:raise SystemExit(f'REJECT: {side} contains {invalid_neg} negative power samples; scientific review required')
            if ok==0:raise SystemExit(f'REJECT: {side} no valid positive power pixels')
            stats[side]={'positive_valid_pixels':ok,'pixels':total,'fraction':round(ok/total,6)}
        inputs={'before':digest(before),'after':digest(after)}
        if dest.exists():
            receipt=dest/'input-provenance.json'
            if not receipt.exists():raise SystemExit(f'REJECT: destination exists without receipt: {dest}')
            existing=json.loads(receipt.read_text())
            if existing.get('input_sha256') != inputs:raise SystemExit(f'REJECT: destination holds different data: {dest}')
            for side in ('before','after'):
                if not (dest/f'{side}_HHHH.tif').is_file() or digest(dest/f'{side}_HHHH.tif')!=inputs[side]:
                    raise SystemExit(f'REJECT: staged {side} differs from original data')
            print('VERIFIED existing data pair:',dest)
            return
        dest.mkdir(parents=True)
        try:
            for side,ds,path in (('before',b,before),('after',a,after)):
                shutil.copy2(path,dest/f'{side}_HHHH.tif')
                profile=ds.profile.copy()
                profile.update(driver='GTiff',count=1,dtype='uint8',nodata=None,compress='deflate',predictor=1)
                with rasterio.open(dest/f'{side}_valid_mask.tif','w',**profile) as dst:
                    for _,win in ds.block_windows(1):
                        data=ds.read(1,window=win)
                        mask=((ds.read_masks(1,window=win)>0)&np.isfinite(data)&(data>0)).astype('uint8')
                        dst.write(mask,1,window=win)
            manifest={
                'schema_version':'1.0','sensor':'NISAR','pair_id':'NISAR_GCOV_073_055_20261017_20261029_REAL',
                'source_provider':'NASA ASF NISAR GCOV remotely read with GDAL (user supplied extracts)',
                'processing_software':'GDAL HDF5 /vsicurl subset and SPECTRA M1 real-input importer',
                'processing_version':'P05023 before / P05036 after (MIXED: science review required)',
                'product_type':'GCOV','acquisition_mode':'4005','radiometry':'nisar_gcov_diagonal','units':'linear_power',
                'polarizations':['HHHH'],
                'grid':{'crs':str(b.crs),'pixel_size_m':float(b.res[0]),'width':b.width,'height':b.height},
                'source_ids':{'before':SCENES['before']['scene_id'],'after':SCENES['after']['scene_id']},
                'data_limitations':[
                    'Metadata for NASA granules supplied by user ASF GDAL snippets, not independently authenticated by this software',
                    'Before PROVISIONAL P05023; After VALIDATED P05036: cross-processing comparisons may be biased',
                    'AOI is experimental near -153.1,64.64, NOT the Mendenhall Valley event area',
                    'No incidence-angle comparison, terrain/shadow masks, or subpixel registration certificate',
                    'Candidate radar backscatter changes are NOT verified flooding, damage or AI-labelled impact',
                ],
            }
            for side in ('before','after'):
                rec=SCENES[side]
                manifest[side]={
                    'scene_id':rec['scene_id'],'acquired_utc':rec['acquired_utc'],
                    'relative_orbit':73,'orbit_direction':'DESCENDING','incidence_angle_deg_summary':None,
                    'raster_files':{'HHHH':f'{side}_HHHH.tif'},'valid_mask_file':f'{side}_valid_mask.tif',
                    'source_url':source_url(rec),'internal_layer':LAYER,'collection':rec['collection'],
                    'processing_identifier':rec['processing_identifier'],
                }
            (dest/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            receipt={'imported_utc':datetime.now(timezone.utc).isoformat(),
                     'input_sha256':inputs,'input_paths':{'before':str(before),'after':str(after)},
                     'input_statistics':stats,'scientific_approval':False,
                     'source_granules':SCENES,'internal_layer':LAYER,
                     'note':'Local hashes prove the imported bytes, not remote NASA signature or event attribution.'}
            (dest/'input-provenance.json').write_text(json.dumps(receipt,indent=2)+'\n')
        except BaseException:
            shutil.rmtree(dest,ignore_errors=True)
            raise
        print('REAL_PAIR_PREPARED:',dest)
        print('SHA256:',json.dumps(inputs))
        print('PIXELS:',json.dumps(stats))

if __name__=='__main__':main()
