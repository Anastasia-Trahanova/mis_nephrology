"""
Технический разбор значений HTML-форм.

Этот модуль нужен, чтобы убрать из роутеров повторяющуюся механику работы с
form.get(), form.getlist(), пустыми строками, числами с запятой и датами.

Здесь намеренно нет:
- SQL-запросов;
- FastAPI request/session;
- медицинских формул;
- сохранения данных в БД.

Функции из этого файла используются при создании нового пациента и при создании
нового приёма существующему пациенту.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable


def empty_to_none(value: Any) -> str | None:
    """Пустые строки превращает в None, чтобы в БД не летели пустые значения."""
    if value is None:
        return None

    value = str(value).strip()
    if value == "":
        return None

    return value


def numeric_to_db(value: Any) -> str | None:
    """
    Готовит числовое значение для PostgreSQL.

    Примеры:
    - "3,6" -> "3.6";
    - " 1 234,5 " -> "1234.5";
    - "" -> None.

    Возвращаем строку, как это было в исходном patients.py: psycopg сам приведёт
    значение к нужному числовому типу при INSERT.
    """
    value = empty_to_none(value)
    if value is None:
        return None

    return value.replace(" ", "").replace(",", ".")


def parse_bool(value: Any) -> bool:
    """Преобразует значение из формы в boolean."""
    return str(value).lower() in ["true", "1", "yes", "on"]


def join_form_values(values: Iterable[Any], other_value: Any = None) -> str | None:
    """
    Собирает значения чекбоксов и поле «другое» в одну строку.

    Используется, например, для кожных покровов и отёков:
    несколько выбранных вариантов + свободное поле.
    """
    result: list[str] = []

    for value in values:
        value = empty_to_none(value)
        if value:
            result.append(value)

    other_value = empty_to_none(other_value)
    if other_value:
        result.append(other_value)

    if not result:
        return None

    return ", ".join(result)


def has_any_value(form: Any, field_names: Iterable[str]) -> bool:
    """Проверяет, заполнено ли хоть одно поле из списка."""
    for field_name in field_names:
        if empty_to_none(form.get(field_name)):
            return True
    return False


def get_text_list(form: Any, field_name: str) -> list[str | None]:
    """Получает список текстовых значений из формы."""
    return [empty_to_none(value) for value in form.getlist(field_name)]


def get_numeric_list(form: Any, field_name: str) -> list[str | None]:
    """Получает список числовых значений из формы."""
    return [numeric_to_db(value) for value in form.getlist(field_name)]


def get_form_list_keep_empty(form: Any, field_name: str) -> list[str | None]:
    """
    Возвращает список значений формы с сохранением порядка.

    Пустые значения превращает в None, но не удаляет. Это нужно, чтобы связанные
    списки не разъезжались, например:
    - диагноз МКБ-10;
    - уточнение врача к этому диагнозу.
    """
    return [empty_to_none(value) for value in form.getlist(field_name)]


def value_at(values: list[Any] | None, index: int, default: Any = None) -> Any:
    """Безопасно возвращает значение из списка по индексу."""
    if values is None:
        return default

    if index < 0 or index >= len(values):
        return default

    return values[index]


def has_any_indexed_value(lists: Iterable[list[Any]], index: int) -> bool:
    """Проверяет, есть ли хоть одно заполненное значение в конкретном столбце анализа."""
    for values in lists:
        if empty_to_none(value_at(values, index)):
            return True
    return False


def date_at(values: list[Any] | None, index: int, default_date: Any) -> Any:
    """Берёт дату исследования из столбца анализа или дату приёма по умолчанию."""
    value = empty_to_none(value_at(values, index))
    return value or default_date


def parse_date_or_default(value: Any, default_date: Any) -> Any:
    """
    Преобразует дату из строки YYYY-MM-DD в date.

    Если даты нет — возвращает default_date. Если на вход уже пришёл date/datetime,
    возвращает его как дату без дополнительного преобразования.
    """
    value = empty_to_none(value)
    if not value:
        return default_date

    if hasattr(value, "year"):
        return value

    return datetime.strptime(value, "%Y-%m-%d").date()


def max_list_length(*lists: list[Any]) -> int:
    """Возвращает максимальную длину набора списков. Удобно для табличных анализов."""
    if not lists:
        return 0
    return max(len(values) for values in lists)
