"""
Назначение файла: главный сервис сборки Word-заключения.

Что выполняет файл:
- создаёт python-docx Document;
- задаёт базовые параметры страницы и шрифта;
- вызывает разделы документа в нужном порядке;
- возвращает готовый BytesIO и имя файла для роутера экспорта.
"""

from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.shared import Cm, Pt

from .data import get_word_export_context
from .formatting import fmt_date, safe_filename
from .sections import (
    add_clinic_header,
    add_conclusion_section,
    add_document_title,
    add_examination_section,
    add_lab_sections,
    add_patient_section,
    add_signature_section,
    add_survey_section,
    add_treatment_section,
)


def build_appointment_docx(appointment_id: int):
    """Возвращает (buffer, filename) для Word-экспорта или None, если приём не найден."""
    context = get_word_export_context(appointment_id)
    if context is None:
        return None

    appointment = context["appointment"]
    doc = Document()

    section = doc.sections[0]
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.7)
    section.right_margin = Cm(1.3)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    add_clinic_header(doc, context["location_info"])
    add_document_title(doc)
    add_patient_section(doc, appointment)
    add_survey_section(doc, appointment)
    add_examination_section(doc, appointment)
    add_lab_sections(doc, context)
    add_conclusion_section(doc, context)
    add_treatment_section(doc, context)
    add_signature_section(doc, appointment)

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    patient_fio = safe_filename(appointment.get("patient_fio"))
    appointment_date = fmt_date(appointment.get("appointment_date")).replace(".", "-")
    filename = f"Заключение_{patient_fio}_{appointment_date}.docx"
    return buffer, filename
