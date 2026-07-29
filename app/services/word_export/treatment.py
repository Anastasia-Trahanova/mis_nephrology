"""Диета, рекомендации, медикаментозная терапия и дата следующего приёма."""

from __future__ import annotations

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt

from .formatting import add_field_inline, fmt_date, has_value, set_run_font
from .text import clean_word_recommendations


def _medication_text(medication) -> str:
    name = str(medication.get("medication") or "").strip()
    if not name:
        return ""

    text = name
    if has_value(medication.get("dosage")):
        text += f" — {str(medication.get('dosage')).strip()}"
    if has_value(medication.get("schedule")):
        text += f" ({str(medication.get('schedule')).strip()})"
    return text


def _add_medications_list(doc, medications):
    values = [
        text
        for text in (_medication_text(item) for item in medications or [])
        if text
    ]
    if not values:
        return

    title_paragraph = doc.add_paragraph()
    title_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    title_paragraph.paragraph_format.left_indent = Cm(0)
    title_paragraph.paragraph_format.first_line_indent = Cm(1.25)
    title_paragraph.paragraph_format.space_before = Pt(0)
    title_paragraph.paragraph_format.space_after = Pt(1)
    title_paragraph.paragraph_format.line_spacing = 1
    title_run = title_paragraph.add_run("Медикаментозная терапия:")
    set_run_font(title_run, size=12, bold=True)

    for value in values:
        paragraph = doc.add_paragraph()
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        paragraph.paragraph_format.left_indent = Cm(1.25)
        paragraph.paragraph_format.first_line_indent = Cm(-0.5)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.space_after = Pt(1)
        paragraph.paragraph_format.line_spacing = 1
        run = paragraph.add_run(f"• {value}")
        set_run_font(run, size=12, bold=False)


def add_treatment_section(doc, context):
    appointment = context["appointment"]
    medications = context.get("medications") or []
    diet_info = context.get("diet_info") or {}

    diet = diet_info.get("diet") or appointment.get("diet")
    recommendations = (
        diet_info.get("recommendations")
        or appointment.get("recommendations")
    )
    recommendations = clean_word_recommendations(recommendations)
    next_control_date = (
        diet_info.get("next_control_date")
        or appointment.get("next_control_date")
    )

    add_field_inline(doc, "Диета", diet, space_before=0)
    add_field_inline(doc, "Рекомендации", recommendations)
    _add_medications_list(doc, medications)
    next_date_paragraph = add_field_inline(doc, "Дата следующего приёма", fmt_date(next_control_date),)
    if next_date_paragraph is not None:
        next_date_paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        next_date_paragraph.paragraph_format.left_indent = Cm(0)
        next_date_paragraph.paragraph_format.first_line_indent = Cm(1.25)
