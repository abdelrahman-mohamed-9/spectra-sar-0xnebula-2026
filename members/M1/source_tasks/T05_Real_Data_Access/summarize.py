#!/usr/bin/env python3
"""Produce a concise, credential-free status artifact for an actual T05 run."""
import json
from pathlib import Path
root=Path(__file__).resolve().parent
out=root/'output';out.mkdir(exist_ok=True)
report={'status':'NO_RASTER_QA_YET','pair':None,'data_origin_verified':False}
qa=out/'t05-real-data-qa.json'
if qa.is_file():
    try: report=json.loads(qa.read_text())
    except Exception: report={'status':'QA_REPORT_UNREADABLE','pair':None,'data_origin_verified':False}
lines=['SPECTRA-SAR M1 T05 — REAL DATA STATUS','--------------------------------','']
for role in ('before','after'):
    man=root/'reports'/f'{role}-harmony-job.json'
    if man.is_file():
        try:
            d=json.loads(man.read_text())
            status=d.get('status','UNKNOWN')
            reason=str(d.get('error','')).splitlines()[0][:200]
            lines.append(f'{role.upper()}: {status}'+(f' — {reason}' if reason else ''))
            lines.append(f'  CMR ID: {d.get("cmr_granule_concept_id","N/A")}')
            lines.append(f'  Job ID: {d.get("job_id","N/A")}')
        except Exception: lines.append(f'{role.upper()}: INVALID_REPORT')
    else: lines.append(f'{role.upper()}: NO_HARMONY_JOB_YET')
lines.append('')
if qa.is_file():
    pair=report.get('pair') or {}
    lines.extend([f'RASTER_BEFORE: {(report.get("before") or {}).get("status","N/A")}',
                  f'RASTER_AFTER: {(report.get("after") or {}).get("status","N/A")}',
                  f'PAIR: {pair.get("status","N/A")}',
                  f'LOCAL_HARMONY_TRACE: {report.get("local_harmony_job_trace_verified",False)}'])
else:lines.append('RASTER QA: NOT RUN (NO VERIFIED PAIR DOWNLOADED)')
lines.extend(['', 'This report never claims flood detection or glacier displacement.','Do not send NASA login credentials or tokens.'])
(out/'t05-status.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('A shareable status report was saved to output/t05-status.txt')
