from fastapi.testclient import TestClient
from spectra.main import create_app

client = TestClient(create_app())


def test_liveness():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive", "components": None}
    assert response.headers.get("X-Request-ID")


def test_readiness_never_false_positive():
    response = client.get("/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "integration_not_verified"
    assert set(body["components"]) == {"database", "queue", "object_storage"}


def test_api_index():
    response = client.get("/api/v1/")
    assert response.status_code == 200
    assert response.json()["status"] == "scaffold"


def test_openapi():
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/health/live" in response.json()["paths"]


def test_request_id_header():
    response = client.get("/health/live", headers={"X-Request-ID": "m5-test-123"})
    assert response.headers["X-Request-ID"] == "m5-test-123"


def test_cors_allowlist():
    allowed = client.options("/health/live", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("Access-Control-Allow-Origin") == "http://localhost:3000"
    denied = client.options("/health/live", headers={"Origin": "https://not-trusted.example", "Access-Control-Request-Method": "GET"})
    assert denied.headers.get("Access-Control-Allow-Origin") is None
