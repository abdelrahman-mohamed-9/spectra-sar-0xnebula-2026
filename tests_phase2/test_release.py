import json
import shutil
from pathlib import Path

import numpy as np
import pytest
import rasterio
from fastapi.testclient import TestClient

from phase2.datasets import DEFAULT_ID, register, resolve
from phase2.jobs import CATALOG, Jobs, work_one
from phase2.application import create_local_app
from phase2.detection import compare
from phase2.benchmark import tuned_comparator, chip


def test_import_real_pair_without_geography_remains_unknown(tmp_path):
    state=tmp_path/'state'
    entry=register(state,'second-pair',CATALOG/'data/nisar')
    assert entry['reference_available'] is False
    assert resolve(state,'second-pair').is_dir()
    queue=Jobs(state)
    job=queue.submit('alice','second-pair','review')
    work_one(queue)
    row=queue.get('alice',job)
    assert row['status']=='COMPLETED_EXPLORATORY'
    result=json.loads(row['result'])
    assert result['m2']['candidate_mode']=='review'
    assert result['m3']['estimated_residents_exposed'] is None
    assert result['m3']['mapped_buildings_intersecting'] is None
    assert result['m3']['mapped_road_overlap_m'] is None
    assert set(result['m3']['data_gaps'])=={'population','roads','buildings'}
    assert result['m2']['external_benchmark']=='NOT_INCLUDED_FOR_IMPORTED_DATASET'
    assert queue.get('bob',job) is None
    assert queue.list('bob')==[]
    with pytest.raises(ValueError,match='already exists'):
        register(state,'second-pair',CATALOG/'data/nisar')
    with pytest.raises(ValueError): resolve(state,'../anything')


def test_import_rejects_changed_receipt_and_identical_pair(tmp_path):
    pair=tmp_path/'pair';shutil.copytree(CATALOG/'data/nisar',pair)
    receipt=pair/'input-provenance.json'
    obj=json.loads(receipt.read_text());obj['input_sha256']['before']='0'*64;receipt.write_text(json.dumps(obj))
    with pytest.raises(ValueError,match='receipt'):
        register(tmp_path/'state','bad-receipt',pair)
    assert not (tmp_path/'state/datasets/bad-receipt').exists()
    shutil.copy2(pair/'before_HHHH.tif',pair/'after_HHHH.tif')
    with pytest.raises(ValueError,match='Identical'):
        register(tmp_path/'state','same-pair',pair)


def test_import_independent_reference_flows_through_worker(tmp_path):
    pair=CATALOG/'data/nisar'
    ref=tmp_path/'labels.tif';provenance=tmp_path/'provenance.json'
    with rasterio.open(pair/'before_HHHH.tif') as src:
        profile=src.profile.copy();profile.update(dtype='uint8',nodata=255,predictor=1)
        truth=np.full(src.shape,255,dtype='uint8');truth[50:80,50:80]=0;truth[100:130,100:130]=1
        with rasterio.open(ref,'w',**profile) as dst:dst.write(truth,1)
    from phase2.run_m2 import sha256
    manifest=json.loads((pair/'manifest.json').read_text())
    provenance.write_text(json.dumps({'pair_id':manifest['pair_id'],'sha256':sha256(ref),
        'source':'SOFTWARE TEST FIXTURE ONLY', 'label_definition':'test squares, not event evidence',
        'labeling_method':'independent software fixture', 'independent_of_predictions':True}))
    state=tmp_path/'state';register(state,'labeled-test',pair,reference=ref,reference_metadata=provenance)
    queue=Jobs(state);job=queue.submit('alice','labeled-test');work_one(queue)
    row=queue.get('alice',job);assert row['status']=='COMPLETED_EXPLORATORY'
    result=json.loads(row['result']);assert result['scientific_approval'] is False
    assert result['m2']['pair_accuracy']=='EVALUATED_USER_SUPPLIED_REFERENCE'
    report=json.loads((queue.runs/job/'M2/evaluation-report.json').read_text())
    assert report['independent_evaluation']['review']['labeled_valid_pixels']==1800


def test_integrated_app_has_both_phases_and_dashboard(tmp_path,monkeypatch):
    monkeypatch.setenv('SPECTRA_PHASE2_STATE',str(tmp_path/'state'))
    token='local-test-operator-token-'*2
    monkeypatch.setenv('SPECTRA_PHASE2_TOKEN',token)
    app=create_local_app()
    with TestClient(app) as client:
        page=client.get('/');assert page.status_code==200
        assert 'Content-Security-Policy' in page.headers
        assert client.get('/assets/app.js').status_code==200
        routes=set(app.openapi()["paths"])
        assert '/api/v1/phase1/runs' in routes
        assert '/api/v1/phase2/jobs' in routes
        assert client.get('/api/v1/phase2/datasets').status_code==401
        response=client.get('/api/v1/phase2/datasets',headers={'Authorization':'Bearer '+token})
        assert response.json()[0]['id']==DEFAULT_ID
        assert client.post('/api/v1/phase2/jobs',json={'candidate_mode':'fake'},headers={'Authorization':'Bearer '+token}).status_code==422


def test_review_does_not_center_away_widespread_change():
    result=compare(np.full((50,50),4,dtype='float32'))
    assert (result['adaptive']==0).all()
    assert (result['review']==2).all()
    assert np.isfinite(result['review_stability']).all()


def test_heldout_labels_cannot_change_selected_threshold_or_predictions():
    x,y,_,_=chip(CATALOG/'data/benchmark/Spain_1167260')
    p1,m1=tuned_comparator(CATALOG/'data/benchmark',x,y)
    changed=y.copy();changed[y!=255]=1-y[y!=255]
    p2,m2=tuned_comparator(CATALOG/'data/benchmark',x,changed)
    assert np.array_equal(p1,p2)
    assert m1==m2
    assert m1['test_labels_used_for_selection'] is False
    assert all('Spain' not in f['validated_on']+f['trained_on'] for f in m1['validation_folds'])


def test_phase1_doctor_uses_current_receipted_pair():
    from phase1.doctor import diagnose
    report=diagnose()
    assert report['status']=='READY_FOR_INPUT_QA'
    assert report['source_mode']=='CONFIGURED_PAIR'
    assert report['pair_id']=='NISAR_GCOV_073_055_20261017_20261029_REAL'
    assert report['science_validated'] is False
