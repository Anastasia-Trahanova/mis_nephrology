"""
Тесты KDIGO v7: медицинское определение категории и риска.

Зачем:
- закрывает основные клетки матрицы KDIGO;
- проверяет нормализацию латинской C/G в русскую С;
- защищает формулировку, которая дальше попадает в live-блок и БД.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.medical_algorithms.kdigo_risk import calculate_kdigo_risk, format_risk_phrase


@pytest.mark.parametrize(
    ("gfr", "albuminuria", "combined", "level", "text"),
    [
        ("C1", "A1", "С1A1", "low", "низкий риск"),
        ("C1", "A2", "С1A2", "moderate", "умеренно повышенный риск"),
        ("C1", "A3", "С1A3", "high", "высокий риск"),
        ("G2", "A1", "С2A1", "low", "низкий риск"),
        ("G2", "A2", "С2A2", "moderate", "умеренно повышенный риск"),
        ("G2", "A3", "С2A3", "high", "высокий риск"),
        ("C3a", "a1", "С3аA1", "moderate", "умеренно повышенный риск"),
        ("C3a", "a2", "С3аA2", "high", "высокий риск"),
        ("C3a", "a3", "С3аA3", "very_high", "очень высокий риск"),
        ("C3b", "A1", "С3бA1", "high", "высокий риск"),
        ("C3b", "A2", "С3бA2", "very_high", "очень высокий риск"),
        ("C4", "A1", "С4A1", "very_high", "очень высокий риск"),
        ("C4", "A2", "С4A2", "very_high", "очень высокий риск"),
        ("C4", "A3", "С4A3", "very_high", "очень высокий риск"),
        ("C5", "A1", "С5A1", "very_high", "очень высокий риск"),
        ("C5", "A2", "С5A2", "very_high", "очень высокий риск"),
        ("C5", "A3", "С5A3", "very_high", "очень высокий риск"),
    ],
)
def test_kdigo_matrix_core_scenarios(gfr, albuminuria, combined, level, text):
    result = calculate_kdigo_risk(gfr, albuminuria)

    assert result["status"] == "calculated"
    assert result["combined_category"] == combined
    assert result["prognosis_level"] == level
    assert result["prognosis_text"] == text


def test_kdigo_phrase_for_diagnosis_uses_single_selected_assessment_text():
    phrase = format_risk_phrase(
        {
            "combined_category": "С3аA2",
            "prognosis_text": "высокий риск",
            "gfr_investigation_date": date(2026, 7, 4),
            "albuminuria_investigation_date": date(2026, 7, 4),
        }
    )

    assert phrase == (
        "По KDIGO: С3аA2 — высокий риск прогрессирования ХБП и развития ХПН "
        "(рассчитано по СКФ от 04.07.2026, альбуминурия от 04.07.2026)"
    )
