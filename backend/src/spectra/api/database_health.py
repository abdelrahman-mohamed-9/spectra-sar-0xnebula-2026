"""Database status endpoint; returns no secrets or stack traces."""
from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from spectra.persistence.database import get_engine, database_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/database")
def database_health() -> dict[str, str]:
    try:
        return {"status": "ready", **database_status(get_engine())}
    except (SQLAlchemyError, RuntimeError, ValueError, OSError):
        raise HTTPException(status_code=503, detail="Database unavailable or schema not current") from None
