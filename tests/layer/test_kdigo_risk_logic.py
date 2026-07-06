"""
Тесты чистой логики KDIGO.

Проверяют не БД и не HTML, а медицинскую бизнес-логику:
- матрица СКФ × альбуминурия;
- формулировка для врача;
- сообщения при отсутствии данных;
- сообщение при устаревшем показателе.
"""

from datetime import date

from app.medical_algorithms.kdigo_risk import (
    build_source_pair_key,
    calculate_kdigo_risk,
    format_missing_phrase,
    format_risk_phrase,
    format_stale_phrase,
    is_interval_allowed,
    source_interval_days,
)


def test_kdigo_matrix_returns_combined_category_and_risk_text():
    result = calculate_kdigo_risk("C3a", "a2")

    assert result["combined_category"] == "С3аA2"
    assert result["prognosis_level"] == "high"
    assert result["prognosis_text"] == "высокий риск"


def test_kdigo_phrase_matches_required_doctor_wording():
    phrase = format_risk_phrase(
        {
            "combined_category": "С3аA2",
            "prognosis_text": "высокий риск",
            "gfr_investigation_date": date(2026, 7, 3),
            "albuminuria_investigation_date": date(2026, 6, 29),
        }
    )

    assert phrase == (
        "По KDIGO: С3аA2 — высокий риск прогрессирования ХБП и развития ХПН "
        "(рассчитано по СКФ от 03.07.2026, альбуминурия от 29.06.2026)"
    )


def test_missing_phrases_are_short_and_specific():
    assert format_missing_phrase("albuminuria") == (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        "данные по альбуминурии не предоставлены."
    )
    assert format_missing_phrase("gfr") == (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        "данные по СКФ не предоставлены."
    )
    assert format_missing_phrase("both") == (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        "данные по альбуминурии и СКФ не предоставлены."
    )


def test_high_risk_interval_over_90_days_is_not_allowed():
    interval = source_interval_days(date(2026, 7, 3), date(2026, 3, 1))

    assert interval > 90
    assert is_interval_allowed("high", interval) is False
    assert format_stale_phrase("albuminuria", interval) == (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        "данные по альбуминурии были получены 4 месяца назад, рекомендовано повторить исследование."
    )


def test_pair_key_is_shared_between_frontend_and_backend():
    assert build_source_pair_key("2026-07-03", "C3a", "2026-06-29", "a2") == (
        "2026-07-03|С3а|2026-06-29|A2"
    )
