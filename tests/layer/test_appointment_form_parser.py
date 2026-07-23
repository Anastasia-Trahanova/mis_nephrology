"""
Что тестируется:
- parse_new_patient_form, включая существующее поле patients.phone;
- parse_required_appointment_fields;
- parse_appointment_form после миграции 0009;
- сохранение порядка списков анализов;
- серверный расчёт BMI;
- сохранение блока АД вместе с примечанием;
- сохранение прежней логики отёков;
- отсутствие удалённых полей старой формы.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi import HTTPException

from app.services.appointment_form_parser import (
    parse_appointment_form,
    parse_new_patient_form,
    parse_required_appointment_fields,
)

from .factories import FakeForm, full_fake_form


def test_parse_new_patient_form_extracts_patient_and_phone():
    patient = parse_new_patient_form(full_fake_form())

    assert patient["last_name"] == "Тестова"
    assert patient["first_name"] == "Пациентка"
    assert patient["birth_date"] == date(1980, 1, 15)
    assert patient["gender"] is True
    assert patient["phone"] == "+7 900 000-00-00"


def test_parse_new_patient_form_rejects_missing_required_fields():
    with pytest.raises(HTTPException):
        parse_new_patient_form(
            FakeForm({"first_name": "НетФамилии", "birth_date": "1980-01-01"})
        )


def test_parse_required_appointment_fields_builds_datetime():
    result = parse_required_appointment_fields(full_fake_form())

    # Врач определяется по сессии и намеренно не читается из HTML как источник истины.
    assert "doctor_id" not in result
    assert result["location_id"] == 1
    assert result["appointment_datetime"] == datetime(2026, 7, 4, 10, 30)


def test_parse_required_appointment_fields_rejects_missing_time():
    with pytest.raises(HTTPException):
        parse_required_appointment_fields(
            FakeForm(
                {
                    "location_id": "1",
                    "appointment_date": "2026-07-04",
                    "appointment_time": "",
                }
            )
        )


def test_parse_appointment_form_returns_stage2_sections_and_bmi():
    data = parse_appointment_form(full_fake_form(), datetime(2026, 7, 4, 10, 30))

    assert set(data) >= {
        "survey",
        "examination",
        "cbc",
        "biochemistry",
        "urinalysis",
        "albuminuria",
        "ultrasound",
        "icd10",
        "diet",
        "prescriptions",
        "appointment_date_default",
    }
    assert "diagnoses" not in data

    survey = data["survey"]
    assert survey["complaints"] == "Жалобы из автотеста"
    assert survey["education_and_professional_history"] == "Высшее образование, бухгалтер"
    assert survey["disease_onset"] == "Заболевание началось около пяти лет назад"
    assert survey["heredity_description"].startswith("Наследственность отягощена")
    assert "heredity" not in survey
    assert "life_anamnesis" not in survey
    assert "disease_anamnesis" not in survey
    assert "comorbidities" not in survey

    examination = data["examination"]
    assert examination["height"] == "170"
    assert examination["weight"] == "70"
    assert examination["bmi"] == 24.22
    assert examination["body_temperature"] == "36.6"
    assert examination["skin_and_mucous_membranes"].startswith("Кожа бледная")
    assert examination["bp_note"] == "сидя"
    assert "Периферические отёки" in examination["edema_location"]
    assert examination["bed_position_details"] == "Полусидя из-за одышки"
    assert examination["kidney_palpation_details"].startswith("Правая почка")
    assert "skin_condition" not in examination

    assert data["cbc"]["hemoglobin"] == ["130", None]
    assert data["biochemistry"]["creatinine"] == ["100", None]
    # В фабрике намеренно используется привычная запись 1015.
    assert data["urinalysis"]["specific_gravity"] == ["1.015", None]
    assert data["albuminuria"]["urine_albumin_unit"] == ["mg_l", "mg_l"]
    assert data["prescriptions"]["medications"] == ["Лозартан", ""]
    assert data["appointment_date_default"] == date(2026, 7, 4)


def test_parser_clears_details_that_do_not_match_selected_value():
    form = FakeForm(
        {
            "bed_position": "active",
            "bed_position_details": "не должно сохраниться",
            "kidney_palpation": "not_palpable",
            "kidney_palpation_details": "не должно сохраниться",
            "heredity_description": "Не отягощена",
            "medication": [],
            "dosage": [],
            "schedule": [],
        }
    )

    data = parse_appointment_form(form, datetime(2026, 7, 4, 10, 30))

    assert "heredity" not in data["survey"]
    assert data["survey"]["heredity_description"] == "Не отягощена"
    assert data["examination"]["bed_position_details"] is None
    assert data["examination"]["kidney_palpation_details"] is None
