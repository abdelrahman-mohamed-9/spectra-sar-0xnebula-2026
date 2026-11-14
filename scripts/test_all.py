"""Run member suites in isolated subprocesses to prevent module-name collisions."""
from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'reports/tests'
REPORT.mkdir(parents=True,exist_ok=True)
suites=[('M1',ROOT/'members/M1',ROOT/'members/M1/tests'),('unified',ROOT,ROOT/'tests'),('M2',ROOT/'members/M2',ROOT/'members/M2/tests'),
        ('M3_pipeline',ROOT/'members/M3/T09',ROOT/'members/M3/T09/tests'),
        ('M3_geodata',ROOT/'members/M3/T02',ROOT/'members/M3/T02/tests'),
        ('M4',ROOT/'members/M4',ROOT/'members/M4'),('M5',ROOT/'backend',ROOT/'backend/tests')]
for task in ('T02','T03','T04','T05','T06','T07','T08','T09','T10'):
    suites.append(('M6_'+task,ROOT/'members/M6'/task,ROOT/'members/M6'/task/'tests'))
results=[]
for name,cwd,tests in suites:
    print('Testing '+name,flush=True)
    env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join(map(str,[ROOT,ROOT/'backend/src',cwd]))
    # Prevent inherited real credentials/URLs from turning offline tests into live actions.
    for key in ('DATABASE_URL','SPECTRA_DATABASE_URL','SPECTRA_API_BASE_URL','SPECTRA_BACKEND_URL','SPECTRA_TOKEN','REDIS_URL','S3_ENDPOINT_URL','INTERNAL_API_KEY','JWT_SECRET'):
        env.pop(key,None)
    xml=REPORT/(name+'.xml')
    try:
        proc=subprocess.run([sys.executable,'-m','pytest','-q',str(tests),'--junitxml',str(xml)],
                            cwd=cwd,env=env,capture_output=True,text=True,timeout=300)
        (REPORT/(name+'.log')).write_text(proc.stdout+'\n'+proc.stderr)
        row={'suite':name,'exit_code':proc.returncode}
        if xml.exists():
            trees=ET.parse(xml).getroot()
            row.update({k:sum(int(t.attrib.get(k,0)) for t in trees.findall('testsuite'))
                        for k in ('tests','failures','errors','skipped')})
        results.append(row)
    except subprocess.TimeoutExpired:
        results.append({'suite':name,'exit_code':124,'error':'timeout'})
    print(json.dumps(results[-1]),flush=True)
report={'created_at':datetime.now(timezone.utc).isoformat(),'scope':'Software-only tests; temporary generated fixtures; no real SAR E2E or live Docker verification',
        'suites':results,'status':'PASS' if all(r['exit_code']==0 for r in results) else 'FAIL'}
(REPORT/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
raise SystemExit(0 if report['status']=='PASS' else 1)
