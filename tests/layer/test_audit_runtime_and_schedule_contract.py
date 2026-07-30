"""Проверки подключения аудита и журналирования действий расписания."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path
from types import SimpleNamespace

from app.middleware import audit as audit_middleware
from app.repositories import audit_log
from app.routers import schedule


ROOT = Path(__file__).resolve().parents[2]


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        session={
            "user_id": 10,
            "login": "doctor",
            "display_name": "Врач",
            "role": "doctor",
            "doctor_id": 7,
        }
    )


def test_audit_middleware_is_connected_after_logging_and_before_session():
    source = (ROOT / "app" / "main.py").read_text(encoding="utf-8")

    assert "from .middleware.audit import AuditMiddleware" in source
    logging_position = source.index("app.add_middleware(LoggingMiddleware)")
    audit_position = source.index("app.add_middleware(AuditMiddleware)")
    session_position = source.index("SessionMiddleware,")

    assert logging_position < audit_position < session_position


def test_schedule_and_admin_pages_are_classified_by_middleware():
    schedule_request = SimpleNamespace(
        url=SimpleNamespace(path="/schedule", query=""),
        method="GET",
    )
    admin_request = SimpleNamespace(
        url=SimpleNamespace(path="/admin/audit", query=""),
        method="GET",
    )

    schedule_event = audit_middleware.classify_request(schedule_request, 200)
    admin_event = audit_middleware.classify_request(admin_request, 200)

    assert schedule_event is not None
    assert schedule_event.action == "open_schedule"
    assert admin_event is not None
    assert admin_event.action == "open_admin_audit"


def test_schedule_actions_have_readable_labels():
    assert audit_log.ACTION_LABELS["create_schedule_entry"] == "Создал запись в расписании"
    assert audit_log.ACTION_LABELS["change_schedule_status"] == "Изменил статус записи"
    assert audit_log.ACTION_CATEGORIES["create_walk_in_schedule_entry"] == "appointment"


def test_schedule_create_entry_writes_audit_event(monkeypatch):
    events = []
    item = {
        "id": 15,
        "patient_id": 22,
        "appointment_id": None,
        "starts_at": "2026-08-01T09:00:00",
    }

    monkeypatch.setattr(schedule, "_require_schedule_access", lambda request: None)
    monkeypatch.setattr(schedule, "create_schedule_entry", lambda **kwargs: item)
    monkeypatch.setattr(
        schedule,
        "log_audit_event",
        lambda request, action, **kwargs: events.append((action, kwargs)),
    )

    payload = schedule.ScheduleEntryPayload(
        appointment_date=date(2026, 8, 1),
        scheduled_doctor_id=7,
        location_id=2,
        starts_at=time(9, 0),
        ends_at=time(9, 30),
        patient_id=22,
    )
    response = schedule.schedule_create_entry(payload, _request())

    assert response["item"] == item
    assert events[-1][0] == "create_schedule_entry"
    assert events[-1][1]["patient_id"] == 22
    assert events[-1][1]["entity_id"] == 15


def test_schedule_status_and_walk_in_write_audit_events(monkeypatch):
    events = []
    request = _request()

    monkeypatch.setattr(schedule, "_require_schedule_access", lambda request: None)
    monkeypatch.setattr(schedule, "require_doctor_with_id", lambda request: 7)
    monkeypatch.setattr(
        schedule,
        "set_schedule_entry_status",
        lambda **kwargs: {
            "id": 18,
            "patient_id": 31,
            "appointment_id": None,
            "starts_at": "2026-08-02T10:00:00",
        },
    )
    monkeypatch.setattr(
        schedule,
        "create_walk_in_schedule_entry",
        lambda **kwargs: {
            "id": 19,
            "patient_id": 31,
            "appointment_id": None,
            "starts_at": "2026-07-30T16:00:00",
        },
    )
    monkeypatch.setattr(
        schedule,
        "log_audit_event",
        lambda request, action, **kwargs: events.append((action, kwargs)),
    )

    schedule.schedule_update_status(
        18,
        schedule.ScheduleStatusPayload(status="no_show"),
        request,
    )
    schedule.patient_create_walk_in(
        31,
        schedule.WalkInAppointmentPayload(
            action="keep_and_create",
            scheduled_entry_id=18,
        ),
        request,
    )

    assert events[0][0] == "change_schedule_status"
    assert "не явился" in events[0][1]["details"]
    assert events[1][0] == "create_walk_in_schedule_entry"
    assert "будущая запись сохранена" in events[1][1]["details"]


def test_audit_page_keeps_advanced_filters_collapsed_and_table_compact():
    source = (ROOT / "app" / "templates" / "admin" / "audit.html").read_text(
        encoding="utf-8"
    )

    assert "Дополнительные фильтры" in source
    assert "Только проблемы" in source
    assert "Скачать CSV" in source
    assert "Пациент / приём" not in source
    assert source.count("<th") <= 7
