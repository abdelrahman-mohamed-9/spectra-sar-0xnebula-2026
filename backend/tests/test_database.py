import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from spectra.main import app
from spectra.persistence.database import normalize_database_url, database_status
from alembic.script import ScriptDirectory
from alembic.config import Config


def test_url_normalization():
    value = normalize_database_url("postgresql://user:pw@localhost:5432/db")
    assert make_url(value).drivername == "postgresql+psycopg"
    assert normalize_database_url(value) == value
    with pytest.raises(ValueError):
        normalize_database_url("sqlite:///db.sqlite")


def test_database_status_checks_real_sql_contract():
    engine = MagicMock()
    cx = engine.connect.return_value.__enter__.return_value
    cx.execute.side_effect = [Mock(scalar_one=lambda: 1),
                              Mock(scalar_one_or_none=lambda: "3.4.0"),
                              Mock(scalar_one_or_none=lambda: "0002_auth_rbac")]
    assert database_status(engine)["migrations"] == "current"
    assert cx.execute.call_count == 3


def test_database_status_rejects_old_revision():
    engine = MagicMock()
    cx = engine.connect.return_value.__enter__.return_value
    cx.execute.side_effect = [Mock(scalar_one=lambda: 1),
                              Mock(scalar_one_or_none=lambda: "3.4.0"),
                              Mock(scalar_one_or_none=lambda: "old")]
    with pytest.raises(RuntimeError, match="revision"):
        database_status(engine)


def test_database_health_does_not_leak_secrets():
    with patch("spectra.api.database_health.get_engine", side_effect=RuntimeError("mysecret")):
        r = TestClient(app).get("/health/database")
    assert r.status_code == 503
    assert "mysecret" not in r.text


def test_alembic_revision_is_discoverable():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    scripts = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    assert scripts.get_current_head() == "0002_auth_rbac"


def test_initial_migration_contains_spatial_schema():
    from pathlib import Path
    import importlib.util
    root = Path(__file__).resolve().parents[1]
    path = root / "alembic/versions/0001_postgis_initial.py"
    spec = importlib.util.spec_from_file_location("initial_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert len(mod.DDL) == 19
    assert "CREATE EXTENSION IF NOT EXISTS postgis" in mod.DDL[0]
    assert sum(s.startswith("CREATE TABLE") for s in mod.DDL) == 9
    assert sum(s.startswith("CREATE INDEX") for s in mod.DDL) == 9
