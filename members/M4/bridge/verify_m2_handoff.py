#!/usr/bin/env python3
"""Verify M2 T09 delivered file bytes against m3-delivery.json declared digests.
This proves consistency only, not authenticity or scientific correctness.
"""
import argparse, hashlib, json, re, sys
from pathlib import Path
SHA = re.compile(r'[0-9a-f]{64}\Z')

def verify(folder):
    root = Path(folder).resolve()
    report = {'status': 'FAIL', 'contract': 'SPECTRA-SAR-M2-T09/v1.0', 'files': [], 'limitations': []}
    docfile = root / 'm3-delivery.json'
    if not docfile.is_file() or docfile.is_symlink():
        report['reason'] = 'MISSING_M2_RUNTIME_DELIVERY_JSON'
        return report
    try:
        doc = json.loads(docfile.read_text(encoding='utf-8'))
    except (ValueError, OSError) as e:
        report['reason'] = f'INVALID_DELIVERY_JSON: {e}'
        return report
    mandatory = ['schema_version','producer','pair_id','polarization','delivery_status','scientific_approval','artifacts','limitations']
    missing = [x for x in mandatory if x not in doc]
    if missing or doc.get('schema_version') != '1.0' or doc.get('producer') != 'SPECTRA-SAR-M2-T09' or doc.get('delivery_status') != 'EXPLORATORY_NOT_SCIENTIFICALLY_VALIDATED' or doc.get('scientific_approval') is not False or doc.get('polarization') not in ('VV','VH','HHHH') or not isinstance(doc.get('artifacts'), dict) or not doc['artifacts']:
        report['reason'] = 'INVALID_M2_CONTRACT_OR_UNSUPPORTED_SCIENTIFIC_STATUS'
        report['missing_fields'] = missing
        return report
    report['pair_id'] = doc['pair_id']
    report['limitations'] = doc['limitations'] if isinstance(doc['limitations'], list) else []
    used = set()
    for key, obj in doc['artifacts'].items():
        if not isinstance(obj,dict):
            report['files'].append({'artifact':key,'status':'FAIL','reason':'INVALID_ARTIFACT_OBJECT'}); continue
        rel = obj.get('path'); expected = obj.get('sha256')
        if not isinstance(rel,str) or not rel or '\\' in rel or '\x00' in rel or rel.startswith('/') or any(x in ('.','..','') for x in rel.split('/')) or rel in used:
            report['files'].append({'artifact':key,'status':'FAIL','reason':'UNSAFE_OR_DUPLICATE_PATH'}); continue
        used.add(rel)
        if not isinstance(expected,str) or not SHA.fullmatch(expected):
            report['files'].append({'artifact':key,'status':'FAIL','reason':'INVALID_EXPECTED_SHA256'}); continue
        path = root / rel
        if not path.resolve().is_relative_to(root) or any(p.is_symlink() for p in [path,*list(path.parents)[:len(Path(rel).parts)]]) or not path.is_file():
            report['files'].append({'artifact':key,'status':'FAIL','reason':'MISSING_OR_UNSAFE_FILE','path':rel}); continue
        h = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
        actual = h.hexdigest()
        report['files'].append({'artifact':key,'path':rel,'status':'PASS' if actual==expected else 'FAIL','reason':'HASH_MATCH' if actual==expected else 'HASH_MISMATCH','sha256':actual})
    report['status'] = 'PASS' if report['files'] and all(f['status']=='PASS' for f in report['files']) else 'FAIL'
    report['scientific_approval'] = False
    report['authenticity_verified'] = False
    report['reason'] = 'BYTE_INTEGRITY_MATCHES_M2_DECLARATIONS' if report['status']=='PASS' else 'ARTIFACT_VERIFICATION_FAILED'
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser(description='M4 checks M2 T09 handoff SHA-256 artifacts')
    parser.add_argument('m2_output_folder',type=Path)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    result=verify(args.m2_output_folder)
    txt=json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(txt,encoding='utf-8')
    print(txt)
    sys.exit(0 if result['status']=='PASS' else 1)
