"""Mounted on the genuine M5 application; same service-key authentication.

Local file mode is independently usable. PostgreSQL/Celery/MinIO API routes
remain available separately and never masquerade as verified infrastructure.
"""
import os
import threading
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from spectra.api.v1.security import require_service_key
from phase1.common import ROOT, load, safe, sha, command
from phase1.configuration import resolve_config
from phase1.doctor import diagnose
from phase1.pipeline import fresh_run

router = APIRouter(prefix='/api/v1/phase1',tags=['unified-phase1'],dependencies=[Depends(require_service_key)])
_run_lock = threading.Lock()

def runs_root():
    return Path(os.getenv('SPECTRA_RUNS_DIR',str(ROOT/'runs'))).resolve()

def run_dir(run_id):
    try: UUID(run_id)
    except ValueError: raise HTTPException(404,'Run not found') from None
    directory = safe(runs_root(),run_id)
    if not (directory/'run.json').is_file(): raise HTTPException(404,'Run not found')
    return directory

@router.get('/status')
def status(): return diagnose()

@router.get('/runs')
def runs():
    return [load(p) for p in sorted(runs_root().glob('*/run.json'),reverse=True) if not p.is_symlink()]

class Request(BaseModel):
    # Only allow operator-created config files inside config/, never arbitrary modules.
    config_name: str = Field(default='local.json',pattern=r'^[A-Za-z0-9_-]+\.json$')

@router.post('/runs',status_code=201)
def execute(request: Request):
    config_path = safe(ROOT/'config',request.config_name)
    if not config_path.is_file(): raise HTTPException(404,'Config not found')
    if not _run_lock.acquire(blocking=False): raise HTTPException(409,'An analysis is already running')
    try:
        result = fresh_run(resolve_config(load(config_path)),runs_root())
        # HTTP success only means the operation was recorded, inspect explicit run status.
        return result
    finally: _run_lock.release()

@router.get('/runs/{run_id}')
def detail(run_id: str): return load(run_dir(run_id)/'run.json')

@router.post('/runs/{run_id}/verify')
def verify(run_id: str):
    directory = run_dir(run_id)
    if not (directory/'M6/provenance.json').exists(): raise HTTPException(409,'No completed integrity manifest')
    try: command(['-m','phase1.worker','verify',directory],directory/'logs/reverify.log')
    except RuntimeError: raise HTTPException(409,'Artifact integrity check failed') from None
    return load(directory/'M6/verification.json')

@router.get('/runs/{run_id}/files/{relative_path:path}')
def artifact(run_id: str,relative_path: str):
    directory = run_dir(run_id)
    try: target = safe(directory,relative_path)
    except ValueError: raise HTTPException(404,'Artifact not found') from None
    manifest_file = directory/'M6/provenance.json'
    if not manifest_file.is_file(): raise HTTPException(409,'Run not finalized')
    allowed = {a['storage_uri'].removeprefix('file://') for a in load(manifest_file)['artifacts']}
    if relative_path not in allowed or not target.is_file(): raise HTTPException(404,'Artifact not found')
    expected = next(a['sha256'] for a in load(manifest_file)['artifacts'] if a['storage_uri']=='file://'+relative_path)
    if sha(target)!=expected: raise HTTPException(409,'Artifact integrity check failed')
    return FileResponse(target,filename=target.name)
