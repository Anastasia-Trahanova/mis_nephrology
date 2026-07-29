"""Блок «Заключение» Word-документа."""

from __future__ import annotations

from .formatting import add_field_inline, add_table_title
from .text import icd10_diagnosis_item_text


_DIAGNOSIS_LABELS = (
    ("main", "Основной диагноз"),
    ("complication", "Осложнения основного диагноза"),
    ("comorbidity", "Сопутствующие заболевания"),
)


def _group_text(records, diagnosis_type: str) -> str:
    items = [
        item
        for item in records
        if item.get("diagnosis_type") == diagnosis_type
    ]
    items.sort(key=lambda item: (item.get("sort_order") or 0, item.get("id") or 0))
    values = [icd10_diagnosis_item_text(item) for item in items]
    return "; ".join(value for value in values if value)


def add_conclusion_section(doc, context):
    """Выводит только заполненные группы диагнозов."""
    records = context.get("diagnoses") or []
    groups = [
        (label, _group_text(records, diagnosis_type))
        for diagnosis_type, label in _DIAGNOSIS_LABELS
    ]
    if not any(value for _, value in groups):
        return

    add_table_title(doc, "Заключение")
    for label, value in groups:
        add_field_inline(doc, label, value, space_before=0)
