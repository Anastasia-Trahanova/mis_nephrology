"""Шапка и заголовок Word-заключения."""

from __future__ import annotations

from .formatting import add_centered_paragraph


def add_clinic_header(doc, location_info):
    """Шапка клиники в две строки."""
    if location_info:
        company_name = location_info.get("company_name") or "ООО «КОМПАНИЯ «ФЕСФАРМ»"
        location_name = location_info.get("location_name") or ""
        location_address = location_info.get("location_address") or ""
        branch_phone = location_info.get("branch_phone") or ""
        company_phone = location_info.get("company_phone") or ""
        phone = branch_phone or company_phone or ""
        branch_email = location_info.get("branch_email") or ""
        company_email = location_info.get("company_email") or ""
        email = branch_email or company_email or ""

        first_line = company_name
        if location_name:
            first_line += f" — {location_name}"

        second_line_parts = []
        if location_address:
            second_line_parts.append(location_address)
        if phone:
            second_line_parts.append(f"Тел: {phone}")
        if email:
            second_line_parts.append(f"Email: {email}")

        add_centered_paragraph(doc, first_line, size=9, bold=False, space_after=0)
        add_centered_paragraph(doc, " | ".join(second_line_parts), size=9, bold=False, space_after=4)
    else:
        add_centered_paragraph(doc, "ООО «КОМПАНИЯ «ФЕСФАРМ»", size=9, bold=False, space_after=4)


def add_document_title(doc):
    add_centered_paragraph(doc, "КОНСУЛЬТАТИВНОЕ ЗАКЛЮЧЕНИЕ", size=14, bold=True, space_after=6)
