"""Тесты цепочки форма → parser → save service → repository."""

from __future__ import annotations

from datetime import datetime

import app.repositories.prescriptions as repo
import app.services.appointment_save_service as save_service
from app.services.appointment_form_parser import parse_appointment_form

from .factories import FakeCursor, FakeForm


def test_parser_reads_four_parallel_prescription_lists():
    form = FakeForm(
        {
            "therapy_group": [
                "Коррекция АД, ЧСС",
                "Нефропротекция",
                "Другие препараты",
            ],
            "medication": ["Лозартан", "Дапаглифлозин", "Препарат вручную"],
            "dosage": ["50 мг", "10 мг", "1 таблетка"],
            "schedule": ["утром", "утром", "по схеме"],
        }
    )

    parsed = parse_appointment_form(form, datetime(2026, 8, 1, 10, 0))

    assert parsed["prescriptions"] == {
        "therapy_groups": [
            "Коррекция АД, ЧСС",
            "Нефропротекция",
            "Другие препараты",
        ],
        "medications": ["Лозартан", "Дапаглифлозин", "Препарат вручную"],
        "dosages": ["50 мг", "10 мг", "1 таблетка"],
        "schedules": ["утром", "утром", "по схеме"],
    }


def test_save_prescriptions_saves_group_and_skips_fully_empty_rows(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        save_service,
        "insert_prescription",
        lambda **kwargs: calls.append(kwargs),
    )

    save_service.save_prescriptions(
        cur=FakeCursor(),
        appointment_id=77,
        prescriptions_data={
            "therapy_groups": [
                "Коррекция АД, ЧСС",
                "Нефропротекция",
                "Коррекция анемии",
            ],
            "medications": ["Лозартан", "Дапаглифлозин", ""],
            "dosages": ["50 мг", "10 мг", ""],
            "schedules": ["утром", "утром", ""],
        },
    )

    assert calls == [
        {
            "cur": calls[0]["cur"],
            "appointment_id": 77,
            "therapy_group": "Коррекция АД, ЧСС",
            "medication": "Лозартан",
            "dosage": "50 мг",
            "schedule": "утром",
        },
        {
            "cur": calls[1]["cur"],
            "appointment_id": 77,
            "therapy_group": "Нефропротекция",
            "medication": "Дапаглифлозин",
            "dosage": "10 мг",
            "schedule": "утром",
        },
    ]


def test_save_prescriptions_normalizes_missing_or_unknown_group(monkeypatch):
    calls: list[dict] = []
    monkeypatch.setattr(
        save_service,
        "insert_prescription",
        lambda **kwargs: calls.append(kwargs),
    )

    save_service.save_prescriptions(
        cur=FakeCursor(),
        appointment_id=78,
        prescriptions_data={
            "therapy_groups": ["несуществующая группа"],
            "medications": ["Препарат вручную", "Ещё один препарат"],
            "dosages": ["1 мг", "2 мг"],
            "schedules": ["утром", "вечером"],
        },
    )

    assert [call["therapy_group"] for call in calls] == [
        "Другие препараты",
        "Другие препараты",
    ]
    assert [call["medication"] for call in calls] == [
        "Препарат вручную",
        "Ещё один препарат",
    ]


def test_repository_insert_includes_therapy_group_and_all_values():
    cur = FakeCursor()

    repo.insert_prescription(
        cur,
        appointment_id=15,
        therapy_group="Коррекция анемии",
        medication="Эпоэтин альфа",
        dosage="4000 МЕ",
        schedule="3 раза в неделю",
    )

    normalized_sql = " ".join(cur.last_query.split())
    assert "INSERT INTO prescriptions" in normalized_sql
    assert "therapy_group" in normalized_sql
    assert cur.last_params == (
        15,
        "Коррекция анемии",
        "Эпоэтин альфа",
        "4000 МЕ",
        "3 раза в неделю",
    )


def test_repository_fetch_returns_group_and_keeps_database_order():
    expected = [
        {
            "id": 1,
            "therapy_group": "Нефропротекция",
            "medication": "Финеренон",
            "dosage": "10 мг",
            "schedule": "1 раз в день",
        },
        {
            "id": 2,
            "therapy_group": "Другие препараты",
            "medication": "Аллопуринол",
            "dosage": "100 мг",
            "schedule": "после еды",
        },
    ]

    class FetchAllCursor(FakeCursor):
        def fetchall(self):
            return expected

    cur = FetchAllCursor()
    result = repo._fetch_appointment_medications(cur, 41)

    normalized_sql = " ".join(cur.last_query.split())
    assert "SELECT id, therapy_group, medication, dosage, schedule" in normalized_sql
    assert "ORDER BY id" in normalized_sql
    assert cur.last_params == (41,)
    assert result == expected
