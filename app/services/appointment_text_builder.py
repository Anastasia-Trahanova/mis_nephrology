"""
Сборка текстовых медицинских описаний из полей формы приёма.

Этот модуль нужен, чтобы одинаково формировать текстовые блоки для:
- первого приёма нового пациента;
- повторного приёма существующего пациента.

Здесь нет SQL и сохранения в БД. Модуль только превращает набор отдельных полей
формы в готовые строки, которые затем сохраняются в examinations.
"""

from __future__ import annotations

from typing import Any

from .form_parsing import empty_to_none, join_form_values


def build_skin_condition(form: Any) -> str | None:
    """
    Формирует строку описания кожных покровов.

    Источники из формы:
    - skin_color;
    - skin_color_other;
    - skin_moisture;
    - skin_moisture_other;
    - skin_rash;
    - skin_rash_description;
    - skin_other.
    """
    skin_color = join_form_values(
        form.getlist("skin_color"),
        form.get("skin_color_other"),
    )
    skin_moisture = join_form_values(
        form.getlist("skin_moisture"),
        form.get("skin_moisture_other"),
    )
    skin_rash = empty_to_none(form.get("skin_rash"))
    skin_rash_description = empty_to_none(form.get("skin_rash_description"))
    skin_other = empty_to_none(form.get("skin_other"))

    skin_parts: list[str] = []

    if skin_color:
        skin_parts.append(f"Окраска: {skin_color}")

    if skin_moisture:
        skin_parts.append(f"Влажность: {skin_moisture}")

    if skin_rash:
        if skin_rash == "есть" and skin_rash_description:
            skin_parts.append(f"Высыпания: есть ({skin_rash_description})")
        else:
            skin_parts.append(f"Высыпания: {skin_rash}")

    if skin_other:
        skin_parts.append(f"Дополнительно: {skin_other}")

    return "; ".join(skin_parts) if skin_parts else None


def build_edema_location(form: Any) -> str | None:
    """
    Формирует строку описания отёков.

    Источники из формы:
    - edema_peripheral;
    - edema_peripheral_other;
    - edema_serositis;
    - edema_serositis_other;
    - edema_other.
    """
    edema_peripheral = join_form_values(
        form.getlist("edema_peripheral"),
        form.get("edema_peripheral_other"),
    )
    edema_serositis = join_form_values(
        form.getlist("edema_serositis"),
        form.get("edema_serositis_other"),
    )
    edema_other = empty_to_none(form.get("edema_other"))

    edema_parts: list[str] = []

    if edema_peripheral:
        edema_parts.append(f"Периферические отёки: {edema_peripheral}")

    if edema_serositis:
        edema_parts.append(f"Серозиты: {edema_serositis}")

    if edema_other:
        edema_parts.append(f"Дополнительно: {edema_other}")

    return "; ".join(edema_parts) if edema_parts else None
