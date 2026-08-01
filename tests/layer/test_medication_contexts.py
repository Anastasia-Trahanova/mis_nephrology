"""Тесты подготовки групп для повторного приёма и карточки пациента."""

from __future__ import annotations

from datetime import datetime

import app.services.appointment_form_context_service as form_context
import app.services.patient_card_context_service as card_context


class _ContextManager:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, exc_type, exc, traceback):
        return False


class _Connection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return _ContextManager(self._cursor)


def _patch_db(monkeypatch, module):
    cursor = object()
    monkeypatch.setattr(module, "get_db_connection", lambda: _ContextManager(_Connection(cursor)))
    return cursor


def test_repeat_appointment_context_groups_previous_prescriptions_and_suggestions(monkeypatch):
    _patch_db(monkeypatch, form_context)
    previous = [
        {
            "therapy_group": "Нефропротекция",
            "medication": "Дапаглифлозин",
            "dosage": "10 мг",
            "schedule": "утром",
        },
        {
            "therapy_group": "Коррекция АД, ЧСС",
            "medication": "Лозартан",
            "dosage": "50 мг",
            "schedule": "вечером",
        },
    ]
    dictionary = [
        {"display_name": "Лозартан"},
        {"display_name": "Дапаглифлозин"},
        {"display_name": "Финеренон"},
    ]

    monkeypatch.setattr(form_context, "_fetch_patient_by_id", lambda *_: {"id": 5})
    monkeypatch.setattr(form_context, "_fetch_patient_appointments", lambda *_: [{"appointment_id": 12}])
    monkeypatch.setattr(form_context, "_fetch_last_appointment_data", lambda *_: {"appointment_id": 12})
    monkeypatch.setattr(form_context, "_fetch_appointment_medications", lambda *_: previous)
    monkeypatch.setattr(form_context, "_fetch_medications_dictionary", lambda *_: dictionary)
    monkeypatch.setattr(form_context, "_fetch_doctor_by_id", lambda *_: {"id": 8})
    monkeypatch.setattr(form_context, "_fetch_doctor_locations", lambda *_: [{"id": 1}])
    monkeypatch.setattr(form_context, "_fetch_appointment_icd10_diagnoses", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_appointment_diet", lambda *_: None)
    monkeypatch.setattr(form_context, "_fetch_branches", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_icd10_diagnoses", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_metrics_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_albuminuria_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_ckd_prognosis_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_cbc_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_biochemistry_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_urinalysis_history", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_patient_ultrasound_history", lambda *_: [])
    monkeypatch.setattr(form_context, "build_kdigo_risk_matrix", lambda rows: {"rows": rows})

    context = form_context.get_new_appointment_context(5, 8)
    groups = {group["value"]: group for group in context["medication_therapy_groups"]}

    assert context["last_medications"] == previous
    assert groups["Нефропротекция"]["prescriptions"] == [previous[0]]
    assert groups["Коррекция АД, ЧСС"]["prescriptions"] == [previous[1]]
    assert groups["Нефропротекция"]["suggestions"] == [
        "Лозартан",
        "Дапаглифлозин",
        "Финеренон",
    ]


def test_new_patient_context_has_all_groups_without_prefilled_rows(monkeypatch):
    _patch_db(monkeypatch, form_context)
    dictionary = [{"display_name": "Аллопуринол"}, {"display_name": "Фебуксостат"}]

    monkeypatch.setattr(form_context, "_fetch_medications_dictionary", lambda *_: dictionary)
    monkeypatch.setattr(form_context, "_fetch_branches", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_icd10_diagnoses", lambda *_: [])
    monkeypatch.setattr(form_context, "_fetch_doctor_by_id", lambda *_: {"id": 8})
    monkeypatch.setattr(form_context, "_fetch_doctor_locations", lambda *_: [{"id": 1}])
    monkeypatch.setattr(form_context, "build_kdigo_risk_matrix", lambda rows: {})

    context = form_context.get_new_patient_context(8)

    assert len(context["medication_therapy_groups"]) == 5
    assert all(not group["prescriptions"] for group in context["medication_therapy_groups"])
    additional = next(
        group for group in context["medication_therapy_groups"] if group["value"] == "Другие препараты"
    )
    assert additional["suggestions"] == ["Аллопуринол", "Фебуксостат"]


def test_patient_card_context_uses_saved_therapy_group(monkeypatch):
    _patch_db(monkeypatch, card_context)
    selected = {
        "appointment_id": 13,
        "patient_id": 5,
        "appointment_date": datetime(2026, 4, 5, 10, 0),
    }
    medications = [
        {
            "therapy_group": "Коррекция анемии",
            "medication": "Эпоэтин альфа",
            "dosage": "4000 МЕ",
            "schedule": "3 раза в неделю",
        }
    ]

    monkeypatch.setattr(card_context, "_fetch_patient_by_id", lambda *_: {"id": 5})
    monkeypatch.setattr(card_context, "_fetch_patient_appointments", lambda *_: [{"appointment_id": 13}])
    monkeypatch.setattr(card_context, "_fetch_appointment_full_data", lambda *_: selected)
    monkeypatch.setattr(card_context, "_fetch_appointment_medications", lambda *_: medications)
    monkeypatch.setattr(card_context, "_fetch_appointment_diet", lambda *_: None)
    monkeypatch.setattr(card_context, "_fetch_appointment_icd10_diagnoses", lambda *_: [])
    monkeypatch.setattr(card_context, "_fetch_patient_ckd_prognosis_history", lambda *_: [])
    monkeypatch.setattr(card_context, "_fetch_appointment_ckd_prognosis_results", lambda *_: [])
    monkeypatch.setattr(card_context, "_fetch_appointment_ckd_prognosis", lambda *_: None)
    monkeypatch.setattr(card_context, "build_kdigo_risk_matrix", lambda rows: {})
    for name in (
        "_fetch_patient_biochemistry_history",
        "_fetch_patient_cbc_history",
        "_fetch_patient_urinalysis_history",
        "_fetch_patient_metrics_history",
        "_fetch_patient_ultrasound_history",
        "_fetch_patient_albuminuria_history",
    ):
        monkeypatch.setattr(card_context, name, lambda *_: [])

    context = card_context.get_patient_card_context(5, selected_appointment_id=13)
    anemia = next(
        group for group in context["medication_therapy_groups"] if group["value"] == "Коррекция анемии"
    )

    assert context["medications"] == medications
    assert anemia["prescriptions"] == medications
