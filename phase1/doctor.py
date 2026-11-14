from phase1.common import ROOT, sha, load

def diagnose():
    before = ROOT/'members/M1/data/before_HHHH_20260920.tif'
    after = ROOT/'members/M1/data/after_HHHH_20261002.tif'
    checks = {}
    for name, path in [('M1','members/M1/fetch_harmony.py'),('M2','members/M2/pipeline.py'),
                       ('M3','members/M3/T09/pipeline.py'),('M4','members/M4/provenance.py'),
                       ('M5','backend/src/spectra/main.py'),('M6','members/M6/T06/provenance.py')]:
        checks[name] = (ROOT/path).is_file()
    config_path = ROOT/'config/local.json'
    configured = load(config_path).get('pair_dir') if config_path.is_file() else None
    if configured:
        from phase1.common import safe
        pair = safe(ROOT, configured)
        try:
            manifest = load(pair/'manifest.json')
            receipt = load(pair/'input-provenance.json')['input_sha256']
            pol = manifest['polarizations'][0]
            verified = {side: sha(safe(pair, manifest[side]['raster_files'][pol])) == receipt[side]
                        for side in ('before','after')}
            return {'project':'SPECTRA-SAR','phase':1,'canonical_modules':checks,
                'source_mode':'CONFIGURED_PAIR','pair_id':manifest['pair_id'],
                'before_present_and_matches_receipt':verified['before'],'after_present':verified['after'],
                'science_validated':False,'distributed_services_verified':False,
                'status':'READY_FOR_INPUT_QA' if all(verified.values()) and all(checks.values()) else 'BLOCKED_REAL_DATA',
                'missing':[], 'impact_requirements':['Independent population and asset data'],
                'next_command':'bash START.command'}
        except (OSError, ValueError, KeyError):
            return {'status':'BLOCKED_REAL_DATA','science_validated':False,'reason':'Configured pair failed receipt verification'}
    known = load(ROOT/'members/M1/reports/before-harmony-job.json').get('sha256')
    before_ok = before.is_file() and sha(before)==known
    return {'project':'SPECTRA-SAR','phase':1,'canonical_modules':checks,
            'before_present_and_matches_receipt':before_ok,'after_present':after.is_file(),
            'science_validated':False,'distributed_services_verified':False,
            'status':'READY_FOR_INPUT_QA' if before_ok and after.is_file() and all(checks.values()) else 'BLOCKED_REAL_DATA',
            'missing':['members/M1/data/after_HHHH_20261002.tif'] if not after.is_file() else [],
            'impact_requirements':['AOI','OSM GeoJSON','population GeoTIFF','population units and provenance'],
            'next_command':'python -m phase1 download' if not after.is_file() else 'python -m phase1 run'}
