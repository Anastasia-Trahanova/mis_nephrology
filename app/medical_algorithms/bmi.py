"""
Расчёт индекса массы тела (ИМТ).

Модуль содержит чистую медицинскую расчётную функцию:
- не работает с БД;
- не читает .env;
- не зависит от FastAPI, request, session, HTML;
- не выполняет INSERT/UPDATE.

height_cm — рост в сантиметрах.
weight_kg — вес в килограммах.

Формула:
    BMI = weight_kg / (height_m ** 2)
"""

from typing import Optional, Union


NumberLike = Union[int, float, str]


def _to_float(value: NumberLike | None) -> Optional[float]:
    """
    Безопасно преобразует значение в float.

    Поддерживает:
    - числа;
    - строки;
    - десятичную запятую;
    - пробелы внутри строки.

    Возвращает None, если значение пустое или нечисловое.
    """
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        number = float(value)
        return number if number == number else None  # защита от NaN

    normalized = str(value).strip().replace(" ", "").replace(",", ".")
    if not normalized:
        return None

    try:
        return float(normalized)
    except ValueError:
        return None


def calculate_bmi(
    height_cm: NumberLike | None,
    weight_kg: NumberLike | None,
) -> Optional[float]:
    """
    Считает индекс массы тела.

    Возвращает:
    - float с двумя знаками после запятой;
    - None, если рост/вес не заполнены или некорректны.

    Примеры:
        calculate_bmi(170, 70) -> 24.22
        calculate_bmi("175", "85") -> 27.76
        calculate_bmi("170", "70,5") -> 24.39
    """
    height = _to_float(height_cm)
    weight = _to_float(weight_kg)

    if height is None or weight is None:
        return None

    if height <= 0 or weight <= 0:
        return None

    height_m = height / 100
    if height_m <= 0:
        return None

    return round(weight / (height_m ** 2), 2)