#!/usr/bin/env python3
"""Turn a REAL M2 runtime output into an M4-integrity audit and optional M4 evidence.
No generated satellite data, no scientific validation, no automatic trust in M2 hashes.
"""
import argparse, json, sys, hashlib
from pathlib import Path
from datetime import datetime, timezone
from verify_m2_handoff import verify

M4 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(M4))
from provenance import build_record, write_record, verify_record

def safe_json(p):
    def pairs(items):
        obj = {}
        for key,val in items:
            if key in obj: raise ValueError('Duplicate JSON key: '+key)
            obj[key] = val
        return obj
    return json.loads(Path(p).read_text(encoding='utf-8'), object_pairs_hook=pairs)

def main(argv=None):
    p = argparse.ArgumentParser(description='M2/M4 REAL-output integrity and scientific-evidence handoff')
    p.add_argument('--m2-output', type=Path, required=True, help='Folder containing m3-delivery.json AND its real raster outputs')
    p.add_argument('--reports', type=Path, required=True)
    p.add_argument('--source-metadata', type=Path, help='Reviewed, real M1 scene metadata JSON matching source-metadata.example.json')
    a = p.parse_args(argv)
    out = a.reports.resolve(); out.mkdir(parents=True,exist_ok=True)
    root = a.m2_output.resolve()
    audit = verify(root)
    audit['run_time_utc'] = datetime.now(timezone.utc).isoformat()
    audit['integrity_verdict_only'] = True
    audit['scientific_validation'] = 'NOT_PERFORMED'
    audit['baseline_trust'] = 'M2_SELF_REPORTED_UNAUTHENTICATED'
    (out/'m2_integrity_report.json').write_text(json.dumps(audit,indent=2)+'\n')
    status = {'integrity':audit['status'], 'evidence':'NOT_CREATED', 'scientific_approval':False,
              'authenticity_verified':False,'limitations':['M2 hashes are self-declared, not trusted without independent baseline.',
              'Scientific correctness, terrain interpretation and source authenticity are not verified.']}
    if audit['status'] != 'PASS':
        status['next_action']='Supply actual M2 runtime output folder with m3-delivery.json and each referenced raster.'
    elif not a.source_metadata:
        status['next_action']='Provide VERIFIED REAL M1 source scene provenance using --source-metadata to create M4 evidence.'
    else:
        try:
            source = safe_json(a.source_metadata)
            scenes = source['source_scenes']
            if not isinstance(scenes,list) or len(scenes) < 2: raise ValueError('Need two genuine source scene metadata records')
            # Reject unresolved placeholders instead of inventing source scene provenance.
            for sc in scenes:
                for key in ('scene_id','provider','product_type','acquisition_time_utc','source_url'):
                    value = sc[key]
                    if not isinstance(value,str) or not value.strip() or '<' in value or '>' in value:
                        raise ValueError('Incomplete source scene metadata: '+key)
            doc = safe_json(root/'m3-delivery.json')
            files = [x['path'] for x in doc['artifacts'].values()]
            evidence = build_record(root=root, files=files,scenes=scenes,
                producer={'member':'M2','component':'SPECTRA-SAR-M2-T09','version':'1.0'},
                algorithm='Exploratory SAR change detection (M2 pipeline)',
                parameters={'pair_id':doc['pair_id'],'polarization':doc['polarization'],
                            'change_detection':doc.get('change_detection')},
                claims=[],limitations=doc.get('limitations',[])+status['limitations'])
            outfile=out/'m4_evidence_record.json'
            write_record(evidence,outfile)
            validation=verify_record(evidence,root)
            (out/'m4_evidence_verification.json').write_text(json.dumps(validation,indent=2)+'\n')
            status['evidence']='CREATED_UNVERIFIED' if validation['status']=='PASS' else 'FAILED'
            status['evidence_record']=str(outfile)
            status['next_action']='Independently authenticate M1 source and protect/sign a baseline; never infer scientific approval from matched hashes.'
        except (Exception) as exc:
            status['evidence']='FAILED'; status['error']=str(exc)
    (out/'integration_status.json').write_text(json.dumps(status,indent=2)+'\n')
    print(json.dumps(status,indent=2))
    return 0 if audit['status']=='PASS' and status['evidence']!='FAILED' else 1

if __name__=='__main__': sys.exit(main())
