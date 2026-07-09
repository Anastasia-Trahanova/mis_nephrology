"""
Сервис сборки рабочих представлений аудита для административных страниц.

Задача сервиса — превратить сырые audit_events/audit_event_changes в понятный
протокол: паспорт события, резюме, счётчики, разделы, timeline приёма.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from app.repositories.audit_log import (
    ACTION_CATEGORY_LABELS,
    CHANGE_TYPE_LABELS,
    SUMMARY_CHANGE_GROUPS,
    build_audit_change_counters,
    build_audit_protocol_summary,
    group_audit_changes_by_section,
)


MANUAL_CHANGE_TYPES = {
    "patient_created",
    "appointment_created",
    "filled_new",
    "changed_from_prefill",
    "cleared_from_prefill",
    "lab_added",
    "overridden_system_main",
    "diagnosis_added",
    "diagnosis_removed",
    "diagnosis_note_changed",
    "date_set",
    "date_changed",
    "date_removed",
    "medication_added",
    "medication_removed",
    "medication_name_changed",
    "dosage_changed",
    "schedule_changed",
    "medication_row_changed",
    "selected_by_doctor",
}

PREFILL_CHANGE_TYPES = {
    "changed_from_prefill",
    "cleared_from_prefill",
    "medication_continued",
    "diagnosis_continued",
}

SYSTEM_CHANGE_TYPES = {
    "autocalculated",
    "system_suggested_main",
    "accepted_system_main",
    "accepted_system",
}

RISK_CHANGE_TYPES = {
    "cleared_from_prefill",
    "diagnosis_removed",
    "medication_removed",
    "lab_save_error",
    "field_not_filled",
    "not_assessable",
}

SOURCE_LABELS = {
    "manual": "врач / ручной ввод",
    "prefill": "подстановка из прошлого приёма",
    "system": "система / расчёт",
    "validation": "контроль качества",
    "unknown": "не определено",
}


SECTION_PURPOSES = {
    "patient": "идентификация пациента",
    "appointment": "паспорт приёма",
    "survey": "жалобы и анамнез",
    "examination": "осмотр и витальные показатели",
    "cbc": "общий анализ крови",
    "biochemistry": "биохимия и расчёты СКФ",
    "urinalysis": "общий анализ мочи",
    "albuminuria": "ACR и категория альбуминурии",
    "ultrasound": "УЗИ почек",
    "kdigo": "выбор прогноза KDIGO",
    "icd10": "диагнозы МКБ-10",
    "diet": "диета, рекомендации и контроль",
    "medications": "лекарственные назначения",
    "other": "прочие данные",
}


def _group_key(change_type: str | None) -> str:
    for key, group in SUMMARY_CHANGE_GROUPS.items():
        if change_type in group["types"]:
            return key
    return "other"


def _source_for_change(change: dict[str, Any]) -> str:
    change_type = change.get("change_type")
    if change_type in SYSTEM_CHANGE_TYPES:
        return "system"
    if change_type in PREFILL_CHANGE_TYPES:
        return "prefill"
    if change_type in {"field_not_filled", "not_assessable", "lab_save_error"}:
        return "validation"
    if change_type in MANUAL_CHANGE_TYPES:
        return "manual"
    return "unknown"


def _value_preview(change: dict[str, Any]) -> str | None:
    old_value = change.get("old_value")
    new_value = change.get("new_value")
    details = change.get("details")
    change_type = change.get("change_type")

    if change_type in {"cleared_from_prefill", "diagnosis_removed", "medication_removed", "date_removed"}:
        return f"удалено: {old_value}" if old_value else "удалено"
    if old_value and new_value and old_value != new_value:
        return f"было: {old_value}; стало: {new_value}"
    if new_value:
        return str(new_value)
    if old_value:
        return str(old_value)
    if details:
        return str(details)
    return None


def _decorate_change_for_view(change: dict[str, Any]) -> dict[str, Any]:
    decorated = dict(change)
    source = _source_for_change(decorated)
    decorated["source"] = source
    decorated["source_label"] = SOURCE_LABELS.get(source, source)
    decorated["group_key"] = _group_key(decorated.get("change_type"))
    decorated["group_label"] = SUMMARY_CHANGE_GROUPS.get(decorated["group_key"], {}).get("short_label", "Прочее")
    decorated["value_preview"] = _value_preview(decorated)
    decorated["is_risk"] = decorated.get("change_type") in RISK_CHANGE_TYPES
    decorated["change_type_label"] = decorated.get("change_type_label") or CHANGE_TYPE_LABELS.get(
        decorated.get("change_type"), decorated.get("change_type")
    )
    return decorated


def _decorate_groups_for_view(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = group_audit_changes_by_section(changes)
    for section in grouped:
        section["purpose"] = SECTION_PURPOSES.get(section.get("section"), "раздел формы")
        section["type_counts"] = Counter(change.get("group_key") for change in section.get("changes", []))
        section["risk_count"] = sum(1 for change in section.get("changes", []) if change.get("is_risk"))
    return grouped


def _stats_cards(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counters = build_audit_change_counters(changes)
    cards = []
    for key in ["added", "changed", "system", "unchanged", "removed", "not_filled"]:
        meta = SUMMARY_CHANGE_GROUPS[key]
        cards.append(
            {
                "key": key,
                "label": meta.get("short_label") or meta["label"],
                "description": meta["label"],
                "count": counters.get(key, 0),
            }
        )
    cards.append(
        {
            "key": "total",
            "label": "Всего строк",
            "description": "Все зафиксированные изменения",
            "count": counters.get("total", len(changes)),
        }
    )
    return cards


def _technical_items(event: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for label, key in [
        ("ID события", "id"),
        ("ID пользователя", "user_id"),
        ("Роль", "user_role"),
        ("ID пациента", "patient_id"),
        ("ID приёма", "appointment_id"),
        ("Entity", "entity_type"),
        ("Entity ID", "entity_id"),
        ("IP", "ip_address"),
        ("Метод", "method"),
        ("Путь", "path"),
        ("HTTP", "status_code"),
    ]:
        value = event.get(key)
        if value not in (None, ""):
            items.append({"label": label, "value": str(value)})
    return items


def _human_join(items: list[str]) -> str:
    cleaned = [item for item in items if item]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return ", ".join(cleaned[:-1]) + " и " + cleaned[-1]


def _narrative(event: dict[str, Any], changes: list[dict[str, Any]]) -> str:
    user = event.get("user_login") or "неизвестный пользователь"
    role = event.get("user_role") or "роль не указана"
    action = (event.get("action_label") or event.get("action") or "выполнил действие").lower()
    patient = event.get("patient_name")
    appointment_id = event.get("appointment_id")
    result = event.get("result_label") or event.get("result") or "результат не указан"

    counters = build_audit_change_counters(changes)
    facts: list[str] = []
    if counters.get("added"):
        facts.append(f"добавлено {counters['added']}")
    if counters.get("changed"):
        facts.append(f"изменено врачом {counters['changed']}")
    if counters.get("system"):
        facts.append(f"рассчитано/подтверждено системой {counters['system']}")
    if counters.get("unchanged"):
        facts.append(f"перенесено без изменений {counters['unchanged']}")
    if counters.get("removed"):
        facts.append(f"удалено {counters['removed']}")
    if counters.get("not_filled"):
        facts.append(f"не заполнено или не оценено {counters['not_filled']}")

    target = ""
    if patient and appointment_id:
        target = f" для пациента {patient}, приём №{appointment_id}"
    elif patient:
        target = f" для пациента {patient}"
    elif appointment_id:
        target = f" по приёму №{appointment_id}"

    base = f"{user} ({role}) {action}{target}. Результат: {result}."
    if facts:
        return base + " В протоколе: " + _human_join(facts) + "."
    if event.get("error_message"):
        return base + f" Зафиксирована ошибка: {event['error_message']}."
    if event.get("details"):
        return base + f" Детали: {event['details']}."
    return base + " Подробных медицинских изменений по событию нет."


def _attention_flags(event: dict[str, Any], changes: list[dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    if event.get("result") == "error":
        flags.append({"level": "danger", "title": "Ошибка", "text": event.get("error_message") or "Событие завершилось ошибкой."})
    if event.get("result") == "denied":
        flags.append({"level": "warning", "title": "Отказ доступа", "text": "Пользователь попытался выполнить действие без достаточных прав."})

    risk_changes = [change for change in changes if change.get("is_risk")]
    if risk_changes:
        flags.append(
            {
                "level": "warning",
                "title": "Есть контрольные точки",
                "text": f"В протоколе есть строки удаления, незаполненности или невозможности оценки: {len(risk_changes)}.",
            }
        )

    if event.get("action_category") == "export":
        flags.append(
            {
                "level": "info",
                "title": "Выгрузка данных",
                "text": "Это событие связано с экспортом. При проверке важно видеть, кто и когда выгрузил данные.",
            }
        )
    return flags


def _passport_items(event: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {"label": "Дата и время", "value": event.get("created_at") or "—"},
        {"label": "Пользователь", "value": event.get("user_login") or "—"},
        {"label": "Роль", "value": event.get("user_role") or "—"},
        {"label": "Категория", "value": event.get("action_category_label") or ACTION_CATEGORY_LABELS.get(event.get("action_category"), "—")},
        {"label": "Действие", "value": event.get("action_label") or event.get("action") or "—"},
        {"label": "Результат", "value": event.get("result_label") or event.get("result") or "—"},
        {"label": "Пациент", "value": event.get("patient_name") or "—", "patient_id": event.get("patient_id")},
        {"label": "Приём", "value": event.get("appointment_id") or "—", "appointment_id": event.get("appointment_id")},
    ]


def build_audit_event_view_model(
    event: dict[str, Any],
    changes: list[dict[str, Any]],
    *,
    related_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Собирает view model страницы одного события аудита."""
    decorated_changes = [_decorate_change_for_view(change) for change in changes]
    return {
        "event": event,
        "changes": decorated_changes,
        "grouped_changes": _decorate_groups_for_view(decorated_changes),
        "protocol_summary": build_audit_protocol_summary(decorated_changes),
        "stats_cards": _stats_cards(decorated_changes),
        "narrative": _narrative(event, decorated_changes),
        "attention_flags": _attention_flags(event, decorated_changes),
        "passport_items": _passport_items(event),
        "technical_items": _technical_items(event),
        "related_events": related_events or [],
    }


def build_appointment_audit_view_model(
    appointment_id: int,
    events: list[dict[str, Any]],
    changes_by_event: dict[int, list[dict[str, Any]]],
) -> dict[str, Any]:
    """Собирает протокол аудита всего приёма из цепочки событий."""
    decorated_events: list[dict[str, Any]] = []
    all_changes: list[dict[str, Any]] = []

    for event in events:
        event_changes = [_decorate_change_for_view(change) for change in changes_by_event.get(int(event["id"]), [])]
        event_copy = dict(event)
        event_copy["changes"] = event_changes
        event_copy["change_count"] = len(event_changes)
        event_copy["summary"] = build_audit_protocol_summary(event_changes)
        event_copy["narrative"] = _narrative(event_copy, event_changes)
        decorated_events.append(event_copy)
        all_changes.extend(event_changes)

    patient_name = None
    patient_id = None
    appointment_date = None
    for event in decorated_events:
        patient_name = patient_name or event.get("patient_name")
        patient_id = patient_id or event.get("patient_id")
        appointment_date = appointment_date or event.get("appointment_date")

    category_counts = Counter(event.get("action_category") or "other" for event in decorated_events)
    result_counts = Counter(event.get("result") or "unknown" for event in decorated_events)

    return {
        "appointment_id": appointment_id,
        "patient_name": patient_name,
        "patient_id": patient_id,
        "appointment_date": appointment_date,
        "events": decorated_events,
        "event_count": len(decorated_events),
        "all_changes": all_changes,
        "grouped_changes": _decorate_groups_for_view(all_changes),
        "stats_cards": _stats_cards(all_changes),
        "protocol_summary": build_audit_protocol_summary(all_changes),
        "category_counts": dict(category_counts),
        "result_counts": dict(result_counts),
        "has_errors": any(event.get("result") in {"error", "denied"} for event in decorated_events),
    }
