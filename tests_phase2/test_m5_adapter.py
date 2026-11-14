"""Exercise the original M5 app and its JWT decoder with an isolated user table."""

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

PHASE1 = os.environ.get("SPECTRA_PHASE1")


@pytest.mark.skipif(not PHASE1, reason="Requires the supplied Phase 1 M5 backend")
def test_original_m5_app_mount_and_real_jwt(tmp_path, monkeypatch):

    monkeypatch.syspath_prepend(str(Path(PHASE1) / "backend/src"))
    monkeypatch.syspath_prepend(PHASE1)
    monkeypatch.setenv("SPECTRA_PHASE2_STATE", str(tmp_path / "state"))
    monkeypatch.setenv("JWT_SECRET", "test-signing-material-for-qa-" * 2)

    from spectra.core.config import get_settings
    from spectra.persistence.database import get_db
    from spectra.persistence.models import User
    from spectra.security.auth import issue_token
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from phase2.jobs import Jobs, work_one
    from phase2.m5_adapter import create_integrated_app

    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{tmp_path / 'test-identities.sqlite3'}")
    User.__table__.create(engine)
    with Session(engine) as session:
        users = [
            User(
                id=uuid4(),
                email=f"user{i}@example.test",
                password_hash="unused-test-value",
                is_active=True,
                is_platform_admin=False,
            )
            for i in range(2)
        ]
        session.add_all(users)
        session.commit()
        tokens = [issue_token(user)[0] for user in users]

    def test_db():
        with Session(engine) as session:
            yield session

    app = create_integrated_app()
    app.dependency_overrides[get_db] = test_db
    route = "/api/v1/phase2/jobs"
    auth = [{"Authorization": f"Bearer {token}"} for token in tokens]
    try:
        with TestClient(app) as client:
            assert client.post(route, json={}).status_code == 401
            accepted = client.post(route, json={}, headers=auth[0])
            assert accepted.status_code == 202
            job = accepted.json()["id"]
            work_one(Jobs(tmp_path / "state"))
            endpoint = f"{route}/{job}"
            assert client.get(endpoint, headers=auth[1]).status_code == 404
            assert client.get(endpoint, headers=auth[0]).json()["status"] == "COMPLETED_EXPLORATORY"
    finally:
        engine.dispose()
        get_settings.cache_clear()
