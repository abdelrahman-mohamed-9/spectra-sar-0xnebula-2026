import math
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from spectra.main import create_app
from spectra.core.config import Settings
from spectra.persistence.database import get_db
from spectra.api.v1 import geospatial
from spectra.geospatial.geojson_converter import InvalidGeoJSON, parse_polygon_geometry, normalize_multipolygon, feature_from_postgis
from spectra.geospatial.geo_service import query_scenes_in_bbox, query_impacts_in_bbox, scene_footprint, impact_footprint

POLY = {'type':'Polygon','coordinates':[[[31,30],[32,30],[32,31],[31,31],[31,30]]]}

@pytest.mark.parametrize('geometry',[
    {'type':'Point','coordinates':[31,30]},
    {'type':'Polygon','coordinates':[[[31,30],[32,30],[32,31],[31,31]]]},
    {'type':'Polygon','coordinates':[[[31,30],[32,31],[31,31],[32,30],[31,30]]]},
    {'type':'Polygon','coordinates':[[[31,30],[181,30],[32,31],[31,30]]]},
    {'type':'Polygon','coordinates':[[[31,30],[32,float('nan')],[32,31],[31,30]]]},
    {'type':'Polygon','coordinates':[[[31,30,12],[32,30],[32,31],[31,30,12]]]},
    {'type':'Polygon','coordinates':[]},
    {'type':'Polygon','coordinates':[[[31,30],[31,30],[31,30],[31,30]]]},
    {'type':'Polygon','coordinates':[[[31,30],[32,30],[32,31],[31,30]]], 'crs':'EPSG:3857'},
])
def test_invalid_geometry_rejected(geometry):
    with pytest.raises(InvalidGeoJSON): parse_polygon_geometry(geometry)


def test_polygon_normalization_and_feature():
    normalized = normalize_multipolygon(POLY)
    assert normalized['type']=='MultiPolygon'
    assert normalized['coordinates'][0][0][0]==[31,30]
    assert feature_from_postgis(normalized,feature_id='real-item')['geometry']==normalized


def test_valid_multipolygon():
    multi=normalize_multipolygon(POLY)
    assert parse_polygon_geometry(multi).is_valid


@pytest.mark.parametrize('bbox',[
    '31,30,32', 'nan,30,32,31','31,30,inf,31',
    '32,30,31,31','31,31,32,30','-181,30,32,31',
    '31,30,32,91','179,-10,-179,10', 'hello'
])
def test_bbox_invalid(bbox):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        geospatial.validate_bbox(bbox)
    assert exc.value.status_code==422


def test_bbox_valid():
    assert geospatial.validate_bbox('30,29,33,32')==(30,29,33,32)


def test_scenes_sql_uses_spatial_intersection_and_pagination():
    db=Mock()
    db.execute.return_value=[]
    result=query_scenes_in_bbox(db,(30,29,33,32),limit=10,offset=3)
    assert result=={'type':'FeatureCollection','features':[]}
    sql=str(db.execute.call_args.args[0].compile(dialect=postgresql.dialect()))
    assert 'ST_Intersects' in sql and 'ST_MakeEnvelope' in sql
    assert 'sar_scenes.footprint IS NOT NULL' in sql
    assert 'LIMIT' in sql and 'OFFSET' in sql


def test_impacts_sql_restricted_to_project():
    db=Mock()
    db.execute.return_value=[]
    project_id=uuid4()
    result=query_impacts_in_bbox(db,(30,29,33,32),project_id=project_id)
    assert result['features']==[]
    stmt=db.execute.call_args.args[0]
    compiled=stmt.compile(dialect=postgresql.dialect())
    assert 'ST_Intersects' in str(compiled)
    assert 'scene_pairs.project_id' in str(compiled)
    assert project_id in compiled.params.values()


def test_footprint_feature_reads_real_db_geometry():
    sid=uuid4()
    db=Mock()
    db.execute.return_value.one_or_none.return_value=SimpleNamespace(id=sid,geom='{"type":"Polygon","coordinates":[[[31,30],[32,30],[32,31],[31,31],[31,30]]]}')
    feature=scene_footprint(db,sid)
    assert feature['id']==str(sid) and feature['geometry']['type']=='MultiPolygon'


def test_impact_footprint_includes_risk():
    sid=uuid4()
    db=Mock()
    db.execute.return_value.one_or_none.return_value=SimpleNamespace(id=sid,risk_level='high',geom=POLY)
    result=impact_footprint(db,sid)
    assert result['properties']['risk_level']=='high'


@pytest.fixture
def client(monkeypatch):
    app=create_app()
    monkeypatch.setattr('spectra.api.v1.security.get_settings',lambda:Settings(internal_api_key='x'*48))
    db=Mock()
    app.dependency_overrides[get_db]=lambda:db
    return TestClient(app),db


def test_geo_endpoints_require_api_key(client):
    http,db=client
    assert http.get('/api/v1/geospatial/scenes/within?bbox=30,29,33,32').status_code==401
    db.assert_not_called()


def test_geo_bbox_validation_http(client):
    http,_=client
    r=http.get('/api/v1/geospatial/scenes/within?bbox=100,40,10,50',headers={'X-API-Key':'x'*48})
    assert r.status_code==422


def test_geo_http_feature_collection(client,monkeypatch):
    http,db=client
    monkeypatch.setattr(geospatial.geo_service,'query_scenes_in_bbox', lambda session,bbox,**kwargs: {'type':'FeatureCollection','features':[]})
    r=http.get('/api/v1/geospatial/scenes/within?bbox=30,29,33,32',headers={'X-API-Key':'x'*48})
    assert r.status_code==200 and r.json()['type']=='FeatureCollection'


def test_geo_http_not_found(client,monkeypatch):
    http,_=client
    monkeypatch.setattr(geospatial.geo_service,'scene_footprint',lambda db,sid:None)
    r=http.get('/api/v1/geospatial/scenes/'+str(uuid4())+'/footprint',headers={'X-API-Key':'x'*48})
    assert r.status_code==404


def test_geo_openapi_routes():
    paths=create_app().openapi()['paths']
    assert '/api/v1/geospatial/scenes/within' in paths
    assert '/api/v1/geospatial/impacts/within' in paths
