"""
Сборка текстовых медицинских описаний из полей формы приёма.

Этот модуль нужен, чтобы одинаково формировать текстовые блоки для:
- первого приёма нового пациента;
- повторного приёма существующего пациента;
- подробного аудита уже сохранённой формы.

Форма может быть представлена как Starlette FormData либо как обычный dict.
Последний вариант используется после подготовки данных для аудита, поэтому helper-функции
ниже обязаны поддерживать оба формата.
"""

from __future__ import annotations

from typing import Any

from .form_parsing import empty_to_none, join_form_values


def _form_get(form: Any, key: str, default: Any = None) -> Any:
    """Безопасно получает одно значение из FormData или обычного словаря."""
    try:
        return form.get(key, default)
    except AttributeError:
        return default


def _form_getlist(form: Any, key: str) -> list[Any]:
    """Безопасно получает список значений из FormData или обычного словаря."""
    if hasattr(form, "getlist"):
        return list(form.getlist(key))

    value = _form_get(form, key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def build_skin_condition(form: Any) -> str | None:
    """
    Формирует строку старого checkbox-описания кожных покровов.

    Функция оставлена только для обратной совместимости старых сценариев и тестовых данных.
    Новая форма этапа 2 сохраняет поле skin_and_mucous_membranes как обычный текст.
    """
    skin_color = join_form_values(
        _form_getlist(form, "skin_color"),
        _form_get(form, "skin_color_other"),
    )
    skin_moisture = join_form_values(
        _form_getlist(form, "skin_moisture"),
        _form_get(form, "skin_moisture_other"),
    )
    skin_rash = empty_to_none(_form_get(form, "skin_rash"))
    skin_rash_description = empty_to_none(_form_get(form, "skin_rash_description"))
    skin_other = empty_to_none(_form_get(form, "skin_other"))

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

    Поддерживаются оба варианта входа:
    - реальный FormData из HTTP-запроса;
    - обычный dict, который создаётся перед записью подробного аудита.
    """
    edema_peripheral = join_form_values(
        _form_getlist(form, "edema_peripheral"),
        _form_get(form, "edema_peripheral_other"),
    )
    edema_serositis = join_form_values(
        _form_getlist(form, "edema_serositis"),
        _form_get(form, "edema_serositis_other"),
    )
    edema_other = empty_to_none(_form_get(form, "edema_other"))

    edema_parts: list[str] = []

    if edema_peripheral:
        edema_parts.append(f"Периферические отёки: {edema_peripheral}")

    if edema_serositis:
        edema_parts.append(f"Серозиты: {edema_serositis}")

    if edema_other:
        edema_parts.append(f"Дополнительно: {edema_other}")

    return "; ".join(edema_parts) if edema_parts else None
