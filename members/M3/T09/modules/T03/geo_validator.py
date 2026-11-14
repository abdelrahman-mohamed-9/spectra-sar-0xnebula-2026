"""SPECTRA-SAR M3/T03: strict scientific QA, report PASS/WARNING/REJECT.

WARNING is not permission to ignore validation problems. REJECT blocks T04.
Validation never fixes, clips, or silently changes real data.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import math
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import transform_bounds
from shapely.geometry import shape, box
from shapely.validation import explain_validity
from geo_loader import GeoDataError,load_geojson,load_geotiff


def _issue(code, severity, message): return {'code':code,'severity':severity,'message':message}

def _report(kind,path,issues,details):
    status=('REJECT' if any(i['severity']=='ERROR' for i in issues) else
            'WARNING' if issues else 'PASS')
    return {'dataset_type':kind,'file':str(path),'status':status,'issues':issues,'details':details}


def validate_vector(path, aoi=None, require_nonempty=True):
    issues=[]; details={'features':0, 'geometry_types':{},'bbox':None}
    try:
        dataset=load_geojson(path)
        if require_nonempty and not dataset.features:
            issues.append(_issue('EMPTY_VECTOR','WARNING','No OSM features found; not proof that assets are absent'))
        bounds=[]
        for idx,f in enumerate(dataset.features):
            if not isinstance(f,dict) or f.get('type')!='Feature':
                issues.append(_issue('INVALID_FEATURE','ERROR',f'Feature {idx} is not a GeoJSON Feature'));continue
            geom=f.get('geometry')
            if geom is None:
                issues.append(_issue('NULL_GEOMETRY','ERROR',f'Feature {idx} has null geometry'));continue
            try: g=shape(geom)
            except (ValueError,TypeError,KeyError) as e:
                issues.append(_issue('GEOMETRY_PARSE','ERROR',f'Feature {idx}: {e}'));continue
            details['geometry_types'][g.geom_type]=details['geometry_types'].get(g.geom_type,0)+1
            if g.is_empty:
                issues.append(_issue('EMPTY_GEOMETRY','ERROR',f'Feature {idx} geometry empty'));continue
            if not g.is_valid:
                issues.append(_issue('INVALID_TOPOLOGY','ERROR',f'Feature {idx}: {explain_validity(g)}'))
            b=g.bounds
            if not all(math.isfinite(x) for x in b) or b[0]<-180 or b[2]>180 or b[1]<-90 or b[3]>90:
                issues.append(_issue('COORDINATE_RANGE','ERROR',f'Feature {idx}: coordinates outside EPSG:4326'))
            else: bounds.append(b)
            if not isinstance(f.get('properties',{}), dict):
                issues.append(_issue('PROPERTIES','ERROR',f'Feature {idx}: properties must be object'))
        details['features']=len(dataset.features)
        if bounds:
            details['bbox']=[min(x[0] for x in bounds),min(x[1] for x in bounds),max(x[2] for x in bounds),max(x[3] for x in bounds)]
            if aoi is not None and not box(*details['bbox']).intersects(aoi):
                issues.append(_issue('NO_AOI_OVERLAP','WARNING','Feature bounds do not intersect AOI'))
        if aoi is not None:
            # Bbox candidates need clipping in T04; warn even when all within bbox.
            issues.append(_issue('NOT_CLIPPED','WARNING','T02 Overpass results are bbox candidates; T04 must clip by AOI/hazard'))
    except (GeoDataError,OSError) as e:
        issues.append(_issue('LOAD_ERROR','ERROR',str(e)))
    return _report('vector',path,issues,details)


def validate_aoi(path):
    issues=[]; details={}
    try:
        ds=load_geojson(path)
        if len(ds.features)!=1: issues.append(_issue('AOI_COUNT','ERROR','AOI must contain exactly one polygon feature'))
        aoi=None
        for f in ds.features:
            g=shape(f['geometry'])
            if g.geom_type not in ('Polygon','MultiPolygon'):
                issues.append(_issue('AOI_TYPE','ERROR','AOI must be Polygon/MultiPolygon'))
            if g.is_empty or not g.is_valid: issues.append(_issue('AOI_TOPOLOGY','ERROR',explain_validity(g)))
            if any(not math.isfinite(v) for v in g.bounds) or g.bounds[0]<-180 or g.bounds[2]>180 or g.bounds[1]<-90 or g.bounds[3]>90:
                issues.append(_issue('AOI_COORDS','ERROR','AOI must use valid longitude/latitude'))
            if (g.bounds[2]-g.bounds[0])>=180: issues.append(_issue('ANTIMERIDIAN','ERROR','Split antimeridian AOI'))
            aoi=g
        if aoi is not None: details['bbox']=list(aoi.bounds)
    except (GeoDataError,KeyError,ValueError,TypeError) as e:
        issues.append(_issue('AOI_LOAD','ERROR',str(e)))
    return _report('aoi',path,issues,details)


def validate_raster(path, aoi=None, population=True, chunk_size=512):
    issues=[]; details={}
    try:
        ds_meta=load_geotiff(path);details.update(ds_meta.metadata)
        with rasterio.open(path) as ds:
            if ds.driver!='GTiff': issues.append(_issue('FORMAT','ERROR','Raster must be GeoTIFF'))
            if ds.crs is None: issues.append(_issue('MISSING_CRS','ERROR','Raster has no CRS'))
            if ds.transform.is_identity or abs(ds.transform.a*ds.transform.e-ds.transform.b*ds.transform.d)<1e-20:
                issues.append(_issue('GEOREFERENCE','ERROR','Raster has invalid/identity transform'))
            if ds.width<=0 or ds.height<=0 or ds.count!=1:
                issues.append(_issue('RASTER_BANDS','ERROR','Expected one raster band with nonzero dimensions'))
            if ds.nodata is None: issues.append(_issue('NO_NODATA','WARNING','No explicit NoData value; masks may still exist'))
            if aoi is not None and ds.crs is not None:
                try:
                    raster_geo=transform_bounds(ds.crs,'EPSG:4326',*ds.bounds,densify_pts=21)
                    details['bounds_epsg4326']=list(raster_geo)
                    if not box(*raster_geo).intersects(aoi):
                        issues.append(_issue('NO_AOI_OVERLAP','ERROR','Raster extent does not overlap requested AOI'))
                    elif not box(*raster_geo).covers(aoi):
                        issues.append(_issue('PARTIAL_COVERAGE','WARNING','Raster extent only partially covers AOI; T04 must compute exact valid-pixel coverage'))
                except Exception as e: issues.append(_issue('TRANSFORM_BOUNDS','ERROR',str(e)))
            valid=0;neg=0;nonfinite=0;minval=None;maxval=None
            for _,window in ds.block_windows(1):
                band=ds.read(1,window=window,masked=True)
                vals=np.asarray(band.compressed(),dtype=np.float64)
                valid+=int(vals.size)
                if vals.size:
                    nonfinite+=int(np.count_nonzero(~np.isfinite(vals)))
                    vals=vals[np.isfinite(vals)]
                    if vals.size:
                        neg+=int(np.count_nonzero(vals<0))
                        mn,mx=float(vals.min()),float(vals.max())
                        minval=mn if minval is None else min(minval,mn)
                        maxval=mx if maxval is None else max(maxval,mx)
            details.update({'valid_pixels':valid,'negative_pixels':neg,'nonfinite_pixels':nonfinite,'min_valid':minval,'max_valid':maxval})
            if not valid: issues.append(_issue('ALL_NODATA','ERROR','No usable pixels'))
            if nonfinite: issues.append(_issue('NONFINITE','ERROR','Nonfinite raster values detected'))
            if population and neg: issues.append(_issue('NEGATIVE_POPULATION','ERROR','Population counts cannot be negative'))
            if population and ds.dtypes[0] not in ('float32','float64','int16','int32','uint16','uint32','uint8','int64','uint64'):
                issues.append(_issue('POPULATION_DTYPE','ERROR',f'Unexpected raster dtype {ds.dtypes[0]}'))
            if population:
                issues.append(_issue('POPULATION_UNITS','WARNING','Raster pixels assumed people/cell; source product metadata and year must be confirmed'))
    except (GeoDataError,rasterio.errors.RasterioError,OSError,ValueError) as e:
        issues.append(_issue('RASTER_LOAD','ERROR',str(e)))
    return _report('population_raster' if population else 'raster',path,issues,details)


def validate_manifest(path, osm_path=None, population_path=None):
    issues=[];details={}
    try:
        manifest=json.loads(Path(path).read_text(encoding='utf-8'))
        sources=manifest.get('sources',{})
        details['sources']={k:v.get('status') for k,v in sources.items() if isinstance(v,dict)}
        for name,filepath in [('osm',osm_path),('worldpop',population_path)]:
            if filepath is None: continue
            record=sources.get(name)
            if not isinstance(record,dict) or record.get('status')!='downloaded':
                issues.append(_issue('SOURCE_STATUS','ERROR',f'{name} not marked downloaded'))
                continue
            import hashlib
            fingerprint=record.get('metadata',{}).get('sha256')
            if not fingerprint:
                issues.append(_issue('MISSING_HASH','ERROR',f'{name} missing source SHA-256'))
                continue
            files=record.get('files',[])
            # T02 checksum is of raw OSM JSON, not derived geojson
            candidate=next((p for p in files if (name=='osm' and str(p).endswith('osm_overpass_raw.json')) or
                            (name=='worldpop' and str(p).endswith('.tif'))),None)
            if not candidate:
                issues.append(_issue('MANIFEST_FILE','ERROR',f'{name} source file missing in manifest'))
                continue
            source=Path(candidate)
            if not source.is_absolute(): source=(Path(path).parent/source) if not source.exists() else source
            if not source.is_file():
                issues.append(_issue('MISSING_SOURCE_FILE','ERROR',f'Cannot inspect source file {source}'))
                continue
            h=hashlib.sha256()
            with source.open('rb') as stream:
                for part in iter(lambda:stream.read(1<<20),b''): h.update(part)
            if h.hexdigest()!=fingerprint: issues.append(_issue('HASH_MISMATCH','ERROR',f'{name} source SHA-256 mismatch'))
        if not sources: issues.append(_issue('EMPTY_MANIFEST','ERROR','No sources in manifest'))
    except (OSError,ValueError,TypeError) as e: issues.append(_issue('MANIFEST_LOAD','ERROR',str(e)))
    return _report('source_manifest',path,issues,details)


def main():
    p=argparse.ArgumentParser(description='M3/T03: validate real AOI, OSM GeoJSON and population GeoTIFF; never fabricate or repair data.')
    p.add_argument('--aoi',required=True)
    p.add_argument('--osm',required=True)
    p.add_argument('--population',required=True)
    p.add_argument('--manifest',default=None)
    p.add_argument('--report',default='data/validated/qa_report.json')
    args=p.parse_args()
    aoi_report=validate_aoi(args.aoi)
    aoi=None
    if aoi_report['status']!='REJECT':
        features=load_geojson(args.aoi).features
        aoi=shape(features[0]['geometry'])
    reports={'aoi':aoi_report,'osm':validate_vector(args.osm,aoi),
             'population':validate_raster(args.population,aoi)}
    if args.manifest: reports['manifest']=validate_manifest(args.manifest,args.osm,args.population)
    overall='REJECT' if any(r['status']=='REJECT' for r in reports.values()) else ('WARNING' if any(r['status']=='WARNING' for r in reports.values()) else 'PASS')
    result={'task':'M3-P1-T03','created_at_utc':datetime.now(timezone.utc).isoformat(),
            'overall_status':overall,'reports':reports,
            't04_gate':'BLOCK' if overall=='REJECT' else 'REVIEW_REQUIRED' if overall=='WARNING' else 'READY',
            'note':'WARNING requires analyst review. No clipping, raster reprojection, hazard classification or impact calculations were done.'}
    target=Path(args.report);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({'status':overall,'t04_gate':result['t04_gate'],'report':str(target)},indent=2))
    if overall=='REJECT': raise SystemExit(1)

if __name__=='__main__': main()
