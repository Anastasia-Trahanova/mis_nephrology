from __future__ import annotations

import os

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.main import app
from app.routers import auth


@pytest.fixture()
def client():
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


def test_trusted_host_middleware_is_connected():
    middleware_classes = [item.cls for item in app.user_middleware]
    assert TrustedHostMiddleware in middleware_classes
    assert all(item.__name__ != "AuthRequiredMiddleware" for item in middleware_classes)


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "testserver.evil.example",
        "testserver%2Flogin",
        "testserver%3Fnext=%2Flogin",
        "user@testserver",
        r"testserver\login",
    ],
)
def test_rejects_invalid_or_encoded_host(client: TestClient, host: str):
    response = client.get(
        "/login",
        headers={"host": host},
        follow_redirects=False,
    )
    assert response.status_code == 400


@pytest.mark.parametrize("host", ["testserver", "localhost", "127.0.0.1"])
def test_accepts_configured_host(client: TestClient, host: str):
    response = client.get(
        "/login",
        headers={"host": host},
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_protected_router_redirects_without_session(client: TestClient):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login?next=%2F"
