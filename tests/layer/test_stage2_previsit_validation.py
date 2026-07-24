"""
Назначение файла: точечные тесты серверной валидации верхней части формы
после миграций 0009–0010.

Проверяем только новые структурированные поля. Лабораторные исследования,
KDIGO и нижняя часть формы этим файлом не затрагиваются.
"""

from __future__ import annotations

from datetime import date

from app.validation import validate_appointment_form


class FakeForm(dict):
    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


def error_fields(errors):
    return {item["field"] for item in errors}


def test_valid_structured_previsit_fields_are_accepted():
    form = FakeForm(
        {
            "heredity_description": "У матери артериальная гипертензия",
            "general_condition": "moderate",
            "consciousness": "clear",
            "bed_position": "forced",
            "bed_position_details": "полусидя",
            "constitution_type": "normosthenic",
            "body_temperature": "36,6",
            "kidney_palpation": "palpable",
            "kidney_palpation_details": "пальпируется справа",
            "pasternatsky_result": "negative",
            "pasternatsky_side": "bilateral",
            "systolic_pressure": "130",
            "diastolic_pressure": "80",
        }
    )

    assert validate_appointment_form(form, date(2026, 7, 4)) == []


def test_forced_position_requires_details():
    errors = validate_appointment_form(
        FakeForm({"bed_position": "forced"}), date(2026, 7, 4)
    )
    assert "bed_position_details" in error_fields(errors)


def test_heredity_is_optional_free_text():
    assert validate_appointment_form(
        FakeForm({"heredity_description": "Не отягощена"}), date(2026, 7, 4)
    ) == []
    assert validate_appointment_form(FakeForm({}), date(2026, 7, 4)) == []


def test_palpable_kidney_requires_details():
    errors = validate_appointment_form(
        FakeForm({"kidney_palpation": "palpable"}), date(2026, 7, 4)
    )
    assert "kidney_palpation_details" in error_fields(errors)


def test_pasternatsky_result_and_side_must_be_filled_together():
    missing_side = validate_appointment_form(
        FakeForm({"pasternatsky_result": "positive"}), date(2026, 7, 4)
    )
    missing_result = validate_appointment_form(
        FakeForm({"pasternatsky_side": "right"}), date(2026, 7, 4)
    )

    assert "pasternatsky_side" in error_fields(missing_side)
    assert "pasternatsky_result" in error_fields(missing_result)


def test_temperature_outside_database_range_is_rejected():
    errors = validate_appointment_form(
        FakeForm({"body_temperature": "48"}), date(2026, 7, 4)
    )
    assert "body_temperature" in error_fields(errors)


def test_daily_albumin_excretion_must_be_nonnegative_number():
    errors = validate_appointment_form(
        FakeForm({"daily_albumin_excretion": "-1"}),
        date(2026, 7, 4),
    )
    assert "daily_albumin_excretion" in error_fields(errors)
