"""QA-only checks, NOT the M1 gatekeeper or a substitute for SAR calibration.

Metadata is provided by real upstream acquisitions in production. These checks
never synthesize scenes or infer real Earth-observation findings.
"""
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")

class QualityError(ValueError):
    pass

def parse_iso_utc(value):
    if not isinstance(value, str):
        raise QualityError("acquired_at must be a string")
    try:
        value = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise QualityError("invalid acquisition timestamp") from exc
    if dt.tzinfo is None:
        raise QualityError("timezone must be specified")
    return dt.astimezone(timezone.utc)

def validate_pair(before, after, *, max_angle_diff=2.0):
    """Conservative QA policy for comparable scenes; team must approve M1 rules.

    PASSED indicates metadata compatibility under this policy, NOT that scenes
    are scientifically coregistered or calibrated. Incidence threshold is a
    project QA default, not a universal SAR scientific requirement.
    """
    for label, scene in [('before', before), ('after', after)]:
        for k in ['provider','provider_scene_id','acquired_at','orbit_direction','polarizations','incidence_angle_degrees']:
            if k not in scene: raise QualityError(f'{label}.{k} missing')
        if not scene['provider'] or not scene['provider_scene_id']:
            raise QualityError(f'{label} provider or scene identifier missing')
        if scene['orbit_direction'] not in {'ASCENDING','DESCENDING'}:
            raise QualityError(f'{label} invalid orbit direction')
        pol = scene['polarizations']
        if not isinstance(pol,list) or not pol or not all(p in {'VV','VH','HH','HV'} for p in pol):
            raise QualityError(f'{label} invalid polarizations')
        angle = scene['incidence_angle_degrees']
        if isinstance(angle,bool) or not isinstance(angle,(float,int)) or not (0 <= angle <= 90):
            raise QualityError(f'{label} invalid incidence angle')
    if (before['provider'],before['provider_scene_id']) == (after['provider'],after['provider_scene_id']):
        raise QualityError('same acquisition used twice')
    if parse_iso_utc(before['acquired_at']) >= parse_iso_utc(after['acquired_at']):
        raise QualityError('before must precede after')
    if before['orbit_direction'] != after['orbit_direction']:
        raise QualityError('orbit directions differ')
    if not set(before['polarizations']).intersection(after['polarizations']):
        raise QualityError('no common polarization')
    if abs(before['incidence_angle_degrees'] - after['incidence_angle_degrees']) > max_angle_diff:
        raise QualityError('incidence-angle delta exceeds project QA threshold')
    return True

def verify_file(path, expected_sha256, expected_bytes):
    """Streams file and compares against a recorded artifact manifest."""
    if not isinstance(expected_sha256,str) or not HEX64.fullmatch(expected_sha256):
        raise QualityError('invalid SHA-256 manifest')
    if isinstance(expected_bytes,bool) or not isinstance(expected_bytes,int) or expected_bytes < 0:
        raise QualityError('invalid expected byte size')
    p = Path(path)
    if not p.is_file(): raise QualityError('artifact file missing')
    digest = hashlib.sha256()
    total=0
    with p.open('rb') as handle:
        while True:
            chunk=handle.read(1024*1024)
            if not chunk: break
            total += len(chunk)
            digest.update(chunk)
    if total != expected_bytes: raise QualityError('artifact size mismatch')
    if digest.hexdigest() != expected_sha256: raise QualityError('artifact checksum mismatch')
    return True

def validate_lineage(artifacts):
    """Validate a finite DAG of artifact IDs; all parents must be present.

    Callers must provide manifest objects with asset_id and input_asset_ids.
    No provider truth or scientific validity is asserted.
    """
    if not isinstance(artifacts,list): raise QualityError('artifacts must be an array')
    by_id={}
    for art in artifacts:
        aid=art.get('asset_id')
        if not isinstance(aid,str) or not aid: raise QualityError('missing asset_id')
        if aid in by_id: raise QualityError('duplicate asset_id')
        inputs=art.get('input_asset_ids')
        if not isinstance(inputs,list) or any(not isinstance(i,str) or not i for i in inputs):
            raise QualityError('invalid input_asset_ids')
        by_id[aid]=inputs
    state={}
    def visit(node):
        if state.get(node)==1: raise QualityError('artifact lineage cycle')
        if state.get(node)==2: return
        state[node]=1
        for parent in by_id[node]:
            if parent not in by_id: raise QualityError('missing referenced parent artifact')
            visit(parent)
        state[node]=2
    for k in by_id: visit(k)
    return True
