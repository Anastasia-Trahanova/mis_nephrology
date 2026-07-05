"""
Назначение файла: проверяет основные комбинации дат пациента, приёма,
следующего контроля и дат исследований.

Смысл теста:
дата приёма может быть в прошлом; система не должна падать и не должна
блокировать такую дату сама по себе. Блокируются только реально конфликтующие
связи дат.
"""
from datetime import date

import pytest

from app.validation import validate_appointment_form, validate_patient_and_visit_dates


class FakeForm(dict):
    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


TODAY = date(2026, 7, 5)


@pytest.mark.parametrize(
    "form, expected",
    [
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": ""},
            [],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-05", "next_control_date": ""},
            [],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-20", "next_control_date": ""},
            [],
        ),
        (
            {"birth_date": "2026-07-06", "appointment_date": "2026-07-06", "next_control_date": ""},
            [("birth_date", "Дата рождения не может быть в будущем")],
        ),
        (
            {"birth_date": "2026-07-04", "appointment_date": "2026-07-03", "next_control_date": ""},
            [("appointment_date", "Дата приёма не может быть раньше даты рождения")],
        ),
        
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": "2026-07-04"},
            [("next_control_date", "Дата следующего визита не может быть раньше текущей даты")],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": "2026-07-02"},
            [
                ("next_control_date", "Дата следующего визита не может быть раньше даты приёма"),
                ("next_control_date", "Дата следующего визита не может быть раньше текущей даты"),
            ],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": "2026-07-05"},
            [],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": "2026-08-01"},
            [],
        ),
        (
            {"birth_date": "12.09.1965", "appointment_date": "2026-07-03", "next_control_date": ""},
            [("birth_date", "Некорректная дата")],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "03.07.2026", "next_control_date": ""},
            [("appointment_date", "Некорректная дата")],
        ),
        (
            {"birth_date": "1965-09-12", "appointment_date": "2026-07-03", "next_control_date": "05.07.2026"},
            [("next_control_date", "Некорректная дата")],
        ),
    ],
)
def test_patient_and_visit_date_combinations(form, expected):
    errors = validate_patient_and_visit_dates(FakeForm(form), current_date=TODAY)
    actual = [(error["field"], error["message"]) for error in errors]

    assert actual == expected


@pytest.mark.parametrize(
    "field_name",
    [
        "cbc_investigation_date",
        "biochemistry_investigation_date",
        "urinalysis_investigation_date",
        "albuminuria_investigation_date",
        "ultrasound_investigation_date",
    ],
)
def test_investigation_date_after_appointment_is_rejected(field_name):
    errors = validate_appointment_form(
        FakeForm({field_name: ["2026-07-04"]}),
        "2026-07-03",
        birth_date_value="1965-09-12",
        current_date=TODAY,
    )

    assert (field_name, "Дата исследования не может быть позже даты приёма") in [
        (error["field"], error["message"]) for error in errors
    ]


@pytest.mark.parametrize(
    "investigation_date",
    ["2026-07-03", "2026-07-02", ""],
)
def test_investigation_date_on_or_before_appointment_is_allowed(investigation_date):
    errors = validate_appointment_form(
        FakeForm(
            {
                "cbc_investigation_date": [investigation_date],
                "biochemistry_investigation_date": [investigation_date],
                "urinalysis_investigation_date": [investigation_date],
                "albuminuria_investigation_date": [investigation_date],
                "ultrasound_investigation_date": [investigation_date],
            }
        ),
        "2026-07-03",
        birth_date_value="1965-09-12",
        current_date=TODAY,
    )

    assert errors == []
