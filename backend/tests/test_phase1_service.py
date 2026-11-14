from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from spectra.main import create_app
from spectra.persistence.database import database_status

def test_ready_requires_all_protocol_checks():
    with patch('spectra.api.health.dependency_probe',return_value='ready'):
        response=TestClient(create_app()).get('/health/ready')
        assert response.status_code==200
    with patch('spectra.api.health.dependency_probe',side_effect=lambda name,settings:'unavailable' if name=='database' else 'ready'):
        response=TestClient(create_app()).get('/health/ready')
        assert response.status_code==503

def test_obsolete_migration_is_rejected():
    import pytest
    engine=MagicMock()
    conn=engine.connect.return_value.__enter__.return_value
    conn.execute.side_effect=[MagicMock(scalar_one=lambda:1),MagicMock(scalar_one_or_none=lambda:'3.4.0'),
                              MagicMock(scalar_one_or_none=lambda:'0001_postgis_initial')]
    with pytest.raises(RuntimeError,match='revision'):database_status(engine)

def test_unified_handler_is_registered_and_rejects_unrelated_jobs():
    from spectra.workers.task_queue import HANDLERS
    from types import SimpleNamespace
    import pytest
    assert 'other' in HANDLERS
    with pytest.raises(ValueError,match='pipeline'):
        HANDLERS['other'](None,SimpleNamespace(input_parameters={}))

def test_nisar_gcov_channel_cannot_be_relabelled_as_rtc():
    from spectra.domain.schemas import SarSceneCreate
    import pytest
    from pydantic import ValidationError
    data=dict(provider='TEST_ONLY',collection='TEST_GCOV',provider_item_id='TEST_SCENE',product_type='GCOV',
              acquisition_start='2026-10-02T00:00:00Z',polarizations=['HHHH'],
              stac_item={'type':'Feature','id':'TEST_SCENE','properties':{},
                         'assets':{'test':{'href':'https://example.test/TEST_ONLY'}}})
    assert SarSceneCreate(**data).polarizations==['HHHH']
    with pytest.raises(ValidationError,match='GCOV'):
        SarSceneCreate(**{**data,'product_type':'RTC'})
