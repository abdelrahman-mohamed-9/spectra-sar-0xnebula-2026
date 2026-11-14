"""Portable provenance manifest matching T03 artifacts/artifact_inputs/sar_scenes.

A manifest proves *consistency with its claimed digest*, not provider identity.
For production, capture trusted provider URLs, licensing, original provider
metadata, and store signed/append-only copies out-of-band.
"""
from __future__ import annotations
import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from integrity_validator import IntegrityError, HEX_SHA256, local_path_from_uri, verify_file

VERSION = '1.0.0'
ALLOWED_COMPONENTS = {'M1', 'M2', 'M3', 'M4', 'M5', 'M6'}

class ProvenanceError(ValueError):
    pass

def canonical_json(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')

def digest_manifest(payload: dict) -> str:
    """SHA256 over manifest fields excluding manifest_sha256 (no self-hash)."""
    clean = {k: v for k, v in payload.items() if k != 'manifest_sha256'}
    return hashlib.sha256(canonical_json(clean)).hexdigest()

def _uuid(value, name):
    try:
        uuid.UUID(value)
    except (TypeError, ValueError, AttributeError) as exc:
        raise ProvenanceError(f'{name} must be UUID') from exc

def _timestamp(value):
    if not isinstance(value, str):
        raise ProvenanceError('created_at must be ISO 8601 UTC')
    try:
        timestamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ProvenanceError('invalid created_at timestamp') from exc
    if timestamp.tzinfo is None or timestamp.utcoffset().total_seconds() != 0:
        raise ProvenanceError('created_at must include UTC offset')

def validate_manifest(doc: dict) -> bool:
    if not isinstance(doc, dict):
        raise ProvenanceError('manifest must be an object')
    if doc.get('schema_version') != VERSION:
        raise ProvenanceError('unsupported schema_version')
    _timestamp(doc.get('created_at'))
    scenes = doc.get('scenes')
    artifacts = doc.get('artifacts')
    if not isinstance(scenes, list) or not isinstance(artifacts, list):
        raise ProvenanceError('scenes and artifacts must be arrays')
    scene_ids = set()
    scene_provider_keys = set()
    for scene in scenes:
        if not isinstance(scene, dict): raise ProvenanceError('scene must be an object')
        _uuid(scene.get('id'), 'scene.id')
        if scene['id'] in scene_ids: raise ProvenanceError('duplicate scene id')
        scene_ids.add(scene['id'])
        for key in ('provider', 'provider_scene_id', 'source_license'):
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise ProvenanceError(f'scene.{key} required')
        provider_key = (scene['provider'], scene['provider_scene_id'])
        if provider_key in scene_provider_keys: raise ProvenanceError('duplicate provider scene key')
        scene_provider_keys.add(provider_key)
        url = scene.get('provider_record_url')
        if not isinstance(url, str) or urlparse(url).scheme != 'https' or not urlparse(url).netloc:
            raise ProvenanceError('provider_record_url must be HTTPS')
    parents = {}
    ids = set()
    for art in artifacts:
        if not isinstance(art, dict): raise ProvenanceError('artifact must be an object')
        aid = art.get('id')
        _uuid(aid, 'artifact.id')
        if aid in ids: raise ProvenanceError('duplicate artifact id')
        ids.add(aid)
        scene_id = art.get('scene_id')
        run_id = art.get('run_id')
        if scene_id is None and run_id is None:
            raise ProvenanceError('artifact must have scene_id or run_id (T03)')
        if scene_id is not None:
            _uuid(scene_id, 'artifact.scene_id')
            if scene_id not in scene_ids: raise ProvenanceError('unknown scene reference')
        if run_id is not None: _uuid(run_id, 'artifact.run_id')
        if not isinstance(art.get('sha256'), str) or not HEX_SHA256.fullmatch(art['sha256']):
            raise ProvenanceError('invalid artifact sha256')
        if type(art.get('bytes_size')) is not int or art['bytes_size'] < 0:
            raise ProvenanceError('invalid artifact bytes_size')
        for key in ('storage_uri', 'artifact_type'):
            if not isinstance(art.get(key), str) or not art[key]: raise ProvenanceError(f'artifact.{key} required')
        if not art['storage_uri'].startswith(('file://', 's3://')):
            raise ProvenanceError('artifact URI must match T03 file:// or s3://')
        component = art.get('producer_component')
        if component is not None and component not in ALLOWED_COMPONENTS:
            raise ProvenanceError('unrecognized producer component')
        inputs = art.get('input_artifact_ids')
        if not isinstance(inputs, list) or len(inputs) != len(set(inputs)):
            raise ProvenanceError('input_artifact_ids must be unique list')
        parents[aid] = inputs
    states = {}
    def visit(aid):
        state = states.get(aid, 0)
        if state == 1: raise ProvenanceError('lineage cycle')
        if state == 2: return
        if aid not in parents: raise ProvenanceError('missing input artifact reference')
        states[aid] = 1
        for parent in parents[aid]:
            if not isinstance(parent, str): raise ProvenanceError('invalid input artifact reference')
            visit(parent)
        states[aid] = 2
    for aid in parents: visit(aid)
    expected_digest = doc.get('manifest_sha256')
    if not isinstance(expected_digest, str) or not HEX_SHA256.fullmatch(expected_digest):
        raise ProvenanceError('manifest_sha256 required')
    if expected_digest != digest_manifest(doc):
        raise ProvenanceError('manifest digest mismatch')
    return True

def make_manifest(*, scenes: list, artifacts: list, created_at: str | None = None) -> dict:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    document = {'schema_version': VERSION, 'created_at': created_at, 'scenes': scenes, 'artifacts': artifacts}
    document['manifest_sha256'] = digest_manifest(document)
    validate_manifest(document)
    return document

def verify_local_artifacts(manifest: dict, *, root: str | Path) -> dict:
    validate_manifest(manifest)
    verified = 0
    skipped_remote = 0
    for artifact in manifest['artifacts']:
        uri = artifact['storage_uri']
        if uri.startswith('s3://'):
            skipped_remote += 1
            continue
        path = local_path_from_uri(uri, root=root)
        verify_file(path, artifact['sha256'], artifact['bytes_size'])
        verified += 1
    return {'verified_local': verified, 'not_verified_remote': skipped_remote,
            'all_artifacts_verified': skipped_remote == 0}
