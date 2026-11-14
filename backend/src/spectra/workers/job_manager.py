"""Durable DB-backed job state transitions; Redis is transport, DB is truth.

Atomic conditional UPDATE is the worker claim: competing workers cannot both run
one job. Production retries should be coordinated by the task implementation.
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import update, select
from sqlalchemy.orm import Session
from spectra.persistence.models import ProcessingJob

TERMINAL = frozenset({'succeeded', 'failed', 'cancelled'})


def claim_job(db: Session, job_id: UUID) -> bool:
    now = datetime.now(timezone.utc)
    result = db.execute(update(ProcessingJob).where(
        ProcessingJob.id == job_id, ProcessingJob.status == 'queued'
    ).values(status='running', started_at=now, finished_at=None, failure_reason=None))
    db.commit()
    return result.rowcount == 1


def finish_job(db: Session, job_id: UUID, *, success: bool, reason: str | None = None) -> bool:
    if not success and not reason:
        raise ValueError('Failure must include a reason')
    result = db.execute(update(ProcessingJob).where(
        ProcessingJob.id == job_id, ProcessingJob.status == 'running'
    ).values(status='succeeded' if success else 'failed',
             failure_reason=None if success else reason[:1000],
             finished_at=datetime.now(timezone.utc)))
    db.commit()
    return result.rowcount == 1


def requeue_job(db: Session, job_id: UUID, *, reason: str) -> bool:
    """Used only for transient failure before a Celery retry; preserves attempt history externally."""
    result = db.execute(update(ProcessingJob).where(
        ProcessingJob.id == job_id, ProcessingJob.status == 'running'
    ).values(status='queued', failure_reason=reason[:1000], finished_at=None))
    db.commit()
    return result.rowcount == 1


def cancel_job(db: Session, job_id: UUID) -> bool:
    """Cancels *queued* jobs. Running jobs cannot safely be interrupted here."""
    result = db.execute(update(ProcessingJob).where(
        ProcessingJob.id == job_id, ProcessingJob.status == 'queued'
    ).values(status='cancelled', finished_at=datetime.now(timezone.utc)))
    db.commit()
    return result.rowcount == 1


def get_job_status(db: Session, job_id: UUID) -> dict | None:
    obj = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id))
    if obj is None:
        return None
    return {'id': str(obj.id), 'project_id': str(obj.project_id), 'job_type': obj.job_type,
            'status': obj.status, 'failure_reason': obj.failure_reason,
            'started_at': obj.started_at, 'finished_at': obj.finished_at}
