from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.middleware import audit as audit_middleware
from app.repositories import audit_log


def _client(monkeypatch):
    events = []

    def fake_log_event(request, action, **kwargs):
        events.append({"action": action, **kwargs})

    monkeypatch.setattr(audit_middleware, "log_audit_event", fake_log_event)
    app = FastAPI()
    app.add_middleware(audit_middleware.AuditMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret")

    @app.get("/set-user")
    def set_user(request: Request):
        request.session.update({"user_id": 17, "role": "chief_physician"})
        return PlainTextResponse("ok")

    @app.get("/ckd-registry")
    def page():
        return PlainTextResponse("ok")

    @app.get("/ckd-registry/export.xlsx")
    def export():
        return PlainTextResponse("ok")

    @app.post("/ckd-registry/patient/{patient_id}/include")
    def include(patient_id: int):
        return PlainTextResponse("ok")

    @app.post("/ckd-registry/patient/{patient_id}/outcome")
    def outcome(patient_id: int):
        return PlainTextResponse("ok")

    return TestClient(app), events


def test_local_registry_actions_are_audited(monkeypatch):
    client, events = _client(monkeypatch)
    with client:
        client.get("/set-user")
        client.get("/ckd-registry")
        client.get("/ckd-registry", params={"stage": "С4"})
        client.get("/ckd-registry/export.xlsx")
        client.post("/ckd-registry/patient/11/include")
        client.post("/ckd-registry/patient/11/outcome")

    assert [event["action"] for event in events[-5:]] == [
        "open_local_ckd_registry",
        "filter_local_ckd_registry",
        "export_local_ckd_registry",
        "include_local_ckd_registry_patient",
        "add_local_ckd_registry_outcome",
    ]
    assert events[-2]["patient_id"] == 11
    assert events[-1]["patient_id"] == 11


def test_local_registry_actions_have_readable_labels():
    assert audit_log.ACTION_LABELS["open_local_ckd_registry"] == "Открыл регистр ХБП"
    assert audit_log.ACTION_LABELS["export_local_ckd_registry"] == "Выгрузил регистр ХБП"
    assert audit_log.ACTION_CATEGORIES["export_local_ckd_registry"] == "export"
    assert audit_log.ACTION_CATEGORIES["add_local_ckd_registry_outcome"] == "patient"
