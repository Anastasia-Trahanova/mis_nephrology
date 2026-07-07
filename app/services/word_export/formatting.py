"""
Назначение файла: форматирование Word-заключения.

Что выполняет файл:
- форматирует даты, пустые значения и имя файла;
- применяет шрифт Times New Roman;
- добавляет стандартные абзацы и таблицы в python-docx документ;
- не загружает данные из БД и не решает, какие разделы должны быть в заключении.
"""

from __future__ import annotations

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt


def fmt_date(value, with_time: bool = False) -> str:
    """Форматирует date/datetime для заключения."""
    if not value:
        return "—"
    try:
        if with_time:
            return value.strftime("%d.%m.%Y %H:%M")
        return value.strftime("%d.%m.%Y")
    except Exception:
        return str(value)


def clean_value(value) -> str:
    """Красиво выводит пустые значения."""
    if value is None or value == "":
        return "—"
    return str(value)


def safe_filename(text) -> str:
    """Безопасное имя файла для скачивания."""
    text = text or "patient"
    text = re.sub(r'[\\/*?:"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_")[:100]


def set_run_font(run, size: int = 12, bold: bool = False):
    run.bold = bold
    run.font.name = "Times New Roman"
    run.font.size = Pt(size)


def add_centered_paragraph(doc, text, size: int = 9, bold: bool = False, space_after: int = 0):
    if not text:
        return
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1
    run = paragraph.add_run(str(text))
    set_run_font(run, size=size, bold=bold)


def add_field_inline(doc, title, value, size: int = 12, space_before: int = 0, space_after: int = 1):
    """Одно поле = одна строка/один абзац: Жалобы: текст жалоб."""
    if value is None or value == "":
        value = "—"

    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(space_before)
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = 1

    title_run = paragraph.add_run(f"{title}: ")
    set_run_font(title_run, size=size, bold=True)

    value_run = paragraph.add_run(str(value))
    set_run_font(value_run, size=size, bold=False)


def add_table_title(doc, title):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.space_before = Pt(6)
    paragraph.paragraph_format.space_after = Pt(2)
    paragraph.paragraph_format.line_spacing = 1
    run = paragraph.add_run(title)
    set_run_font(run, size=12, bold=True)


def format_table_cell(cell, value, bold: bool = False, size: int = 10):
    cell.text = ""
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_before = Pt(0)
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.line_spacing = 1
    run = paragraph.add_run(clean_value(value))
    set_run_font(run, size=size, bold=bold)


def add_small_table(doc, title, headers, rows):
    """Компактная таблица с названием исследования."""
    add_table_title(doc, title)
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True

    header_cells = table.rows[0].cells
    for index, header in enumerate(headers):
        format_table_cell(header_cells[index], header, bold=True, size=10)

    for row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(row):
            format_table_cell(cells[index], value, bold=False, size=10)

    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1

    doc.add_paragraph()


def add_history_table(doc, title, records, fields, date_key: str = "investigation_date"):
    """
    Таблица истории анализов/расчётов.

    Первый столбец — показатель, дальше столбцы по датам исследования/оценки.
    date_key позволяет использовать не только investigation_date, но и assessment_date
    для прогноза ХБП.
    """
    add_table_title(doc, title)

    if not records:
        add_field_inline(doc, title, "нет данных")
        return

    headers = ["Показатель"]
    for record in records:
        headers.append(fmt_date(record.get(date_key)))

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.autofit = True

    header_cells = table.rows[0].cells
    for index, header in enumerate(headers):
        format_table_cell(header_cells[index], header, bold=True, size=10)

    for label, key in fields:
        cells = table.add_row().cells
        format_table_cell(cells[0], label, bold=True, size=10)
        for index, record in enumerate(records, start=1):
            format_table_cell(cells[index], record.get(key), bold=False, size=10)

    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                paragraph.paragraph_format.space_before = Pt(0)
                paragraph.paragraph_format.space_after = Pt(0)
                paragraph.paragraph_format.line_spacing = 1

    doc.add_paragraph()


def unit_label(value) -> str:
    """Человекочитаемые единицы измерения для Word-отчёта."""
    labels = {
        "mg_l": "мг/л",
        "g_l": "г/л",
        "mmol_l": "ммоль/л",
        "umol_l": "мкмоль/л",
    }
    return labels.get(value, value or "")


def value_with_unit(value, unit) -> str:
    if value is None or value == "":
        return "—"
    unit_text = unit_label(unit)
    return f"{value} {unit_text}".strip()


def prognosis_display(record) -> str:
    if not record:
        return "—"

    combined = clean_value(record.get("combined_category"))
    text = clean_value(record.get("prognosis_text"))

    if combined == "—" and text == "—":
        return "—"
    if combined == "—":
        return text
    if text == "—":
        return combined
    return f"{combined}: {text}"
