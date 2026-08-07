"""Шапка и заголовок Word-заключения."""

from __future__ import annotations

from .formatting import add_centered_paragraph, has_value


def _first(location_info, *keys) -> str:
    for key in keys:
        value = location_info.get(key)
        if has_value(value):
            return " ".join(str(value).split())
    return ""


def _join_unique(parts, separator=", ") -> str:
    result = []
    for part in parts:
        text = " ".join(str(part or "").split()).strip(" ,")
        if text and text not in result:
            result.append(text)
    return separator.join(result)


def _location_name(location_info) -> str:
    """Отделение, затем филиал, затем юридическое лицо."""
    location_name = _first(location_info, "location_name", "name")
    branch_name = _first(location_info, "branch_name")
    company_name = _first(location_info, "company_name")

    same_as_company = (
        bool(branch_name)
        and bool(company_name)
        and branch_name.casefold() == company_name.casefold()
    )
    branch_display = (
        "" if same_as_company else (f"Филиал «{branch_name}»" if branch_name else "")
    )
    return _join_unique(
        [
            location_name,
            branch_display,
            company_name,
        ]
    )

def _location_address(location_info) -> str:
    postal_code = _first(
        location_info,
        "postal_code",
        "branch_postal_code",
        "location_postal_code",
        "zip_code",
        "index",
    )

    address = _first(
        location_info,
        "location_full_address",
        "location_address",
        "branch_address",
        "full_address",
        "address",
        "company_address",
    )

    if not address:
        address = _join_unique(
            [
                location_info.get("region"),
                location_info.get("district"),
                location_info.get("city"),
                location_info.get("settlement"),
                location_info.get("street"),
                location_info.get("house"),
                location_info.get("building"),
                location_info.get("office"),
            ]
        )

    if postal_code and address and not address.startswith(postal_code):
        return f"{postal_code}, {address}"
    return address or postal_code


def add_clinic_header(doc, location_info):
    """Единая строка: отделение, филиал, компания, адрес и контакты."""
    location_info = location_info or {}

    name = _location_name(location_info)
    address = _location_address(location_info)

    phone = _first(
        location_info,
        "location_phone",
        "branch_phone",
        "company_phone",
        "phone",
    )
    fax = _first(
        location_info,
        "location_fax",
        "branch_fax",
        "fax",
    )
    email = _first(
        location_info,
        "location_email",
        "branch_email",
        "company_email",
        "email",
    )

    organization_and_address = _join_unique([name, address])
    if organization_and_address and not organization_and_address.endswith("."):
        organization_and_address += "."

    contacts = []
    if phone:
        contacts.append(f"Тел.: {phone}")
    if fax:
        contacts.append(f"факс: {fax}")
    if email:
        contacts.append(email)

    header_text = " ".join(
        part for part in (organization_and_address, "; ".join(contacts)) if part
    )
    add_centered_paragraph(
        doc,
        header_text,
        size=9,
        bold=False,
        space_after=4,
    )

def add_document_title(doc, visit_kind: str = "повторный"):
    """Добавляет заголовок в том же виде, что и в ЭМК."""
    kind = "первичный" if visit_kind == "первичный" else "повторный"
    add_centered_paragraph(
        doc,
        f"Консультативный приём ({kind})",
        size=14,
        bold=True,
        space_after=6,
    )
