"""Honest aggregate-only fallback for WorldPop empty spatial rasters.

This never creates population pixels or promotes an unvalidated exposure claim.
"""
from __future__ import annotations
import hashlib
import json
import math
from pathlib import Path
from datetime import datetime,timezone

def is_only_population_nodata(qa):
    if qa.get('overall_status')!='REJECT' or not isinstance(qa.get('reports'),dict):
        return False
    reports=qa['reports']
    for part in ('aoi','osm','population','manifest'):
        if part not in reports:
            return False
    if reports['aoi'].get('status')!='PASS' or reports['manifest'].get('status')!='PASS':
        return False
    if reports['osm'].get('status')=='REJECT':
        return False
    errors=[(part,i.get('code')) for part,doc in reports.items() for i in doc.get('issues',[])
            if i.get('severity')=='ERROR']
    return errors==[('population','ALL_NODATA')]

def request_worldpop_aggregate(aoi_file,year=2026,timeout=35):
    import requests
    endpoint='https://api.worldpop.org/v3/population'
    aoi=json.loads(Path(aoi_file).read_text(encoding='utf-8'))
    try:
        r=requests.post(endpoint,json={'geojson':aoi,'year':year},timeout=(10,timeout),
                        headers={'Accept':'application/json','User-Agent':'SPECTRA-SAR-Phase1/1.0'})
        r.raise_for_status()
        doc=r.json()
        if not isinstance(doc,dict): raise ValueError('Aggregate response not a JSON object')
        population=doc.get('total_population'); area=doc.get('area_km2')
        if (not isinstance(population,(float,int)) or isinstance(population,bool) or
            not math.isfinite(population) or population<0 or
            not isinstance(area,(float,int)) or not math.isfinite(area) or area<=0 or
            doc.get('data_year')!=year or not isinstance(doc.get('data_source'),str)):
            raise ValueError('Aggregate response missing expected validated fields')
        return {'status':'RETURNED','area_population_estimate':float(population),
                'area_km2':float(area),'data_year':year,'data_source':doc['data_source'],
                'service':endpoint,'response':doc}
    except (requests.RequestException,ValueError,TypeError) as ex:
        return {'status':'UNAVAILABLE','reason':str(ex),'service':endpoint,
                'area_population_estimate':None}

def create_population_gap_report(aoi_file,pop_raster,qa_path,output,aggregate,source_manifest):
    qa_path=Path(qa_path)
    qa=json.loads(qa_path.read_text(encoding='utf-8'))
    if not is_only_population_nodata(qa):
        raise ValueError('Refuse fallback: QA contains more than isolated population ALL_NODATA')
    output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
    sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
    result={'module':'M3','status':'PARTIAL_DATA_GAP',
        'reason':'Population raster contains zero usable pixels (ALL_NODATA); not the same as zero residents.',
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'population_spatial_status':'UNAVAILABLE',
        'estimated_people_exposed_to_radar_change':None,
        'verified_population_count_in_footprint':None,
        'verified_buildings_impacted':None,
        'aggregate_worldpop_area_estimate':aggregate.get('area_population_estimate'),
        'aggregate_worldpop_status':aggregate.get('status'),
        'aggregate_worldpop_source':aggregate.get('data_source'),
        'aggregate_worldpop_area_km2':aggregate.get('area_km2'),
        'aggregate_worldpop_year':aggregate.get('data_year'),
        'aggregate_is_NOT_spatial_exposure':True,
        'source_notes':'WorldPop area aggregate is a modeled estimate for AOI, NOT exposed population nor proof of raster coverage.',
        'osm_status':'UNVERIFIED' if qa['reports']['osm']['status']!='PASS' else 'T03_VALIDATED',
        'qa_status':qa['overall_status'],
        'qa_report_sha256':sha(qa_path),'population_raster_sha256':sha(pop_raster),
        'source_manifest_sha256':sha(source_manifest),
        'science_approved':False,
        'next_action':'For spatial exposure use a genuine independently validated population raster with valid cells, or change the study site with corresponding genuine SAR scenes.'}
    output.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return result
