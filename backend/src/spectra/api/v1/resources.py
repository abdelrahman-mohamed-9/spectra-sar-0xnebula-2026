"""T06 authenticated synchronous REST contract for trusted processing services.

No synthetic scientific data is created here. Job creation does not dispatch
workers; queuing is part of T08. Database constraints remain authoritative.
"""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy.orm import Session
from spectra.api.v1.security import require_service_key
from spectra.domain import schemas
from spectra.persistence.database import get_db
from spectra.persistence import repositories as repo

router = APIRouter(prefix='/resources', tags=['SAR Resources'],
                   dependencies=[Depends(require_service_key)])


def _write(db: Session, repository, payload, read_type):
    try:
        item = repository(db).add(payload)
        db.commit()
        db.refresh(item)
        return read_type.model_validate(item)
    except (IntegrityError, DataError) as exc:
        db.rollback()
        # Do not leak DB or credential information in external error responses.
        raise HTTPException(status_code=409, detail='Conflicting or invalid referenced resource') from exc
    except Exception:
        db.rollback()
        raise


def _read(db: Session, repository, entity_id: UUID, read_type):
    item = repository(db).get(entity_id)
    if item is None:
        raise HTTPException(status_code=404, detail='Resource not found')
    return read_type.model_validate(item)


def _list(db: Session, repository, read_type, limit: int, offset: int):
    return [read_type.model_validate(item) for item in repository(db).list(limit=limit, offset=offset)]


@router.post('/scenes', response_model=schemas.SarSceneRead, status_code=201)
def create_scene(data: schemas.SarSceneCreate, db: Session = Depends(get_db)):
    return _write(db, repo.SarSceneRepository, data, schemas.SarSceneRead)

@router.get('/scenes/{scene_id}', response_model=schemas.SarSceneRead)
def get_scene(scene_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.SarSceneRepository, scene_id, schemas.SarSceneRead)

@router.get('/scenes', response_model=list[schemas.SarSceneRead])
def list_scenes(limit: int = Query(50,ge=1,le=100), offset: int = Query(0,ge=0), db: Session = Depends(get_db)):
    return _list(db, repo.SarSceneRepository, schemas.SarSceneRead, limit, offset)


@router.post('/artifacts', response_model=schemas.ArtifactRead, status_code=201)
def create_artifact(data: schemas.ArtifactCreate, db: Session = Depends(get_db)):
    return _write(db, repo.ArtifactRepository, data, schemas.ArtifactRead)

@router.get('/artifacts/{artifact_id}', response_model=schemas.ArtifactRead)
def get_artifact(artifact_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.ArtifactRepository, artifact_id, schemas.ArtifactRead)


@router.post('/scene-pairs', response_model=schemas.ScenePairRead, status_code=201)
def create_pair(data: schemas.ScenePairCreate, db: Session = Depends(get_db)):
    return _write(db, repo.ScenePairRepository, data, schemas.ScenePairRead)

@router.get('/scene-pairs/{pair_id}', response_model=schemas.ScenePairRead)
def get_pair(pair_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.ScenePairRepository, pair_id, schemas.ScenePairRead)


@router.post('/jobs', response_model=schemas.ProcessingJobRead, status_code=201)
def create_job(data: schemas.ProcessingJobCreate, db: Session = Depends(get_db)):
    # T06 only creates queued rows; it does not start scientific processing.
    return _write(db, repo.ProcessingJobRepository, data, schemas.ProcessingJobRead)

@router.get('/jobs/{job_id}', response_model=schemas.ProcessingJobRead)
def get_job(job_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.ProcessingJobRepository, job_id, schemas.ProcessingJobRead)


@router.post('/change-results', response_model=schemas.ChangeResultRead, status_code=201)
def create_change(data: schemas.ChangeResultCreate, db: Session = Depends(get_db)):
    return _write(db, repo.ChangeResultRepository, data, schemas.ChangeResultRead)

@router.get('/change-results/{result_id}', response_model=schemas.ChangeResultRead)
def get_change(result_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.ChangeResultRepository, result_id, schemas.ChangeResultRead)


@router.post('/impact-assessments', response_model=schemas.ImpactAssessmentRead, status_code=201)
def create_impact(data: schemas.ImpactAssessmentCreate, db: Session = Depends(get_db)):
    return _write(db, repo.ImpactAssessmentRepository, data, schemas.ImpactAssessmentRead)

@router.get('/impact-assessments/{impact_id}', response_model=schemas.ImpactAssessmentRead)
def get_impact(impact_id: UUID, db: Session = Depends(get_db)):
    return _read(db, repo.ImpactAssessmentRepository, impact_id, schemas.ImpactAssessmentRead)
