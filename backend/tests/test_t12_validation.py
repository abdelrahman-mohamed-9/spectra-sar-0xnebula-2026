"""T12 regression, contract, security-boundary, and operability checks."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from spectra.main import create_app
from spectra.core.config import get_settings

ROOT = Path(__file__).resolve().parents[1]
app = create_app()
from spectra.persistence.database import get_db
def dummy_db():
    yield object()
app.dependency_overrides[get_db] = dummy_db
client = TestClient(app)

def test_liveness_is_public_and_valid():
    response = client.get('/health/live')
    assert response.status_code == 200
    assert response.json()['status'] == 'alive'

def test_readiness_does_not_falsely_claim_production_ready():
    response = client.get('/health/ready')
    assert response.status_code == 503
    assert response.json()['status'] == 'integration_not_verified'

def test_openapi_has_no_duplicate_operation_ids():
    ops = [spec.get('operationId') for item in create_app().openapi()['paths'].values()
           for method, spec in item.items() if method in ('get','post','put','patch','delete')]
    assert len(ops) == len(set(ops))

def test_protected_routes_reject_anonymous_requests():
    for path in ('/api/v1/resources/scenes', '/api/v1/geospatial/scenes/within',
                 '/api/v1/storage/artifacts/00000000-0000-0000-0000-000000000000/download-url'):
        result = client.get(path)
        assert result.status_code in (401, 403, 503), (path, result.status_code)

def test_user_profile_rejects_anonymous_request():
    assert client.get('/api/v1/auth/me').status_code == 401

def test_project_access_requires_jwt():
    path = '/api/v1/auth/projects/00000000-0000-0000-0000-000000000000/access'
    assert client.get(path).status_code == 401

def test_request_id_is_returned_and_sanitized():
    r = client.get('/health/live',headers={'X-Request-ID':'trace-123'})
    assert r.headers['X-Request-ID'] == 'trace-123'
    r = client.get('/health/live',headers={'X-Request-ID':'bad value/../'})
    assert r.headers['X-Request-ID'] != 'bad value/../'

def test_generated_contracts_exist_and_are_parseable():
    for path in (ROOT/'contracts'/'generated').glob('*.json'):
        assert isinstance(json.loads(path.read_text(encoding='utf8')), dict)
    assert len(list((ROOT/'contracts'/'generated').glob('*.schema.json'))) == 6

def test_compose_declares_required_services():
    content=(ROOT/'deploy'/'compose.yaml').read_text(encoding='utf8')
    for key in ('  db:', '  redis:', '  minio:', '  migrate:', '  api:', '  worker:'):
        assert key in content

def test_deployment_secrets_are_required_not_hardcoded():
    content=(ROOT/'deploy'/'compose.yaml').read_text(encoding='utf8')
    for key in ('INTERNAL_API_KEY', 'JWT_SECRET', 'POSTGRES_PASSWORD', 'MINIO_ROOT_PASSWORD'):
        assert '${'+key+':?' in content

def test_schema_migrations_present_and_ordered():
    versions=ROOT/'alembic'/'versions'
    a=(versions/'0001_postgis_initial.py').read_text()
    b=(versions/'0002_auth_rbac.py').read_text()
    assert 'revision' in a and 'revision' in b and 'down_revision' in b

def test_settings_limit_uploaded_object_size():
    from spectra.core.config import Settings
    assert Settings(max_upload_bytes=512*1024*1024).max_upload_bytes == 536870912
