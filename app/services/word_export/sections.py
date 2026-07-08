"""
Назначение файла: публичные функции разделов Word-заключения.

Что выполняет файл:
- собирает экспортируемые функции разделов из тематических модулей;
- оставляет стабильный импорт для service.py;
- не содержит детальной логики разделов.
"""

from __future__ import annotations

from .conclusion import add_conclusion_section
from .header import add_clinic_header, add_document_title
from .labs import add_lab_sections
from .patient import add_examination_section, add_patient_section, add_survey_section
from .signature import add_signature_section
from .treatment import add_treatment_section

__all__ = [
    "add_clinic_header",
    "add_document_title",
    "add_patient_section",
    "add_survey_section",
    "add_examination_section",
    "add_lab_sections",
    "add_conclusion_section",
    "add_treatment_section",
    "add_signature_section",
]
