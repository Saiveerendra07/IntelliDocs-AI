import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.core.config import settings

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["app"] == settings.APP_NAME
    assert data["version"] == settings.APP_VERSION


def test_api_v1_health_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_root_endpoint():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "Welcome to IntelliDocs AI" in data["message"]


def test_404_error_format():
    response = client.get("/non-existent-endpoint-test")
    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "HTTP_404"


def test_settings_cors_parsing():
    from backend.app.core.config import Settings
    custom = Settings(CORS_ORIGINS="http://localhost:3000, http://example.com")
    assert "http://localhost:3000" in custom.CORS_ORIGINS
    assert "http://example.com" in custom.CORS_ORIGINS
