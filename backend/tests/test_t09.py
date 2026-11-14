import hashlib
import io
from uuid import uuid4
from unittest.mock import Mock
import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from spectra.storage.file_validator import validate_name, validate_signature
from spectra.storage.storage_service import upload_artifact, parse_managed_uri, presigned_download
from spectra.core.config import Settings, get_settings
from spectra.main import app

class FakeS3:
    def __init__(self): self.payload=None; self.key=None; self.meta=None
    def upload_fileobj(self, stream, bucket, key, ExtraArgs):
        self.payload=stream.read(); self.key=key; self.meta=ExtraArgs
    def generate_presigned_url(self, method, Params, ExpiresIn):
        assert method=='get_object' and ExpiresIn==300
        return 'https://download.example.test/signed'

@pytest.mark.parametrize('name', ['../bad.tif','/bad.tif','evil.exe','.hidden.png','x\\bad.png','a'*181+'.png'])
def test_bad_filenames(name):
    with pytest.raises(HTTPException): validate_name(name)

@pytest.mark.parametrize('name,mime', [
    ('radar.tif','image/tiff'), ('radar.tiff','image/tiff'),
    ('map.geojson','application/geo+json'), ('mask.png','image/png'),
    ('results.json','application/json'),('bundle.zip','application/zip')])
def test_allowed_files(name,mime):
    assert validate_name(name)[1]==mime

@pytest.mark.parametrize('ext,data', [('.tif',b'xxxx'),('.png',b'notpng'),('.zip',b'badzip'),('.json',b'nope')])
def test_invalid_signatures(ext,data):
    with pytest.raises(HTTPException) as exc: validate_signature(ext,data)
    assert exc.value.status_code==415

@pytest.mark.parametrize('ext,data', [('.tif',b'II*\x00image'), ('.png',b'\x89PNG\r\n\x1a\npng'),('.zip',b'PK\x03\x04data'),('.geojson',b'  {"type":"Feature"}')])
def test_valid_signatures(ext,data):
    validate_signature(ext,data)


def test_hash_upload_and_object_key():
    payload=b'II*\x00'+b'X'*2048
    client=FakeS3()
    project=uuid4()
    stored=upload_artifact(UploadFile(filename='sentinel.tif',file=io.BytesIO(payload)), project,client=client)
    assert client.payload==payload
    assert stored.size_bytes==len(payload)
    assert stored.sha256==hashlib.sha256(payload).hexdigest()
    assert stored.uri.startswith(f's3://spectra-sar/projects/{project}/artifacts/')
    assert client.meta['Metadata']['sha256']==stored.sha256
    assert parse_managed_uri(stored.uri)==client.key
    assert presigned_download(stored.uri,client=client).startswith('https://')


def test_empty_and_invalid_content_not_uploaded():
    for name,payload,expected in [('x.png',b'',422),('x.png',b'NOT A PNG',415)]:
        client=FakeS3()
        with pytest.raises(HTTPException) as exc:
            upload_artifact(UploadFile(filename=name,file=io.BytesIO(payload)), uuid4(),client=client)
        assert exc.value.status_code==expected
        assert client.payload is None


def test_limit_is_streamed(monkeypatch):
    import spectra.storage.storage_service as storage
    settings=Settings(max_upload_bytes=4)
    monkeypatch.setattr(storage,'get_settings',lambda:settings)
    client=FakeS3()
    with pytest.raises(HTTPException) as exc:
        upload_artifact(UploadFile(filename='x.tif',file=io.BytesIO(b'II*\x00OVER LIMIT')),uuid4(),client=client)
    assert exc.value.status_code==413
    assert client.payload is None


def test_private_uri_restrictions():
    for uri in ['https://evil.org/img.tif','s3://other/abc','s3://spectra-sar/../secrets','s3://spectra-sar/other/test']:
        with pytest.raises(HTTPException): parse_managed_uri(uri)


def test_routes_fail_closed_without_service_key(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv('INTERNAL_API_KEY',raising=False)
    with TestClient(app) as client:
        r=client.get(f'/api/v1/storage/artifacts/{uuid4()}/download-url')
        assert r.status_code in {401,503}
        r=client.post('/api/v1/storage/artifacts/upload')
        assert r.status_code in {401,503}
    get_settings.cache_clear()


def test_route_auth_and_not_found(monkeypatch):
    from spectra.persistence.database import get_db
    monkeypatch.setenv('INTERNAL_API_KEY','a'*36)
    get_settings.cache_clear()
    class Repo:
        def get(self, key): return None
    # Mock query session; repository object uses session.get()
    class Db:
        def get(self, model, id): return None
    app.dependency_overrides[get_db]=lambda: Db()
    try:
        with TestClient(app) as client:
            url=f'/api/v1/storage/artifacts/{uuid4()}/download-url'
            assert client.get(url).status_code==401
            assert client.get(url, headers={'X-API-Key':'a'*36}).status_code==404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
