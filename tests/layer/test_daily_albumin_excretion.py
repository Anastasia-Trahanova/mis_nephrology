"""
Назначение файла:
Проверка определения категории альбуминурии по суточной экскреции альбумина.

Что проверяется:
- границы A1, A2 и A3;
- поддержка десятичной запятой;
- отказ от отрицательных и пустых значений.
"""

from app.medical_algorithms.albuminuria import (
    get_daily_albumin_excretion_category,
)


def test_daily_albumin_excretion_categories():
    assert get_daily_albumin_excretion_category("0") == "A1"
    assert get_daily_albumin_excretion_category("29,9") == "A1"
    assert get_daily_albumin_excretion_category("30") == "A2"
    assert get_daily_albumin_excretion_category("300") == "A2"
    assert get_daily_albumin_excretion_category("300.1") == "A3"


def test_daily_albumin_excretion_rejects_invalid_values():
    assert get_daily_albumin_excretion_category(None) is None
    assert get_daily_albumin_excretion_category("") is None
    assert get_daily_albumin_excretion_category("-1") is None
