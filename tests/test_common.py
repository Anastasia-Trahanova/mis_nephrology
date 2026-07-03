"""
Тесты общих вспомогательных функций медицинских алгоритмов.
Этот файл проверяет подготовку данных, которые потом используются в расчетах:
1. перевод введенного значения в число;
2. расчет возраста пациента на дату приема;
3. определение женского пола в старом формате проекта.

Если возраст рассчитан неверно или строка с числом не преобразовалась в float, то CKD-EPI, Cockcroft–Gault и другие расчеты тоже будут неверными.

Какие случаи проверяются
------------------------
- число с точкой: "123.4";
- число с запятой: "123,4";
- пустое значение;
- нечисловой текст;
- возраст до дня рождения;
- возраст в день рождения;
- даты как строки и как date-объекты;
- варианты пола: False, "Женский", "female" и т.д.

"""

from datetime import date

import pytest

from app.medical_algorithms.common import calculate_age, is_female_gender, to_float


def test_to_float_accepts_dot_and_comma():
    assert to_float("123.4") == 123.4
    assert to_float("123,4") == 123.4


def test_to_float_empty_or_invalid_returns_none():
    assert to_float(None) is None
    assert to_float("") is None
    assert to_float("не число") is None


def test_calculate_age_before_birthday():
    assert calculate_age("1980-06-10", "2026-06-09") == 45


def test_calculate_age_on_birthday():
    assert calculate_age("1980-06-10", "2026-06-10") == 46


def test_calculate_age_accepts_date_objects():
    assert calculate_age(date(1980, 1, 1), date(2026, 1, 1)) == 46


def test_calculate_age_missing_value_returns_none():
    assert calculate_age(None, "2026-01-01") is None
    assert calculate_age("1980-01-01", None) is None


@pytest.mark.parametrize(
    "gender",
    [False, "false", "False", "Женский", "женский", "female", "Female"],
)
def test_is_female_gender_true_variants(gender):
    assert is_female_gender(gender) is True


@pytest.mark.parametrize(
    "gender",
    [True, "true", "Мужской", "мужской", "male", "Male", None],
)
def test_is_female_gender_false_variants(gender):
    assert is_female_gender(gender) is False
