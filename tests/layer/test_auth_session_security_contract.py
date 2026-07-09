"""
Назначение файла: contract-тесты базовой безопасности сессий МИС.

Как работает:
- поднимает маленькое тестовое FastAPI-приложение с тем же AuthRequiredMiddleware,
  SessionMiddleware и auth.router, что используются в основном приложении;
- не подключается к реальной БД: пользователя подменяем через monkeypatch;
- проверяет, что публичны только /login и /static/*;
- проверяет, что внутренние страницы, Word-export и API закрыты без active session;
- проверяет, что idle-timeout выкидывает пользователя после бездействия;
- проверяет, что keepalive продлевает сессию, когда врач реально работает.

Что редактировать здесь:
- список критичных внутренних URL, которые должны быть закрыты;
- ожидаемый idle-timeout в тестовой настройке;
- тестовые роли/логины при появлении полноценного ролевого доступа.

Что не редактировать здесь:
- медицинскую логику;
- SQL-запросы;
- реальные пароли пользователей.
"""

from __future__ import annotations

import os
from types import SimpleNamespace

# Эти значения нужны только на случай, если тест запускается в чистой среде без .env.
# Они не используются как реальные пароли пользователей МИС.
os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.routers import auth


TEST_SESSION_COOKIE = "test_mis_session"
TEST_IDLE_TIMEOUT_SECONDS = 60


@pytest.fixture()
def fast_clock(monkeypatch):
    """
    Управляемое время для проверки idle-timeout.

    Вместо реального ожидания 60 минут тесты двигают timestamp вручную.
    """
    current = {"value": 1_700_000_000}

    def fake_now_ts() -> int:
        return current["value"]

    monkeypatch.setattr(auth, "now_ts", fake_now_ts)
    return current


@pytest.fixture()
def auth_settings(monkeypatch):
    """
    Тестовые настройки auth-модуля.

    Здесь idle-timeout равен 60 секундам, чтобы быстро проверять истечение сессии.
    """
    fake_settings = SimpleNamespace(session_idle_timeout_seconds=TEST_IDLE_TIMEOUT_SECONDS)
    monkeypatch.setattr(auth, "settings", fake_settings)
    return fake_settings


@pytest.fixture()
def fake_user():
    """Тестовый пользователь с password_hash, без хранения открытого пароля в БД."""
    return {
        "id": 1,
        "login": "admin",
        "password_hash": auth.make_password_hash("secret", iterations=1000),
        "role": "admin",
        "doctor_id": None,
        "patient_id": None,
        "display_name": "Администратор",
    }


@pytest.fixture()
def test_app(auth_settings):
    """
    Мини-приложение для проверки security-контракта.

    Оно не зависит от настоящих маршрутов пациентов и БД, но использует настоящий
    AuthRequiredMiddleware и настоящие login/logout/session endpoints.
    """
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    app.add_middleware(auth.AuthRequiredMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        max_age=604800,
        same_site="lax",
        https_only=False,
    )

    app.include_router(auth.router)

    @app.get("/")
    def internal_home():
        return PlainTextResponse("internal home")

    @app.get("/patient/{patient_id}")
    def patient_card(patient_id: int):
        return PlainTextResponse(f"patient {patient_id}")

    @app.get("/new-appointment/{patient_id}")
    def new_appointment(patient_id: int):
        return PlainTextResponse(f"new appointment {patient_id}")

    @app.get("/export/{appointment_id}/docx")
    def export_docx(appointment_id: int):
        return Response(
            b"fake docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    @app.get("/api/protected")
    def protected_api():
        return JSONResponse({"ok": True})

    @app.get("/static/{path:path}")
    def static_file(path: str):
        return PlainTextResponse(f"static {path}")

    return app


@pytest.fixture()
def client(test_app):
    """TestClient сохраняет cookies как браузер: это позволяет проверять сессии."""
    with TestClient(test_app) as test_client:
        yield test_client


def patch_valid_user(monkeypatch, fake_user):
    """Подменяет поиск пользователя без обращения к реальной БД."""
    def fake_get_user_by_login(login: str):
        if login == "admin":
            return fake_user
        return None

    monkeypatch.setattr(auth, "get_user_by_login", fake_get_user_by_login)


def login_as_admin(client: TestClient, monkeypatch, fake_user, next_url: str = "/"):
    """Выполняет настоящий POST /login и создаёт session-cookie."""
    patch_valid_user(monkeypatch, fake_user)
    return client.post(
        "/login",
        data={"login": "admin", "password": "secret", "next": next_url},
        follow_redirects=False,
    )


def assert_redirects_to_login(response):
    """Проверяет, что HTML-страница без сессии ушла на login."""
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login?next=")


def test_01_login_page_is_public(client):
    response = client.get("/login", follow_redirects=False)

    assert response.status_code == 200


def test_02_static_files_are_public_for_login_design(client):
    response = client.get("/static/css/04_kdigo_risk.css", follow_redirects=False)

    assert response.status_code == 200
    assert response.text == "static css/04_kdigo_risk.css"


def test_03_logout_is_not_public_page_without_session(client):
    response = client.get("/logout", follow_redirects=False)

    assert_redirects_to_login(response)
    assert "%2Flogout" in response.headers["location"]


def test_04_root_without_session_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)

    assert_redirects_to_login(response)
    assert response.headers["location"] == "/login?next=%2F"


def test_05_patient_card_without_session_redirects_to_login(client):
    response = client.get("/patient/1", follow_redirects=False)

    assert_redirects_to_login(response)
    assert "%2Fpatient%2F1" in response.headers["location"]


def test_06_new_appointment_without_session_redirects_to_login(client):
    response = client.get("/new-appointment/1", follow_redirects=False)

    assert_redirects_to_login(response)
    assert "%2Fnew-appointment%2F1" in response.headers["location"]


def test_07_word_export_without_session_redirects_to_login(client):
    response = client.get("/export/1/docx", follow_redirects=False)

    assert_redirects_to_login(response)
    assert "%2Fexport%2F1%2Fdocx" in response.headers["location"]


def test_08_next_url_preserves_query_string(client):
    response = client.get("/patient/1?appointment_id=26", follow_redirects=False)

    assert_redirects_to_login(response)
    assert "%2Fpatient%2F1%3Fappointment_id%3D26" in response.headers["location"]


def test_09_api_without_session_returns_401_json(client):
    response = client.get("/api/protected", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["authenticated"] is False
    assert response.json()["reason"] == "not_authenticated"


def test_10_keepalive_without_session_returns_401_json(client):
    response = client.post("/auth/session/keepalive", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["authenticated"] is False


def test_11_status_without_session_returns_401_json(client):
    response = client.get("/auth/session/status", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["authenticated"] is False


def test_12_docs_without_session_are_not_public(client):
    response = client.get("/docs", follow_redirects=False)

    assert_redirects_to_login(response)


def test_13_redoc_without_session_is_not_public(client):
    response = client.get("/redoc", follow_redirects=False)

    assert_redirects_to_login(response)


def test_14_openapi_without_session_is_not_public(client):
    response = client.get("/openapi.json", follow_redirects=False)

    assert_redirects_to_login(response)


def test_15_valid_login_creates_session_cookie_and_redirects_to_next(
    client, monkeypatch, fake_user
):
    response = login_as_admin(client, monkeypatch, fake_user, next_url="/patient/1")

    assert response.status_code == 303
    assert response.headers["location"] == "/patient/1"
    assert client.cookies.get(TEST_SESSION_COOKIE)


def test_16_invalid_login_does_not_open_internal_pages(client, monkeypatch):
    monkeypatch.setattr(auth, "get_user_by_login", lambda login: None)

    response = client.post(
        "/login",
        data={"login": "admin", "password": "wrong", "next": "/patient/1"},
        follow_redirects=False,
    )
    protected_response = client.get("/patient/1", follow_redirects=False)

    assert response.status_code == 401
    assert_redirects_to_login(protected_response)


def test_17_closing_tab_does_not_logout_before_idle_timeout(
    client, monkeypatch, fake_user
):
    """
    Закрытая вкладка сама по себе не является logout.

    Пока session-cookie жива и idle-timeout не истёк, повторное открытие / должно пустить
    пользователя внутрь. Именно это пользователь видит в браузере после закрытия вкладки.
    """
    login_response = login_as_admin(client, monkeypatch, fake_user)
    response_after_reopen = client.get("/", follow_redirects=False)

    assert login_response.status_code == 303
    assert response_after_reopen.status_code == 200
    assert response_after_reopen.text == "internal home"


def test_18_logged_in_user_can_open_root(client, monkeypatch, fake_user):
    login_as_admin(client, monkeypatch, fake_user)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200


def test_19_logged_in_user_can_open_patient_card(client, monkeypatch, fake_user):
    login_as_admin(client, monkeypatch, fake_user)

    response = client.get("/patient/1", follow_redirects=False)

    assert response.status_code == 200
    assert response.text == "patient 1"


def test_20_logged_in_user_can_use_internal_api(client, monkeypatch, fake_user):
    login_as_admin(client, monkeypatch, fake_user)

    response = client.get("/api/protected", follow_redirects=False)

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_21_logged_in_user_can_download_word_export(client, monkeypatch, fake_user):
    login_as_admin(client, monkeypatch, fake_user)

    response = client.get("/export/1/docx", follow_redirects=False)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


def test_22_login_page_for_active_session_redirects_to_next(
    client, monkeypatch, fake_user
):
    login_as_admin(client, monkeypatch, fake_user)

    response = client.get("/login?next=/patient/1", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/patient/1"


def test_23_logout_clears_session(client, monkeypatch, fake_user):
    login_as_admin(client, monkeypatch, fake_user)

    logout_response = client.get("/logout", follow_redirects=False)
    protected_response = client.get("/patient/1", follow_redirects=False)

    assert logout_response.status_code == 303
    assert logout_response.headers["location"] == "/login"
    assert_redirects_to_login(protected_response)


def test_24_idle_timeout_redirects_html_to_login(
    client, monkeypatch, fake_user, fast_clock
):
    login_as_admin(client, monkeypatch, fake_user)

    fast_clock["value"] += TEST_IDLE_TIMEOUT_SECONDS + 1
    response = client.get("/patient/1", follow_redirects=False)

    assert_redirects_to_login(response)


def test_25_idle_timeout_returns_401_for_api(
    client, monkeypatch, fake_user, fast_clock
):
    login_as_admin(client, monkeypatch, fake_user)

    fast_clock["value"] += TEST_IDLE_TIMEOUT_SECONDS + 1
    response = client.get("/api/protected", follow_redirects=False)

    assert response.status_code == 401
    assert response.json()["reason"] == "idle_timeout"


def test_26_keepalive_extends_session_when_user_is_active(
    client, monkeypatch, fake_user, fast_clock
):
    login_as_admin(client, monkeypatch, fake_user)

    # Через 50 секунд сессия ещё активна. Keepalive обновляет last_seen_at.
    fast_clock["value"] += 50
    keepalive_response = client.post("/auth/session/keepalive", follow_redirects=False)

    # Прошло 105 секунд после login, но только 55 секунд после keepalive.
    # Сессия должна быть активна.
    fast_clock["value"] += 55
    protected_response = client.get("/patient/1", follow_redirects=False)

    assert keepalive_response.status_code == 200
    assert keepalive_response.json()["authenticated"] is True
    assert protected_response.status_code == 200


def test_27_safe_next_url_accepts_only_local_paths():
    assert auth.safe_next_url("/patient/1") == "/patient/1"
    assert auth.safe_next_url("/patient/1?appointment_id=26") == (
        "/patient/1?appointment_id=26"
    )


@pytest.mark.parametrize(
    "unsafe_next",
    [
        "https://evil.example/patient/1",
        "http://evil.example/patient/1",
        "//evil.example/patient/1",
        "patient/1",
        "/patient/1\nSet-Cookie:bad=true",
        "",
        None,
    ],
)
def test_28_safe_next_url_rejects_external_or_invalid_urls(unsafe_next):
    assert auth.safe_next_url(unsafe_next) == "/"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/login", True),
        ("/static/app.css", True),
        ("/logout", False),
        ("/docs", False),
        ("/redoc", False),
        ("/openapi.json", False),
        ("/patient/1", False),
        ("/auth/session/keepalive", False),
    ],
)
def test_29_public_path_contract(path, expected):
    assert auth.is_public_path(path) is expected


def test_30_password_hash_does_not_store_plain_password():
    password_hash = auth.make_password_hash("very-secret-password", iterations=1000)

    assert "very-secret-password" not in password_hash
    assert password_hash.startswith("pbkdf2_sha256$")
    assert auth.verify_password("very-secret-password", password_hash) is True
    assert auth.verify_password("wrong-password", password_hash) is False
