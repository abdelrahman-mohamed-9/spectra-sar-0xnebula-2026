"""Celery task transport for existing processing_jobs.

External M1/M2/M3 scientific processors are intentionally NOT simulated.
Register explicit handlers after their real contracts and runtime dependencies
are available. Without a handler, the job fails visibly, never succeeds falsely.
"""
from __future__ import annotations
from uuid import UUID
from celery import Celery
from sqlalchemy.orm import Session
from spectra.core.config import get_settings
from spectra.persistence.database import get_engine
from spectra.workers.job_manager import claim_job, finish_job, requeue_job

settings = get_settings()
celery_app = Celery('spectra', broker=settings.redis_url or 'redis://localhost:6379/0')
celery_app.conf.update(
    task_serializer='json', accept_content=['json'], result_serializer='json',
    task_track_started=True, task_acks_late=True, worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True, task_time_limit=1800, task_soft_time_limit=1740,
    broker_connection_retry_on_startup=True,
)

class TransientProcessingError(Exception):
    """Only retryable infrastructure failures should use this exception."""

class HandlerNotConfigured(Exception):
    """No real scientific processor registered for the requested job type."""

# Registration deliberately explicit; do not pass arbitrary module/function names
# from user-controlled input_parameters to importlib or subprocess.
HANDLERS: dict[str, object] = {}

def register_handler(job_type: str, handler):
    if job_type not in {'preprocess','denoise','change_detection','impact_assessment','other'}:
        raise ValueError('Unsupported job type')
    if not callable(handler):
        raise TypeError('Handler must be callable')
    HANDLERS[job_type] = handler

@celery_app.task(bind=True, name='spectra.run_processing_job', max_retries=3)
def run_processing_job(self, job_id: str):
    """Execute only against a persisted queued job; no synthetic output.

    Handlers receive (db_session, job_record), and must persist science outputs
    in the SAME transaction; success is committed only after handler completes.
    """
    from spectra.persistence.models import ProcessingJob
    parsed = UUID(job_id)
    with Session(get_engine(), expire_on_commit=False) as db:
        if not claim_job(db, parsed):
            return {'job_id': job_id, 'outcome': 'not_claimed'}
        try:
            job = db.get(ProcessingJob, parsed)
            handler = HANDLERS.get(job.job_type)
            if handler is None:
                raise HandlerNotConfigured(f'No real scientific processor registered for {job.job_type}')
            handler(db, job)
            db.flush()
            finish_job(db, parsed, success=True)
            return {'job_id': job_id, 'outcome': 'succeeded'}
        except TransientProcessingError as exc:
            db.rollback()
            if self.request.retries >= self.max_retries:
                finish_job(db, parsed, success=False, reason='Transient failure: retries exhausted')
                return {'job_id': job_id, 'outcome': 'failed'}
            requeue_job(db, parsed, reason='Transient infrastructure failure; retry scheduled')
            raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 5, 60))
        except Exception as exc:
            db.rollback()
            # Do not disclose traceback or secrets through API-facing failure text.
            reason = str(exc) if isinstance(exc, HandlerNotConfigured) else type(exc).__name__
            finish_job(db, parsed, success=False, reason=reason)
            return {'job_id': job_id, 'outcome': 'failed'}


def enqueue_job(job_id: UUID) -> str:
    """Caller must commit the database job row before invoking this."""
    result = run_processing_job.apply_async(args=[str(job_id)], task_id=f'spectra-{job_id}')
    return result.id

# Only the monorepo distribution provides this explicit fixed scientific handler.
try:
    from phase1.distributed import handle as phase1_handler
except ModuleNotFoundError as exc:
    if exc.name != "phase1": raise
else:
    register_handler("other", phase1_handler)
