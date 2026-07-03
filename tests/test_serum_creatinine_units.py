"""
Тесты пересчета единиц креатинина крови/плазмы.
Этот файл проверяет новую возможность расчетного слоя принимать креатинин крови в разных единицах измерения:
- `umol_l` — мкмоль/л;
- `mg_dl`  — мг/дл.
"""

import pytest

from app.medical_algorithms.common import (
    SERUM_CREATININE_MG_DL,
    SERUM_CREATININE_UMOL_L,
    normalize_serum_creatinine_to_mg_dl,
    normalize_serum_creatinine_to_umol_l,
)
from app.medical_algorithms.cockcroft_gault import calculate_cockcroft_gault
from app.medical_algorithms.egfr import calculate_ckd_epi_2021
from app.medical_algorithms.metrics import calculate_all_metrics


@pytest.mark.parametrize(
    ("creatinine_umol_l", "expected_mg_dl"),
    [
        (88.4, 1.0),
        (106.08, 1.2),
        (176.8, 2.0),
    ],
)
def test_normalize_serum_creatinine_umol_l_to_mg_dl(
    creatinine_umol_l,
    expected_mg_dl,
):
    assert normalize_serum_creatinine_to_mg_dl(
        creatinine_umol_l,
        SERUM_CREATININE_UMOL_L,
    ) == pytest.approx(expected_mg_dl)


@pytest.mark.parametrize(
    ("creatinine_mg_dl", "expected_umol_l"),
    [
        (1.0, 88.4),
        (1.2, 106.08),
        (2.0, 176.8),
    ],
)
def test_normalize_serum_creatinine_mg_dl_to_umol_l(
    creatinine_mg_dl,
    expected_umol_l,
):
    assert normalize_serum_creatinine_to_umol_l(
        creatinine_mg_dl,
        SERUM_CREATININE_MG_DL,
    ) == pytest.approx(expected_umol_l)


def test_normalize_serum_creatinine_default_unit_is_umol_l():
    assert normalize_serum_creatinine_to_mg_dl(88.4) == pytest.approx(1.0)
    assert normalize_serum_creatinine_to_umol_l(88.4) == pytest.approx(88.4)


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (None, SERUM_CREATININE_UMOL_L),
        ("", SERUM_CREATININE_UMOL_L),
        (0, SERUM_CREATININE_UMOL_L),
        (-1, SERUM_CREATININE_UMOL_L),
        (88.4, "unknown_unit"),
    ],
)
def test_normalize_serum_creatinine_invalid_values_return_none(value, unit):
    assert normalize_serum_creatinine_to_mg_dl(value, unit) is None
    assert normalize_serum_creatinine_to_umol_l(value, unit) is None


def test_ckd_epi_same_result_for_umol_l_and_mg_dl_male():
    result_umol_l = calculate_ckd_epi_2021(
        creatinine_umol_l=106.08,
        age=60,
        gender="Мужской",
        serum_creatinine_unit=SERUM_CREATININE_UMOL_L,
    )

    result_mg_dl = calculate_ckd_epi_2021(
        creatinine_umol_l=1.2,
        age=60,
        gender="Мужской",
        serum_creatinine_unit=SERUM_CREATININE_MG_DL,
    )

    assert result_umol_l == 69.23
    assert result_mg_dl == 69.23
    assert result_umol_l == result_mg_dl


def test_ckd_epi_same_result_for_umol_l_and_mg_dl_female():
    result_umol_l = calculate_ckd_epi_2021(
        creatinine_umol_l=88.4,
        age=50,
        gender="Женский",
        serum_creatinine_unit=SERUM_CREATININE_UMOL_L,
    )

    result_mg_dl = calculate_ckd_epi_2021(
        creatinine_umol_l=1.0,
        age=50,
        gender="Женский",
        serum_creatinine_unit=SERUM_CREATININE_MG_DL,
    )

    assert result_umol_l == 68.63
    assert result_mg_dl == 68.63
    assert result_umol_l == result_mg_dl


def test_cockcroft_gault_same_result_for_umol_l_and_mg_dl_male():
    result_umol_l = calculate_cockcroft_gault(
        creatinine_umol_l=106.08,
        age=60,
        weight_kg=70,
        gender="Мужской",
        serum_creatinine_unit=SERUM_CREATININE_UMOL_L,
    )

    result_mg_dl = calculate_cockcroft_gault(
        creatinine_umol_l=1.2,
        age=60,
        weight_kg=70,
        gender="Мужской",
        serum_creatinine_unit=SERUM_CREATININE_MG_DL,
    )

    assert result_umol_l == 64.81
    assert result_mg_dl == 64.81
    assert result_umol_l == result_mg_dl


def test_cockcroft_gault_same_result_for_umol_l_and_mg_dl_female():
    result_umol_l = calculate_cockcroft_gault(
        creatinine_umol_l=88.4,
        age=60,
        weight_kg=70,
        gender="Женский",
        serum_creatinine_unit=SERUM_CREATININE_UMOL_L,
    )

    result_mg_dl = calculate_cockcroft_gault(
        creatinine_umol_l=1.0,
        age=60,
        weight_kg=70,
        gender="Женский",
        serum_creatinine_unit=SERUM_CREATININE_MG_DL,
    )

    assert result_umol_l == 66.11
    assert result_mg_dl == 66.11
    assert result_umol_l == result_mg_dl


def test_calculate_all_metrics_same_result_for_umol_l_and_mg_dl():
    result_umol_l = calculate_all_metrics(
        creatinine_umol_l=106.08,
        birth_date="1966-01-01",
        appointment_date="2026-01-01",
        gender="Мужской",
        weight_kg=70,
        serum_creatinine_unit=SERUM_CREATININE_UMOL_L,
    )

    result_mg_dl = calculate_all_metrics(
        creatinine_umol_l=1.2,
        birth_date="1966-01-01",
        appointment_date="2026-01-01",
        gender="Мужской",
        weight_kg=70,
        serum_creatinine_unit=SERUM_CREATININE_MG_DL,
    )

    assert result_umol_l == result_mg_dl
    assert result_umol_l == {
        "egfr_ckdepi": 69.23,
        "crcl_cockcroft_gault": 64.81,
        "ckd_stage": "С2",
    }


def test_unknown_serum_creatinine_unit_blocks_false_calculation():
    assert (
        calculate_ckd_epi_2021(
            creatinine_umol_l=106.08,
            age=60,
            gender="Мужской",
            serum_creatinine_unit="bad_unit",
        )
        is None
    )

    assert (
        calculate_cockcroft_gault(
            creatinine_umol_l=106.08,
            age=60,
            weight_kg=70,
            gender="Мужской",
            serum_creatinine_unit="bad_unit",
        )
        is None
    )


def test_calculations_bridge_exports_serum_creatinine_normalizers():
    from app.calculations import (
        normalize_serum_creatinine_to_mg_dl as bridge_to_mg_dl,
        normalize_serum_creatinine_to_umol_l as bridge_to_umol_l,
    )

    assert bridge_to_mg_dl(106.08, "umol_l") == pytest.approx(1.2)
    assert bridge_to_umol_l(1.2, "mg_dl") == pytest.approx(106.08)
