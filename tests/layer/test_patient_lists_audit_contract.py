"""Contract-тесты аудита страницы динамических списков пациентов."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.middleware.sessions import SessionMiddleware

from app.middleware import audit as audit_middleware
from app.repositories import audit_log


def _client(monkeypatch):
    events: list[dict] = []

    def fake_log_event(request, action, **kwargs):
        events.append({"action": action, **kwargs})

    monkeypatch.setattr(audit_middleware, "log_audit_event", fake_log_event)

    app = FastAPI()
    app.add_middleware(audit_middleware.AuditMiddleware)
    app.add_middleware(SessionMiddleware, secret_key="test-secret-key")

    @app.get("/set-doctor")
    def set_doctor(request: Request):
        request.session.update({"user_id": 7, "role": "doctor", "display_name": "Врач"})
        return PlainTextResponse("ok")

    @app.get("/patient-lists")
    def patient_lists():
        return PlainTextResponse("page")

    @app.get("/patient-lists/export.csv")
    def patient_lists_export():
        return PlainTextResponse("csv")

    return TestClient(app), events


def test_patient_lists_open_is_audited(monkeypatch):
    client, events = _client(monkeypatch)
    with client:
        client.get("/set-doctor")
        client.get("/patient-lists")

    event = events[-1]
    assert event["action"] == "open_patient_lists"
    assert event["details"] == "открыта страница списков пациентов"


def test_patient_lists_filter_is_audited_without_patient_data(monkeypatch):
    client, events = _client(monkeypatch)
    with client:
        client.get("/set-doctor")
        client.get(
            "/patient-lists",
            params={
                "indicator": "egfr",
                "mode": "category",
                "egfr_category": "С4",
                "period_months": "6",
            },
        )

    event = events[-1]
    assert event["action"] == "filter_patient_lists"
    assert "показатель: СКФ" in event["details"]
    assert "категория: С4" in event["details"]
    assert "за 6 месяцев" in event["details"]


def test_patient_lists_csv_export_is_audited(monkeypatch):
    client, events = _client(monkeypatch)
    with client:
        client.get("/set-doctor")
        client.get(
            "/patient-lists/export.csv",
            params={
                "indicator": "hemoglobin",
                "operator": "lt",
                "value_from": "120",
                "period_months": "3",
            },
        )

    event = events[-1]
    assert event["action"] == "export_patient_lists"
    assert "показатель: гемоглобин" in event["details"]
    assert "условие: ниже 120" in event["details"]
    assert "за 3 месяца" in event["details"]


def test_patient_lists_actions_have_readable_labels_and_categories():
    assert audit_log.ACTION_LABELS["open_patient_lists"] == "Открыл списки пациентов"
    assert audit_log.ACTION_LABELS["filter_patient_lists"] == "Сформировал список пациентов"
    assert audit_log.ACTION_LABELS["export_patient_lists"] == "Выгрузил список пациентов"
    assert audit_log.ACTION_CATEGORIES["filter_patient_lists"] == "view"
    assert audit_log.ACTION_CATEGORIES["export_patient_lists"] == "export"
