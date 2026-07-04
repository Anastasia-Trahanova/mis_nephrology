"""
Что тестируется:
- разбор структурированных диагнозов МКБ-10 из формы;
- сохранение главного диагноза, осложнений и сопутствующих диагнозов;
- ошибка, если выбранного диагноза нет в активном справочнике.

Зачем:
МКБ-10 был вынесен из patients.py в отдельный сервис. Этот тест защищает связь
между HTML-полями формы и таблицей appointment_icd10_diagnoses.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.services.appointment_diagnosis_service as svc

from .factories import FakeCursor, FakeForm


def test_parse_icd10_diagnoses_from_form_keeps_order_and_empty_values():
    form = FakeForm(
        {
            "icd10_main_diagnosis": "N18.3 — Хроническая болезнь почек, стадия 3",
            "icd10_main_note": "основной диагноз",
            "icd10_complication_diagnosis": ["I12 — Гипертензивная болезнь с поражением почек", ""],
            "icd10_complication_note": ["уточнение", ""],
            "icd10_comorbidity_diagnosis": ["E11 — Сахарный диабет 2 типа"],
            "icd10_comorbidity_note": ["сопутствующий"],
        }
    )

    result = svc.parse_icd10_diagnoses_from_form(form)

    assert result["main_diagnosis"].startswith("N18.3")
    assert result["complication_diagnoses"] == ["I12 — Гипертензивная болезнь с поражением почек", None]
    assert result["comorbidity_notes"] == ["сопутствующий"]


def test_save_appointment_icd10_diagnoses_saves_main_complication_and_comorbidity(monkeypatch):
    saved: list[dict[str, object]] = []

    monkeypatch.setattr(svc, "find_active_icd10_diagnosis_id", lambda cur, text: 777)
    monkeypatch.setattr(
        svc,
        "insert_appointment_icd10_diagnosis_row",
        lambda **kwargs: saved.append(kwargs),
    )

    svc.save_appointment_icd10_diagnoses(
        cur=FakeCursor(),
        appointment_id=202,
        icd10_data={
            "main_diagnosis": "N18.3 — ХБП",
            "main_note": "main note",
            "complication_diagnoses": ["I12 — ГБ", None],
            "complication_notes": ["comp note", None],
            "comorbidity_diagnoses": ["E11 — СД2"],
            "comorbidity_notes": ["comorb note"],
        },
    )

    assert [row["diagnosis_type"] for row in saved] == ["main", "complication", "comorbidity"]
    assert saved[0]["sort_order"] == 1
    assert saved[1]["doctor_note"] == "comp note"


def test_insert_icd10_diagnosis_raises_when_dictionary_row_missing(monkeypatch):
    monkeypatch.setattr(svc, "find_active_icd10_diagnosis_id", lambda cur, text: None)

    with pytest.raises(HTTPException):
        svc.insert_appointment_icd10_diagnosis(
            cur=FakeCursor(),
            appointment_id=202,
            diagnosis_type="main",
            diagnosis_text="Неизвестный диагноз",
        )
