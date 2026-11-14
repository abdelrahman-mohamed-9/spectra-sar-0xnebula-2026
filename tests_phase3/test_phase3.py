import hashlib
import json

import numpy as np
import pytest
from fastapi.testclient import TestClient

from phase2.jobs import Jobs, work_one
from phase2.phase3 import quality_confidence, risk_score
from tests_phase2.test_system import app_for


def test_quality_screen_excludes_boundaries_and_small_components():
    labels = np.zeros((30, 30), dtype='uint8')
    labels[0:6, 0:6] = 1
    labels[10:15, 10:15] = 2
    labels[25, 25] = 2
    labels[20, 20] = 255
    stability = np.ones(labels.shape)
    stability[10:15, 10:15] = 2/3
    retained, confidence, _ = quality_confidence(labels, stability, {})
    assert retained[0, 0] == 0
    assert retained[2, 2] == 1
    assert retained[12, 12] == 0
    assert retained[25, 25] == 0
    assert retained[20, 20] == 255 and np.isnan(confidence[20, 20])
    assert confidence[2, 2] == pytest.approx(0.35)


def test_risk_missing_is_not_zero_and_saturates():
    assert risk_score(0.8, None, 0, 0, True) is None
    assert risk_score(0.8, 0, 0, 0, False) is None
    assert risk_score(0.8, 0, 0, 0, True) == 0
    assert risk_score(0.8, 1000, 1000, 10000, True) == 80


def test_real_pipeline_evidence_ownership_restart_and_tampering(tmp_path):
    queue = Jobs(tmp_path/'state')
    job = queue.submit('A', 'nisar-oct2026')
    work_one(queue)
    queue = Jobs(queue.root)
    route = f'/api/v1/phase2/jobs/{job}/phase3'
    with TestClient(app_for(queue)) as client:
        assert client.get(route).status_code == 401
        assert client.get(route, headers={'X-Test-Actor':'B'}).status_code == 404
        response = client.get(route, headers={'X-Test-Actor':'A'})
        assert response.status_code == 200, queue.get('A', job)
        data = response.json()
        assert data['analysis']['input_candidate_pixels'] == 566
        assert 0 < data['analysis']['retained_pixels'] <= 566
        assert all(zone['properties']['risk_score'] is None for zone in data['zones']['features'])
        previous = '0'*64
        for entry in data['evidence']['records']:
            digest = entry.pop('sha256')
            assert entry['previous_sha256'] == previous
            assert hashlib.sha256(json.dumps(entry, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == digest
            previous = digest
        assert previous == data['evidence']['head_sha256']
        (queue.runs/job/'Phase3/analysis.json').write_text('{}')
        assert client.get(route, headers={'X-Test-Actor':'A'}).status_code == 409


def test_worker_lock_is_exclusive(tmp_path):
    queue = Jobs(tmp_path/'state')
    with queue.worker_lock():
        with pytest.raises(OSError):
            with Jobs(queue.root).worker_lock():
                pass


def test_spatial_risk_with_complete_fixture_and_missing_coverage(tmp_path):
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.warp import transform_geom
    from shapely.geometry import box, mapping, LineString
    from phase2.phase3 import assess
    from phase2.run_m2 import write_json, write_raster

    for name in ('complete', 'incomplete'):
        root = tmp_path/name
        (root/'M2').mkdir(parents=True)
        geo = root/'sources/geography'
        geo.mkdir(parents=True)
        grid = dict(width=20, height=20, crs=rasterio.crs.CRS.from_epsg(32605), transform=from_origin(400000, 7000000, 10, 10))
        labels = np.zeros((20, 20), dtype='uint8')
        labels[5:15, 5:15] = 1
        write_raster(root/'M2/adaptive_change_mask.tif', labels, grid, nodata=255, quantity='TEST FIXTURE')
        write_raster(root/'M2/confidence_stability.tif', np.ones((20, 20)), grid, nodata=-9999, quantity='TEST FIXTURE')
        write_raster(geo/'counts.tif', np.ones((20, 20)), grid, nodata=-9999, quantity='TEST FIXTURE')
        write_json(geo/'geography-source.json', {'population_raster': {'file':'counts.tif','source':'TEST FIXTURE','units':'people_per_cell'}, 'roads':{'coverage_verified': name=='complete'}, 'buildings':{'coverage_verified':True}})
        building = transform_geom(grid['crs'], 'EPSG:4326', mapping(box(400070, 6999890, 400090, 6999910)))
        road = transform_geom(grid['crs'], 'EPSG:4326', mapping(LineString([(400060, 6999900),(400140, 6999900)])))
        for filename, geometry in [('buildings.geojson',building),('roads-2.geojson',road),('roads-6.geojson',None),('roads-8.geojson',None)]:
            write_json(geo/filename, {'type':'FeatureCollection','features':[{'type':'Feature','geometry':geometry,'properties':{}}] if geometry else []})
        assess(root, {'holdout_p90_residual_after_px':0, 'processing_identifiers':{'before':'same','after':'same'}}, 'conservative')
        zones = json.loads((root/'Phase3/risk-zones.geojson').read_text())['features']
        assert len(zones) == 1
        props = zones[0]['properties']
        assert props['population']['estimated_residents'] == pytest.approx(100, abs=0.1)
        assert props['mapped_buildings'] == 1
        assert props['mapped_roads_m'] == pytest.approx(80, abs=0.1)
        if name == 'complete':
            assert props['risk_score'] == pytest.approx(39.33, abs=0.1)
            assert props['risk_level'] == 'medium'
        else:
            assert props['risk_score'] is None


def test_bundled_population_uses_unchanged_sar_and_verified_source(tmp_path):
    from phase2.datasets import PACKAGE, listing, resolve, register
    from phase2.integrity import inventory, verify_inventory

    dataset = resolve(tmp_path, 'nisar-oct2026-ghsl2025')
    names = [path.name for path in (PACKAGE/'data/nisar').iterdir() if path.is_file()]
    assert inventory(PACKAGE/'data/nisar', names) == inventory(dataset/'data/nisar', names)
    pins = json.loads((dataset/'catalog.json').read_text())['nisar-oct2026-ghsl2025']
    verify_inventory(dataset/'data', pins)
    assert any(row['id'] == 'nisar-oct2026-ghsl2025' for row in listing(tmp_path))
    with pytest.raises(ValueError, match='immutable'):
        register(tmp_path, 'nisar-oct2026-ghsl2025', PACKAGE/'data/nisar')


def test_population_dataset_runs_through_api(tmp_path):
    queue = Jobs(tmp_path/'state')
    with TestClient(app_for(queue)) as client:
        headers = {'X-Test-Actor':'A'}
        response = client.post('/api/v1/phase2/jobs',json={'dataset':'nisar-oct2026-ghsl2025'},headers=headers)
        assert response.status_code == 202
        job = response.json()['id']
        work_one(queue)
        route = f'/api/v1/phase2/jobs/{job}'
        data = client.get(route,headers=headers).json()
        assert data['status'] == 'COMPLETED_EXPLORATORY'
        assert data['result']['m3']['estimated_residents_exposed'] == 0
        assert 'population_exposure' not in data['result']['m3']['data_gaps']
        advanced = client.get(route+'/phase3',headers=headers).json()
        assert advanced['analysis']['population_source']['year'] == 2025
        assert advanced['analysis']['population_source']['units'] == 'people_per_cell'
        assert all(zone['properties']['population']['coverage_fraction'] >= 0.999 for zone in advanced['zones']['features'])
        assert all(zone['properties']['risk_score'] is None for zone in advanced['zones']['features'])
