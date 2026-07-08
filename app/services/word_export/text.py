"""
Назначение файла: медицинский текст для Word-заключения.

Что выполняет файл:
- формирует строку диагноза по МКБ-10;
- формирует строку прогноза KDIGO для блока «Заключение»;
- очищает рекомендации от служебных автогенерируемых KDIGO-фраз;
- не создаёт Document и не управляет шрифтами/таблицами.
"""

from __future__ import annotations

import re

from .formatting import clean_value, fmt_date


def prognosis_display(record) -> str:
    """Короткий вывод прогноза для табличных представлений."""
    if not record:
        return "—"

    display_text = record.get("display_text")
    if display_text:
        return str(display_text)

    combined = clean_value(record.get("combined_category"))
    text = clean_value(record.get("prognosis_text"))

    if combined == "—" and text == "—":
        return "—"
    if combined == "—":
        return text
    if text == "—":
        return combined
    return f"{combined}: {text}"


def strip_kdigo_leading_label(text: str) -> str:
    """Убирает служебный префикс «По KDIGO:» из значения прогноза."""
    text = (text or "").strip()
    return re.sub(r"^По\s+KDIGO\s*:\s*", "", text, flags=re.IGNORECASE).strip()


def kdigo_conclusion_text(record) -> str:
    """Понятная формулировка KDIGO для блока «Заключение»."""
    if not record:
        return ""

    display_text = record.get("display_text")
    if display_text:
        return strip_kdigo_leading_label(str(display_text))

    combined = record.get("combined_category")
    prognosis_text = record.get("prognosis_text")
    if not combined or not prognosis_text:
        return ""

    gfr_date = fmt_date(record.get("gfr_investigation_date"))
    albuminuria_date = fmt_date(record.get("albuminuria_investigation_date"))
    return (
        f"{combined} — {prognosis_text} прогрессирования ХБП "
        f"и развития ХПН (рассчитано по СКФ от {gfr_date}, "
        f"альбуминурия от {albuminuria_date})"
    )


def clean_word_recommendations(value) -> str:
    """Убирает из Word-рекомендаций служебные KDIGO-фразы."""
    if value is None or value == "":
        return ""

    text = str(value).strip()
    if not text:
        return ""

    service_patterns = [
        r"\s*Категория\s+ХБП\s*:\s*[^.。!\n\r]+[.。!]?\s*",
        r"\s*Прогноз\s+по\s+KDIGO\s*:\s*[^.。!\n\r]+[.。!]?\s*",
        r"\s*Учитывая\s+[^.。!\n\r]*?риск\s*[—-]\s*[^.。!\n\r]+[.。!]?\s*",
    ]
    for pattern in service_patterns:
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text).strip(" ;.\n\r\t")
    if text:
        text += "."
    return text


def icd10_diagnosis_item_text(record) -> str:
    """Одна строка диагноза МКБ-10 для Word без служебных подзаголовков."""
    diagnosis = (record.get("icd10_diagnosis") or "").strip()
    if not diagnosis:
        return ""

    note = (record.get("doctor_note") or "").strip()
    if note:
        return f"{diagnosis} ({note})"
    return diagnosis


def icd10_diagnoses_conclusion_text(records) -> str:
    """Склеивает диагнозы в порядке: основной, осложнения, сопутствующие."""
    if not records:
        return ""

    type_order = {"main": 1, "complication": 2, "comorbidity": 3}

    def sort_key(record):
        return (
            type_order.get(record.get("diagnosis_type"), 9),
            record.get("sort_order") or 0,
            record.get("id") or 0,
        )

    parts = [
        icd10_diagnosis_item_text(record)
        for record in sorted(records, key=sort_key)
    ]
    parts = [part for part in parts if part]
    return "; ".join(parts)
