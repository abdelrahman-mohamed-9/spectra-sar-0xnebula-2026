"""T10 JWT identity, Argon2id password verification and project-level RBAC.

Service-key routes from T06–T09 remain *internal only*, and MUST NOT be
exposed directly to browsers/public internet. This module protects new user routes.
"""
from __future__ import annotations
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session
from spectra.core.config import get_settings
from spectra.persistence.database import get_db
from spectra.persistence.models import User, ProjectMembership

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
bearer = HTTPBearer(auto_error=False)
ROLES = {'viewer': 0, 'analyst': 1, 'editor': 2, 'owner': 3}


def normalize_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or '@' not in email or not email.split('@')[1]:
        raise ValueError('Invalid email')
    return email


def hash_password(password: str) -> str:
    if len(password) < 12 or len(password) > 1024:
        raise ValueError('Password must contain 12–1024 characters')
    return ph.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return ph.verify(encoded, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError, TypeError):
        return False


def _secret() -> str:
    key = get_settings().jwt_secret
    if not key or len(key) < 32:
        raise HTTPException(503, 'JWT signing key not configured')
    return key


def issue_token(user: User) -> tuple[str, int]:
    cfg = get_settings()
    now = datetime.now(timezone.utc)
    seconds = cfg.jwt_ttl_minutes * 60
    token = jwt.encode({'sub': str(user.id), 'iss': cfg.jwt_issuer,
                        'aud': cfg.jwt_audience, 'iat': now,
                        'nbf': now, 'exp': now + timedelta(seconds=seconds),
                        'jti': str(uuid.uuid4())}, _secret(), algorithm='HS256')
    return token, seconds


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
                 db: Session = Depends(get_db)) -> User:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Bearer token required', headers={'WWW-Authenticate': 'Bearer'})
    cfg = get_settings()
    try:
        payload = jwt.decode(credentials.credentials, _secret(), algorithms=['HS256'],
                             audience=cfg.jwt_audience, issuer=cfg.jwt_issuer,
                             options={'require': ['sub','iss','aud','iat','nbf','exp','jti']})
        user_id = uuid.UUID(payload['sub'])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise HTTPException(401, 'Invalid or expired access token', headers={'WWW-Authenticate': 'Bearer'}) from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, 'User not found or disabled', headers={'WWW-Authenticate': 'Bearer'})
    return user


def authorize_project(db: Session, user: User, project_id: uuid.UUID, min_role: str = 'viewer') -> str:
    if min_role not in ROLES:
        raise ValueError('Unknown required role')
    if user.is_platform_admin:
        return 'platform_admin'
    membership = db.execute(select(ProjectMembership).where(
        ProjectMembership.project_id == project_id,
        ProjectMembership.user_id == user.id)).scalar_one_or_none()
    # 404 prevents leaking existence of projects to nonmembers.
    if membership is None:
        raise HTTPException(404, 'Project not found')
    if ROLES[membership.role] < ROLES[min_role]:
        raise HTTPException(403, 'Insufficient project permissions')
    return membership.role
