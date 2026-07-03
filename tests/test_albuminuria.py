"""
Тесты расчета ACR и категории альбуминурии.
Этот файл проверяет расчет альбумин-креатининового отношения мочи:

    ACR = альбумин мочи / креатинин мочи

Основная единица результата мг/ммоль

Тесты проверяют не только саму формулу, но и пересчет единиц измерения перед подстановкой значений в формулу.
Код должен сначала привести значения к единому виду:
    альбумин мочи   -> мг/л
    креатинин мочи -> ммоль/л
и только потом считать:
    мг/л / ммоль/л = мг/ммоль

Какие единицы проверяются
-------------------------
Альбумин мочи:
- mg_l — мг/л;
- g_l  — г/л.

Креатинин мочи:
- mmol_l — ммоль/л;
- umol_l — мкмоль/л.

Контрольные случаи
------------------
- 30 мг/л / 10 ммоль/л = 3 мг/ммоль;
- 0.03 г/л / 10000 мкмоль/л = 3 мг/ммоль;
- 300 мг/л / 10 ммоль/л = 30 мг/ммоль.

Также проверяется пересчет: ACR мг/г = ACR мг/ммоль × 8.84

Категории альбуминурии
----------------------
- A1: ACR < 3 мг/ммоль;
- A2: ACR 3–30 мг/ммоль;
- A3: ACR > 30 мг/ммоль.

"""

import pytest

from app.medical_algorithms.albuminuria import (
    calculate_albumin_creatinine_ratio,
    calculate_albuminuria_metrics,
    get_albuminuria_category,
    normalize_urine_albumin_to_mg_l,
    normalize_urine_creatinine_to_mmol_l,
)


def test_normalize_urine_albumin_units():
    assert normalize_urine_albumin_to_mg_l(30, "mg_l") == 30
    assert normalize_urine_albumin_to_mg_l(0.03, "g_l") == 30


def test_normalize_urine_creatinine_units():
    assert normalize_urine_creatinine_to_mmol_l(10, "mmol_l") == 10
    assert normalize_urine_creatinine_to_mmol_l(10000, "umol_l") == 10


@pytest.mark.parametrize(
    ("urine_albumin", "albumin_unit", "urine_creatinine", "creatinine_unit", "expected_acr"),
    [
        # 30 мг/л / 10 ммоль/л = 3 мг/ммоль
        (30, "mg_l", 10, "mmol_l", 3.0),

        # 0.03 г/л = 30 мг/л; 10000 мкмоль/л = 10 ммоль/л; ACR = 3
        (0.03, "g_l", 10000, "umol_l", 3.0),

        # 300 мг/л / 10 ммоль/л = 30 мг/ммоль
        (300, "mg_l", 10, "mmol_l", 30.0),
    ],
)
def test_calculate_albumin_creatinine_ratio(
    urine_albumin,
    albumin_unit,
    urine_creatinine,
    creatinine_unit,
    expected_acr,
):
    assert (
        calculate_albumin_creatinine_ratio(
            urine_albumin=urine_albumin,
            urine_albumin_unit=albumin_unit,
            urine_creatinine=urine_creatinine,
            urine_creatinine_unit=creatinine_unit,
        )
        == expected_acr
    )


@pytest.mark.parametrize(
    ("acr_mg_mmol", "expected_category"),
    [
        (0, "A1"),
        (2.99, "A1"),
        (3, "A2"),
        (30, "A2"),
        (30.01, "A3"),
        (100, "A3"),
    ],
)
def test_get_albuminuria_category_boundaries(acr_mg_mmol, expected_category):
    assert get_albuminuria_category(acr_mg_mmol) == expected_category


def test_calculate_albuminuria_metrics_returns_acr_mg_mmol_mg_g_and_category():
    result = calculate_albuminuria_metrics(
        urine_albumin=30,
        urine_albumin_unit="mg_l",
        urine_creatinine=10,
        urine_creatinine_unit="mmol_l",
    )

    assert result["albumin_creatinine_ratio"] == 3.0
    assert result["albumin_creatinine_ratio_mg_g"] == 26.52
    assert result["albuminuria_category"] == "A2"


@pytest.mark.parametrize(
    ("urine_albumin", "albumin_unit", "urine_creatinine", "creatinine_unit"),
    [
        (None, "mg_l", 10, "mmol_l"),
        (30, "bad_unit", 10, "mmol_l"),
        (30, "mg_l", None, "mmol_l"),
        (30, "mg_l", 0, "mmol_l"),
        (30, "mg_l", -1, "mmol_l"),
        (30, "mg_l", 10, "bad_unit"),
    ],
)
def test_calculate_albumin_creatinine_ratio_invalid_inputs_return_none(
    urine_albumin,
    albumin_unit,
    urine_creatinine,
    creatinine_unit,
):
    assert (
        calculate_albumin_creatinine_ratio(
            urine_albumin=urine_albumin,
            urine_albumin_unit=albumin_unit,
            urine_creatinine=urine_creatinine,
            urine_creatinine_unit=creatinine_unit,
        )
        is None
    )
