"""Данные пациента, жалобы, анамнез и объективный статус для Word."""

from __future__ import annotations

from .formatting import add_field_inline, clean_value, fmt_date


def add_patient_section(doc, appointment):
    add_field_inline(doc, "Пациент", appointment.get("patient_fio"))
    add_field_inline(doc, "Дата рождения", fmt_date(appointment.get("birth_date")))

    if appointment.get("age_at_appointment") is not None:
        try:
            age_text = f"{int(appointment.get('age_at_appointment'))} лет"
        except Exception:
            age_text = str(appointment.get("age_at_appointment"))
        add_field_inline(doc, "Возраст на момент приёма", age_text)


def _sentence(value: str) -> str:
    """Нормализует фрагмент текста до одной фразы с точкой в конце."""
    value = (value or "").strip()
    if not value:
        return ""
    value = value.rstrip(" ;")
    if value[-1] not in ".!?:":
        value += "."
    return value


def _join_sentences(parts) -> str:
    return " ".join(part for part in parts if part).strip()


def add_survey_section(doc, appointment):
    add_field_inline(doc, "Жалобы", appointment.get("complaints"), space_before=5)


def add_examination_section(doc, appointment):
    """Компактный абзац анамнеза и объективных данных без лишних подзаголовков."""
    pressure = "—"
    if appointment.get("systolic_pressure") or appointment.get("diastolic_pressure"):
        pressure = (
            f"{clean_value(appointment.get('systolic_pressure'))}/"
            f"{clean_value(appointment.get('diastolic_pressure'))} мм рт. ст."
        )

    bp_note = (appointment.get("bp_note") or "").strip()
    if bp_note and pressure != "—":
        pressure = f"{pressure} ({bp_note})"

    anamnesis_parts = [
        _sentence(appointment.get("life_anamnesis")),
        _sentence(appointment.get("disease_anamnesis")),
    ]

    heredity_description = (appointment.get("heredity_description") or "").strip()
    if heredity_description:
        anamnesis_parts.append(_sentence(heredity_description))
    elif appointment.get("heredity"):
        anamnesis_parts.append("Отягощённая наследственность.")

    comorbidities = (appointment.get("comorbidities") or "").strip()
    if comorbidities:
        anamnesis_parts.append(_sentence(f"Сопутствующие заболевания: {comorbidities}"))

    skin_condition = (appointment.get("skin_condition") or "").strip()
    if skin_condition:
        anamnesis_parts.append(_sentence(f"Кожные покровы: {skin_condition}"))

    anamnesis_parts.extend(
        [
            _sentence(f"Отёки: {clean_value(appointment.get('edema_location'))}"),
            _sentence(f"Артериальное давление: {pressure}"),
            _sentence(f"ЧСС: {clean_value(appointment.get('heart_rate'))}"),
            _sentence(f"Рост: {clean_value(appointment.get('height'))}"),
            _sentence(f"Вес: {clean_value(appointment.get('weight'))}"),
            _sentence(f"ИМТ: {clean_value(appointment.get('bmi'))}"),
        ]
    )

    add_field_inline(doc, "Анамнез", _join_sentences(anamnesis_parts))
