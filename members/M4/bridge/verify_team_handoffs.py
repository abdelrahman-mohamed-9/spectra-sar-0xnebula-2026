#!/usr/bin/env python3
"""Universal SPECTRA-SAR M4 team handoff verifier.

Verifies locally supplied artifact bytes; does not authenticate their source.
Never fabricates telemetry, imagery, or scientific claims.
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys
from datetime import datetime, timezone
from pathlib import Path

MEMBERS=('M1','M2','M3','M5','M6')
HEX=re.compile(r'^[0-9a-f]{64}$')
MAX_MANIFEST=2*1024*1024

def parse_json(path):
    if path.stat().st_size > MAX_MANIFEST: raise ValueError('manifest too large')
    def unique(pairs):
        r={}
        for k,v in pairs:
            if k in r: raise ValueError('duplicate JSON key: '+k)
            r[k]=v
        return r
    return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=unique)

def digest_file(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def resolve_artifact(root,rel):
    if not isinstance(rel,str) or not rel or '\\' in rel or '\x00' in rel or rel.startswith('/') or any(x in ('','.','..') for x in rel.split('/')):
        raise ValueError('unsafe relative file path')
    p=root.joinpath(*rel.split('/'))
    if p.resolve(strict=False).is_relative_to(root.resolve(strict=True)) is False:
        raise ValueError('file outside handoff root')
    if any(x.is_symlink() for x in [p,*list(p.parents)[:len(Path(rel).parts)] ]):
        raise ValueError('symlink in artifact path')
    if not p.is_file(): raise FileNotFoundError(rel)
    return p

def verify_member(root,member):
    root=root.resolve()
    report={'member':member,'status':'BLOCKED','artifacts':[], 'authenticity_verified':False,'scientific_validation':'NOT_PERFORMED'}
    manifest=root/'handoff.json'
    if not manifest.is_file() or manifest.is_symlink():
        report['reason']='MISSING_HANDOFF_JSON';return report
    try:
        doc=parse_json(manifest)
        if not isinstance(doc,dict) or doc.get('schema_version')!='1.0' or doc.get('member')!=member:raise ValueError('wrong schema_version/member')
        artifacts=doc.get('artifacts')
        if not isinstance(artifacts,list) or not artifacts:raise ValueError('missing artifact list')
        if len(artifacts)>10000:raise ValueError('too many artifacts')
        seen=set()
        for entry in artifacts:
            if not isinstance(entry,dict): raise ValueError('artifact is not an object')
            rel=entry.get('path');expected=entry.get('sha256')
            if not isinstance(rel,str) or rel in seen:raise ValueError('invalid or duplicate path')
            seen.add(rel)
            if not isinstance(expected,str) or not HEX.fullmatch(expected):raise ValueError('malformed SHA256: '+rel)
            p=resolve_artifact(root,rel)
            before=p.stat();actual=digest_file(p);after=p.stat()
            if (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)!=(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns):raise ValueError('file changed while hashing: '+rel)
            same=actual==expected and before.st_size==entry.get('size_bytes')
            report['artifacts'].append({'path':rel,'status':'PASS' if same else 'FAIL','sha256':actual,'bytes':before.st_size})
        report['status']='PASS' if all(x['status']=='PASS' for x in report['artifacts']) else 'FAIL'
        report['reason']='MATCHES_SELF_DECLARED_HASHES' if report['status']=='PASS' else 'HASH_OR_SIZE_MISMATCH'
        report['source_details']=doc.get('source_details',{})
        return report
    except (OSError,ValueError,TypeError,KeyError) as exc:
        report['status']='FAIL';report['reason']=str(exc);return report

def verify_m2(root):
    # Existing M2 T09 contract is verified by the established M2 adapter.
    from verify_m2_handoff import verify
    if (root/'m3-delivery.json').is_file():
        r=verify(root)
        return {'member':'M2','status':r['status'],'reason':r.get('reason'),'artifacts':r.get('files',[]),
                'authenticity_verified':False,'scientific_validation':'NOT_PERFORMED'}
    return verify_member(root,'M2')

def run(base, reports):
    result={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'system':'SPECTRA-SAR-M4','members':{},'overall':'BLOCKED',
            'disclaimer':'SHA256 agreement with self-reported hashes is NOT provenance authentication or scientific validation.'}
    for member in MEMBERS:
        folder=base/member
        if not folder.is_dir():
            result['members'][member]={'member':member,'status':'BLOCKED','reason':'MISSING_MEMBER_HANDOFF'}
        else:
            result['members'][member]=verify_m2(folder) if member=='M2' else verify_member(folder,member)
    counts={s:sum(v['status']==s for v in result['members'].values()) for s in ('PASS','FAIL','BLOCKED')}
    result['counts']=counts
    result['overall']='BYTE_CHECKS_PASS_UNAUTHENTICATED' if counts['PASS']==len(MEMBERS) else 'BLOCKED'
    reports.mkdir(parents=True,exist_ok=True)
    (reports/'team_integrity_report.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    md=['# M4 team integration verification','',f"**Overall:** {result['overall']}",'', '| Member | Status | Reason |','|---|---|---|']
    for m,v in result['members'].items():md.append(f"| {m} | {v['status']} | {str(v.get('reason','')) .replace('|','/')} |")
    md.extend(['','**Warning:** Matching locally supplied SHA-256 hashes does not prove image authenticity, trusted custody, or scientific correctness.'])
    (reports/'TEAM-STATUS.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--handoffs',type=Path,default=Path(__file__).resolve().parents[1]/'handoffs');ap.add_argument('--reports',type=Path,default=Path(__file__).resolve().parents[1]/'reports')
    a=ap.parse_args();r=run(a.handoffs,a.reports);print(json.dumps({'overall':r['overall'],'counts':r['counts'],'report':str(a.reports/'team_integrity_report.json')},indent=2));return 0 if r['counts']['PASS']==len(MEMBERS) else 2
if __name__=='__main__':sys.exit(main())
