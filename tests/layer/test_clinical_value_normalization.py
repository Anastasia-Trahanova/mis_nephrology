"""
Что тестируется:
- нормализация клинических числовых значений формы;
- безопасная обработка альтернативных форматов;
- отсутствие опасных автоматических преобразований для реально высоких значений;
- совместимость нормализованной формы с form.get() и form.getlist();
- интеграция нормализации с validate_appointment_form.

Зачем:
врач может вводить часть значений в привычном формате, например удельный вес
мочи 1015 вместо 1.015. Система должна принять такие однозначные варианты и
сохранить единый внутренний формат. Но она не должна автоматически делить или
умножать любые подозрительные числа, потому что для ряда показателей высокие
значения могут быть реальными критическими значениями.
"""

from __future__ import annotations

from datetime import date

from app.services.clinical_value_normalization import (
    get_normalization_warnings,
    normalize_appointment_form_values,
    normalize_hematocrit_value,
    normalize_specific_gravity_value,
)
from app.validation import validate_appointment_form

from .factories import FakeForm


def test_specific_gravity_accepts_common_laboratory_format():
    assert normalize_specific_gravity_value("1015") == "1.015"
    assert normalize_specific_gravity_value("1005") == "1.005"
    assert normalize_specific_gravity_value("1030") == "1.030"
    assert normalize_specific_gravity_value("1050") == "1.050"


def test_specific_gravity_keeps_decimal_format():
    assert normalize_specific_gravity_value("1.015") == "1.015"
    assert normalize_specific_gravity_value("1,015") == "1.015"


def test_specific_gravity_does_not_guess_unsafe_values():
    # 900, 1500 и 1.5 не являются безопасными альтернативными записями 1.015.
    # Их нельзя тихо преобразовывать, они должны дойти до валидации как ошибки.
    assert normalize_specific_gravity_value("900") == "900"
    assert normalize_specific_gravity_value("1500") == "1500"
    assert normalize_specific_gravity_value("1.5") == "1.5"


def test_hematocrit_accepts_percent_and_fraction_format():
    assert normalize_hematocrit_value("39") == "39"
    assert normalize_hematocrit_value("0.39") == "39"
    assert normalize_hematocrit_value("0,39") == "39"


def test_hematocrit_does_not_turn_any_small_number_into_percent():
    # 1.2 не преобразуем в 120. Это подозрительное значение должно проверяться
    # обычной медицинской валидацией.
    assert normalize_hematocrit_value("1.2") == "1.2"


def test_normalized_form_supports_get_and_getlist():
    form = FakeForm(
        {
            "specific_gravity": ["1015", "1,020", ""],
            "glucose": ["5,1"],
            "creatinine": ["1 000"],
            "complaints": "текст без нормализации",
        }
    )

    normalized = normalize_appointment_form_values(form)

    assert normalized.getlist("specific_gravity") == ["1.015", "1.020", None]
    assert normalized.get("glucose") == "5.1"
    assert normalized.get("creatinine") == "1000"
    assert normalized.get("complaints") == "текст без нормализации"


def test_normalization_warnings_are_collected_for_future_ui():
    form = FakeForm({"specific_gravity": ["1015"], "hematocrit": ["0.39"]})

    warnings = get_normalization_warnings(form)

    assert len(warnings) == 2
    assert warnings[0].field == "specific_gravity"
    assert warnings[0].original_value == "1015"
    assert warnings[0].normalized_value == "1.015"


def test_validation_accepts_specific_gravity_1015_after_normalization():
    form = FakeForm({"specific_gravity": ["1015"]})

    errors = validate_appointment_form(form, date(2026, 7, 4))

    assert errors == []


def test_validation_rejects_specific_gravity_when_value_is_not_safely_normalizable():
    form = FakeForm({"specific_gravity": ["1500"]})

    errors = validate_appointment_form(form, date(2026, 7, 4))

    assert errors
    assert errors[0]["field"] == "specific_gravity"
    assert errors[0]["message"] == "Неверное значение"
