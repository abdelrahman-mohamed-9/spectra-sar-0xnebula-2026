"""SQLAlchemy connection lifecycle. No connection is opened at module import."""
from collections.abc import Iterator
from functools import lru_cache
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from spectra.core.config import get_settings


def normalize_database_url(url: str) -> str:
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgresql+psycopg://"):
        return url
    raise ValueError("DATABASE_URL must be PostgreSQL (psycopg 3)")


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = get_settings().database_url
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_engine(normalize_database_url(url), pool_pre_ping=True,
                         pool_size=5, max_overflow=10, pool_timeout=10,
                         connect_args={"connect_timeout": 5})


def get_db() -> Iterator[Session]:
    """FastAPI Depends(get_db): always closes/rolls back on exception."""
    factory = sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)
    with factory() as session:
        yield session


def database_status(engine: Engine) -> dict[str, str]:
    """Real SQL queries; checks PostGIS and the expected migration revision."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1")).scalar_one()
        extension = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname = 'postgis'")).scalar_one_or_none()
        revision = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    if not extension:
        raise RuntimeError("PostGIS extension not installed")
    if revision != "0002_auth_rbac":
        raise RuntimeError("Database migration revision mismatch")
    return {"database": "ready", "postgis": "ready", "migrations": "current"}
