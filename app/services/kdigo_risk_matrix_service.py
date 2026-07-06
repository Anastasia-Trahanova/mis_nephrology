"""
Назначение файла: подготовка матрицы риска по KDIGO для карточки пациента.

Что выполняет файл:
- получает список уже сохранённых строк из ckd_prognosis_results;
- строит матрицу: строки = даты СКФ, столбцы = даты альбуминурии;
- добавляет к заголовкам строк/столбцов не только даты, но и категории
  показателей, например "03.07.2026 / С3а" и "29.06.2026 / A2";
- кладёт в ячейки только те комбинации, которые реально были сохранены
  на приёмах;
- не пересчитывает риск задним числом и не создаёт новых сочетаний.

Что редактировать здесь:
- порядок сортировки строк и столбцов матрицы;
- правила формирования подписи даты и категории;
- правила группировки нескольких сохранённых строк в одной ячейке.

Что не редактировать здесь:
- SQL-запросы;
- медицинскую матрицу риска;
- текст заключения для врача;
- HTML-разметку карточки пациента.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _to_date(value: Any) -> date | None:
    """Безопасно приводит значение из БД к date для группировки матрицы."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return None


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    """Читает поле как из dict, так и из RealDictRow/объекта."""
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return getattr(row, key, default)


def _unique_categories(values: list[str]) -> list[str]:
    """Возвращает категории без дублей, сохраняя исходный порядок."""
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _format_label(value: date, categories: list[str]) -> str:
    """Формирует заголовок матрицы: дата + стадия/категория."""
    if categories:
        return f"{_format_date(value)} / {', '.join(categories)}"
    return _format_date(value)


def build_kdigo_risk_matrix(history: list[Any] | tuple[Any, ...] | None) -> dict[str, Any]:
    """Строит матрицу сохранённых KDIGO-комбинаций для шаблона.

    Важно: функция работает только с уже сохранёнными строками.
    Она не создаёт новые сочетания СКФ × альбуминурия и не пересчитывает
    риск для старых анализов.
    """
    history = list(history or [])

    gfr_dates: list[date] = []
    albuminuria_dates: list[date] = []
    gfr_categories_by_date: dict[date, list[str]] = {}
    albuminuria_categories_by_date: dict[date, list[str]] = {}
    cell_map: dict[tuple[date, date], list[Any]] = {}

    for item in history:
        gfr_date = _to_date(_row_get(item, "gfr_investigation_date"))
        albuminuria_date = _to_date(_row_get(item, "albuminuria_investigation_date"))
        if not gfr_date or not albuminuria_date:
            continue

        if gfr_date not in gfr_dates:
            gfr_dates.append(gfr_date)
        if albuminuria_date not in albuminuria_dates:
            albuminuria_dates.append(albuminuria_date)

        gfr_categories_by_date.setdefault(gfr_date, []).append(str(_row_get(item, "gfr_category", "") or ""))
        albuminuria_categories_by_date.setdefault(albuminuria_date, []).append(
            str(_row_get(item, "albuminuria_category", "") or "")
        )
        cell_map.setdefault((gfr_date, albuminuria_date), []).append(item)

    gfr_dates.sort()
    albuminuria_dates.sort()

    albuminuria_columns: list[dict[str, Any]] = []
    for albuminuria_date in albuminuria_dates:
        categories = _unique_categories(albuminuria_categories_by_date.get(albuminuria_date, []))
        albuminuria_columns.append(
            {
                "date": albuminuria_date,
                "categories": categories,
                "label": _format_label(albuminuria_date, categories),
            }
        )

    rows: list[dict[str, Any]] = []
    for gfr_date in gfr_dates:
        gfr_categories = _unique_categories(gfr_categories_by_date.get(gfr_date, []))
        cells = []
        for albuminuria_column in albuminuria_columns:
            albuminuria_date = albuminuria_column["date"]
            cells.append(
                {
                    "albuminuria_date": albuminuria_date,
                    "items": cell_map.get((gfr_date, albuminuria_date), []),
                }
            )
        rows.append(
            {
                "gfr_date": gfr_date,
                "gfr_categories": gfr_categories,
                "label": _format_label(gfr_date, gfr_categories),
                "cells": cells,
            }
        )

    return {
        "gfr_dates": gfr_dates,
        "albuminuria_dates": albuminuria_dates,
        "albuminuria_columns": albuminuria_columns,
        "rows": rows,
        "has_values": bool(gfr_dates and albuminuria_dates and history),
    }
