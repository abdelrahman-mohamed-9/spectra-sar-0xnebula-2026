#!/usr/bin/env python3
"""SPECTRA-SAR M1 T03: NISAR GCOV/GOFF scientific gatekeeper.

Metadata catalog checks can pass independently of raster checks. A catalog PASS
is never presented as proof of real flooding or validated ice motion.

Stdlib works for catalog-only validation. Rasterio (COG) and h5py (HDF5)
are OPTIONAL, used only when actual products are provided by the operator.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

REQUIRED_GCOV_FIELDS = ('granule_id', 'cmr_concept_id', 'product', 'maturity',
                        'acquisition_start_utc', 'name_metadata')
MATCH_FIELDS = ('track', 'direction', 'frame', 'mode', 'polarization_code')
DIAGONALS = ('HHHH', 'HVHV', 'VVVV', 'VHVH', 'RHRH', 'RVRV')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def check(name: str, result: bool | None, message: str, category: str = 'catalog') -> dict:
    return {'name': name, 'outcome': ('PASS' if result is True else 'FAIL' if result is False else 'PENDING'),
            'description': message, 'category': category}


def iso_dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace('Z', '+00:00'))


def crid(granule_id: str) -> str | None:
    # NISAR filename suffix: <CRID>_<accuracy>_<coverage>_<location>_<counter>.
    m = re.search(r'_([A-Z]\d{5})_[PMNF]_[FP]_[A-Z]_\d{3}(?:\.|$)', granule_id)
    return m.group(1) if m else None


def validate_catalog(selection: dict) -> dict:
    results: list[dict] = []
    pair = selection.get('flood_gcOV_primary', {})
    before, after = pair.get('before', {}), pair.get('during_event', pair.get('after', {}))
    for name, scene in [('GCOV.before', before), ('GCOV.during_event', after)]:
        missing = [k for k in REQUIRED_GCOV_FIELDS if not scene.get(k)]
        results.append(check(f'{name}.required_metadata', not missing,
                             f'Missing: {missing}' if missing else 'Required CMR fields present'))
        results.append(check(f'{name}.type', scene.get('product') == 'GCOV',
                             f"Product: {scene.get('product')}"))
        results.append(check(f'{name}.maturity', scene.get('maturity') == 'PROVISIONAL',
                             f"Maturity: {scene.get('maturity')}"))
        results.append(check(f'{name}.source_identifier', bool(re.match(r'^G\d+-ASF$',scene.get('cmr_concept_id',''))),
                             'CMR granule concept identifier'))
        results.append(check(f'{name}.download_location', str(scene.get('download_url','')).startswith('https://nisar.asf.earthdatacloud.nasa.gov/'),
                             'Official ASF HTTPS download link recorded; accessibility not tested'))
    bm, am = before.get('name_metadata') or {}, after.get('name_metadata') or {}
    for field in MATCH_FIELDS:
        ok = bool(bm.get(field) and am.get(field) and bm[field] == am[field])
        results.append(check(f'GCOV.match_{field}', ok,
                             f"before={bm.get(field)!r}, during={am.get(field)!r}"))
    same_collection = before.get('collection_concept_id') == after.get('collection_concept_id') and bool(before.get('collection_concept_id'))
    results.append(check('GCOV.same_collection', same_collection,
                         f"{before.get('collection_concept_id')} / {after.get('collection_concept_id')}"))
    bcrid, acrid = crid(before.get('granule_id','')), crid(after.get('granule_id',''))
    results.append(check('GCOV.same_CRID', bool(bcrid and acrid and bcrid == acrid),
                         f'{bcrid} / {acrid}; filename-derived, HDF5 processing metadata pending'))
    try:
        bdt = iso_dt(before['acquisition_start_utc'])
        adt = iso_dt(after['acquisition_start_utc'])
        baseline = round((adt - bdt).total_seconds()/86400, 4)
        results.append(check('GCOV.time_order', baseline > 0, f'Time difference {baseline} days'))
    except (ValueError, KeyError, TypeError) as exc:
        bdt = adt = None
        baseline = None
        results.append(check('GCOV.time_order', False, f'Invalid timestamp: {exc}'))
    for name,scene in [('GOFF.primary', selection.get('glacier_GOFF_primary', {})),
                       ('GOFF.backup', selection.get('glacier_GOFF_backup', {}))]:
        results.append(check(f'{name}.catalog_type', scene.get('product') == 'GOFF' and scene.get('maturity') == 'PROVISIONAL',
                             f"product={scene.get('product')}; maturity={scene.get('maturity')}"))
        results.append(check(f'{name}.catalog_id', bool(re.match(r'^G\d+-ASF$', scene.get('cmr_concept_id',''))),
                             'CMR GOFF granule identifier'))
        results.append(check(f'{name}.catalog_coverage', scene.get('approximate_CMR_footprint_intersection_of_AOI_bbox_pct',0) > 0,
                             f"Approximate AOI intersection {scene.get('approximate_CMR_footprint_intersection_of_AOI_bbox_pct',0)}%, NOT raster valid-pixel coverage"))
        # GOFF has 2 acquisition epochs in one product ID; do not assume two separate GCOV rasters.
        times = re.findall(r'20\d{6}T\d{6}', scene.get('granule_id',''))
        result = len(times) == 4 and times[2] > times[0]
        results.append(check(f'{name}.paired_epochs', result,
                             f"First epoch {times[0] if times else '?'}; second epoch {times[2] if len(times)>2 else '?'}"))
        if name.endswith('primary') and bdt is not None and adt is not None and len(times)==4:
            eq = (times[0] == bdt.strftime('%Y%m%dT%H%M%S') and times[2] == adt.strftime('%Y%m%dT%H%M%S'))
            results.append(check('GOFF.primary_same_epochs_as_GCOV', eq,
                                 f'GOFF {times[0]} -> {times[2]}, GCOV {bdt:%Y%m%dT%H%M%S} -> {adt:%Y%m%dT%H%M%S}'))
    # These are intentionally PENDING: no CMR entry is evidence of actual valid pixels.
    results.append(check('GCOV.pixel_coverage_and_alignment', None,
                         'Actual GCOV rasters not supplied; georeferencing/valid pixels unverified', 'raster'))
    results.append(check('GOFF.offset_quality', None,
                         'Actual GOFF displacement and SNR/outlier layers not supplied', 'raster'))
    results.append(check('Flood_event_interpretation', None,
                         'Flood-extent claim requires examination of actual data and independent flood evidence', 'science'))
    failures = [r for r in results if r['category']=='catalog' and r['outcome']=='FAIL']
    return {'catalog_status': 'FAIL' if failures else 'PASS', 'checks': results,
            'time_baseline_days': baseline, 'science_approved': False,
            'assessment': 'CATALOG_REJECTED' if failures else 'CATALOG_PASS_RASTER_AND_SCIENCE_PENDING'}


def inspect_geotiff(path: Path) -> dict:
    try:
        import numpy as np
        import rasterio
    except ImportError as e:
        return {'status':'DEPENDENCY_MISSING','message':str(e),'file':str(path)}
    if not path.is_file():
        return {'status':'FILE_MISSING','file':str(path)}
    try:
        with rasterio.open(path) as ds:
            if ds.count < 1 or not ds.crs or not ds.transform or ds.width < 1 or ds.height < 1:
                return {'status':'REJECT','file':str(path), 'reason':'Missing band, CRS or affine transform'}
            # Read a bounded/downsampled preview for large datasets; never load a full huge raster blindly.
            height, width = min(256, ds.height), min(256, ds.width)
            from rasterio.enums import Resampling
            a = ds.read(1, masked=True, out_shape=(height,width), resampling=Resampling.nearest)
            valid = (~np.ma.getmaskarray(a)) & np.isfinite(a.data)
            frac = float(valid.sum()/valid.size)
            bounds = [float(ds.bounds.left), float(ds.bounds.bottom), float(ds.bounds.right), float(ds.bounds.top)]
            return {'status': 'PASS' if frac > 0.05 else 'REVIEW', 'file':str(path),
                    'size_bytes':path.stat().st_size, 'sha256':sha256(path),
                    'crs':ds.crs.to_string(), 'width':ds.width, 'height':ds.height,
                    'bands':ds.count,'transform':list(ds.transform)[:6], 'bounds':bounds,
                    'nodata':ds.nodata,'sample_valid_fraction':round(frac,5),
                    'sample_finite_min':float(a.data[valid].min()) if valid.any() else None,
                    'sample_finite_max':float(a.data[valid].max()) if valid.any() else None,
                    'note':'Sample statistics, not whole-raster completeness or scientific interpretation'}
    except Exception as exc:
        return {'status':'ERROR','file':str(path),'reason':f'{type(exc).__name__}: {exc}'}


def inspect_hdf5(path: Path, product: str) -> dict:
    try:
        import h5py
        import numpy as np
    except ImportError as e:
        return {'status':'DEPENDENCY_MISSING', 'file':str(path), 'message':str(e)}
    if not path.is_file():
        return {'status':'FILE_MISSING','file':str(path)}
    root = f'/science/LSAR/{product}/grids'
    try:
        with h5py.File(path,'r') as h:
            if root not in h:
                return {'status':'REJECT','file':str(path), 'reason':f'Missing expected product grid group {root}'}
            paths=[]
            def get_dataset(n, obj):
                if isinstance(obj,h5py.Dataset):
                    if len(obj.shape)==2 and np.issubdtype(obj.dtype, np.number):
                        paths.append((f'{root}/{n}',obj.shape,str(obj.dtype)))
            h[root].visititems(get_dataset)
            primary = [v for v in paths if v[0].split('/')[-1] in DIAGONALS] if product=='GCOV' else [v for v in paths if 'offset' in v[0].lower()]
            info={'status':'REVIEW','file':str(path),'size_bytes':path.stat().st_size,'sha256':sha256(path),
                  'product':product,'grid_root':root,'two_dimensional_numeric_layers':
                  [{'path':p,'shape':list(sh),'dtype':dtype} for p,sh,dtype in paths[:100]],
                  'candidate_signal_layers':[p for p,_,_ in primary],
                  'note':'HDF5 structure inspection only; actual AOI valid coverage/geolocation and physical quality still require checking'}
            if not primary:
                info['status']='REJECT';info['reason']='No expected product layers found in HDF5 grids'
            return info
    except Exception as exc:
        return {'status':'ERROR','file':str(path),'reason':f'{type(exc).__name__}: {exc}'}


def inspect_file(path_str: str | None, product: str) -> dict | None:
    if not path_str:
        return None
    path = Path(path_str).expanduser().resolve()
    if path.suffix.lower() in {'.tif','.tiff'}:
        report=inspect_geotiff(path)
        report['input_format']='GEOTIFF'
        report['note_extra']='GeoTIFF layer name/polarization must be verified from provenance or Harmony export name'
        return report
    if path.suffix.lower() in {'.h5','.hdf5'}:
        report=inspect_hdf5(path,product)
        report['input_format']='HDF5'
        return report
    return {'status':'UNSUPPORTED_FORMAT','file':str(path),'expected':'.h5 or .tif'}


def inspect_pair(b: dict | None, a: dict | None) -> dict:
    if not b and not a:
        return {'status':'PENDING', 'reason':'Real GCOV files not supplied'}
    if not b or not a:
        return {'status':'PENDING','reason':'Both GCOV files required for pair compatibility check'}
    if b.get('status') not in ('PASS','REVIEW') or a.get('status') not in ('PASS','REVIEW'):
        return {'status':'REJECT','reason':'At least one source raster failed to open or lacked grid information'}
    if b.get('input_format')=='GEOTIFF' and a.get('input_format')=='GEOTIFF':
        same_crs=b.get('crs')==a.get('crs')
        same_pixel_grid=b.get('transform')==a.get('transform') and (b['width'],b['height'])==(a['width'],a['height'])
        enough_pixels=b.get('sample_valid_fraction',0)>0.05 and a.get('sample_valid_fraction',0)>0.05
        return {'status':'PASS' if (same_crs and same_pixel_grid and enough_pixels) else 'REJECT',
                'same_crs':same_crs,'same_pixel_grid':same_pixel_grid,'valid_pixel_test':enough_pixels,
                'note':'PASS means basic raster geometry + sampling only; not verified physical flood mapping or correct covariance layer'}
    return {'status':'PENDING', 'reason':'HDF5 pair requires extracting common matching layer and testing reprojected AOI pixel grid'}


def main(argv=None) -> int:
    p=argparse.ArgumentParser(description='NISAR M1 T03 — scientific gatekeeper')
    p.add_argument('--selection', default='inputs/selected-scenes.json',help='T02 selected-scenes.json')
    p.add_argument('--before',help='Local GCOV before COG .tif or original .h5')
    p.add_argument('--after',help='Local GCOV during-event COG .tif or original .h5')
    p.add_argument('--goff',help='Local GOFF .h5 or extracted .tif')
    p.add_argument('--output',default='validation-report.json')
    args=p.parse_args(argv)
    inp=Path(args.selection).expanduser().resolve()
    if not inp.is_file():
        p.error(f'Missing selected-scenes file: {inp}')
    selection=json.loads(inp.read_text(encoding='utf-8'))
    catalog=validate_catalog(selection)
    before=inspect_file(args.before,'GCOV')
    after=inspect_file(args.after,'GCOV')
    goff=inspect_file(args.goff,'GOFF')
    raster={'before':before,'during_event':after,'goff':goff,'gcov_pair':inspect_pair(before,after)}
    report={'task':'M1-T03','generated_utc':datetime.now(timezone.utc).isoformat(),
            'source_selection':str(inp),'source_selection_sha256':sha256(inp),
            'study_area':selection.get('case_study',{}),
            'catalog':catalog,'files':raster,
            'scientific_acceptance':{'status':'NOT_APPROVED',
               'reasons':['Catalog match cannot verify geocoded raster pixels or signal changes',
                          'Flood mapping requires actual event-appropriate observation and independent comparison',
                          'GOFF offset magnitude and SNR/outliers need scientific QA before motion velocity estimates']},
            'handoff':{'M2':'Catalog baseline and recommended matching GCOV layer; request extracted GeoTIFF files',
                       'M3':'AOI location known; area statistics cannot be asserted before real change masks',
                       'M4':'Scene CMR identifiers/URLs and selection file SHA256 can be recorded',
                       'M5':'Gatekeeper report available, but do not mark science_ready=true',
                       'M6':'Real scene metadata available; do not display flood/glacier results as verified yet'}}
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('CATALOG:',catalog['assessment'])
    for item in catalog['checks']:
        if item['category']=='catalog' and item['outcome']=='FAIL':
            print('FAIL:',item['name'],'—',item['description'])
    print('GCOV raster pair:',raster['gcov_pair']['status'])
    print('GOFF file:',goff['status'] if goff else 'NOT_SUPPLIED')
    print('SCIENCE READY: NO — validation requires real SAR raster QA')
    print('REPORT:',Path(args.output).resolve())
    return 2 if catalog['catalog_status']=='FAIL' else 0

if __name__ == '__main__':
    sys.exit(main())
