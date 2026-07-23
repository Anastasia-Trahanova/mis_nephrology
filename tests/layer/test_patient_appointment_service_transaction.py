"""
Что тестируется:
- patient_appointment_service.py как транзакционный слой;
- создание пациента с телефоном и первого приёма;
- сохранение возраста на дату приёма;
- создание нового приёма существующему пациенту;
- commit при успехе;
- rollback и HTTPException при ошибке сохранения.

Тест не пишет в реальную БД: подключение, repositories и сохранение деталей
заменяются monkeypatch-ами.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest
from fastapi import HTTPException

import app.services.patient_appointment_service as svc

from .factories import FakeCursor, full_fake_form


class FakeCursorContext:
    def __init__(self, cursor: FakeCursor):
        self.cursor = cursor

    def __enter__(self):
        return self.cursor

    def __exit__(self, exc_type, exc, tb):
        return False


class FakeConnection:
    def __init__(self):
        self.cursor_obj = FakeCursor()
        self.committed = False
        self.rolled_back = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return FakeCursorContext(self.cursor_obj)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def _patch_common(monkeypatch, conn: FakeConnection):
    monkeypatch.setattr(svc, "get_db_connection", lambda: conn)
    monkeypatch.setattr(
        svc,
        "validate_appointment_form",
        lambda form, appointment_date, **kwargs: [],
    )
    monkeypatch.setattr(
        svc,
        "parse_new_patient_form",
        lambda form: {
            "last_name": "Тестова",
            "first_name": "Пациентка",
            "patronymic": "Автотестовна",
            "birth_date": date(1980, 1, 15),
            "gender": True,
            "phone": "+7 900 000-00-00",
        },
    )
    monkeypatch.setattr(
        svc,
        "parse_required_appointment_fields",
        lambda form: {
            "location_id": 2,
            "appointment_datetime": datetime(2026, 7, 4, 10, 30),
        },
    )
    monkeypatch.setattr(
        svc,
        "parse_appointment_form",
        lambda form, appointment_datetime: {"parsed": True},
    )
    monkeypatch.setattr(
        svc,
        "doctor_can_work_in_location",
        lambda cur, doctor_id, location_id: True,
    )


def test_create_patient_with_first_appointment_commits_and_passes_age(monkeypatch):
    conn = FakeConnection()
    saved: dict[str, Any] = {}
    appointment_call: dict[str, Any] = {}
    _patch_common(monkeypatch, conn)

    monkeypatch.setattr(svc, "create_patient", lambda cur, patient_data: 101)

    def fake_create_appointment(**kwargs):
        appointment_call.update(kwargs)
        return 202

    monkeypatch.setattr(svc, "create_appointment", fake_create_appointment)
    monkeypatch.setattr(
        svc,
        "save_appointment_details",
        lambda **kwargs: saved.update(kwargs),
    )

    result = svc.create_patient_with_first_appointment(
        full_fake_form(), current_doctor_id=1
    )

    assert result.patient_id == 101
    assert result.appointment_id == 202
    assert appointment_call["age_at_appointment"] == 46
    assert conn.committed is True
    assert conn.rolled_back is False
    assert saved["appointment_id"] == 202


def test_create_appointment_for_existing_patient_commits_and_passes_age(monkeypatch):
    conn = FakeConnection()
    appointment_call: dict[str, Any] = {}
    _patch_common(monkeypatch, conn)

    monkeypatch.setattr(
        svc,
        "get_patient_for_appointment",
        lambda cur, patient_id: {
            "id": patient_id,
            "birth_date": date(1980, 1, 15),
            "gender": True,
        },
    )

    def fake_create_appointment(**kwargs):
        appointment_call.update(kwargs)
        return 303

    monkeypatch.setattr(svc, "create_appointment", fake_create_appointment)
    monkeypatch.setattr(svc, "save_appointment_details", lambda **kwargs: None)

    result = svc.create_appointment_for_existing_patient(
        101, full_fake_form(), current_doctor_id=1
    )

    assert result.patient_id == 101
    assert result.appointment_id == 303
    assert appointment_call["age_at_appointment"] == 46
    assert conn.committed is True
    assert conn.rolled_back is False


def test_create_appointment_for_missing_patient_rolls_back(monkeypatch):
    conn = FakeConnection()
    _patch_common(monkeypatch, conn)
    monkeypatch.setattr(
        svc, "get_patient_for_appointment", lambda cur, patient_id: None
    )
    monkeypatch.setattr(svc, "create_appointment", lambda **kwargs: 303)

    with pytest.raises(HTTPException):
        svc.create_appointment_for_existing_patient(
            999999, full_fake_form(), current_doctor_id=1
        )

    assert conn.committed is False
    assert conn.rolled_back is True


def test_create_patient_rolls_back_when_save_details_fails(monkeypatch):
    conn = FakeConnection()
    _patch_common(monkeypatch, conn)
    monkeypatch.setattr(svc, "create_patient", lambda cur, patient_data: 101)
    monkeypatch.setattr(svc, "create_appointment", lambda **kwargs: 202)

    def fail_save(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "save_appointment_details", fail_save)

    with pytest.raises(HTTPException):
        svc.create_patient_with_first_appointment(
            full_fake_form(), current_doctor_id=1
        )

    assert conn.committed is False
    assert conn.rolled_back is True
