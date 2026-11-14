"""Launch the integrated local server and supervised independent worker."""
import argparse
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def secret(path):
    if path.is_symlink(): raise ValueError('Credential files cannot be symbolic links')
    if path.exists():
        if os.name != 'nt' and path.stat().st_mode & 0o077: raise ValueError(f'Credential file must be private: {path.name}')
        return path.read_text().strip()
    value=secrets.token_urlsafe(36)
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f: f.write(value+'\n')
    return value

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,default=ROOT/'state')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    sys.path[:0]=[str(ROOT),str(ROOT/'backend/src'),str(ROOT/'phase1_compat/m2')]
    from phase2.jobs import Jobs
    from phase2.integrity import verify_inventory
    import json
    queue=Jobs(args.state)
    verify_inventory(ROOT/'data',json.loads((ROOT/'catalog.json').read_text())['nisar-oct2026'])
    token=secret(queue.root/'operator-token.txt')
    service=secret(queue.root/'internal-api-key.txt')
    env=os.environ.copy();env.update(PYTHONPATH=os.pathsep.join([str(ROOT),str(ROOT/'backend/src'),str(ROOT/'phase1_compat/m2')]),
        SPECTRA_PHASE2_STATE=str(queue.root),SPECTRA_PHASE2_TOKEN=token,INTERNAL_API_KEY=service,
        SPECTRA_RUNS_DIR=str(queue.root/'phase1-runs'),OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    with socket.socket() as probe: probe.bind(('127.0.0.1',args.port))
    logs=queue.root/'logs';logs.mkdir(exist_ok=True)
    children=[]
    stopping=False
    def stop(signum=None, frame=None):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    url=f'http://127.0.0.1:{args.port}'
    print('\nSPECTRA Phase 1 + Phase 2\nWorkspace: '+url+'\nAccess token: '+token+'\nKeep this token private. Press Ctrl+C to stop.\n',flush=True)
    try:
        with (logs/'worker.log').open('a') as worker_log:
            worker=subprocess.Popen([sys.executable,'-m','phase2.jobs','--state',str(queue.root)],cwd=ROOT,env=env,stdout=worker_log,stderr=subprocess.STDOUT)
            children.append(worker)
            api=subprocess.Popen([sys.executable,'-m','uvicorn','phase2.application:create_local_app','--factory','--host','127.0.0.1','--port',str(args.port)],cwd=ROOT,env=env)
            children.append(api)
            deadline=time.monotonic()+30
            while time.monotonic()<deadline and not stopping:
                if any(p.poll() is not None for p in children): raise RuntimeError('Server or worker exited; inspect state/logs/worker.log')
                with socket.socket() as probe:
                    if probe.connect_ex(('127.0.0.1',args.port))==0: break
                time.sleep(.2)
            else: raise RuntimeError('Server did not become ready')
            if not args.no_browser: webbrowser.open(url)
            while not stopping:
                if any(p.poll() is not None for p in children): raise RuntimeError('Server or worker exited; inspect worker log')
                time.sleep(.5)
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':main()
