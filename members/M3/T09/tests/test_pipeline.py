import json, sys
from pathlib import Path
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import execute

def write_json(path,doc):
    path.write_text(json.dumps(doc));return path

def fc(geometries):
    return {'type':'FeatureCollection','features':[{'type':'Feature','geometry':geom,'properties':props} for geom,props in geometries]}

def polygon(x0,y0,x1,y1):
    return {'type':'Polygon','coordinates':[[[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]]}

@pytest.fixture
def sample(tmp_path):
    # ALL inputs are deliberately synthetic TEST FIXTURES, never satellite observations.
    aoi=write_json(tmp_path/'aoi.geojson',fc([(polygon(30,30,30.02,30.02),{})]))
    hazard=write_json(tmp_path/'hazard.geojson',fc([(polygon(30.005,30.005,30.015,30.015),{})]))
    osm=write_json(tmp_path/'osm.geojson',fc([
        (polygon(30.007,30.007,30.009,30.009),{'osm_id':'b1','building':'yes'}),
        ({'type':'LineString','coordinates':[[30.001,30.01],[30.018,30.01]]},{'osm_id':'r1','highway':'residential'})]))
    tif=tmp_path/'population.tif'
    with rasterio.open(tif,'w',driver='GTiff',width=6,height=6,count=1,dtype='float32',crs='EPSG:4326',
                       transform=from_origin(29.995,30.025,0.005,0.005),nodata=-9999) as dst:
        dst.write(np.full((6,6),20,dtype='float32'),1)
    config={'aoi':str(aoi),'osm':str(osm),'population':str(tif),'hazard':str(hazard),
            'hazard_provenance':'SYNTHETIC_TEST_FIXTURE_NOT_M2',
            'population_provenance':'SYNTHETIC_TEST_FIXTURE_NOT_WORLDPOP',
            'population_unit':'count_per_pixel','hazard_type':'unknown','evidence_status':'UNVERIFIED',
            'approve_qa_warning':True}
    return config

def test_complete_pipeline_review_required(sample,tmp_path):
    result=execute(sample,tmp_path/'run')
    assert result['status']=='PIPELINE_EXECUTED'
    assert len(result['steps'])==6
    assert result['risk_status']=='REVIEW_REQUIRED'
    assert all(Path(entry['path']).exists() for entry in result['outputs'].values())
    risk=json.loads((tmp_path/'run/risk_assessment.json').read_text())
    assert risk['decision']['priority_score'] is None
    assert json.loads((tmp_path/'run/impact_statistics.json').read_text())['module']=='SPECTRA-SAR/M3/T07'

def test_fail_closed_unapproved_warning(sample,tmp_path):
    sample['approve_qa_warning']=False
    with pytest.raises(ValueError,match='WARNING'):
        execute(sample,tmp_path/'blocked')
    assert not (tmp_path/'blocked/spatial_metrics.json').exists()

def test_fail_closed_missing_file(sample,tmp_path):
    sample['population']=str(tmp_path/'missing.tif')
    with pytest.raises(FileNotFoundError):execute(sample,tmp_path/'missing')

def test_missing_provenance(sample,tmp_path):
    sample['hazard_provenance']=''
    with pytest.raises(ValueError,match='hazard_provenance'):execute(sample,tmp_path/'provenance')
