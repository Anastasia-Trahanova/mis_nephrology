"""Пациент, жалобы, анамнез и объективный статус для Word-заключения."""

from __future__ import annotations

from .formatting import (
    add_centered_paragraph,
    add_field_inline,
    add_fields_inline,
    add_table_title,
    fmt_date,
    has_value,
)

_GENERAL_CONDITION = {
    "satisfactory": "Удовлетворительное",
    "moderate": "Средней тяжести",
    "severe": "Тяжёлое",
}
_CONSCIOUSNESS = {
    "clear": "Ясное",
    "confused": "Спутанное",
    "sopor": "Сопорозное",
    "coma": "Коматозное",
}
_BED_POSITION = {
    "active": "Активное",
    "passive": "Пассивное",
    "forced": "Вынужденное",
}
_CONSTITUTION = {
    "normosthenic": "Нормостеник",
    "asthenic": "Астеник",
    "hypersthenic": "Гиперстеник",
}
_KIDNEY_PALPATION = {
    "palpable": "Пальпируются",
    "not_palpable": "Не пальпируются",
}
_PASTERNATSKY_RESULT = {
    "positive": "Положительный",
    "negative": "Отрицательный",
}
_PASTERNATSKY_SIDE = {
    "right": "Справа",
    "left": "Слева",
    "bilateral": "с двух сторон",
}


def _mapped(mapping, value) -> str:
    if not has_value(value):
        return ""
    return mapping.get(value, str(value).strip())


def _age_text(value) -> str:
    if not has_value(value):
        return ""
    try:
        age = int(value)
    except (TypeError, ValueError):
        return str(value).strip()

    remainder_100 = age % 100
    remainder_10 = age % 10
    if 11 <= remainder_100 <= 14:
        suffix = "лет"
    elif remainder_10 == 1:
        suffix = "год"
    elif 2 <= remainder_10 <= 4:
        suffix = "года"
    else:
        suffix = "лет"
    return f"{age} {suffix}"


def _sentence(value) -> str:
    """Возвращает заполненный фрагмент с корректным окончанием предложения."""
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    text = text.rstrip(" ;")
    if text[-1] not in ".!?":
        text += "."
    return text


def _join_filled(appointment, keys) -> str:
    return " ".join(
        part
        for part in (_sentence(appointment.get(key)) for key in keys)
        if part
    ).strip()


def _value_with_unit(value, unit: str) -> str:
    if not has_value(value):
        return ""
    return f"{value} {unit}".strip()


def add_patient_section(doc, appointment):
    """Выводит ФИО, дату рождения и возраст одной строкой по центру."""
    parts = []
    if has_value(appointment.get("patient_fio")):
        parts.append(str(appointment.get("patient_fio")).strip())
    birth_date = fmt_date(appointment.get("birth_date"))
    if birth_date:
        parts.append(birth_date)
    age = _age_text(appointment.get("age_at_appointment"))
    if age:
        parts.append(age)

    add_centered_paragraph(
        doc,
        ", ".join(parts),
        size=12,
        bold=True,
        space_after=6,
    )


def add_survey_section(doc, appointment):
    """Жалобы и два блока анамнеза; незаполненные блоки не выводятся."""
    add_field_inline(doc, "Жалобы", appointment.get("complaints"), space_before=5)

    life_anamnesis = _join_filled(
        appointment,
        (
            "education_and_professional_history",
            "housing_conditions",
            "past_diseases",
            "habitual_intoxications",
            "gynecological_history",
            "heredity_description",
            "family_life",
            "allergological_history",
            "epidemiological_history",
            "insurance_history",
        ),
    )
    add_field_inline(doc, "Анамнез жизни", life_anamnesis)

    disease_parts = []
    disease_onset = _sentence(appointment.get("disease_onset"))
    disease_course = _sentence(appointment.get("disease_course"))
    if disease_onset:
        disease_parts.append(f"Начало болезни: {disease_onset}")
    if disease_course:
        disease_parts.append(f"Течение заболевания: {disease_course}")
    add_field_inline(
        doc,
        "Анамнез данного заболевания",
        " ".join(disease_parts),
    )


def _blood_pressure(appointment) -> str:
    systolic = appointment.get("systolic_pressure")
    diastolic = appointment.get("diastolic_pressure")
    if not has_value(systolic) or not has_value(diastolic):
        return ""

    value = f"{systolic}/{diastolic} мм рт. ст."
    if has_value(appointment.get("bp_note")):
        value += f" ({str(appointment.get('bp_note')).strip()})"
    return value

def _pasternatsky_text(appointment) -> str:
    result = _mapped(
        _PASTERNATSKY_RESULT,
        appointment.get("pasternatsky_result"),
    )
    side = _mapped(
        _PASTERNATSKY_SIDE,
        appointment.get("pasternatsky_side"),
    )

    return ", ".join(
        value for value in (result, side) if has_value(value)
    )



def add_examination_section(doc, appointment):
    """
    Выводит только заполненные данные объективного осмотра.

    Подписи внутри раздела обычного начертания. Рост, вес и ИМТ объединены
    в одну строку; АД и ЧСС — в другую.
    """
    fields = [
        ("Общее состояние", _mapped(_GENERAL_CONDITION, appointment.get("general_condition"))),
        ("Сознание", _mapped(_CONSCIOUSNESS, appointment.get("consciousness"))),
        ("Положение в постели", _mapped(_BED_POSITION, appointment.get("bed_position"))),
        ("Особенности положения", appointment.get("bed_position_details")),
        ("Телосложение", appointment.get("body_build")),
        ("Тип конституции", _mapped(_CONSTITUTION, appointment.get("constitution_type"))),
        ("Кожа и слизистые оболочки", appointment.get("skin_and_mucous_membranes")),
        ("Отёки", appointment.get("edema_location")),
        ("Температура тела", _value_with_unit(appointment.get("body_temperature"), "°C")),
        ("Лимфатические узлы", appointment.get("lymph_nodes")),
        ("Щитовидная железа", appointment.get("thyroid_gland")),
        ("Опорно-двигательный аппарат", appointment.get("musculoskeletal_system")),
        ("Состояние вен", appointment.get("veins_condition")),
        ("Аускультация лёгких", appointment.get("lung_auscultation")),
        ("Живот", appointment.get("abdomen")),
        ("Пальпация почек", _mapped(_KIDNEY_PALPATION, appointment.get("kidney_palpation"))),
        ("Уточнение", appointment.get("kidney_palpation_details")),
        ("Симптом Пастернацкого", _pasternatsky_text(appointment)),
    ]
    measurements = [
        ("Рост", _value_with_unit(appointment.get("height"), "см")),
        ("Вес", _value_with_unit(appointment.get("weight"), "кг")),
        ("ИМТ", _value_with_unit(appointment.get("bmi"), "кг/м²")),
    ]
    circulation = [
        ("АД", _blood_pressure(appointment)),
        ("ЧСС", _value_with_unit(appointment.get("heart_rate"), "уд/мин")),
    ]

    has_any = any(has_value(value) for _, value in fields + measurements + circulation)
    if not has_any:
        return

    add_table_title(doc, "Данные объективного исследования больного")

    # Первые шесть полей идут до антропометрии, как в карточке.
    for title, value in fields[:6]:
        add_field_inline(doc, title, value, title_bold=False)

    add_fields_inline(doc, measurements, title_bold=False)

    # Кожа, отёки, температура.
    for title, value in fields[6:9]:
        add_field_inline(doc, title, value, title_bold=False)

    add_fields_inline(doc, circulation, title_bold=False)

    # Остальная часть объективного статуса.
    for title, value in fields[9:]:
        add_field_inline(doc, title, value, title_bold=False)
