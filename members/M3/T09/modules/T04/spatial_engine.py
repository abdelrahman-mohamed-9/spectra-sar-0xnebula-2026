"""SPECTRA-SAR M3/T04: geospatial intersections with explicit non-causal metrics.

Inputs from T02/T03 are GeoJSON (EPSG:4326). Does NOT download or synthesize
observational data. Hazard polygons must be verified outputs from M2.
"""
from __future__ import annotations
import argparse
import json
import math
from datetime import datetime,timezone
from pathlib import Path
from shapely.geometry import shape, mapping
from shapely.ops import unary_union
from geo_loader import load_geojson
from geometry_utils import area_m2, length_m, validate_polygon

class SpatialInputError(ValueError): pass

def _feature_geometries(path, *, allowed, kind):
    ds=load_geojson(path)
    result=[]
    for i, feature in enumerate(ds.features):
        if not isinstance(feature,dict) or feature.get('type')!='Feature':
            raise SpatialInputError(f'{kind} feature {i} is not a GeoJSON Feature')
        try: geom=shape(feature['geometry'])
        except (KeyError, ValueError, TypeError) as exc: raise SpatialInputError(f'{kind} feature {i} invalid: {exc}') from exc
        if geom.is_empty or not geom.is_valid or geom.geom_type not in allowed:
            raise SpatialInputError(f'{kind} feature {i}: invalid / unsupported geometry {geom.geom_type}')
        if not all(math.isfinite(v) for v in geom.bounds) or geom.bounds[0] < -180 or geom.bounds[2] > 180 or geom.bounds[1] < -90 or geom.bounds[3] > 90 or geom.bounds[2]-geom.bounds[0]>=180:
            raise SpatialInputError(f'{kind} feature {i}: invalid WGS84 coordinate extent')
        result.append((geom, feature.get('properties') or {},i))
    return result

def _region(path,label):
    features=_feature_geometries(path,allowed={'Polygon','MultiPolygon'},kind=label)
    if len(features)!=1: raise SpatialInputError(f'{label}: exactly one polygon feature required')
    geom=features[0][0]
    validate_polygon(geom,label)
    return geom

def _qa_gate(path, *, approve_warning=False):
    if path is None: raise SpatialInputError('T03 QA report required; pass --qa-report')
    doc=json.loads(Path(path).read_text(encoding='utf-8'))
    # T03 report has top-level status and per-dataset statuses.
    if doc.get('overall_status') == 'REJECT' or doc.get('status') == 'REJECT':
        raise SpatialInputError('T03 QA REJECT: cannot process')
    for k,v in doc.get('reports',{}).items():
        if isinstance(v,dict) and v.get('status') == 'REJECT':
            raise SpatialInputError(f'T03 QA REJECT in {k}: cannot process')
    gate=doc.get('t04_gate')
    if gate=='BLOCK': raise SpatialInputError('T03 gate BLOCK')
    if (gate=='REVIEW_REQUIRED' or doc.get('overall_status')=='WARNING') and not approve_warning:
        raise SpatialInputError('T03 WARNING: review QA and explicitly pass --approve-qa-warning')
    return {'qa_report':str(path),'qa_status':doc.get('overall_status',doc.get('status','UNKNOWN')), 'qa_warning_approved':bool(approve_warning)}

def analyze(aoi_path, hazard_path, osm_path, *, qa_report, hazard_provenance, approve_qa_warning=False):
    if not hazard_provenance or not hazard_provenance.strip():
        raise SpatialInputError('Provide real M2 hazard source using --hazard-provenance')
    qa=_qa_gate(qa_report,approve_warning=approve_qa_warning)
    aoi=_region(aoi_path,'AOI')
    hazard=_region(hazard_path,'hazard change polygon')
    hazard_in_aoi=hazard.intersection(aoi)
    # Geodetic area applies to clipped WGS84 geometry. Dedupe union for geometries.
    affected_area=area_m2(hazard_in_aoi)
    aoi_area=area_m2(aoi)
    if aoi_area<=0:raise SpatialInputError('AOI area zero')
    entries=_feature_geometries(osm_path,allowed={'Polygon','MultiPolygon','LineString','MultiLineString','Point','MultiPoint'},kind='OSM')
    buildings=[]; roads=[]; ignored=0; affected_buildings=[]; affected_roads=[]
    seen_building_ids=set(); seen_road_ids=set()
    for geom,props,i in entries:
        # Only classify objects with explicit OSM tags; OSM can include many POIs.
        osm_id=props.get('osm_id') or props.get('id')
        if props.get('building') and geom.geom_type in ('Polygon','MultiPolygon'):
            key=('building',str(osm_id)) if osm_id is not None else ('building',i)
            if key in seen_building_ids: continue
            seen_building_ids.add(key)
            buildings.append(geom)
            if geom.intersects(hazard_in_aoi) and area_m2(geom.intersection(hazard_in_aoi))>0:
                affected_buildings.append(geom)
        elif props.get('highway') and geom.geom_type in ('LineString','MultiLineString'):
            key=('road',str(osm_id)) if osm_id is not None else ('road',i)
            if key in seen_road_ids: continue
            seen_road_ids.add(key)
            roads.append(geom)
            if length_m(geom.intersection(hazard_in_aoi))>0:
                affected_roads.append(geom.intersection(hazard_in_aoi))
        else: ignored+=1
    affected_building_parts=[g.intersection(hazard_in_aoi) for g in affected_buildings]
    # Footprint union prevents overlapping footprints being double-counted in area.
    footprint_union=unary_union(affected_building_parts) if affected_building_parts else None
    road_union=unary_union(affected_roads) if affected_roads else None
    result={
        'schema_version':'1.0.0','module':'SPECTRA-SAR/M3/T04',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'inputs':{'aoi':str(aoi_path),'hazard':str(hazard_path),'osm':str(osm_path),
                  'hazard_provenance':hazard_provenance,**qa},
        'methodology':{'crs':'EPSG:4326','measurement':'WGS84 ellipsoid (pyproj.Geod)',
                       'hazard_interpretation':'M2 geospatial change footprint; not verified damage',
                       'building_count':'number of unique OSM building polygons with positive area overlap',
                       'road_length':'unique overlapping road geometry union; excludes line boundary-only touches'},
        'statistics':{
            'aoi_area_m2':round(aoi_area,3),
            'hazard_area_within_aoi_m2':round(affected_area,3),
            'hazard_area_within_aoi_km2':round(affected_area/1e6,6),
            'hazard_percent_of_aoi':round(100*affected_area/aoi_area,5),
            'osm_buildings_found':len(buildings),'potentially_exposed_buildings':len(affected_buildings),
            'building_footprint_overlap_m2':round(area_m2(footprint_union),3) if footprint_union else 0.0,
            'osm_road_features_found':len(roads),'road_features_intersected':len(affected_roads),
            'road_length_overlap_m':round(length_m(road_union),3) if road_union else 0.0,
            'osm_unclassified_features':ignored,
        },
        'warnings':['Geospatial overlap represents potential exposure, not confirmed damage or displaced persons.',
                    'OSM completeness varies by region; absence of features does not imply absence of assets.',
                    'Actual hazards require event-specific SAR interpretation and independent validation.',
                    'Population overlay and risk categorization are outside T04 (T05/T06).']
    }
    geom_output={'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{'layer':'hazard_clipped','source':hazard_provenance},'geometry':mapping(hazard_in_aoi)}
    ] if not hazard_in_aoi.is_empty else []}
    return result,geom_output

def main():
    p=argparse.ArgumentParser(description='M3/T04 real geospatial overlays; requires validated T03 input and verified M2 hazard polygon')
    p.add_argument('--aoi',required=True);p.add_argument('--hazard',required=True);p.add_argument('--osm',required=True)
    p.add_argument('--qa-report',required=True);p.add_argument('--hazard-provenance',required=True)
    p.add_argument('--approve-qa-warning',action='store_true',help='Explicit analyst approval for documented T03 WARNING conditions')
    p.add_argument('--out',default='data/spatial/spatial_metrics.json')
    p.add_argument('--clipped-hazard-out',default='data/spatial/clipped_hazard.geojson')
    args=p.parse_args()
    try:
        metrics,geojson=analyze(args.aoi,args.hazard,args.osm,qa_report=args.qa_report,hazard_provenance=args.hazard_provenance,approve_qa_warning=args.approve_qa_warning)
        for dest,content in [(args.out,metrics),(args.clipped_hazard_out,geojson)]:
            target=Path(dest);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'status':'PASS','metrics':args.out,'clipped_hazard':args.clipped_hazard_out,'statistics':metrics['statistics']},indent=2))
    except (SpatialInputError,FileNotFoundError,ValueError,KeyError) as exc:
        p.exit(2,f'REJECT: {exc}\n')
if __name__=='__main__': main()
