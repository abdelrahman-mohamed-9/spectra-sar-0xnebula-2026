"""Subprocess boundary prevents M2/M3/M4/M6 generic module-name collisions."""
import sys
from pathlib import Path
from uuid import uuid4
from phase1.common import ROOT, load, write, sha, now

def m4(run):
    sys.path.insert(0, str(ROOT/'members/M4'))
    sys.path.insert(0, str(ROOT/'members/M4/bridge'))
    from verify_m2_handoff import verify
    from provenance import build_record, write_record, verify_record
    audit = verify(run/'M2')
    write(run/'M4/m2-integrity.json', audit)
    if audit['status'] != 'PASS':
        raise ValueError('M4 rejected M2 artifact integrity')
    manifest = load(run/'M1/input-manifest.json')
    scenes = []
    for side in ('before', 'after'):
        scene = manifest[side]
        source_url = scene.get('source_url')
        if not source_url:
            # A local receipt URI is provenance, never an independent provider claim.
            source_url = 'urn:spectra:unverified-source:' + scene['scene_id']
        scenes.append(dict(scene_id=scene['scene_id'], provider=manifest['source_provider'],
                           product_type=manifest['product_type'],
                           acquisition_time_utc=scene['acquired_utc'], source_url=source_url,
                           orbit_direction=scene['orbit_direction'], polarization=manifest['polarizations']))
    files = [p.relative_to(run).as_posix() for folder in ('M1','M2','M3')
             for p in sorted((run/folder).rglob('*')) if p.is_file() and '.tmp' != p.suffix]
    record = build_record(root=run, files=files, scenes=scenes,
                          producer={'member':'M4','component':'Phase1 evidence','version':'1.0'},
                          algorithm='M1 QA → original M2 pipeline → original M3 pipeline when inputs exist',
                          parameters={'scientific_approval':False}, claims=[],
                          limitations=['Hashes verify consistency only; no independent NASA signature.',
                                       'Candidate change is not confirmed flood or damage.',
                                       'Coverage: M1/M2/M3 artifacts; downstream M5/M6 verified separately.'])
    write_record(record, run/'M4/evidence.json')
    result = verify_record(record, run)
    write(run/'M4/verification.json', result)
    if result['status'] != 'PASS': raise ValueError('M4 evidence verification failed')

def m6(run, verify_only=False):
    sys.path.insert(0, str(ROOT/'members/M6/T06'))
    from provenance import make_manifest, verify_local_artifacts
    if verify_only:
        result = verify_local_artifacts(load(run/'M6/provenance.json'), root=run)
    else:
        run_id = str(uuid4())
        artifacts = []
        parents = []
        for folder in ('M1','M2','M3','M4','M5'):
            current = []
            for p in sorted((run/folder).rglob('*')):
                if not p.is_file(): continue
                aid = str(uuid4()); current.append(aid)
                artifacts.append(dict(id=aid, run_id=run_id, scene_id=None,
                    sha256=sha(p), bytes_size=p.stat().st_size,
                    storage_uri='file://'+p.relative_to(run).as_posix(),
                    artifact_type=p.suffix.lstrip('.') or 'file',
                    producer_component=folder, input_artifact_ids=list(parents)))
            # Small lineage reference set; don't create a quadratic all-to-all graph.
            parents = current[:1] or parents
        doc = make_manifest(scenes=[], artifacts=artifacts)
        write(run/'M6/provenance.json', doc)
        result = verify_local_artifacts(doc, root=run)
    if not result['all_artifacts_verified']: raise ValueError('M6 incomplete artifact verification')
    write(run/'M6/verification.json', {**result,'scientific_approval':False,
          'scope':'M1–M5 run artifacts, not source authenticity or scientific validation', 'checked_at':now()})
    return result

if __name__ == '__main__':
    action, folder = sys.argv[1:3]
    if action == 'm4': m4(Path(folder).resolve())
    elif action == 'm6': m6(Path(folder).resolve())
    elif action == 'verify': print(m6(Path(folder).resolve(), True))
    else: raise ValueError('Unknown fixed worker action')
