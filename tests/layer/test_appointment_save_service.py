"""
Что тестируется:
- appointment_save_service.py как оркестратор сохранения приёма;
- что заполненные строки анализов передаются в repositories;
- что пустые строки анализов пропускаются;
- что по креатинину создаётся calculated_metric;
- что по альбумину/креатинину мочи сохраняется ACR и категория;
- что лекарства с пустыми строками не сохраняются;
- что после сохранения вызывается пересчёт прогноза ХБП.

Зачем:
это главный слой после дробления patients.py. Если он сломается, форма может
открываться, но данные не будут попадать в нужные таблицы.

Тест НЕ пишет в реальную БД: repository-функции заменяются monkeypatch-ами.
"""

from __future__ import annotations

from datetime import date

import app.services.appointment_save_service as svc

from .factories import FakeCursor, minimal_appointment_data


def test_save_appointment_details_saves_all_sections_and_skips_empty_rows(monkeypatch):
    calls: list[tuple[str, object]] = []

    def record(name):
        def _inner(*args, **kwargs):
            calls.append((name, {"args": args, "kwargs": kwargs}))
        return _inner

    monkeypatch.setattr(svc, "insert_survey", record("survey"))
    monkeypatch.setattr(svc, "insert_examination", record("examination"))
    monkeypatch.setattr(svc, "insert_cbc_result", record("cbc"))
    monkeypatch.setattr(svc, "insert_biochemistry_result", record("biochemistry"))
    monkeypatch.setattr(svc, "insert_calculated_metric", record("metric"))
    monkeypatch.setattr(svc, "insert_urinalysis_result", record("urinalysis"))
    monkeypatch.setattr(svc, "insert_albuminuria_result", record("albuminuria"))
    monkeypatch.setattr(svc, "insert_ultrasound_result", record("ultrasound"))
    monkeypatch.setattr(svc, "insert_text_diagnoses", record("diagnoses"))
    monkeypatch.setattr(svc, "save_appointment_icd10_diagnoses", record("icd10"))
    monkeypatch.setattr(svc, "insert_diet_and_recommendations", record("diet"))
    monkeypatch.setattr(svc, "insert_prescription", record("prescription"))
    monkeypatch.setattr(svc, "save_ckd_prognosis_for_appointment", record("prognosis"))

    monkeypatch.setattr(
        svc,
        "calculate_all_metrics",
        lambda **kwargs: {
            "egfr_ckdepi": 65.12,
            "crcl_cockcroft_gault": 80.34,
            "ckd_stage": "С2",
        },
    )
    monkeypatch.setattr(svc, "calculate_age", lambda birth_date, appointment_date: 46)
    monkeypatch.setattr(
        svc,
        "calculate_albuminuria_metrics",
        lambda **kwargs: {
            "albumin_creatinine_ratio": 3.0,
            "albuminuria_category": "A1",
        },
    )

    appointment_data = minimal_appointment_data()

    svc.save_appointment_details(
        cur=FakeCursor(),
        appointment_id=202,
        appointment_data=appointment_data,
        patient_birth_date=date(1980, 1, 15),
        patient_gender=True,
    )

    call_names = [name for name, _payload in calls]

    assert call_names.count("survey") == 1
    assert call_names.count("examination") == 1
    assert call_names.count("cbc") == 1
    assert call_names.count("biochemistry") == 1
    assert call_names.count("metric") == 1
    assert call_names.count("urinalysis") == 1
    assert call_names.count("albuminuria") == 1
    assert call_names.count("ultrasound") == 1
    assert call_names.count("diagnoses") == 1
    assert call_names.count("icd10") == 1
    assert call_names.count("diet") == 1
    assert call_names.count("prescription") == 1
    assert call_names.count("prognosis") == 1


def test_save_prescriptions_skips_empty_rows(monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(svc, "insert_prescription", lambda *args, **kwargs: calls.append(("prescription", kwargs)))

    svc.save_prescriptions(
        cur=FakeCursor(),
        appointment_id=202,
        prescriptions_data={
            "medications": ["Лозартан", ""],
            "dosages": ["50 мг", ""],
            "schedules": ["1 раз", ""],
        },
    )

    assert len(calls) == 1
