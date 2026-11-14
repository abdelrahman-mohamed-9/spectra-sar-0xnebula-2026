"""Explicit transaction boundary for repository operations."""
from collections.abc import Iterator
from contextlib import contextmanager
from sqlalchemy.orm import Session
from spectra.persistence.database import get_engine

@contextmanager
def transaction() -> Iterator[Session]:
    with Session(get_engine(),expire_on_commit=False) as session:
        with session.begin():
            yield session
