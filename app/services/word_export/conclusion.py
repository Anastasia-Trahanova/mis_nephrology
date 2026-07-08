"""Блок «Заключение» Word-документа."""

from __future__ import annotations

from .formatting import add_field_inline, add_table_title
from .text import icd10_diagnoses_conclusion_text, kdigo_conclusion_text


def add_conclusion_section(doc, context):
    """Диагнозы МКБ-10 одной строкой и сохранённый прогноз KDIGO."""
    diagnosis_text = icd10_diagnoses_conclusion_text(context.get("diagnoses") or [])
    prognosis_text = kdigo_conclusion_text((context.get("kdigo") or {}).get("current"))

    if not diagnosis_text and not prognosis_text:
        return

    add_table_title(doc, "Заключение")

    if diagnosis_text:
        add_field_inline(doc, "Диагноз", diagnosis_text, space_before=0)

    if prognosis_text:
        add_field_inline(doc, "Прогноз по KDIGO", prognosis_text)
