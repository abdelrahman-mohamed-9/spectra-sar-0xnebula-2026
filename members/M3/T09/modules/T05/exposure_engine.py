"""SPECTRA-SAR M3/T05: potential population and asset exposure.

Uses a genuine source raster supplied at runtime; tests use synthetic arrays only.
Only positive-area pixel overlap counts. Does NOT infer casualties or damage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds, Window
from pyproj import CRS, Transformer
from shapely.geometry import shape, box
from shapely.ops import transform

class ExposureInputError(ValueError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def sha256(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):
            h.update(chunk)
    return h.hexdigest()


def _gate(qa_doc, approve_warning):
    if qa_doc.get('overall_status') == 'REJECT' or qa_doc.get('status') == 'REJECT' or qa_doc.get('t04_gate') == 'BLOCK':
        raise ExposureInputError('T03 quality gate rejects input')
    for name, report in qa_doc.get('reports', {}).items():
        if isinstance(report,dict) and report.get('status') == 'REJECT':
            raise ExposureInputError(f'T03 dataset {name} rejected')
    if (qa_doc.get('overall_status') == 'WARNING' or qa_doc.get('t04_gate') == 'REVIEW_REQUIRED') and not approve_warning:
        raise ExposureInputError('T03 has warnings: requires explicit --approve-qa-warning')


def _hazard_geometry(path):
    collection=read_json(path)
    if collection.get('type') != 'FeatureCollection':
        raise ExposureInputError('Clipped hazard must be a GeoJSON FeatureCollection (WGS84)')
    features=collection.get('features',[])
    if len(features) > 1:
        raise ExposureInputError('Clipped hazard must have 0 or 1 features, as emitted by T04')
    if not features:
        return None
    geom=shape(features[0]['geometry'])
    if geom.is_empty:
        return None
    if not geom.is_valid or geom.geom_type not in ('Polygon','MultiPolygon'):
        raise ExposureInputError('Hazard geometry must be valid Polygon or MultiPolygon')
    if not all(math.isfinite(v) for v in geom.bounds) or geom.bounds[0]<-180 or geom.bounds[2]>180 or geom.bounds[1]<-90 or geom.bounds[3]>90 or geom.bounds[2]-geom.bounds[0]>=180:
        raise ExposureInputError('Hazard must be valid WGS84 geometry not crossing antimeridian')
    return geom


def _population_overlap(raster_path, hazard, *, unit, max_cells):
    with rasterio.open(raster_path) as ds:
        if ds.count != 1:
            raise ExposureInputError('Expected one population band')
        if not ds.crs:
            raise ExposureInputError('Raster CRS missing')
        if not ds.crs.is_projected and not ds.crs.is_geographic:
            raise ExposureInputError('Unsupported raster CRS')
        if abs(ds.transform.b)>1e-12 or abs(ds.transform.d)>1e-12:
            raise ExposureInputError('Rotated/skewed rasters not supported in T05')
        if ds.transform.a<=0 or ds.transform.e>=0:
            raise ExposureInputError('Expected north-up raster (x grows east; y grows north)')
        if ds.nodata is None:
            raise ExposureInputError('Population raster must define NoData to detect unknown coverage')
        if hazard is None:
            return dict(population_estimate=0.0, intersected_cells=0, valid_cells=0, missing_cells=0,
                        coverage_fraction=1.0, outside_raster_fraction=0.0, population_lower_bound=0.0, pixel_overlap_area_m2=0.0)
        proj=Transformer.from_crs('EPSG:4326',ds.crs,always_xy=True)
        projected=transform(proj.transform,hazard)
        if projected.is_empty:
            raise ExposureInputError('Hazard projection unexpectedly empty')
        # intersect with raster extent first; don't read any raster if out of coverage
        raster_bounds=box(*ds.bounds)
        if not raster_bounds.intersects(projected) or projected.intersection(raster_bounds).area == 0:
            raise ExposureInputError('Hazard lies outside population raster extent (coverage unknown)')
        raw=from_bounds(*projected.bounds,transform=ds.transform)
        r0=max(0,int(math.floor(raw.row_off))); c0=max(0,int(math.floor(raw.col_off)))
        r1=min(ds.height,int(math.ceil(raw.row_off+raw.height)))
        c1=min(ds.width,int(math.ceil(raw.col_off+raw.width)))
        if r1<=r0 or c1<=c0:
            raise ExposureInputError('Hazard not covered by population raster')
        if (r1-r0)*(c1-c0)>max_cells:
            raise ExposureInputError(f'Raster candidate window exceeds {max_cells} cells; split AOI/use tiled processing')
        window=Window(c0,r0,c1-c0,r1-r0)
        arr=ds.read(1,window=window,masked=True)
        # Compute true area fractions using equal-area projection; safe for regional non-polar scenes.
        equal_area=Transformer.from_crs(ds.crs,'EPSG:6933',always_xy=True)
        haz_eq=transform(equal_area.transform,projected)
        if haz_eq.is_empty or not haz_eq.is_valid:
            raise ExposureInputError('Hazard invalid after equal-area transformation')
        raster_coverage_area=haz_eq.intersection(transform(equal_area.transform,raster_bounds)).area
        hazard_total_area=haz_eq.area
        external_gap_fraction=max(0.0,1-raster_coverage_area/hazard_total_area) if hazard_total_area>0 else 0.0
        total=0.0; overlap_m2=0.0; valid=missing=intersected=0
        for i in range(r0,r1):
            for j in range(c0,c1):
                left,bottom,right,top=rasterio.windows.bounds(Window(j,i,1,1),ds.transform)
                cell=box(left,bottom,right,top)
                if not projected.intersects(cell): continue
                # Positively overlapping pixels only; cell in original CRS then equal-area.
                if projected.intersection(cell).area<=0: continue
                cell_eq=transform(equal_area.transform,cell)
                area=cell_eq.area
                if area<=0 or not math.isfinite(area):
                    raise ExposureInputError('Invalid projected pixel area')
                overlap=haz_eq.intersection(cell_eq).area
                fraction=min(1.0,max(0.0,overlap/area))
                if fraction<=0:continue
                intersected+=1
                value=arr[i-r0,j-c0]
                if np.ma.is_masked(value) or not np.isfinite(float(value)):
                    missing+=1;continue
                count=float(value)
                if count<0:
                    raise ExposureInputError(f'Negative population raster value at row={i}, col={j}')
                valid+=1
                overlap_m2+=overlap
                if unit=='count_per_pixel':
                    total+=count*fraction
                else:
                    total+=count*overlap/1_000_000
        if not intersected:
            raise ExposureInputError('No positive-area raster cells intersect hazard')
        if not valid:
            raise ExposureInputError('All intersected population cells missing or NoData')
        return dict(population_estimate=round(total,3),population_lower_bound=round(total,3),
                    intersected_cells=intersected,valid_cells=valid,missing_cells=missing,
                    coverage_fraction=round(valid/intersected,6),outside_raster_fraction=round(external_gap_fraction,6),pixel_overlap_area_m2=round(overlap_m2,2))


def analyze(t04_metrics_path, clipped_hazard_path, raster_path, qa_report_path, *, raster_provenance,
            population_unit='count_per_pixel', approve_qa_warning=False, max_cells=250000):
    if not raster_provenance.strip():raise ExposureInputError('Real raster provenance is required')
    if population_unit not in ('count_per_pixel','density_per_km2'):
        raise ExposureInputError('Choose a supported population unit explicitly')
    qa=read_json(qa_report_path)
    _gate(qa,approve_qa_warning)
    t04=read_json(t04_metrics_path)
    if t04.get('module')!='SPECTRA-SAR/M3/T04' or t04.get('schema_version')!='1.0.0':
        raise ExposureInputError('Expected genuine T04 metrics schema 1.0.0')
    stats=t04.get('statistics',{})
    required=['hazard_area_within_aoi_m2','potentially_exposed_buildings','building_footprint_overlap_m2','road_length_overlap_m']
    if any(x not in stats for x in required):
        raise ExposureInputError('T04 metrics missing asset/exposure fields')
    if any(not isinstance(stats[x],(float,int)) or not math.isfinite(stats[x]) or stats[x]<0 for x in required):
        raise ExposureInputError('T04 metrics contain invalid measurements')
    hazard=_hazard_geometry(clipped_hazard_path)
    # Make sure geometry expected by T04 is not silently replaced with a different file.
    if (hazard is None) != (stats['hazard_area_within_aoi_m2']==0):
        raise ExposureInputError('T04 hazard area and supplied clipped hazard disagree')
    pop=_population_overlap(raster_path,hazard,unit=population_unit,max_cells=max_cells)
    warnings=['Exposure is not confirmed impact, damage, injuries, displacement or casualties.',
              'WorldPop is modeled population, not individual-level observation; source year/resolution matter.',
              'Fractional pixel overlap assumes uniform population within each cell.',
              'OSM feature completeness varies; counts cannot establish true infrastructure damage.',
              'Population metrics are not hazard severity or a calibrated risk score.']
    if pop['outside_raster_fraction']>1e-8:
        warnings.append('Hazard extends beyond raster coverage; population estimate excludes the uncovered area.')
    if pop['missing_cells']:
        warnings.append(f"Incomplete raster coverage: {pop['missing_cells']} overlapping cells are NoData; population_estimate is a partial lower bound only, not a total.")
    result={'schema_version':'1.0.0','module':'SPECTRA-SAR/M3/T05',
            'generated_at_utc':datetime.now(timezone.utc).isoformat(),
            'inputs':{'t04_metrics':str(t04_metrics_path),'t04_metrics_sha256':sha256(t04_metrics_path),
                      'clipped_hazard':str(clipped_hazard_path),'clipped_hazard_sha256':sha256(clipped_hazard_path),
                      'population_raster':str(raster_path),'population_raster_sha256':sha256(raster_path),
                      'population_provenance':raster_provenance,'population_unit':population_unit,
                      'qa_report':str(qa_report_path),'qa_warning_approved':approve_qa_warning,
                      'hazard_provenance':t04.get('inputs',{}).get('hazard_provenance')},
            'methodology':{'population':'area-weighted fractional overlap using EPSG:6933 pixel areas',
                           'population_assumption':'uniform population distribution inside each raster cell',
                           'asset_metrics':'passed through without recomputing from T04; potential exposure only'},
            'statistics':{'exposed_population_estimate':pop['population_estimate'],
                          'population_result_status':'PARTIAL' if (pop['missing_cells'] or pop['outside_raster_fraction']>1e-8) else 'COMPLETE_WITHIN_RASTER',
                          'population_cells_intersected':pop['intersected_cells'],
                          'population_cells_valid':pop['valid_cells'],
                          'population_cells_missing':pop['missing_cells'],
                          'population_cell_coverage_fraction':pop['coverage_fraction'],
                          'population_outside_raster_fraction':pop['outside_raster_fraction'],
                          'population_raster_overlap_m2':pop['pixel_overlap_area_m2'],
                          'potentially_exposed_buildings':stats['potentially_exposed_buildings'],
                          'building_footprint_overlap_m2':stats['building_footprint_overlap_m2'],
                          'road_length_overlap_m':stats['road_length_overlap_m'],
                          'hazard_area_within_aoi_m2':stats['hazard_area_within_aoi_m2']},
            'warnings':warnings}
    return result


def main():
    p=argparse.ArgumentParser(description='M3 T05 potential exposure using WorldPop raster and verified T04 metrics')
    p.add_argument('--t04-metrics',required=True);p.add_argument('--clipped-hazard',required=True)
    p.add_argument('--population',required=True);p.add_argument('--qa-report',required=True)
    p.add_argument('--population-provenance',required=True,help='WorldPop product URL, year and release')
    p.add_argument('--population-unit',required=True,choices=['count_per_pixel','density_per_km2'])
    p.add_argument('--approve-qa-warning',action='store_true');p.add_argument('--max-cells',type=int,default=250000)
    p.add_argument('--out',default='data/exposure/exposure_metrics.json')
    a=p.parse_args()
    try:
        result=analyze(a.t04_metrics,a.clipped_hazard,a.population,a.qa_report,
                       raster_provenance=a.population_provenance,population_unit=a.population_unit,
                       approve_qa_warning=a.approve_qa_warning,max_cells=a.max_cells)
        dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
        print(json.dumps({'status':'PASS','out':str(dest),'statistics':result['statistics']},indent=2))
    except (ExposureInputError,ValueError,FileNotFoundError,KeyError,rasterio.errors.RasterioError) as exc:
        p.exit(2,f'REJECT: {exc}\n')
if __name__=='__main__': main()
