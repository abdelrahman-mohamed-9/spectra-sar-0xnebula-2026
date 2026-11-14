"""SPECTRA-SAR M6 Phase 1 integration gates (stdlib only; opt-in live probes)."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TASK_FILES = {
    'T01': ['integration-requirements.md', 'system-interfaces.md'],
    'T02': ['docker-compose.yml', '.env.example', 'scripts/validate_env.py'],
    'T03': ['database-schema.sql', 'database.py', 'migrations/001_initial.sql'],
    'T04': ['api-contract.yaml', 'integration-plan.md'],
    'T05': ['pytest.ini', 'test_plan.md'],
    'T06': ['provenance.py', 'integrity_validator.py'],
    'T07': ['scientific_metrics.py', 'verification.py'],
    'T08': ['.github/workflows/ci.yml', 'scripts/run_offline_tests.py'],
    'T09': ['README.md', 'docs/setup-guide.md', 'docs/release-checklist.md'],
}
STAGES = ('M1', 'M2', 'M3', 'M4', 'M5')
SENSITIVE = re.compile(r'(authorization|token|password|secret|api[_-]?key|cookie)', re.I)

@dataclass
class Result:
    id: str
    status: str  # PASS, FAIL, BLOCKED
    detail: str
    evidence: str | None = None


def check_local(member_root: Path):
    results = []
    for task, expected in TASK_FILES.items():
        missing = [f for f in expected if not (member_root / task / f).is_file()]
        results.append(Result('package.' + task, 'FAIL' if missing else 'PASS',
                              'Missing: '+', '.join(missing) if missing else 'Required entrypoints found',
                              str(member_root / task)))
    return results


def check_live_api(base_url: str | None, bearer: str | None = None, timeout=6):
    if not base_url:
        return Result('live.backend', 'BLOCKED', 'Backend URL not supplied')
    if not base_url.startswith(('http://localhost:', 'http://127.0.0.1:', 'https://')):
        return Result('live.backend', 'FAIL', 'Use localhost or an HTTPS endpoint')
    url = base_url.rstrip('/') + '/health/ready'
    try:
        h = {'Accept': 'application/json'}
        if bearer: h['Authorization'] = 'Bearer ' + bearer
        with urlopen(Request(url, headers=h), timeout=timeout) as r:
            code, body = r.status, r.read(65536)
        if code != 200: return Result('live.backend', 'FAIL', f'HTTP {code}', url)
        try: payload = json.loads(body)
        except json.JSONDecodeError: return Result('live.backend','FAIL','Readiness response is not JSON',url)
        if not isinstance(payload, dict): return Result('live.backend','FAIL','Readiness JSON must be an object',url)
        return Result('live.backend','PASS','HTTP 200 and JSON object received; dependent endpoints not verified',url)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        return Result('live.backend', 'FAIL', f'Endpoint unreachable or unhealthy: {type(exc).__name__}',url)


def check_database(dsn: str | None):
    if not dsn: return Result('live.database','BLOCKED','DATABASE_URL not supplied')
    try:
        import psycopg
    except ImportError:
        return Result('live.database','BLOCKED','Install psycopg[binary] for database live probe')
    required = {'sar_scenes','scene_pairs','processing_jobs','artifacts','change_results','impact_assessments','alembic_version','users','project_memberships'}
    try:
        with psycopg.connect(dsn, connect_timeout=5) as con:
            with con.cursor() as cur:
                cur.execute('SELECT tablename FROM pg_tables WHERE schemaname = %s', ('public',))
                found = {r[0] for r in cur.fetchall()}
        missing = sorted(required - found)
        return Result('live.database', 'FAIL' if missing else 'PASS',
                      'Missing tables: ' + ', '.join(missing) if missing else 'Required baseline tables found')
    except Exception as exc:
        return Result('live.database','FAIL',f'DB probe failed ({type(exc).__name__}); credentials redacted')


def check_evidence(evidence_file: Path | None, dataset_root: Path | None):
    if not evidence_file:
        return [Result(f'e2e.{s}', 'BLOCKED', 'No team evidence manifest supplied') for s in STAGES] + [
            Result('e2e.real_sar', 'BLOCKED','No verified Sentinel-1 processing evidence supplied'),
            Result('e2e.scientific','BLOCKED','No independent reference evaluation evidence supplied'),
            Result('e2e.github','BLOCKED','No GitHub-hosted workflow evidence supplied')]
    try:
        m = json.loads(evidence_file.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return [Result('e2e.manifest','FAIL',f'Cannot read evidence: {type(exc).__name__}')]
    if not isinstance(m, dict): return [Result('e2e.manifest','FAIL','Manifest must be an object')]
    records = m.get('records', {})
    if not isinstance(records, dict): return [Result('e2e.manifest','FAIL','records must be an object')]
    out = []
    names = [f'e2e.{s}' for s in STAGES] + ['e2e.real_sar','e2e.scientific','e2e.github']
    for name in names:
        record = records.get(name)
        if not isinstance(record, dict):
            out.append(Result(name,'BLOCKED','Missing evidence record')); continue
        path = record.get('path')
        sha = record.get('sha256')
        if not dataset_root or not isinstance(path,str) or not isinstance(sha,str) or not re.fullmatch('[0-9a-f]{64}',sha):
            out.append(Result(name,'BLOCKED','Evidence file, root, and SHA-256 are required')); continue
        root = dataset_root.resolve()
        target = (root / path).resolve()
        if not target.is_relative_to(root):
            out.append(Result(name,'FAIL','Evidence path escapes allowed root')); continue
        if not target.is_file():
            out.append(Result(name,'FAIL','Referenced evidence file absent')); continue
        with target.open('rb') as f:
            digest = hashlib.file_digest(f,'sha256').hexdigest()
        if digest != sha:
            out.append(Result(name,'FAIL','Evidence SHA-256 mismatch')); continue
        # Integrity PASS alone does not prove scientific or operational correctness.
        out.append(Result(name,'PASS','Evidence file exists and matches SHA-256; substance needs reviewer sign-off',str(target)))
    return out


def report(results: list[Result]):
    counts = {s:sum(r.status == s for r in results) for s in ('PASS','FAIL','BLOCKED')}
    return {'project':'SPECTRA-SAR','component':'M6','phase':1,'task':'T10',
            'generated_at':datetime.now(timezone.utc).isoformat(),
            'overall':'FAIL' if counts['FAIL'] else ('BLOCKED' if counts['BLOCKED'] else 'PASS'),
            'counts':counts,'checks':[asdict(r) for r in results],
            'note':'PASS for local/evidence probes is not scientific validation. Live end-to-end sign-off is separate.'}


def render_md(data):
    lines = ['# M6 Phase 1 — T10 Integration Validation Report','',
             f"Generated (UTC): {data['generated_at']}",
             f"Overall: **{data['overall']}**",'',
             '| Check | Status | Evidence / finding |','|---|---|---|']
    for r in data['checks']:
        v = (r['detail'] + (' — '+r['evidence'] if r.get('evidence') else '')).replace('|','\\|').replace('\n',' ')
        lines.append(f"| `{r['id']}` | {r['status']} | {v} |")
    lines += ['', '**Interpretation:** Evidence SHA matches establish file integrity only; reviewers must verify independent scientific data, real SAR scene IDs, and true end-to-end execution.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    p = argparse.ArgumentParser(description='M6 T10 reproducible integration evidence report')
    p.add_argument('--member-root',type=Path,required=True,help='Directory containing T01...T09')
    p.add_argument('--backend-url',default=os.environ.get('SPECTRA_BACKEND_URL'))
    p.add_argument('--database-url',default=os.environ.get('DATABASE_URL'))
    p.add_argument('--evidence-manifest',type=Path)
    p.add_argument('--evidence-root',type=Path)
    p.add_argument('--output',type=Path,default=Path('reports/integration-report.json'))
    args = p.parse_args(argv)
    results = check_local(args.member_root) + [check_live_api(args.backend_url),check_database(args.database_url)] + check_evidence(args.evidence_manifest,args.evidence_root)
    data = report(results)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    md = args.output.with_suffix('.md')
    md.write_text(render_md(data),encoding='utf-8')
    print(json.dumps({'overall':data['overall'],'counts':data['counts'],'json':str(args.output),'markdown':str(md)},indent=2))
    return {'PASS':0,'BLOCKED':2,'FAIL':1}[data['overall']]

if __name__ == '__main__': sys.exit(main())
