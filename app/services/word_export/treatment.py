"""Назначения, диета, рекомендации и дата контроля для Word."""

from __future__ import annotations

from .formatting import add_field_inline, add_small_table, fmt_date
from .text import clean_word_recommendations


def add_treatment_section(doc, context):
    appointment = context["appointment"]
    medications = context["medications"]
    diet_info = context["diet_info"]

    if medications:
        med_rows = []
        for index, med in enumerate(medications, start=1):
            med_rows.append(
                [
                    index,
                    med.get("medication"),
                    med.get("dosage"),
                    med.get("schedule"),
                ]
            )
        add_small_table(
            doc,
            "Назначения",
            ["№", "Препарат", "Дозировка", "Схема"],
            med_rows,
        )
    else:
        add_field_inline(doc, "Назначения", "—", space_before=5)

    diet = None
    next_control_date = None
    recommendations = None

    if diet_info:
        diet = diet_info.get("diet")
        next_control_date = diet_info.get("next_control_date")
        recommendations = diet_info.get("recommendations")

    if not diet:
        diet = appointment.get("diet")
    if not next_control_date:
        next_control_date = appointment.get("next_control_date")
    if not recommendations:
        recommendations = appointment.get("recommendations")

    recommendations = clean_word_recommendations(recommendations)

    add_field_inline(doc, "Диета", diet, space_before=3)
    if recommendations:
        add_field_inline(doc, "Рекомендации", recommendations)
    add_field_inline(doc, "Дата следующего контроля", fmt_date(next_control_date))
