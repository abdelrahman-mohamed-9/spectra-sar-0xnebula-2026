"""SPECTRA-SAR M4/T04: immutable-by-default local provenance evidence records.

JSON Schema validates shape. This module also validates cross-references and
artifact content against disk. Evidence records are NOT signed/authenticated.
Keep records and trusted SHA256 baselines in a separately protected store.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from integrity import IntegrityError, _safe_relative_path, hash_file

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    Draft202012Validator = None
    FormatChecker = None

SCHEMA_PATH = Path(__file__).with_name('evidence.schema.json')


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def schema_validate(record):
    if Draft202012Validator is None:
        raise IntegrityError('DEPENDENCY_MISSING: pip install jsonschema>=4.18')
    schema = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(record), key=lambda x: str(x.path))
    if errors:
        raise IntegrityError('SCHEMA_VALIDATION_FAILED: ' + '; '.join(e.message for e in errors[:5]))
    ids = [a['artifact_id'] for a in record['artifacts']]
    if len(set(ids)) != len(ids):
        raise IntegrityError('DUPLICATE_ARTIFACT_IDS')
    claim_ids = [c['claim_id'] for c in record['claims']]
    if len(set(claim_ids)) != len(claim_ids):
        raise IntegrityError('DUPLICATE_CLAIM_IDS')
    artifact_ids = set(ids)
    for claim in record['claims']:
        if not set(claim['supporting_artifact_ids']).issubset(artifact_ids):
            raise IntegrityError('CLAIM_REFERENCES_UNKNOWN_ARTIFACT')
    if record['integrity_status'] == 'VERIFIED_AGAINST_BASELINE' and not record.get('baseline_reference'):
        raise IntegrityError('VERIFIED_STATUS_REQUIRES_BASELINE_REFERENCE')
    return True


def build_record(*, root, files, scenes, producer, algorithm, parameters=None, input_artifact_ids=None, claims=None, limitations=None):
    root = Path(root)
    if not files or len(files) != len(set(files)):
        raise IntegrityError('MISSING_OR_DUPLICATE_FILES')
    artifacts = []
    for i, rel in enumerate(sorted(files), start=1):
        f = _safe_relative_path(rel, root)
        size_before = f.stat().st_size
        stat_before = f.stat()
        digest = hash_file(f)
        stat_after = f.stat()
        if (stat_before.st_ino, stat_before.st_size, stat_before.st_mtime_ns) != (stat_after.st_ino, stat_after.st_size, stat_after.st_mtime_ns):
            raise IntegrityError('FILE_CHANGED_DURING_HASH: ' + rel)
        import mimetypes
        media = mimetypes.guess_type(rel)[0] or 'application/octet-stream'
        artifacts.append({'artifact_id':f'asset-{i:03d}','relative_path':rel,'sha256':digest,'size_bytes':size_before,'media_type':media})
    record = {'schema_version':'1.0','evidence_id':'ev-'+str(uuid4()),'created_at_utc':utc_now(),
              'producer':producer, 'source_scenes':scenes,
              'processing':{'algorithm':algorithm,'parameters':parameters or {},'input_artifact_ids':input_artifact_ids or []},
              'artifacts':artifacts,'claims':claims or [],'integrity_status':'UNVERIFIED','limitations':limitations or []}
    schema_validate(record)
    return record


def verify_record(record, root):
    schema_validate(record)
    root = Path(root)
    checks = []
    for a in record['artifacts']:
        rel = a['relative_path']
        try:
            p = _safe_relative_path(rel,root)
            observed = hash_file(p)
            ok = (observed == a['sha256'] and p.stat().st_size == a['size_bytes'])
            checks.append({'path':rel,'status':'PASS' if ok else 'FAIL','reason':'MATCH' if ok else 'CONTENT_MISMATCH'})
        except (OSError, IntegrityError) as exc:
            checks.append({'path':rel,'status':'FAIL','reason':str(exc)})
    return {'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,
            'warning':'Matching self-supplied hashes do not authenticate origin. Compare the evidence record against a separately trusted copy or signature.'}


def write_record(record, output):
    schema_validate(record)
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    # exclusive create prevents accidental baseline replacement
    try:
        with output.open('x',encoding='utf-8') as f:
            json.dump(record,f,indent=2,sort_keys=True)
            f.write('\n')
    except FileExistsError as exc:
        raise IntegrityError('EVIDENCE_ALREADY_EXISTS') from exc


def load_json(path):
    def reject_duplicates(pairs):
        out={}
        for k,v in pairs:
            if k in out: raise IntegrityError('DUPLICATE_JSON_KEY: '+k)
            out[k]=v
        return out
    return json.loads(Path(path).read_text(encoding='utf-8'),object_pairs_hook=reject_duplicates)


def main(argv=None):
    parser=argparse.ArgumentParser(description='SPECTRA-SAR evidence/provenance')
    sub=parser.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build',help='Build provenance record from real file bytes and metadata JSON')
    b.add_argument('--root',type=Path,required=True)
    b.add_argument('--metadata',type=Path,required=True,help='JSON with source_scenes, producer, algorithm, optional parameters/claims')
    b.add_argument('--output',type=Path,required=True)
    b.add_argument('files',nargs='+',help='Paths relative to root')
    v=sub.add_parser('verify',help='Check recorded artifact hashes against actual files')
    v.add_argument('--root',type=Path,required=True)
    v.add_argument('--record',type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.action=='build':
            m=load_json(args.metadata)
            record=build_record(root=args.root,files=args.files,scenes=m['source_scenes'],producer=m['producer'],algorithm=m['algorithm'],parameters=m.get('parameters'),input_artifact_ids=m.get('input_artifact_ids'),claims=m.get('claims'),limitations=m.get('limitations'))
            write_record(record,args.output)
            result={'status':'CREATED','output':str(args.output),'evidence_id':record['evidence_id'],'artifact_count':len(record['artifacts'])}
        else:
            result=verify_record(load_json(args.record),args.root)
        print(json.dumps(result,indent=2))
        return 1 if result['status']=='FAIL' else 0
    except (IntegrityError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status':'FAIL','error':str(exc)}),file=sys.stderr)
        return 2

if __name__=='__main__':
    sys.exit(main())
