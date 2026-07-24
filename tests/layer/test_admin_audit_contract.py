"""
Назначение файла: contract-тесты административной роли и журнала действий.

Как работает:
- проверяет, что admin может открыть /admin/audit;
- проверяет, что doctor получает 403 на административный журнал;
- проверяет, что AuditMiddleware пишет события для ключевых действий;
- проверяет, что auth-роуты создают события login_success/login_failed/logout;
- не подключается к реальной БД: запись журнала и чтение событий подменяются monkeypatch.

Что редактировать здесь:
- список действий, которые должны попадать в audit_events;
- правила доступа к admin-страницам;
- ожидаемые безопасные details, если поменяются подписи действий.

Что не редактировать здесь:
- настоящие пароли;
- SQL миграции;
- медицинские расчёты и шаблоны карточки пациента.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("DB_USER", "test_user")
os.environ.setdefault("DB_PASSWORD", "test_password")
os.environ.setdefault("SESSION_SECRET_KEY", "test-session-secret")

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.middleware import audit as audit_middleware
from app.repositories import audit_log
from app.routers import admin as admin_router
from app.routers import auth
from app.security import permissions


TEST_SESSION_COOKIE = "test_admin_audit_session"


@pytest.fixture()
def admin_session():
    return {
        "user_id": 1,
        "login": "admin",
        "display_name": "Администратор",
        "role": "admin",
        "doctor_id": None,
        "patient_id": None,
        "login_at": 1_700_000_000,
        "last_seen_at": 1_700_000_000,
    }


@pytest.fixture()
def doctor_session():
    return {
        "user_id": 2,
        "login": "doctor",
        "display_name": "Лобанова",
        "role": "doctor",
        "doctor_id": 7,
        "patient_id": None,
        "login_at": 1_700_000_000,
        "last_seen_at": 1_700_000_000,
    }


@pytest.fixture()
def captured_events(monkeypatch):
    events = []

    def fake_log_event(request, action, **kwargs):
        events.append(
            {
                "path": request.url.path if request is not None else None,
                "method": request.method if request is not None else None,
                "session_role": request.session.get("role") if request is not None else None,
                "session_login": request.session.get("display_name") if request is not None else None,
                "action": action,
                **kwargs,
            }
        )

    monkeypatch.setattr(audit_middleware, "log_audit_event", fake_log_event)
    return events


@pytest.fixture()
def audit_test_app(captured_events, admin_session, doctor_session):
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(audit_middleware.AuditMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        max_age=604800,
        same_site="lax",
        https_only=False,
    )

    @app.get("/set-admin")
    def set_admin(request: Request):
        request.session.clear()
        request.session.update(admin_session)
        return PlainTextResponse("admin ok")

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.clear()
        request.session.update(doctor_session)
        return PlainTextResponse("doctor ok")

    @app.get("/patients")
    def patients():
        return PlainTextResponse("patients")

    @app.get("/patient/{patient_id}")
    def patient(patient_id: int):
        return PlainTextResponse(f"patient {patient_id}")

    @app.get("/new-patient")
    def new_patient():
        return PlainTextResponse("new patient")

    @app.get("/new-appointment/{patient_id}")
    def new_appointment(patient_id: int):
        return PlainTextResponse(f"new appointment {patient_id}")

    @app.get("/export/{appointment_id}/docx")
    def export_docx(appointment_id: int):
        return PlainTextResponse(f"docx {appointment_id}")

    @app.get("/ckd-registry")
    def ckd_registry():
        return PlainTextResponse("registry")

    @app.get("/admin/audit")
    def audit_page():
        return PlainTextResponse("audit")

    @app.get("/forbidden")
    def forbidden():
        raise HTTPException(status_code=403, detail="forbidden")

    @app.get("/boom")
    def boom():
        raise RuntimeError("boom")

    @app.post("/auth/session/keepalive")
    def keepalive():
        return JSONResponse({"ok": True})

    @app.get("/static/app.css")
    def static_file():
        return PlainTextResponse("css")

    return app


@pytest.fixture()
def audit_client(audit_test_app):
    with TestClient(audit_test_app) as client:
        yield client


def test_01_current_user_reads_session(admin_session):
    request = SimpleNamespace(session=admin_session)

    user = permissions.current_user(request)

    assert user["user_id"] == 1
    assert user["role"] == "admin"
    assert user["display_name"] == "Администратор"


def test_02_require_admin_allows_admin(admin_session):
    request = SimpleNamespace(session=admin_session)

    permissions.require_admin(request)


def test_03_require_admin_blocks_doctor(doctor_session):
    request = SimpleNamespace(session=doctor_session)

    with pytest.raises(HTTPException) as exc:
        permissions.require_admin(request)

    assert exc.value.status_code == 403


def test_04_doctor_role_is_not_admin(doctor_session):
    request = SimpleNamespace(session=doctor_session)

    assert permissions.is_admin(request) is False
    assert permissions.is_doctor(request) is True


def _patch_admin_page_dependencies(monkeypatch):
    """Изолирует страницу журнала от БД и побочного логирования."""
    monkeypatch.setattr(admin_router, "get_audit_events", lambda **kwargs: [])
    monkeypatch.setattr(admin_router, "get_audit_summary", lambda **kwargs: {})
    monkeypatch.setattr(admin_router, "get_audit_action_choices", lambda: [])
    monkeypatch.setattr(admin_router, "get_audit_action_category_choices", lambda: [])
    monkeypatch.setattr(admin_router, "get_audit_role_choices", lambda: [])
    monkeypatch.setattr(admin_router, "log_audit_event", lambda *args, **kwargs: 1)


def test_05_admin_audit_page_requires_admin(monkeypatch, admin_session):
    _patch_admin_page_dependencies(monkeypatch)

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        https_only=False,
    )
    app.include_router(admin_router.router)

    @app.get("/set-admin")
    def set_admin(request: Request):
        request.session.update(admin_session)
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-admin")
        response = client.get("/admin/audit")

    assert response.status_code == 200
    assert "Журнал работы МИС" in response.text


def test_06_doctor_cannot_open_admin_audit_page(monkeypatch, doctor_session):
    _patch_admin_page_dependencies(monkeypatch)

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret-key",
        session_cookie=TEST_SESSION_COOKIE,
        https_only=False,
    )
    app.include_router(admin_router.router)

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update(doctor_session)
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/set-doctor")
        response = client.get("/admin/audit")

    assert response.status_code == 403


def test_07_audit_middleware_logs_patient_list(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/patients")

    assert captured_events[-1]["action"] == "open_patient_list"
    assert captured_events[-1]["session_role"] == "doctor"


def test_08_audit_middleware_logs_patient_card(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/patient/15")

    assert captured_events[-1]["action"] == "open_patient_card"
    assert captured_events[-1]["patient_id"] == 15


def test_09_audit_middleware_logs_specific_patient_appointment(
    audit_client,
    captured_events,
):
    audit_client.get("/set-doctor")
    audit_client.get("/patient/15?appointment_id=32")

    event = captured_events[-1]
    assert event["action"] == "open_patient_appointment"
    assert event["patient_id"] == 15
    assert event["appointment_id"] == 32
    assert event["details"] == "открыт конкретный приём в карточке пациента"


def test_10_audit_middleware_logs_new_patient_form(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/new-patient")

    assert captured_events[-1]["action"] == "open_new_patient_form"


def test_11_audit_middleware_logs_new_appointment_form(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/new-appointment/22")

    assert captured_events[-1]["action"] == "open_new_appointment_form"
    assert captured_events[-1]["patient_id"] == 22


def test_12_audit_middleware_logs_word_export(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/export/33/docx")

    assert captured_events[-1]["action"] == "download_word_report"
    assert captured_events[-1]["appointment_id"] == 33


def test_13_audit_middleware_logs_ckd_registry_open(audit_client, captured_events):
    audit_client.get("/set-admin")
    audit_client.get("/ckd-registry")

    assert captured_events[-1]["action"] == "open_ckd_registry"


def test_14_audit_middleware_logs_admin_audit_open(audit_client, captured_events):
    audit_client.get("/set-admin")
    audit_client.get("/admin/audit")

    assert captured_events[-1]["action"] == "open_admin_audit"


def test_15_audit_middleware_logs_403_as_access_denied(audit_client, captured_events):
    audit_client.get("/set-doctor")
    audit_client.get("/forbidden")

    assert captured_events[-1]["action"] == "access_denied"
    assert captured_events[-1]["result"] == "denied"


def test_16_audit_middleware_logs_server_error(audit_client, captured_events):
    audit_client.get("/set-doctor")

    with pytest.raises(RuntimeError):
        audit_client.get("/boom")

    assert captured_events[-1]["action"] == "server_error"
    assert captured_events[-1]["result"] == "error"


def test_17_audit_middleware_ignores_static_and_keepalive(audit_client, captured_events):
    audit_client.get("/set-doctor")
    initial_count = len(captured_events)

    audit_client.get("/static/app.css")
    audit_client.post("/auth/session/keepalive")

    assert len(captured_events) == initial_count


def test_18_classify_patients_with_query_marks_filters(admin_session):
    request = SimpleNamespace(
        url=SimpleNamespace(path="/patients", query="search=Иванов"),
        method="GET",
    )

    event = audit_middleware.classify_request(request, 200)

    assert event.action == "open_patient_list"
    assert event.details == "открыт список с фильтрами"


def test_19_action_labels_contain_admin_events():
    assert audit_log.ACTION_LABELS["open_admin_audit"] == "Открыл журнал работы МИС"
    assert audit_log.ACTION_LABELS["open_patient_appointment"] == "Открыл конкретный приём пациента"
    assert audit_log.ACTION_CATEGORIES["open_patient_appointment"] == "view"
    assert audit_log.ACTION_LABELS["access_denied"] == "Отказано в доступе"


def test_20_decorated_event_has_sentence():
    raw = {
        "action": "open_patient_card",
        "result": "success",
        "user_login": "Лобанова",
        "patient_name": "Иванов Иван Иванович",
        "details": None,
        "error_message": None,
    }

    decorated = audit_log._decorate_event(raw)

    assert decorated["action_label"] == "Открыл карточку пациента"
    assert "Лобанова" in decorated["event_sentence"]
    assert "Иванов Иван Иванович" in decorated["event_sentence"]


def test_21_auth_login_success_writes_audit_event(monkeypatch):
    events = []
    fake_user = {
        "id": 1,
        "login": "admin",
        "password_hash": auth.make_password_hash("secret", iterations=1000),
        "role": "admin",
        "doctor_id": None,
        "patient_id": None,
        "display_name": "Администратор",
    }

    monkeypatch.setattr(auth, "get_user_by_login", lambda login: fake_user)
    monkeypatch.setattr(auth, "log_audit_event", lambda request, action, **kwargs: events.append((action, kwargs)))

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key", session_cookie=TEST_SESSION_COOKIE)
    app.include_router(auth.router)

    with TestClient(app) as client:
        response = client.post("/login", data={"login": "admin", "password": "secret", "next": "/"}, follow_redirects=False)

    assert response.status_code == 303
    assert events[-1][0] == "login_success"


def test_22_auth_login_failed_writes_audit_event(monkeypatch):
    events = []

    monkeypatch.setattr(auth, "get_user_by_login", lambda login: None)
    monkeypatch.setattr(auth, "log_audit_event", lambda request, action, **kwargs: events.append((action, kwargs)))

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key", session_cookie=TEST_SESSION_COOKIE)
    app.include_router(auth.router)

    with TestClient(app) as client:
        response = client.post("/login", data={"login": "bad", "password": "wrong", "next": "/"}, follow_redirects=False)

    assert response.status_code == 401
    assert events[-1][0] == "login_failed"
    assert events[-1][1]["result"] == "error"


def test_23_audit_repository_log_event_does_not_raise_when_db_fails(monkeypatch, admin_session):
    class BrokenConnection:
        def __enter__(self):
            raise RuntimeError("db unavailable")
        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(audit_log, "get_db_connection", lambda: BrokenConnection())
    request = SimpleNamespace(
        session=admin_session,
        url=SimpleNamespace(path="/patient/1"),
        method="GET",
        client=SimpleNamespace(host="127.0.0.1"),
    )

    audit_log.log_audit_event(request, "open_patient_card", patient_id=1)


def test_24_middleware_does_not_log_without_session(captured_events):
    app = FastAPI()
    app.add_middleware(audit_middleware.AuditMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key", session_cookie=TEST_SESSION_COOKIE)

    @app.get("/patient/{patient_id}")
    def patient(patient_id: int):
        return PlainTextResponse("ok")

    with TestClient(app) as client:
        client.get("/patient/1")

    assert captured_events == []


def test_25_audit_list_uses_one_details_button():
    """В ленте журнала у каждого действия должна быть одна кнопка подробностей."""
    template = Path("app/templates/admin/audit.html").read_text(encoding="utf-8")

    assert 'href="/admin/audit/{{ event.id }}">Подробнее</a>' in template
    assert '>Событие</a>' not in template
    assert 'href="/admin/audit/appointment/{{ event.appointment_id }}">Приём</a>' not in template
