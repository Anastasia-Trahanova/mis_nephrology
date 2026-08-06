# Проверка шапки медицинской организации в Word-заключении.

from pathlib import Path

from docx import Document

from app.services.word_export.header import add_clinic_header


def test_word_header_uses_location_contacts_and_required_order():
    doc = Document()

    add_clinic_header(
        doc,
        {
            "location_name": "Отделение гемодиализа",
            "branch_name": "ФЕСФАРМ НН",
            "company_name": "ООО «КОМПАНИЯ «ФЕСФАРМ»",
            "location_address": (
                "603065, г. Нижний Новгород, ул. Дьяконова, "
                "д.2/6, литера А"
            ),
            "location_phone": "282-44-82, +7 964 831 4200",
            "location_fax": "282-33-82",
            "location_email": "fesfarm.avtozavod@yandex.ru",
            "branch_phone": "+7 (831) 282-33-82",
            "branch_email": "nn@fesfarm.ru",
        },
    )

    paragraphs = [paragraph.text for paragraph in doc.paragraphs if paragraph.text]
    assert paragraphs == [
        (
            "Отделение гемодиализа, Филиал «ФЕСФАРМ НН», "
            "ООО «КОМПАНИЯ «ФЕСФАРМ», 603065, г. Нижний Новгород, "
            "ул. Дьяконова, д.2/6, литера А. "
            "Тел.: 282-44-82, +7 964 831 4200; "
            "факс: 282-33-82; fesfarm.avtozavod@yandex.ru"
        )
    ]


def test_location_repository_selects_location_contacts_and_fax():
    source = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "repositories"
        / "reference_data.py"
    ).read_text(encoding="utf-8")

    assert "l.phone AS location_phone" in source
    assert "l.email AS location_email" in source
    assert "l.fax AS location_fax" in source
    assert "b.fax AS branch_fax" in source
