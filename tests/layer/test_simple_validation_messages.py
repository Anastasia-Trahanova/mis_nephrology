"""
Назначение файла: тесты коротких сообщений валидации.

Проверяем, что врач не видит технические диапазоны и длинные объяснения.
Наружу должны выходить только короткие сообщения и выбранные сообщения по датам.
"""

from datetime import date

from app.validation import (
    APPOINTMENT_BEFORE_BIRTH,
    DATE_OF_BIRTH_IN_FUTURE,
    INVESTIGATION_AFTER_APPOINTMENT,
    NEXT_VISIT_BEFORE_APPOINTMENT,
    NEXT_VISIT_BEFORE_TODAY,
    validate_appointment_form,
    validate_patient_and_visit_dates,
)


class FakeForm(dict):
    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


def messages(errors):
    return [error["message"] for error in errors]


def test_absurd_numeric_value_returns_short_message_only():
    errors = validate_appointment_form(FakeForm({"height": ["-170"]}), date(2026, 7, 4))

    assert errors
    assert errors[0]["field"] == "height"
    assert errors[0]["message"] == "Неверное значение"
    assert "диапазон" not in errors[0]["message"].lower()


def test_not_a_number_returns_short_message_only():
    errors = validate_appointment_form(FakeForm({"potassium": ["abc"]}), date(2026, 7, 4))

    assert errors
    assert errors[0]["field"] == "potassium"
    assert errors[0]["message"] == "Неверное значение"


def test_specific_gravity_1015_is_accepted_silently_after_normalization():
    errors = validate_appointment_form(FakeForm({"specific_gravity": ["1015"]}), date(2026, 7, 4))

    assert errors == []


def test_specific_gravity_1500_is_rejected_with_short_message():
    errors = validate_appointment_form(FakeForm({"specific_gravity": ["1500"]}), date(2026, 7, 4))

    assert errors
    assert errors[0]["message"] == "Неверное значение"
    assert "1015" not in errors[0]["message"]
    assert "1.015" not in errors[0]["message"]


def test_partial_albuminuria_does_not_block_saving():
    errors = validate_appointment_form(FakeForm({"urine_albumin": ["30"]}), date(2026, 7, 4))

    assert errors == []


def test_investigation_date_after_appointment_is_rejected():
    errors = validate_appointment_form(
        FakeForm({"biochemistry_investigation_date": ["2026-07-05"]}),
        date(2026, 7, 4),
    )

    assert INVESTIGATION_AFTER_APPOINTMENT in messages(errors)


def test_birth_date_cannot_be_in_future():
    errors = validate_patient_and_visit_dates(
        FakeForm({"birth_date": "2026-07-06"}),
        current_date=date(2026, 7, 5),
    )

    assert DATE_OF_BIRTH_IN_FUTURE in messages(errors)


def test_appointment_date_cannot_be_before_birth_date():
    errors = validate_patient_and_visit_dates(
        FakeForm({"birth_date": "2026-07-05", "appointment_date": "2026-07-04"}),
        current_date=date(2026, 7, 5),
    )

    assert APPOINTMENT_BEFORE_BIRTH in messages(errors)


def test_next_visit_cannot_be_before_appointment_date():
    errors = validate_patient_and_visit_dates(
        FakeForm({"appointment_date": "2026-07-05", "next_control_date": "2026-07-04"}),
        current_date=date(2026, 7, 3),
    )

    assert NEXT_VISIT_BEFORE_APPOINTMENT in messages(errors)


def test_next_visit_cannot_be_before_current_date():
    errors = validate_patient_and_visit_dates(
        FakeForm({"appointment_date": "2026-07-01", "next_control_date": "2026-07-04"}),
        current_date=date(2026, 7, 5),
    )

    assert NEXT_VISIT_BEFORE_TODAY in messages(errors)
