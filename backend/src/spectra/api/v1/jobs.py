"""Authenticated job dispatch, status and queued-job cancellation."""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from spectra.api.v1.security import require_service_key
from spectra.persistence.database import get_db
from spectra.workers.job_manager import cancel_job, get_job_status

router = APIRouter(prefix='/processing-jobs', tags=['Processing Jobs'],
                   dependencies=[Depends(require_service_key)])

@router.get('/{job_id}')
def status(job_id: UUID, db: Session = Depends(get_db)):
    result = get_job_status(db, job_id)
    if result is None:
        raise HTTPException(404, 'Job not found')
    return result

@router.post('/{job_id}/dispatch', status_code=202)
def dispatch(job_id: UUID, db: Session = Depends(get_db)):
    job = get_job_status(db, job_id)
    if job is None:
        raise HTTPException(404, 'Job not found')
    if job['status'] != 'queued':
        raise HTTPException(409, 'Job is not queued')
    try:
        from spectra.workers.task_queue import enqueue_job
        task_id = enqueue_job(job_id)
    except Exception as exc:
        # Do not claim success if the broker cannot accept the task.
        raise HTTPException(503, 'Processing broker unavailable') from exc
    return {'job_id': str(job_id), 'task_id': task_id, 'queued': True}

@router.post('/{job_id}/cancel')
def cancel(job_id: UUID, db: Session = Depends(get_db)):
    if get_job_status(db, job_id) is None:
        raise HTTPException(404, 'Job not found')
    if not cancel_job(db, job_id):
        raise HTTPException(409, 'Only queued jobs may be cancelled')
    return {'job_id': str(job_id), 'status': 'cancelled'}
