"""T08 contract tests. Integration with live Celery/Redis/PostGIS is separate."""
from unittest.mock import Mock
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from spectra.main import create_app
from spectra.core.config import Settings
from spectra.persistence.database import get_db
from spectra.api.v1 import jobs
from spectra.workers import job_manager

SECRET='x'*48

def test_claim_uses_atomic_compare_and_swap():
    db=Mock()
    db.execute.return_value.rowcount=1
    assert job_manager.claim_job(db,uuid4()) is True
    compiled=db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    assert 'status' in str(compiled) and 'queued' in compiled.params.values()
    db.commit.assert_called_once()

def test_claim_refuses_conflict():
    db=Mock()
    db.execute.return_value.rowcount=0
    assert job_manager.claim_job(db,uuid4()) is False

def test_finish_rejects_empty_failure_reason():
    with pytest.raises(ValueError):
        job_manager.finish_job(Mock(),uuid4(),success=False)

def test_finish_only_running_jobs():
    db=Mock()
    db.execute.return_value.rowcount=0
    assert job_manager.finish_job(db,uuid4(),success=True) is False
    statement=db.execute.call_args.args[0]
    assert 'running' in statement.compile(dialect=postgresql.dialect()).params.values()

def test_cancel_only_queued():
    db=Mock()
    db.execute.return_value.rowcount=1
    assert job_manager.cancel_job(db,uuid4())
    assert 'queued' in db.execute.call_args.args[0].compile(dialect=postgresql.dialect()).params.values()

def test_cannot_cancel_running_job():
    db=Mock()
    db.execute.return_value.rowcount=0
    assert not job_manager.cancel_job(db,uuid4())

def test_get_job_status_missing():
    db=Mock()
    db.scalar.return_value=None
    assert job_manager.get_job_status(db,uuid4()) is None

def test_get_job_status_existing():
    db=Mock()
    obj=Mock(id=uuid4(),project_id=uuid4(),job_type='denoise',status='queued',failure_reason=None,started_at=None,finished_at=None)
    db.scalar.return_value=obj
    assert job_manager.get_job_status(db,obj.id)['status']=='queued'

@pytest.fixture
def api(monkeypatch):
    app=create_app()
    monkeypatch.setattr('spectra.api.v1.security.get_settings',lambda:Settings(internal_api_key=SECRET))
    app.dependency_overrides[get_db]=lambda:Mock()
    yield TestClient(app)

def test_job_routes_require_auth(api):
    job_id=uuid4()
    for path in [f'/api/v1/processing-jobs/{job_id}',f'/api/v1/processing-jobs/{job_id}/dispatch',f'/api/v1/processing-jobs/{job_id}/cancel']:
        call=api.get if path.endswith(str(job_id)) else api.post
        assert call(path).status_code==401

def test_dispatch_accepted_only_after_broker_ack(api,monkeypatch):
    identifier=uuid4()
    monkeypatch.setattr(jobs,'get_job_status',lambda db,job_id:{'status':'queued'})
    # In real runtime, enqueue_job imports Celery; mocked transport here.
    import sys, types
    mod=types.ModuleType('spectra.workers.task_queue')
    mod.enqueue_job=lambda job_id:'spectra-'+str(job_id)
    monkeypatch.setitem(sys.modules,'spectra.workers.task_queue',mod)
    r=api.post(f'/api/v1/processing-jobs/{identifier}/dispatch',headers={'X-API-Key':SECRET})
    assert r.status_code==202
    assert r.json()['task_id']=='spectra-'+str(identifier)

def test_dispatch_rejected_if_already_running(api,monkeypatch):
    monkeypatch.setattr(jobs,'get_job_status',lambda db,job_id:{'status':'running'})
    r=api.post(f'/api/v1/processing-jobs/{uuid4()}/dispatch',headers={'X-API-Key':SECRET})
    assert r.status_code==409

def test_broker_outage_is_503(api,monkeypatch):
    monkeypatch.setattr(jobs,'get_job_status',lambda db,job_id:{'status':'queued'})
    import sys, types
    mod=types.ModuleType('spectra.workers.task_queue')
    def raise_error(job_id): raise ConnectionError('secret')
    mod.enqueue_job=raise_error
    monkeypatch.setitem(sys.modules,'spectra.workers.task_queue',mod)
    r=api.post(f'/api/v1/processing-jobs/{uuid4()}/dispatch',headers={'X-API-Key':SECRET})
    assert r.status_code==503 and 'secret' not in r.text

def test_cancel_conflict(api,monkeypatch):
    monkeypatch.setattr(jobs,'get_job_status',lambda db,job_id:{'status':'running'})
    monkeypatch.setattr(jobs,'cancel_job',lambda db,job_id:False)
    assert api.post(f'/api/v1/processing-jobs/{uuid4()}/cancel',headers={'X-API-Key':SECRET}).status_code==409

def test_openapi_exposes_job_routes():
    paths=create_app().openapi()['paths']
    assert '/api/v1/processing-jobs/{job_id}/dispatch' in paths
