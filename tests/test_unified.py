"""Generated arrays are temporary SOFTWARE fixtures, never satellite observations."""
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin, from_bounds
from rasterio.warp import transform_bounds
from phase1.common import ROOT, load, write
from phase1.pipeline import run

def pair_fixture(root, pol='HHHH', changed=True):
    root.mkdir()
    profile=dict(driver='GTiff',width=8,height=8,count=1,crs='EPSG:32636',
                 transform=from_origin(500000,3500000,30,30))
    manifest=dict(schema_version='1.0',pair_id='SOFTWARE_FIXTURE_ONLY',source_provider='SYNTHETIC_UNIT_TEST',
                  processing_software='UNIT_TEST',processing_version='1',units='linear_power',
                  sensor='NISAR' if pol=='HHHH' else 'Sentinel-1',
                  product_type='GCOV' if pol=='HHHH' else 'RTC',
                  acquisition_mode='4005' if pol=='HHHH' else 'IW',
                  radiometry='nisar_gcov_diagonal' if pol=='HHHH' else 'gamma0_terrain',
                  polarizations=[pol],grid=dict(crs='EPSG:32636',width=8,height=8,pixel_size_m=30))
    for side,day in [('before','01'),('after','13')]:
        for name,array,dtype in [(pol,np.full((8,8),.023 if side=='after' and changed else .23,dtype='float32'),'float32'),
                                 ('valid',np.ones((8,8),dtype='uint8'),'uint8')]:
            with rasterio.open(root/f'{side}_{name}.tif','w',**profile,dtype=dtype) as ds:ds.write(array,1)
        manifest[side]=dict(scene_id='TEST_ONLY_'+side,acquired_utc=f'2026-10-{day}T10:00:00Z',
                            relative_orbit=15,orbit_direction='ASCENDING',incidence_angle_deg_summary=36.2,
                            raster_files={pol:f'{side}_{pol}.tif'},valid_mask_file=f'{side}_valid.tif',
                            source_url='https://example.test/SYNTHETIC/'+side)
    write(root/'manifest.json',manifest)
    return root

def impact_fixture(root):
    root.mkdir()
    x0,y0,x1,y1=transform_bounds('EPSG:32636','EPSG:4326',499950,3499710,500290,3500050)
    def polygon(a,b,c,d):return {'type':'Polygon','coordinates':[[[a,b],[c,b],[c,d],[a,d],[a,b]]]}
    write(root/'aoi.geojson',{'type':'Feature','geometry':polygon(x0,y0,x1,y1),'properties':{}})
    dx=(x1-x0)/5;dy=(y1-y0)/5
    write(root/'osm.geojson',{'type':'FeatureCollection','features':[{'type':'Feature',
        'geometry':polygon(x0+dx,y0+dy,x0+2*dx,y0+2*dy),'properties':{'osm_id':'TEST_ONLY','building':'yes'}}]})
    with rasterio.open(root/'population.tif','w',driver='GTiff',width=20,height=20,count=1,dtype='float32',
                       crs='EPSG:4326',transform=from_bounds(x0-.001,y0-.001,x1+.001,y1+.001,20,20),nodata=-9999) as ds:
        ds.write(np.full((20,20),2,dtype='float32'),1)
    return {'aoi':str(root/'aoi.geojson'),'osm':str(root/'osm.geojson'),'population':str(root/'population.tif'),
            'population_unit':'count_per_pixel','population_provenance':'SYNTHETIC_TEST_ONLY',
            'approve_qa_warning':True}

@pytest.mark.parametrize('pol',['HHHH','VV'])
def test_six_member_full_pipeline_and_tamper_detection(tmp_path,pol):
    pair=pair_fixture(tmp_path/'pair',pol)
    impact=impact_fixture(tmp_path/'geo')
    out=tmp_path/str(uuid.uuid4())
    result=run({'pair_dir':str(pair),'exploratory':True,'impact':impact,'min_pixels':1,'data_kind':'SYNTHETIC_TEST_ONLY'},out)
    assert result['status']=='COMPLETED_EXPLORATORY',json.dumps(result)
    assert all(r['status']=='PASS' for r in result['stages'].values())
    assert result['scientific_approval'] is False
    assert load(out/'M3/impact/risk_assessment.json')['decision']['priority_score'] is None
    assert load(out/'M6/verification.json')['all_artifacts_verified'] is True
    verify=subprocess.run([sys.executable,'-m','phase1.worker','verify',str(out)],cwd=ROOT,capture_output=True)
    assert verify.returncode==0,verify.stderr
    with (out/'M2/T05_change'/f'change_mask_{pol}.tif').open('ab') as f:f.write(b'tampered')
    verify=subprocess.run([sys.executable,'-m','phase1.worker','verify',str(out)],cwd=ROOT,capture_output=True)
    assert verify.returncode!=0

def test_missing_real_after_never_creates_results(tmp_path):
    out=tmp_path/'blocked'
    result=run({'after':str(tmp_path/'missing.tif')},out)
    assert result['status']=='BLOCKED'
    assert all(v['status']=='BLOCKED' for v in result['stages'].values())
    assert not (out/'M2/m3-delivery.json').exists()

def test_missing_impact_keeps_other_integrations_and_reports_partial(tmp_path):
    pair=pair_fixture(tmp_path/'pair')
    out=tmp_path/'partial'
    result=run({'pair_dir':str(pair),'exploratory':True,'min_pixels':1},out)
    assert result['status']=='PARTIAL',result
    assert result['stages']['M3']['status']=='BLOCKED'
    assert result['stages']['M4']['status']==result['stages']['M6']['status']=='PASS'

def test_no_change_is_legitimate_not_fake_hazard(tmp_path):
    pair=pair_fixture(tmp_path/'pair',changed=False)
    result=run({'pair_dir':str(pair),'exploratory':True},tmp_path/'out')
    assert result['status']=='COMPLETED_EXPLORATORY',result
    assert result['stages']['M3']['status']=='NO_CANDIDATES'
    assert not (tmp_path/'out/M3/impact').exists()

def test_input_grid_mismatch_and_unapproved_warning_block(tmp_path):
    pair=pair_fixture(tmp_path/'pair')
    result=run({'pair_dir':str(pair)},tmp_path/'strict')
    assert result['stages']['M2']['status']=='BLOCKED'
    with rasterio.open(pair/'after_HHHH.tif','r+') as ds: ds.transform=from_origin(500030,3500000,30,30)
    result=run({'pair_dir':str(pair),'exploratory':True},tmp_path/'bad-grid')
    assert result['stages']['M2']['status']=='BLOCKED'

def test_original_m5_api_auth_runs_files_and_verification(tmp_path,monkeypatch):
    sys.path.insert(0,str(ROOT/'backend/src'))
    from fastapi.testclient import TestClient
    from spectra.core.config import get_settings
    from spectra.main import create_app
    key='software-test-secret-'+'x'*32
    monkeypatch.setenv('INTERNAL_API_KEY',key)
    monkeypatch.setenv('SPECTRA_RUNS_DIR',str(tmp_path/'runs'))
    get_settings.cache_clear()
    folder=tmp_path/'runs'/str(uuid.uuid4())
    result=run({'pair_dir':str(pair_fixture(tmp_path/'pair')),'exploratory':True,'min_pixels':1},folder)
    assert result['status']=='PARTIAL',result
    with TestClient(create_app()) as client:
        assert client.get('/api/v1/phase1/status').status_code==401
        headers={'X-API-Key':key}
        assert client.get('/api/v1/phase1/status',headers=headers).status_code==200
        assert len(client.get('/api/v1/phase1/runs',headers=headers).json())==1
        assert client.get('/api/v1/phase1/runs/'+folder.name,headers=headers).json()['status']=='PARTIAL'
        assert client.post('/api/v1/phase1/runs/'+folder.name+'/verify',headers=headers).status_code==200
        assert client.get('/api/v1/phase1/runs/'+folder.name+'/files/M3/candidate-change.geojson',headers=headers).status_code==200
        assert client.get('/api/v1/phase1/runs/'+folder.name+'/files/run.json',headers=headers).status_code==404
        assert client.post('/api/v1/phase1/runs',headers=headers,json={'config_name':'../secret.json'}).status_code==422
    get_settings.cache_clear()

def test_no_overwrite(tmp_path):
    out=tmp_path/'run';out.mkdir()
    with pytest.raises(FileExistsError):run({},out)

def test_distributed_adapter_real_outputs_with_stubbed_infrastructure(tmp_path,monkeypatch):
    """Actual science/artifact code; DB and S3 transports deliberately stubbed."""
    sys.path.insert(0,str(ROOT/'backend/src'))
    from types import SimpleNamespace
    from spectra.persistence.models import ScenePair,SarScene,Artifact,ChangeResult,ImpactAssessment
    import spectra.storage.storage_service as storage
    from phase1.distributed import handle
    pair_input=pair_fixture(tmp_path/'pair')
    impact=impact_fixture(tmp_path/'geo')
    job_id,project_id,pair_id,before_id,after_id=[uuid.uuid4() for _ in range(5)]
    folder=tmp_path/'runs'/str(job_id)
    result=run({'pair_dir':str(pair_input),'exploratory':True,'impact':impact,'min_pixels':1},folder)
    assert result['status']=='COMPLETED_EXPLORATORY',result
    monkeypatch.setenv('SPECTRA_RUNS_DIR',str(tmp_path/'runs'))
    objects=[]
    class DB:
        def get(self,model,id):
            if model is ScenePair:return SimpleNamespace(id=pair_id,project_id=project_id,before_scene_id=before_id,after_scene_id=after_id)
            if model is SarScene:return SimpleNamespace(provider_item_id='TEST_ONLY_before' if id==before_id else 'TEST_ONLY_after')
        def add(self,obj):objects.append(obj)
        def flush(self):pass
    class S3:
        uploaded={}
        def upload_fileobj(self,stream,bucket,key,ExtraArgs):self.uploaded[key]=stream.read()
    client=S3();monkeypatch.setattr(storage,'get_s3_client',lambda:client)
    job=SimpleNamespace(id=job_id,project_id=project_id,scene_pair_id=pair_id,
                        input_parameters={'pipeline':'phase1','config_name':'local.json'})
    handle(DB(),job)
    artifacts=[o for o in objects if isinstance(o,Artifact)]
    assert len(client.uploaded)==len(artifacts)>10
    assert any(o.metadata_json['relative_path']=='M6/provenance.json' for o in artifacts)
    changes=[o for o in objects if isinstance(o,ChangeResult)]
    assert len(changes)==1 and changes[0].evaluation_metrics['scientific_approval'] is False
    assert next(o for o in objects if isinstance(o,ImpactAssessment)).risk_level=='unknown'
