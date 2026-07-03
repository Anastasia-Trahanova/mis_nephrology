"""
Тесты определения и нормализации категории СКФ при ХБП.
Этот файл проверяет логику определения категории СКФ по eGFR: С1, С2, С3а, С3б, С4, С5
Также проверяется нормализация вариантов записи стадии:
    G4  -> С4
    C4  -> С4
    g3b -> С3б
    C3a -> С3а
В проекте принято хранить стадии ХБП с русской буквой `С`. Если где-то в коде появятся `G4` или `C4`, регистр ХБП и SQL-запросы могут начать работать неправильно. 
Эти тесты защищают от такой ошибки.

Какие границы проверяются
-------------------------
- eGFR 90    -> С1
- eGFR 60    -> С2
- eGFR 45    -> С3а
- eGFR 30    -> С3б
- eGFR 15    -> С4
- eGFR ниже 15 -> С5

"""

import pytest

from app.medical_algorithms.ckd_stage import (
    ALLOWED_CKD_STAGES,
    get_ckd_stage,
    is_valid_ckd_stage,
    normalize_ckd_stage_for_storage,
)


@pytest.mark.parametrize(
    ("egfr", "expected_stage"),
    [
        (120, "С1"),
        (90, "С1"),
        (89.99, "С2"),
        (60, "С2"),
        (59.99, "С3а"),
        (45, "С3а"),
        (44.99, "С3б"),
        (30, "С3б"),
        (29.99, "С4"),
        (15, "С4"),
        (14.99, "С5"),
        (0, "С5"),
    ],
)
def test_get_ckd_stage_boundaries(egfr, expected_stage):
    assert get_ckd_stage(egfr) == expected_stage


@pytest.mark.parametrize(
    ("raw_stage", "expected_stage"),
    [
        ("С1", "С1"),
        ("с2", "С2"),
        ("C3a", "С3а"),
        ("c3a", "С3а"),
        ("C3b", "С3б"),
        ("c3b", "С3б"),
        ("G4", "С4"),
        ("g5", "С5"),
        (" С4 ", "С4"),
    ],
)
def test_normalize_ckd_stage_for_storage(raw_stage, expected_stage):
    assert normalize_ckd_stage_for_storage(raw_stage) == expected_stage


def test_normalize_ckd_stage_none_or_empty():
    assert normalize_ckd_stage_for_storage(None) is None
    assert normalize_ckd_stage_for_storage("") is None
    assert normalize_ckd_stage_for_storage("   ") is None


def test_allowed_ckd_stages_use_russian_cyrillic_c():
    assert ALLOWED_CKD_STAGES == {"С1", "С2", "С3а", "С3б", "С4", "С5"}

    for stage in ALLOWED_CKD_STAGES:
        assert stage.startswith("С")  # русская С


@pytest.mark.parametrize("stage", ["С1", "C2", "G3a", "g3b", "С4", "C5"])
def test_is_valid_ckd_stage_accepts_normalizable_values(stage):
    assert is_valid_ckd_stage(stage) is True


@pytest.mark.parametrize("stage", [None, "", "X1", "С6", "A1"])
def test_is_valid_ckd_stage_rejects_wrong_values(stage):
    assert is_valid_ckd_stage(stage) is False
