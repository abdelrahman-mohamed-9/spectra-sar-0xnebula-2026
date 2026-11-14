import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from spectra.main import create_app
from spectra.core.config import get_settings, Settings
from spectra.persistence.database import get_db
from spectra.api.v1 import resources

SECRET = 'a' * 48

@pytest.fixture
def app(monkeypatch):
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(internal_api_key=SECRET)
    # Security uses get_settings directly, so patch module function as well.
    monkeypatch.setattr('spectra.api.v1.security.get_settings', lambda: Settings(internal_api_key=SECRET))
    db=Mock()
    app.dependency_overrides[get_db] = lambda: db
    yield app,db


def test_missing_key_blocks_db(app):
    api, db = app
    r=TestClient(api).get('/api/v1/resources/scenes')
    assert r.status_code == 401
    db.assert_not_called()


def test_wrong_key_rejected(app):
    api,_=app
    assert TestClient(api).get('/api/v1/resources/scenes',headers={'X-API-Key':'bad'}).status_code==401


def test_missing_config_fails_closed(app,monkeypatch):
    api,_=app
    monkeypatch.setattr('spectra.api.v1.security.get_settings',lambda: Settings(internal_api_key=None))
    assert TestClient(api).get('/api/v1/resources/scenes',headers={'X-API-Key':SECRET}).status_code==503


def test_invalid_scene_returns_422(app):
    api,_=app
    r=TestClient(api).post('/api/v1/resources/scenes',headers={'X-API-Key':SECRET},json={'provider':'S1'})
    assert r.status_code==422


def test_valid_scene_contract_and_commit(app,monkeypatch):
    api,db=app
    new_id=uuid.uuid4()
    now=datetime.now(timezone.utc)
    output=SimpleNamespace(id=new_id,created_at=now,updated_at=now,provider='ESA',collection='sentinel-1-grd',provider_item_id='S1A_EXAMPLE',product_type='GRD',acquisition_start=now,orbit_direction='ASCENDING',polarizations=['VV'])
    created=Mock()
    created.add.return_value=output
    monkeypatch.setattr(resources.repo,'SarSceneRepository',lambda session:created)
    data={'provider':'ESA','collection':'sentinel-1-grd','provider_item_id':'S1A_EXAMPLE', 'product_type':'GRD','acquisition_start':now.isoformat(), 'orbit_direction':'ASCENDING','polarizations':['VV'], 'stac_item':{'type':'Feature','id':'S1A_EXAMPLE','properties':{},'assets':{'data':{'href':'https://example.org/scene.tif'}}}}
    r=TestClient(api).post('/api/v1/resources/scenes',headers={'X-API-Key':SECRET},json=data)
    assert r.status_code==201, r.text
    assert r.json()['id']==str(new_id)
    db.commit.assert_called_once()


def test_not_found(app,monkeypatch):
    api,_=app
    repository=Mock()
    repository.get.return_value=None
    monkeypatch.setattr(resources.repo,'SarSceneRepository',lambda session:repository)
    r=TestClient(api).get('/api/v1/resources/scenes/'+str(uuid.uuid4()),headers={'X-API-Key':SECRET})
    assert r.status_code==404


def test_pagination_validation(app):
    api,_=app
    for suffix in ['?limit=101','?offset=-1']:
        assert TestClient(api).get('/api/v1/resources/scenes'+suffix,headers={'X-API-Key':SECRET}).status_code==422


def test_db_conflict_rolls_back(app,monkeypatch):
    api, db=app
    repository=Mock()
    repository.add.side_effect=IntegrityError('insert', {}, Exception('duplicate'))
    monkeypatch.setattr(resources.repo,'ProcessingJobRepository',lambda session:repository)
    r=TestClient(api).post('/api/v1/resources/jobs',headers={'X-API-Key':SECRET},json={'project_id':str(uuid.uuid4()),'job_type':'preprocess'})
    assert r.status_code==409
    assert 'duplicate' not in r.text
    db.rollback.assert_called_once()


def test_openapi_has_all_resources():
    paths = create_app().openapi()['paths']
    for name in ['scenes','artifacts','scene-pairs','jobs','change-results','impact-assessments']:
        assert '/api/v1/resources/'+name in paths
