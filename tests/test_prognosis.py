"""
Тесты прогноза ХБП по матрице KDIGO.
Этот файл проверяет функцию, которая определяет прогноз ХБП по сочетанию категория СКФ + категория альбуминурии

Например:
    С3а + A2 -> высокий риск
    С4  + A3 -> очень высокий риск

Что проверяют тесты
-------------------
1. Основные сочетания категорий СКФ и альбуминурии.
2. Возврат старых ключей результата:
   - level;
   - text;
   - combined.
3. Возврат новых более понятных ключей:
   - gfr_category;
   - albuminuria_category;
   - combined_category;
   - prognosis_level;
   - prognosis_text.
4. Нормализацию старых форматов стадии:
   - C4 -> С4;
   - G4 -> С4;
   - c3a -> С3а;
   - g3b -> С3б.
5. Приведение категории альбуминурии к верхнему регистру:
   - a3 -> A3.
6. Корректную обработку пустых и неправильных значений.

"""


import pytest

from app.medical_algorithms.prognosis import calculate_ckd_prognosis


@pytest.mark.parametrize(
    ("gfr_category", "albuminuria_category", "expected_level", "expected_text"),
    [
        ("С1", "A1", "low", "низкий риск"),
        ("С1", "A2", "moderate", "умеренно повышенный риск"),
        ("С1", "A3", "high", "высокий риск"),
        ("С3а", "A1", "moderate", "умеренно повышенный риск"),
        ("С3а", "A2", "high", "высокий риск"),
        ("С3а", "A3", "very_high", "очень высокий риск"),
        ("С3б", "A1", "high", "высокий риск"),
        ("С3б", "A2", "very_high", "очень высокий риск"),
        ("С4", "A1", "very_high", "очень высокий риск"),
        ("С5", "A3", "very_high", "очень высокий риск"),
    ],
)
def test_calculate_ckd_prognosis_matrix(
    gfr_category,
    albuminuria_category,
    expected_level,
    expected_text,
):
    result = calculate_ckd_prognosis(gfr_category, albuminuria_category)

    assert result["level"] == expected_level
    assert result["text"] == expected_text
    assert result["prognosis_level"] == expected_level
    assert result["prognosis_text"] == expected_text
    assert result["combined"] == f"{gfr_category}{albuminuria_category}"
    assert result["combined_category"] == f"{gfr_category}{albuminuria_category}"


@pytest.mark.parametrize(
    ("raw_stage", "expected_stage"),
    [
        ("C4", "С4"),
        ("G4", "С4"),
        ("c3a", "С3а"),
        ("g3b", "С3б"),
    ],
)
def test_calculate_ckd_prognosis_normalizes_old_stage_formats(raw_stage, expected_stage):
    result = calculate_ckd_prognosis(raw_stage, "A3")

    assert result["gfr_category"] == expected_stage
    assert result["albuminuria_category"] == "A3"
    assert result["combined"].startswith(expected_stage)


def test_calculate_ckd_prognosis_uppercases_albuminuria():
    result = calculate_ckd_prognosis("С4", "a3")

    assert result["albuminuria_category"] == "A3"
    assert result["level"] == "very_high"


@pytest.mark.parametrize(
    ("gfr_category", "albuminuria_category"),
    [
        (None, "A1"),
        ("С4", None),
        ("", "A1"),
        ("С4", ""),
        ("X1", "A1"),
        ("С4", "A4"),
    ],
)
def test_calculate_ckd_prognosis_invalid_or_missing_values_return_empty_result(
    gfr_category,
    albuminuria_category,
):
    result = calculate_ckd_prognosis(gfr_category, albuminuria_category)

    assert result["level"] is None
    assert result["text"] is None
    assert result["combined"] is None
    assert result["prognosis_level"] is None
    assert result["prognosis_text"] is None
