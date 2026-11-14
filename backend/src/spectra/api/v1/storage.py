"""T09 authenticated storage ingress and private temporary download URLs.

Trusted service-to-service API only. End-user project authorization belongs in T10.
"""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError, DataError
from sqlalchemy.orm import Session
from spectra.api.v1.security import require_service_key
from spectra.domain.schemas import ArtifactCreate, ArtifactRead
from spectra.persistence.database import get_db
from spectra.persistence.repositories import ArtifactRepository
from spectra.storage.storage_service import upload_artifact, delete_managed, presigned_download

router = APIRouter(prefix='/storage',tags=['Private Object Storage'],
                   dependencies=[Depends(require_service_key)])

@router.post('/artifacts/upload', response_model=ArtifactRead, status_code=201)
def upload(project_id: UUID = Form(...),
           kind: str = Form(...), scene_id: UUID | None = Form(None),
           file: UploadFile = File(...), db: Session = Depends(get_db)):
    # Validate before storing to avoid orphaned objects on invalid requests.
    if kind not in {'raw_sar','calibrated_sar','filtered_sar','change_mask',
                    'confidence_map','risk_map','report','other'}:
        raise HTTPException(422,'Invalid artifact kind')
    saved = upload_artifact(file,project_id)
    try:
        data = ArtifactCreate(project_id=project_id,scene_id=scene_id,
            kind=kind,storage_uri=saved.uri,media_type=saved.media_type,
            size_bytes=saved.size_bytes,sha256=saved.sha256)
        obj=ArtifactRepository(db).add(data)
        db.commit()
        db.refresh(obj)
        return ArtifactRead.model_validate(obj)
    except (IntegrityError,DataError) as exc:
        db.rollback()
        try: delete_managed(saved.uri)
        except Exception: pass  # reconcile abandoned objects via scheduled cleanup
        raise HTTPException(409,'Invalid project/scene reference') from exc
    except Exception:
        db.rollback()
        try: delete_managed(saved.uri)
        except Exception: pass
        raise
    finally:
        file.file.close()

@router.get('/artifacts/{artifact_id}/download-url')
def download_url(artifact_id: UUID,db: Session=Depends(get_db)):
    artifact=ArtifactRepository(db).get(artifact_id)
    if artifact is None: raise HTTPException(404,'Artifact not found')
    return {'url':presigned_download(artifact.storage_uri), 'expires_in_seconds':300}
