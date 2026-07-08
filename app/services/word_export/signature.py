"""Подпись врача в Word-заключении."""

from __future__ import annotations

from docx.shared import Pt

from .formatting import clean_value, fmt_date, set_run_font


def add_signature_section(doc, appointment):
    doc.add_paragraph()
    signature_paragraph = doc.add_paragraph()
    signature_paragraph.paragraph_format.space_before = Pt(10)
    signature_paragraph.paragraph_format.space_after = Pt(0)
    signature_paragraph.paragraph_format.line_spacing = 1

    appointment_date_text = fmt_date(appointment.get("appointment_date"))
    doctor_name = clean_value(appointment.get("doctor_name"))
    run = signature_paragraph.add_run(
        f"Дата приёма: {appointment_date_text} __________________ / {doctor_name} /"
    )
    set_run_font(run, size=12, bold=False)
