from types import SimpleNamespace
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import pytest
import jwt
from fastapi import HTTPException
from fastapi.testclient import TestClient
from spectra.core.config import Settings, get_settings
from spectra.main import create_app
from spectra.persistence.database import get_db
from spectra.persistence.models import Base, User, ProjectMembership
from spectra.security.auth import hash_password, verify_password, issue_token, authorize_project, current_user

KEY='t'*48
@pytest.fixture
def configured():
    get_settings.cache_clear()
    app=create_app()
    app.dependency_overrides[get_settings]=lambda: Settings(jwt_secret=KEY)
    # auth reads config singleton; monkeypatch it at module level for unit tests.
    import spectra.security.auth as auth
    original=auth.get_settings
    auth.get_settings=lambda: Settings(jwt_secret=KEY)
    yield app
    auth.get_settings=original
    app.dependency_overrides.clear()


def user(**kwargs):
    data=dict(id=uuid4(),email='test@example.org',password_hash=hash_password('verylongpassword123'),is_active=True,is_platform_admin=False)
    data.update(kwargs)
    return SimpleNamespace(**data)


def test_hashing_argon2id_and_wrong_password():
    encoded=hash_password('verylongpassword123')
    assert encoded.startswith('$argon2id$')
    assert verify_password('verylongpassword123',encoded)
    assert not verify_password('wrong',encoded)
    with pytest.raises(ValueError): hash_password('short')


def test_new_tables_and_roles():
    assert {'users','project_memberships'}.issubset(Base.metadata.tables)
    assert {'user_id','project_id','role'}.issubset(Base.metadata.tables['project_memberships'].columns.keys())


def test_jwt_issuer_audience_expiry_and_signature(configured):
    u=user()
    token,secs=issue_token(u)
    assert secs==900
    payload=jwt.decode(token,KEY,algorithms=['HS256'],issuer='spectra-sar',audience='spectra-sar-api')
    assert payload['sub']==str(u.id)
    with pytest.raises(jwt.InvalidAudienceError):jwt.decode(token,KEY,algorithms=['HS256'],audience='other',issuer='spectra-sar')
    with pytest.raises(jwt.InvalidSignatureError):jwt.decode(token,'wrong-key',algorithms=['HS256'],audience='spectra-sar-api',issuer='spectra-sar')


def test_project_roles_and_nonmember_denied():
    u=user(); pid=uuid4()
    db=Mock()
    db.execute.return_value.scalar_one_or_none.return_value=SimpleNamespace(role='viewer')
    assert authorize_project(db,u,pid,'viewer')=='viewer'
    with pytest.raises(HTTPException) as err:authorize_project(db,u,pid,'editor')
    assert err.value.status_code==403
    db.execute.return_value.scalar_one_or_none.return_value=None
    with pytest.raises(HTTPException) as err:authorize_project(db,u,pid)
    assert err.value.status_code==404
    assert authorize_project(db,user(is_platform_admin=True),pid)=='platform_admin'


def test_auth_http_login_me_and_cross_project(configured):
    u=user()
    db=Mock()
    db.execute.return_value.scalar_one_or_none.return_value=u
    db.get.return_value=u
    configured.dependency_overrides[get_db]=lambda:db
    client=TestClient(configured)
    assert client.get('/api/v1/auth/me').status_code==401
    assert client.post('/api/v1/auth/login',json={'email':u.email,'password':'wrong'}).status_code==401
    login=client.post('/api/v1/auth/login',json={'email':'TEST@example.org','password':'verylongpassword123'})
    assert login.status_code==200
    headers={'Authorization':'Bearer '+login.json()['access_token']}
    assert client.get('/api/v1/auth/me',headers=headers).json()['email']==u.email
    assert client.get('/api/v1/auth/me',headers={'Authorization':'Bearer invalid'}).status_code==401
    project=uuid4()
    db.execute.return_value.scalar_one_or_none.return_value=None
    assert client.get(f'/api/v1/auth/projects/{project}/artifacts',headers=headers).status_code==404
    assert client.get(f'/api/v1/auth/projects/{project}/jobs',headers=headers).status_code==404
    db.execute.return_value.scalar_one_or_none.return_value=SimpleNamespace(role='viewer')
    db.execute.return_value.all.return_value=[]
    assert client.get(f'/api/v1/auth/projects/{project}/artifacts',headers=headers).json()==[]
    assert client.get(f'/api/v1/auth/projects/{project}/jobs',headers=headers).json()==[]


def test_disabled_user_denied(configured):
    from fastapi.security import HTTPAuthorizationCredentials
    u=user(is_active=False);db=Mock();db.get.return_value=u
    token,_=issue_token(u)
    with pytest.raises(HTTPException) as err:
        current_user(HTTPAuthorizationCredentials(scheme='Bearer',credentials=token),db)
    assert err.value.status_code==401


def test_no_jwt_secret_fails_closed():
    import spectra.security.auth as auth
    original=auth.get_settings
    auth.get_settings=lambda: Settings(jwt_secret=None)
    try:
        with pytest.raises(HTTPException) as err:issue_token(user())
        assert err.value.status_code==503
    finally:auth.get_settings=original
