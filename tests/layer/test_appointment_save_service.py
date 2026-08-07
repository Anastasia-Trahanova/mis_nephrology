"""
Что тестируется:
- appointment_save_service.py как оркестратор сохранения приёма;
- что заполненные строки анализов передаются в repositories;
- что пустые строки анализов пропускаются;
- что по креатинину создаётся calculated_metric;
- что по альбумину/креатинину мочи сохраняется ACR и категория;
- что диагнозы сохраняются только через МКБ-10;
- что KDIGO после серверного сохранения источников валидирует выбранную пару.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

import app.services.appointment_save_service as svc

from .factories import FakeCursor, minimal_appointment_data


def _patch_common_sections(monkeypatch, calls):
    def record(name):
        def _inner(*args, **kwargs):
            calls.append((name, {"args": args, "kwargs": kwargs}))
            return None

        return _inner

    monkeypatch.setattr(svc, "insert_survey", record("survey"))
    monkeypatch.setattr(svc, "insert_examination", record("examination"))
    monkeypatch.setattr(svc, "insert_cbc_result", record("cbc"))
    monkeypatch.setattr(svc, "insert_biochemistry_result", record("biochemistry"))
    monkeypatch.setattr(svc, "insert_calculated_metric", record("metric"))
    monkeypatch.setattr(svc, "insert_urinalysis_result", record("urinalysis"))
    monkeypatch.setattr(svc, "insert_albuminuria_result", record("albuminuria"))
    monkeypatch.setattr(svc, "insert_ultrasound_result", record("ultrasound"))
    monkeypatch.setattr(svc, "save_appointment_icd10_diagnoses", record("icd10"))
    monkeypatch.setattr(svc, "insert_diet_and_recommendations", record("diet"))
    monkeypatch.setattr(svc, "insert_prescription", record("prescription"))
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
    return record


def test_save_appointment_details_saves_all_sections_and_skips_empty_rows(monkeypatch):
    calls: list[tuple[str, object]] = []
    record = _patch_common_sections(monkeypatch, calls)
    monkeypatch.setattr(svc, "build_kdigo_assessments_for_appointment", lambda cur, appointment_id: [])
    monkeypatch.setattr(svc, "save_ckd_prognosis_for_appointment", record("prognosis"))

    appointment_data = minimal_appointment_data()
    appointment_data.pop("diagnoses", None)

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
    assert "diagnoses" not in call_names
    assert call_names.count("icd10") == 1
    assert call_names.count("diet") == 1
    assert call_names.count("prescription") == 1
    assert call_names.count("prognosis") == 1


def test_save_auto_selects_the_only_kdigo_candidate(monkeypatch):
    calls: list[tuple[str, object]] = []
    record = _patch_common_sections(monkeypatch, calls)
    monkeypatch.setattr(
        svc,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id: [{"selection_key": "only-pair"}],
    )
    saved = []
    monkeypatch.setattr(
        svc,
        "save_ckd_prognosis_for_appointment",
        lambda appointment_id, *, cur, selected_pair=None, **kwargs: saved.append(selected_pair),
    )

    appointment_data = minimal_appointment_data()
    appointment_data["kdigo_selected_pair"] = None
    svc.save_appointment_details(
        cur=FakeCursor(),
        appointment_id=202,
        appointment_data=appointment_data,
        patient_birth_date=date(1980, 1, 15),
        patient_gender=True,
    )

    assert saved == ["only-pair"]


def test_save_requires_explicit_kdigo_choice_when_multiple_candidates_exist(monkeypatch):
    calls: list[tuple[str, object]] = []
    _patch_common_sections(monkeypatch, calls)
    monkeypatch.setattr(
        svc,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id: [
            {"selection_key": "pair-a"},
            {"selection_key": "pair-b"},
        ],
    )
    monkeypatch.setattr(
        svc,
        "save_ckd_prognosis_for_appointment",
        lambda *args, **kwargs: pytest.fail("KDIGO save must not run before the doctor selects a pair"),
    )

    appointment_data = minimal_appointment_data()
    appointment_data["kdigo_selected_pair"] = None
    with pytest.raises(HTTPException) as error:
        svc.save_appointment_details(
            cur=FakeCursor(),
            appointment_id=202,
            appointment_data=appointment_data,
            patient_birth_date=date(1980, 1, 15),
            patient_gender=True,
        )

    assert error.value.status_code == 400
    assert "Выберите один вариант" in str(error.value.detail)


def test_save_rejects_selected_pair_that_no_longer_matches_sources(monkeypatch):
    calls: list[tuple[str, object]] = []
    _patch_common_sections(monkeypatch, calls)
    monkeypatch.setattr(
        svc,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id: [{"selection_key": "actual-pair"}],
    )
    monkeypatch.setattr(
        svc,
        "save_ckd_prognosis_for_appointment",
        lambda *args, **kwargs: pytest.fail("Tampered KDIGO selection must be rejected before save"),
    )

    appointment_data = minimal_appointment_data()
    appointment_data["kdigo_selected_pair"] = "tampered-pair"
    with pytest.raises(HTTPException) as error:
        svc.save_appointment_details(
            cur=FakeCursor(),
            appointment_id=202,
            appointment_data=appointment_data,
            patient_birth_date=date(1980, 1, 15),
            patient_gender=True,
        )

    assert error.value.status_code == 400
    assert "не соответствует текущим анализам" in str(error.value.detail)


def test_save_prescriptions_skips_empty_rows(monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        svc,
        "insert_prescription",
        lambda *args, **kwargs: calls.append(("prescription", kwargs)),
    )

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
