"""
Что тестируется:
- сборка текстового описания кожных покровов;
- сборка текстового описания отёков;
- корректная обработка чекбоксов, поля «другое» и пустых значений.

Зачем:
эти текстовые блоки сохраняются в examinations и потом отображаются в карточке
пациента/экспорте. Новый пациент и повторный приём должны формировать их одинаково.
"""

from __future__ import annotations

from app.services.appointment_text_builder import build_edema_location, build_skin_condition

from .factories import FakeForm


def test_build_skin_condition_from_checkboxes_and_other_fields():
    form = FakeForm(
        {
            "skin_color": ["обычная", "бледная"],
            "skin_color_other": "локальная гиперемия",
            "skin_moisture": ["нормальная"],
            "skin_rash": "есть",
            "skin_rash_description": "мелкая сыпь",
            "skin_other": "рубцов нет",
        }
    )

    result = build_skin_condition(form)

    assert "Окраска: обычная, бледная, локальная гиперемия" in result
    assert "Влажность: нормальная" in result
    assert "Высыпания: есть (мелкая сыпь)" in result
    assert "Дополнительно: рубцов нет" in result


def test_build_skin_condition_returns_none_when_empty():
    assert build_skin_condition(FakeForm({})) is None


def test_build_edema_location_from_checkboxes_and_other_fields():
    form = FakeForm(
        {
            "edema_peripheral": ["голени"],
            "edema_peripheral_other": "стопы",
            "edema_serositis": ["нет"],
            "edema_other": "к вечеру усиливаются",
        }
    )

    result = build_edema_location(form)

    assert "Периферические отёки: голени, стопы" in result
    assert "Серозиты: нет" in result
    assert "Дополнительно: к вечеру усиливаются" in result


def test_build_edema_location_returns_none_when_empty():
    assert build_edema_location(FakeForm({})) is None
