import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from phase1.common import ROOT, load, write, command

def main():
    p = argparse.ArgumentParser(description='SPECTRA-SAR unified Phase 1')
    sub = p.add_subparsers(dest='action',required=True)
    sub.add_parser('doctor')
    a=sub.add_parser('run');a.add_argument('--config',default=str(ROOT/'config/local.json'))
    a.add_argument('--after');a.add_argument('--pair-dir');a.add_argument('--out')
    a=sub.add_parser('verify');a.add_argument('run_dir')
    a=sub.add_parser('serve');a.add_argument('--port',type=int,default=8765)
    sub.add_parser('test');a=sub.add_parser('download');a.add_argument('--new-job',action='store_true')
    a=p.parse_args()
    if a.action=='doctor':
        from phase1.doctor import diagnose
        report=diagnose();print(json.dumps(report,indent=2));return 0 if report['status']=='READY_FOR_INPUT_QA' else 2
    if a.action=='run':
        from phase1.pipeline import fresh_run,run
        cfg=load(a.config)
        # Relative paths in saved configs are relative to the project root.
        for k in ('before','after','pair_dir','model_dir','reference','provenance'):
            if cfg.get(k) and not Path(cfg[k]).is_absolute(): cfg[k]=str(ROOT/cfg[k])
        for k in ('aoi','osm','population','source_manifest'):
            if cfg.get('impact',{}).get(k) and not Path(cfg['impact'][k]).is_absolute():cfg['impact'][k]=str(ROOT/cfg['impact'][k])
        if a.after:cfg['after']=str(Path(a.after).resolve())
        if a.pair_dir:cfg['pair_dir']=str(Path(a.pair_dir).resolve())
        result=run(cfg,a.out) if a.out else fresh_run(cfg)
        print(json.dumps(result,indent=2));return 0 if result['status']=='COMPLETED_EXPLORATORY' else 2
    if a.action=='verify':
        folder=Path(a.run_dir).resolve()
        command(['-m','phase1.worker','verify',folder],folder/'logs/reverify.log')
        print(json.dumps(load(folder/'M6/verification.json'),indent=2));return 0
    if a.action=='download':
        return subprocess.call([sys.executable,str(ROOT/'members/M1/fetch_harmony.py'),*(['--new-job'] if a.new_job else [])],cwd=ROOT)
    if a.action=='test':return subprocess.call([sys.executable,str(ROOT/'scripts/test_all.py')],cwd=ROOT)
    if a.action=='serve':
        sys.path.insert(0,str(ROOT/'backend/src'))
        from dotenv import load_dotenv
        load_dotenv(ROOT/'.local.env')
        import uvicorn
        from spectra.main import app
        uvicorn.run(app,host='127.0.0.1',port=a.port)
        return 0

if __name__=='__main__':raise SystemExit(main())
