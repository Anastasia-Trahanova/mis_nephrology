"""
Что тестируется:
- parse_new_patient_form;
- parse_required_appointment_fields;
- parse_appointment_form;
- сохранение порядка списков анализов;
- серверный расчёт BMI при парсинге формы;
- разбор чекбоксов и свободных текстовых полей.

Зачем:
после дробления patients.py именно этот модуль знает имена HTML-полей. Если в
шаблоне изменится name="...", этот тест должен подсветить проблему раньше, чем
она попадёт к врачу.
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


def test_parse_new_patient_form_extracts_required_patient_fields():
    patient = parse_new_patient_form(full_fake_form())

    assert patient["last_name"] == "Тестова"
    assert patient["first_name"] == "Пациентка"
    assert patient["birth_date"] == date(1980, 1, 15)
    assert patient["gender"] is True


def test_parse_new_patient_form_rejects_missing_required_fields():
    with pytest.raises(HTTPException):
        parse_new_patient_form(FakeForm({"first_name": "НетФамилии", "birth_date": "1980-01-01"}))


def test_parse_required_appointment_fields_builds_datetime():
    result = parse_required_appointment_fields(full_fake_form())

    assert result["doctor_id"] == 1
    assert result["location_id"] == 1
    assert result["appointment_datetime"] == datetime(2026, 7, 4, 10, 30)


def test_parse_required_appointment_fields_rejects_missing_time():
    with pytest.raises(HTTPException):
        parse_required_appointment_fields(
            FakeForm(
                {
                    "doctor_id": "1",
                    "location_id": "1",
                    "appointment_date": "2026-07-04",
                    "appointment_time": "",
                }
            )
        )


def test_parse_appointment_form_returns_structured_sections_and_bmi():
    data = parse_appointment_form(full_fake_form(), datetime(2026, 7, 4, 10, 30))

    assert set(data) >= {
        "survey",
        "examination",
        "cbc",
        "biochemistry",
        "urinalysis",
        "albuminuria",
        "ultrasound",
        "diagnoses",
        "icd10",
        "diet",
        "prescriptions",
        "appointment_date_default",
    }

    assert data["survey"]["complaints"] == "Жалобы из автотеста"
    assert data["examination"]["height"] == "170"
    assert data["examination"]["weight"] == "70"
    assert data["examination"]["bmi"] == 24.22
    assert "Окраска" in data["examination"]["skin_condition"]
    assert "Периферические отёки" in data["examination"]["edema_location"]

    assert data["cbc"]["hemoglobin"] == ["130", None]
    assert data["biochemistry"]["creatinine"] == ["100", None]
    # В фабрике намеренно используется привычная запись удельного веса мочи 1015.
    # Парсер должен получать уже нормализованный внутренний формат 1.015.
    assert data["urinalysis"]["specific_gravity"] == ["1.015", None]
    assert data["albuminuria"]["urine_albumin_unit"] == ["mg_l", "mg_l"]
    assert data["prescriptions"]["medications"] == ["Лозартан", ""]
    assert data["appointment_date_default"] == date(2026, 7, 4)
