import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql
from sqlalchemy import select
from spectra.domain.schemas import (SarSceneCreate, PolygonGeometry, ArtifactCreate,
    ScenePairCreate, ChangeResultCreate, ImpactAssessmentCreate, ProcessingJobCreate)
from spectra.persistence.repositories import (SarSceneRepository, ArtifactRepository,
    postgis_multipolygon, ProcessingJobRepository)

SCENE_ID='S1A_IW_GRDH_1SDV_20261110T040000_20261110T040025_000001_ABCDE'
NOW=datetime(2026,11,10,4,tzinfo=timezone.utc)

def sample_scene(**changes):
    values=dict(provider='copernicus',collection='sentinel-1-grd',provider_item_id=SCENE_ID,
        product_type='GRD',acquisition_start=NOW,orbit_direction='ASCENDING',
        polarizations=['VV','VH'],incidence_angle_deg=34.3,
        stac_item={'type':'Feature','id':SCENE_ID,'properties':{},
                   'assets':{'measurement':{'href':'https://example.org/real-scene.tif'}}})
    values.update(changes)
    return values

def test_scene_contract_accepts_reference_without_download():
    scene=SarSceneCreate(**sample_scene())
    assert scene.polarizations==['VV','VH']

def test_scene_rejects_naive_time():
    with pytest.raises(ValidationError,match='timezone'):
        SarSceneCreate(**sample_scene(acquisition_start=datetime(2026,11,10)))

def test_scene_rejects_fake_stac_shape():
    with pytest.raises(ValidationError,match='STAC'):
        SarSceneCreate(**sample_scene(stac_item={'type':'Feature','id':'other','assets':{}}))

def test_scene_rejects_out_of_range_incidence():
    with pytest.raises(ValidationError): SarSceneCreate(**sample_scene(incidence_angle_deg=110))

def test_scene_rejects_duplicate_polarization_and_order():
    with pytest.raises(ValidationError,match='duplicate'):
        SarSceneCreate(**sample_scene(polarizations=['VV','VV']))
    with pytest.raises(ValidationError,match='before'):
        SarSceneCreate(**sample_scene(acquisition_end=NOW-timedelta(seconds=3)))

def test_polygon_closed_ring_and_bounds():
    polygon=PolygonGeometry(type='Polygon',coordinates=[[[0,0],[1,0],[1,1],[0,0]]])
    assert polygon.type=='Polygon'
    with pytest.raises(ValidationError): PolygonGeometry(type='Polygon',coordinates=[[[0,0],[1,0],[1,1],[2,1]]])
    with pytest.raises(ValidationError): PolygonGeometry(type='Polygon',coordinates=[[[200,0],[1,0],[1,1],[200,0]]])

def test_spatial_expression_is_parameterized():
    polygon=PolygonGeometry(type='Polygon',coordinates=[[[0,0],[1,0],[1,1],[0,0]]])
    stmt=select(postgis_multipolygon(polygon))
    compiled=stmt.compile(dialect=postgresql.dialect())
    assert 'ST_GeomFromGeoJSON' in str(compiled)
    assert 'ST_Multi' in str(compiled)
    assert 'coordinates' not in str(compiled)

def test_artifact_rejects_local_paths():
    base=dict(project_id=uuid4(),kind='raw_sar',storage_uri='file:///tmp/a.tif',media_type='image/tiff')
    with pytest.raises(ValidationError,match='storage_uri'): ArtifactCreate(**base)
    assert ArtifactCreate(**{**base,'storage_uri':'s3://spectra/real/sar.tif'}).kind=='raw_sar'

def test_pair_rejects_equal_scene_ids():
    id=uuid4()
    with pytest.raises(ValidationError): ScenePairCreate(project_id=uuid4(),aoi_id=uuid4(),before_scene_id=id,after_scene_id=id)

def test_change_confidence_and_impact_constraints():
    ids=[uuid4() for _ in range(3)]
    with pytest.raises(ValidationError): ChangeResultCreate(job_id=ids[0],scene_pair_id=ids[1],change_mask_artifact_id=ids[2],algorithm='logratio',algorithm_version='1',mean_confidence=1.2)
    with pytest.raises(ValidationError): ImpactAssessmentCreate(change_result_id=ids[0],assessment_type='flood',population_estimate=-1)

def test_job_type_and_repo_pagination_limits():
    job=ProcessingJobCreate(project_id=uuid4(),job_type='change_detection')
    assert job.job_type=='change_detection'
    with pytest.raises(ValidationError): ProcessingJobCreate(project_id=uuid4(),job_type='unsupported')
    repo=ArtifactRepository(MagicMock())
    with pytest.raises(ValueError): repo.list(limit=1000)

def test_scene_repository_constructs_model_and_flushes():
    session=MagicMock()
    repo=SarSceneRepository(session)
    repo.add(SarSceneCreate(**sample_scene()))
    session.add.assert_called_once()
    session.flush.assert_called_once()
    assert session.add.call_args.args[0].provider_item_id==SCENE_ID

def test_repo_select_by_provider_id_uses_bind_parameters():
    repo=SarSceneRepository(MagicMock())
    repo.by_provider_id('copernicus','sentinel-1-grd',SCENE_ID)
    stmt=repo.session.scalar.call_args.args[0]
    compiled=stmt.compile(dialect=postgresql.dialect())
    assert SCENE_ID not in str(compiled)

def test_job_idempotency_lookup_and_no_autocommit():
    session=MagicMock()
    repo=ProcessingJobRepository(session)
    repo.add(ProcessingJobCreate(project_id=uuid4(),job_type='preprocess',idempotency_key='job-real-001'))
    session.flush.assert_called_once()
    session.commit.assert_not_called()
    repo.by_idempotency_key('job-real-001')
    session.scalar.assert_called_once()
