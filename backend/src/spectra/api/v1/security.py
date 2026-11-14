"""T06 internal service authentication; not a substitute for end-user RBAC.

All /api/v1 resource routes require a secret shared by trusted backend workers.
Production should migrate to managed service identities + project-level authorization.
"""
import hmac
from fastapi import Depends, Header, HTTPException, status
from spectra.core.config import get_settings


def require_service_key(x_api_key: str | None = Header(default=None)) -> None:
    configured = get_settings().internal_api_key
    if not configured or len(configured) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Internal API authentication not configured")
    if not x_api_key or not hmac.compare_digest(x_api_key, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing service credentials",
                            headers={"WWW-Authenticate": "ApiKey"})
