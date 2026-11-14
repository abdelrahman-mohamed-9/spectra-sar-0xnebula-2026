"""S3-compatible upload manager. Content is hashed and bounded before transfer.

Storage is private; only server-generated opaque object keys can be used.
"""
from __future__ import annotations
import hashlib
import tempfile
from dataclasses import dataclass
from uuid import UUID, uuid4
from fastapi import HTTPException, UploadFile
from botocore.exceptions import BotoCoreError, ClientError
from spectra.core.config import get_settings
from spectra.storage.file_validator import validate_name, validate_signature

CHUNK = 1024 * 1024

@dataclass(frozen=True)
class StoredObject:
    key: str
    uri: str
    media_type: str
    size_bytes: int
    sha256: str


def get_s3_client():
    import boto3
    st = get_settings()
    if not all([st.s3_endpoint_url, st.s3_access_key, st.s3_secret_key]):
        raise HTTPException(503, 'Object storage is not configured')
    return boto3.client('s3', endpoint_url=st.s3_endpoint_url,
        aws_access_key_id=st.s3_access_key, aws_secret_access_key=st.s3_secret_key,
        region_name=st.s3_region)


def make_key(project_id: UUID, ext: str) -> str:
    return f'projects/{project_id}/artifacts/{uuid4().hex}{ext}'


def upload_artifact(file: UploadFile, project_id: UUID, *, client=None) -> StoredObject:
    st = get_settings()
    ext, media_type = validate_name(file.filename)
    if client is None:
        client = get_s3_client()
    total = 0
    digest = hashlib.sha256()
    key = make_key(project_id, ext)
    with tempfile.TemporaryFile(mode='w+b') as tmp:
        first = file.file.read(CHUNK)
        if not first:
            raise HTTPException(422, 'Empty file')
        validate_signature(ext, first)
        for chunk in [first]:
            total += len(chunk)
            if total > st.max_upload_bytes:
                raise HTTPException(413, 'File exceeds upload limit')
            digest.update(chunk)
            tmp.write(chunk)
        while True:
            chunk = file.file.read(CHUNK)
            if not chunk: break
            total += len(chunk)
            if total > st.max_upload_bytes:
                raise HTTPException(413, 'File exceeds upload limit')
            digest.update(chunk)
            tmp.write(chunk)
        tmp.seek(0)
        try:
            client.upload_fileobj(tmp, st.s3_bucket, key, ExtraArgs={
                'ContentType': media_type,
                'Metadata': {'sha256': digest.hexdigest()},
            })
        except (BotoCoreError, ClientError, OSError) as exc:
            raise HTTPException(503, 'Object storage unavailable') from exc
    return StoredObject(key, f's3://{st.s3_bucket}/{key}', media_type, total, digest.hexdigest())


def parse_managed_uri(uri: str) -> str:
    st=get_settings()
    prefix=f's3://{st.s3_bucket}/'
    if not uri.startswith(prefix):
        raise HTTPException(422, 'Not a managed storage URI')
    key=uri[len(prefix):]
    if not key.startswith('projects/') or '..' in key or len(key)>500:
        raise HTTPException(422, 'Invalid object key')
    return key


def delete_managed(uri: str, *, client=None) -> None:
    key=parse_managed_uri(uri)
    if client is None: client=get_s3_client()
    client.delete_object(Bucket=get_settings().s3_bucket, Key=key)


def presigned_download(uri: str, *, client=None) -> str:
    key=parse_managed_uri(uri)
    if client is None: client=get_s3_client()
    try:
        return client.generate_presigned_url('get_object', Params={
            'Bucket': get_settings().s3_bucket, 'Key': key}, ExpiresIn=300)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(503, 'Object storage unavailable') from exc
