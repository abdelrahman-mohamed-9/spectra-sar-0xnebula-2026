import json

import pytest
from fastapi.testclient import TestClient

from phase2.jobs import Jobs, work_one
from tests_phase2.test_system import app_for


@pytest.fixture(scope='module')
def completed_runs(tmp_path_factory):
    queue = Jobs(tmp_path_factory.mktemp('experience')/'state')
    first = queue.submit('A','nisar-oct2026-ghsl2025','conservative')
    second = queue.submit('A','nisar-oct2026-ghsl2025','review')
    work_one(queue)
    work_one(queue)
    return queue,first,second


def test_explanations_review_persistence_and_access(completed_runs):
    queue,first,second = completed_runs
    route = '/api/v1/phase2/jobs/'+first
    with TestClient(app_for(queue)) as client:
        headers = {'X-Test-Actor':'A'}
        assert client.get(route+'/insights').status_code == 401
        assert client.get(route+'/insights',headers={'X-Test-Actor':'B'}).status_code == 404
        data = client.get(route+'/insights',headers=headers).json()
        assert len(data['zones']) == 7
        assert all(zone['explanation_en'] and zone['priority_reason_en'] for zone in data['zones'])
        candidates = [alert for alert in data['alerts'] if alert['kind']=='candidate_review']
        assert candidates and not any(alert['official_warning'] for alert in data['alerts'])
        for alert in candidates:
            zone = next(zone for zone in data['zones'] if zone['id']==alert['zone_id'])
            assert zone['area_m2'] >= 1000 and zone['confidence'] >= 0.5
        alert_id = data['alerts'][0]['id']
        assert client.put(route+'/alerts/'+alert_id+'/review',headers={'X-Test-Actor':'B'}).status_code==404
        assert client.put(route+'/alerts/fake/review',headers=headers).status_code==404
        for _ in range(2):
            assert client.put(route+'/alerts/'+alert_id+'/review',headers=headers).status_code==200
    with TestClient(app_for(Jobs(queue.root))) as client:
        reviewed=client.get(route+'/insights',headers=headers).json()['alerts']
        assert next(alert for alert in reviewed if alert['id']==alert_id)['reviewed_at']
        with queue.connect() as db:
            assert db.execute('SELECT COUNT(*) FROM alert_reviews WHERE job_id=? AND alert_id=?',(first,alert_id)).fetchone()[0]==1


def test_same_pair_comparison_is_not_time_evolution(completed_runs):
    queue,first,second=completed_runs
    with TestClient(app_for(queue)) as client:
        route=f'/api/v1/phase2/jobs/{first}/compare/{second}'
        assert client.get(route,headers={'X-Test-Actor':'B'}).status_code==404
        data=client.get(route,headers={'X-Test-Actor':'A'}).json()
        assert data['same_observations'] is True
        assert data['comparison_type']=='same_pair_processing_comparison'
        assert 0 <= data['footprint_iou'] <= 1
        assert data['left']['dates']==data['right']['dates']
        same=client.get(f'/api/v1/phase2/jobs/{first}/compare/{first}',headers={'X-Test-Actor':'A'}).json()
        assert same['area_difference_m2']==0 and same['footprint_iou']==1


def test_report_is_portable_and_evidence_is_verified(completed_runs):
    queue,first,_=completed_runs
    route=f'/api/v1/phase2/jobs/{first}'
    with TestClient(app_for(queue)) as client:
        headers={'X-Test-Actor':'A'}
        assert client.get(route+'/report',headers={'X-Test-Actor':'B'}).status_code==404
        report=client.get(route+'/report',headers=headers)
        assert report.status_code==200
        assert report.text.count('data:image/png;base64,')==3
        assert '<svg' in report.text and 'SHA-256' in report.text and 'GOFF' not in report.text
        assert '<script' not in report.text and 'attachment' in report.headers['content-disposition']
        assert 'lang="en"' in report.text
        assert not any('\u0600' <= c <= '\u06ff' for c in report.text)
        file=queue.runs/first/'M1/quality-report.json'
        original=file.read_bytes()
        try:
            file.write_text('{}')
            assert client.get(route+'/insights',headers=headers).status_code==409
            assert client.get(route+'/report',headers=headers).status_code==409
        finally:
            file.write_bytes(original)


def test_comparison_rejects_other_aoi(monkeypatch,completed_runs):
    from phase2 import experience
    queue,first,second=completed_runs
    original=experience.insights
    def changed(queue,row):
        result=original(queue,row)
        if row['id']==second:
            result['analysis']['bounds_wgs84']=[10,20,11,21]
        return result
    monkeypatch.setattr(experience,'insights',changed)
    with pytest.raises(ValueError,match='same AOI'):
        experience.comparison(queue,queue.get('A',first),queue.get('A',second))
