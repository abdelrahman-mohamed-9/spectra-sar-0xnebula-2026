"""Public user routes secured with bearer JWT and project RBAC."""
from __future__ import annotations
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from spectra.persistence.database import get_db
from spectra.persistence.models import User, Artifact, ProcessingJob
from spectra.security.auth import (normalize_email, verify_password,
                                   issue_token, current_user, authorize_project)

router = APIRouter(prefix='/auth',tags=['User Authentication & RBAC'])

class LoginRequest(BaseModel):
    email: str = Field(min_length=3,max_length=254)
    password: str = Field(min_length=1,max_length=1024)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = 'bearer'
    expires_in: int

@router.post('/login',response_model=TokenResponse)
def login(payload: LoginRequest, db: Session=Depends(get_db)):
    try: email = normalize_email(payload.email)
    except ValueError: raise HTTPException(401,'Invalid credentials') from None
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    # Do not disclose whether an account exists.
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401,'Invalid credentials')
    token, seconds = issue_token(user)
    return TokenResponse(access_token=token, expires_in=seconds)

@router.get('/me')
def me(user: User=Depends(current_user)):
    return {'id':str(user.id),'email':user.email,'is_platform_admin':user.is_platform_admin}

@router.get('/projects/{project_id}/access')
def access(project_id: UUID, db: Session=Depends(get_db),user: User=Depends(current_user)):
    role=authorize_project(db,user,project_id)
    return {'project_id':str(project_id),'role':role}

@router.get('/projects/{project_id}/artifacts')
def project_artifacts(project_id: UUID, limit:int=20, db:Session=Depends(get_db), user:User=Depends(current_user)):
    authorize_project(db,user,project_id,'viewer')
    if not 1 <= limit <= 100: raise HTTPException(422,'limit out of range')
    rows=db.execute(select(Artifact.id,Artifact.kind,Artifact.media_type,Artifact.size_bytes)
        .where(Artifact.project_id==project_id).order_by(Artifact.created_at.desc()).limit(limit)).all()
    return [{'id':str(r.id),'kind':r.kind,'media_type':r.media_type,'size_bytes':r.size_bytes} for r in rows]

@router.get('/projects/{project_id}/jobs')
def project_jobs(project_id: UUID,limit:int=20,db:Session=Depends(get_db),user:User=Depends(current_user)):
    authorize_project(db,user,project_id,'viewer')
    if not 1 <= limit <= 100: raise HTTPException(422,'limit out of range')
    rows=db.execute(select(ProcessingJob.id,ProcessingJob.status,ProcessingJob.job_type)
        .where(ProcessingJob.project_id==project_id).order_by(ProcessingJob.created_at.desc()).limit(limit)).all()
    return [{'id':str(r.id),'status':r.status,'job_type':r.job_type} for r in rows]
