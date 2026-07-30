from __future__ import annotations

import os
from types import SimpleNamespace

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth


TEST_IDLE_TIMEOUT_SECONDS = 60
TEST_SESSION_COOKIE = "test_mis_session"


@pytest.fixture()
def fast_clock(monkeypatch):
    current = {"value": 1_700_000_000}
    monkeypatch.setattr(auth, "now_ts", lambda: current["value"])
    return current


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(
        auth,
        "settings",
        SimpleNamespace(session_idle_timeout_seconds=TEST_IDLE_TIMEOUT_SECONDS),
    )
    monkeypatch.setattr(auth, "log_audit_event", lambda *args, **kwargs: None)

    doctor = {
        "id": 1,
        "login": "doctor",
        "password_hash": auth.make_password_hash("secret", iterations=1000),
        "role": "doctor",
        "doctor_id": 7,
        "patient_id": None,
        "display_name": "Тестовый врач",
    }
    monkeypatch.setattr(
        auth,
        "get_user_by_login",
        lambda login: doctor if login == "doctor" else None,
    )

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    @app.exception_handler(auth.AuthenticationRequired)
    async def handle_auth_error(request: Request, exc: auth.AuthenticationRequired):
        return auth.unauthorized_response(request, exc.reason)

    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        max_age=604800,
        same_site="lax",
        https_only=False,
    )

    app.include_router(auth.router)

    protected = APIRouter(
        dependencies=[Depends(auth.require_authenticated_user)]
    )

    @protected.get("/")
    def home():
        return PlainTextResponse("home")

    @protected.get("/patient/{patient_id}")
    def patient(patient_id: int):
        return PlainTextResponse(f"patient {patient_id}")

    @protected.get("/api/protected")
    def api():
        return JSONResponse({"ok": True})

    app.include_router(protected)

    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient):
    return client.post(
        "/login",
        data={"login": "doctor", "password": "secret", "next": "/"},
        follow_redirects=False,
    )


def test_login_is_public(client):
    assert client.get("/login").status_code == 200


def test_html_route_without_session_redirects(client):
    response = client.get("/patient/1", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_api_without_session_returns_401(client):
    response = client.get("/api/protected", follow_redirects=False)
    assert response.status_code == 401
    assert response.json()["reason"] == "not_authenticated"


def test_doctor_can_open_any_patient_after_login(client):
    assert login(client).status_code == 303
    assert client.get("/patient/1").status_code == 200
    assert client.get("/patient/999999").status_code == 200


def test_logout_and_session_endpoints_are_protected(client):
    assert client.get("/logout", follow_redirects=False).status_code == 303
    assert client.post("/auth/session/keepalive").status_code == 401
    assert client.get("/auth/session/status").status_code == 401


def test_logout_clears_session(client):
    login(client)
    assert client.get("/logout", follow_redirects=False).status_code == 303
    assert client.get("/patient/1", follow_redirects=False).status_code == 303


def test_idle_timeout_is_enforced(client, fast_clock):
    login(client)
    fast_clock["value"] += TEST_IDLE_TIMEOUT_SECONDS + 1
    response = client.get("/api/protected", follow_redirects=False)
    assert response.status_code == 401
    assert response.json()["reason"] == "idle_timeout"


def test_keepalive_extends_session(client, fast_clock):
    login(client)
    fast_clock["value"] += 50
    assert client.post("/auth/session/keepalive").status_code == 200
    fast_clock["value"] += 55
    assert client.get("/patient/1").status_code == 200


def test_safe_next_url_and_password_hash():
    assert auth.safe_next_url("/patient/1") == "/patient/1"
    assert auth.safe_next_url("https://evil.example") == "/"
    password_hash = auth.make_password_hash("secret", iterations=1000)
    assert "secret" not in password_hash
    assert auth.verify_password("secret", password_hash)
