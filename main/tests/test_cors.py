from fastapi.testclient import TestClient

from app.config import cors_settings
from app.main import app

client = TestClient(app, base_url="http://testserver/api")


def test_cors_allows_frontend_origin():
    response = client.get("/", headers={"Origin": cors_settings.frontend_origin})
    assert response.headers["access-control-allow-origin"] == cors_settings.frontend_origin


def test_cors_preflight_allows_authorization_header():
    response = client.options(
        "/auth/me",
        headers={
            "Origin": cors_settings.frontend_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == cors_settings.frontend_origin
    assert "authorization" in response.headers["access-control-allow-headers"].lower()


def test_cors_ignores_other_origin():
    response = client.get("/", headers={"Origin": "https://evil.example.com"})
    assert "access-control-allow-origin" not in response.headers
