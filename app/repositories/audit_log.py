"""
Repository журнала действий и подробностей аудита МИС.

Файл оставляет существующую схему БД без обязательных миграций:
- audit_events хранит факт события, пользователя, роль, пациента/приём, request-метаданные;
- audit_event_changes хранит клинические изменения по сохранённому событию;
- дополнительные представления для админки собираются на уровне Python и SQL-фильтров.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Any

from fastapi import Request

from app.db.connection import get_db_connection


ACTION_LABELS = {
    "login_success": "Вход в систему",
    "login_failed": "Ошибка входа",
    "logout": "Выход из системы",
    "open_patient_list": "Открыл список пациентов",
    "open_patient_card": "Открыл карточку пациента",
    "open_new_patient_form": "Открыл форму нового пациента",
    "open_new_appointment_form": "Открыл форму повторного приёма",
    "create_patient": "Создал нового пациента",
    "create_appointment": "Создал повторный приём",
    "download_word_report": "Скачал Word-заключение",
    "open_ckd_registry": "Открыл регистр ХБП",
    "open_admin_audit": "Открыл журнал работы МИС",
    "open_admin_audit_event": "Открыл протокол события аудита",
    "open_admin_appointment_audit": "Открыл протокол аудита приёма",
    "export_audit_log": "Выгрузил журнал аудита",
    "create_user": "Создал пользователя",
    "update_user": "Изменил пользователя",
    "deactivate_user": "Отключил пользователя",
    "change_user_role": "Изменил роль пользователя",
    "reset_password": "Сбросил пароль пользователя",
    "access_denied": "Отказано в доступе",
    "save_error": "Ошибка сохранения",
    "server_error": "Ошибка сервера",
}

RESULT_LABELS = {
    "success": "успешно",
    "error": "ошибка",
    "denied": "отказано",
}

ACTION_CATEGORY_LABELS = {
    "auth": "Входы и сессии",
    "view": "Просмотры",
    "patient": "Пациенты",
    "appointment": "Приёмы",
    "export": "Выгрузки",
    "admin": "Администрирование",
    "security": "Безопасность",
    "error": "Ошибки",
    "other": "Прочее",
}

ACTION_CATEGORIES = {
    "login_success": "auth",
    "login_failed": "auth",
    "logout": "auth",
    "open_patient_list": "view",
    "open_patient_card": "view",
    "open_new_patient_form": "view",
    "open_new_appointment_form": "view",
    "open_ckd_registry": "view",
    "create_patient": "patient",
    "create_appointment": "appointment",
    "download_word_report": "export",
    "export_audit_log": "export",
    "open_admin_audit": "admin",
    "open_admin_audit_event": "admin",
    "open_admin_appointment_audit": "admin",
    "create_user": "admin",
    "update_user": "admin",
    "deactivate_user": "admin",
    "change_user_role": "admin",
    "reset_password": "admin",
    "access_denied": "security",
    "save_error": "error",
    "server_error": "error",
}

CHANGE_TYPE_LABELS = {
    "patient_created": "Пациент создан",
    "appointment_created": "Приём создан",
    "filled_new": "Заполнено новое поле",
    "changed_from_prefill": "Изменено поле",
    "cleared_from_prefill": "Удалено подставленное значение",
    "lab_added": "Добавлен анализ",
    "lab_save_error": "Ошибка сохранения анализа",
    "autocalculated": "Рассчитано системой",
    "system_suggested_main": "Система предложила основной диагноз",
    "accepted_system_main": "Добавлен автоматически",
    "overridden_system_main": "Добавлен врачом",
    "diagnosis_added": "Добавлен диагноз",
    "diagnosis_removed": "Удалён диагноз",
    "diagnosis_continued": "Диагноз оставлен без изменений",
    "diagnosis_note_changed": "Изменён комментарий к диагнозу",
    "date_set": "Дата установлена",
    "date_changed": "Дата изменена",
    "date_removed": "Дата удалена",
    "field_not_filled": "Поле не заполнено",
    "medication_added": "Добавлен препарат",
    "medication_removed": "Препарат удалён",
    "medication_continued": "Препарат перенесён без изменений",
    "medication_name_changed": "Изменено название препарата",
    "dosage_changed": "Изменена дозировка",
    "schedule_changed": "Изменён режим приёма",
    "medication_row_changed": "Изменено назначение",
    "accepted_system": "Врач оставил расчёт системы",
    "selected_by_doctor": "Врач выбрал вариант",
    "not_assessable": "Невозможно оценить",
    "save_success": "Сохранено",
}

SUMMARY_CHANGE_GROUPS = {
    "added": {
        "label": "Добавлено",
        "short_label": "Добавлено",
        "types": {
            "patient_created",
            "appointment_created",
            "filled_new",
            "lab_added",
            "diagnosis_added",
            "medication_added",
            "date_set",
        },
    },
    "changed": {
        "label": "Изменено врачом",
        "short_label": "Изменено",
        "types": {
            "changed_from_prefill",
            "overridden_system_main",
            "diagnosis_note_changed",
            "date_changed",
            "medication_name_changed",
            "dosage_changed",
            "schedule_changed",
            "medication_row_changed",
        },
    },
    "removed": {
        "label": "Удалено",
        "short_label": "Удалено",
        "types": {
            "cleared_from_prefill",
            "diagnosis_removed",
            "medication_removed",
            "date_removed",
        },
    },
    "system": {
        "label": "Рассчитано или добавлено системой",
        "short_label": "Система",
        "types": {
            "autocalculated",
            "accepted_system",
            "accepted_system_main",
            "selected_by_doctor",
            "system_suggested_main",
        },
    },
    "unchanged": {
        "label": "Оставлено без изменений",
        "short_label": "Без изменений",
        "types": {"medication_continued", "diagnosis_continued"},
    },
    "not_filled": {
        "label": "Не заполнено / невозможно оценить",
        "short_label": "Не заполнено",
        "types": {"field_not_filled", "not_assessable"},
    },
}


CATEGORY_ACTIONS: dict[str, set[str]] = {}
for _action, _category in ACTION_CATEGORIES.items():
    CATEGORY_ACTIONS.setdefault(_category, set()).add(_action)


def _safe_text(value: Any, max_length: int = 1000) -> str | None:
    """Обрезает служебный текст, чтобы журнал не разрастался бесконтрольно."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_length:
        return text[: max_length - 1] + "…"
    return text


def _session_value(request: Request | None, key: str):
    """Безопасно достаёт значение из session, если request передан."""
    if request is None:
        return None
    try:
        return request.session.get(key)
    except Exception:
        return None


def _client_ip(request: Request | None) -> str | None:
    """Возвращает IP клиента без доверия к X-Forwarded-For на этом этапе."""
    if request is None or request.client is None:
        return None
    return request.client.host


def _parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _parse_datetime_start(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(text), time.min)
        except ValueError:
            return None


def _parse_datetime_end(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, time.max)
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
        if "T" not in text and len(text) <= 10:
            return datetime.combine(parsed.date(), time.max)
        return parsed
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(text), time.max)
        except ValueError:
            return None


def _action_category(action: str | None) -> str:
    return ACTION_CATEGORIES.get(action or "", "other")


def log_audit_event(
    request: Request | None,
    action: str,
    *,
    result: str = "success",
    patient_id: int | None = None,
    appointment_id: int | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    details: str | None = None,
    error_message: str | None = None,
    status_code: int | None = None,
    user_login: str | None = None,
    user_role: str | None = None,
) -> int | None:
    """
    Записывает одно событие аудита и возвращает id созданной строки.

    Ошибка записи журнала не должна ломать работу врача. Поэтому исключения
    внутри audit-log ловятся и уходят только в технический app.log.
    """
    try:
        user_id = _session_value(request, "user_id")
        login = user_login or _session_value(request, "display_name") or _session_value(request, "login")
        role = user_role or _session_value(request, "role")
        path = request.url.path if request is not None else None
        method = request.method if request is not None else None
        ip_address = _client_ip(request)

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        user_id, user_login, user_role, action, result,
                        patient_id, appointment_id, entity_type, entity_id,
                        ip_address, path, method, status_code, details, error_message
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        user_id,
                        _safe_text(login, 255),
                        _safe_text(role, 50),
                        _safe_text(action, 100),
                        _safe_text(result, 30),
                        patient_id,
                        appointment_id,
                        _safe_text(entity_type, 100),
                        entity_id,
                        ip_address,
                        _safe_text(path, 500),
                        _safe_text(method, 10),
                        status_code,
                        _safe_text(details),
                        _safe_text(error_message),
                    ),
                )
                row = cur.fetchone()
                return row["id"] if row else None
    except Exception:
        logging.exception("Не удалось записать событие audit_events: %s", action)
        return None


def insert_audit_event_changes(event_id: int | None, changes: list[dict[str, Any]] | None) -> None:
    """
    Записывает подробности события в audit_event_changes.

    Ошибка записи подробностей не должна ломать сохранение приёма.
    """
    if not event_id or not changes:
        return
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for index, change in enumerate(changes, start=1):
                    cur.execute(
                        """
                        INSERT INTO audit_event_changes (
                            audit_event_id, section, section_label, field_name,
                            field_label, change_type, old_value, new_value,
                            details, sort_order
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event_id,
                            _safe_text(change.get("section"), 100),
                            _safe_text(change.get("section_label"), 255),
                            _safe_text(change.get("field_name"), 100),
                            _safe_text(change.get("field_label"), 255),
                            _safe_text(change.get("change_type"), 60),
                            _safe_text(change.get("old_value"), 2000),
                            _safe_text(change.get("new_value"), 2000),
                            _safe_text(change.get("details"), 2000),
                            int(change.get("sort_order") or index),
                        ),
                    )
    except Exception:
        logging.exception("Не удалось записать подробности audit_event_changes: %s", event_id)


def log_audit_changes(event_id: int | None, changes: list[dict[str, Any]] | None) -> None:
    """Короткий alias, чтобы в роутерах читалось как business-действие."""
    insert_audit_event_changes(event_id, changes)


def _event_sentence(event: dict[str, Any]) -> str:
    """Формирует короткое описание события для страницы администратора."""
    user = event.get("user_login") or "неизвестный пользователь"
    action_label = event.get("action_label") or event.get("action") or "действие"
    patient_name = event.get("patient_name")
    appointment_id = event.get("appointment_id")
    details = event.get("details")
    error = event.get("error_message")

    sentence = f"пользователь {user} — {str(action_label).lower()}"
    if patient_name:
        sentence += f": {patient_name}"
    if appointment_id:
        sentence += f", приём №{appointment_id}"
    if details:
        sentence += f" ({details})"
    if error:
        sentence += f" — {error}"
    return sentence


def _decorate_event(event: dict[str, Any]) -> dict[str, Any]:
    """Добавляет к raw-событию человекочитаемые поля для шаблона."""
    event = dict(event)
    category = _action_category(event.get("action"))
    event["action_label"] = ACTION_LABELS.get(event.get("action"), event.get("action"))
    event["result_label"] = RESULT_LABELS.get(event.get("result"), event.get("result"))
    event["action_category"] = category
    event["action_category_label"] = ACTION_CATEGORY_LABELS.get(category, category)
    event["event_sentence"] = _event_sentence(event)
    event["is_security_relevant"] = category in {"auth", "security", "admin"} or event.get("result") in {"error", "denied"}
    event["is_medical_relevant"] = bool(event.get("patient_id") or event.get("appointment_id"))
    event["is_admin_relevant"] = category == "admin"
    return event


def _decorate_change(change: dict[str, Any]) -> dict[str, Any]:
    """Добавляет к raw-изменению человекочитаемый статус."""
    change = dict(change)
    change["change_type_label"] = CHANGE_TYPE_LABELS.get(change.get("change_type"), change.get("change_type"))
    return change


def _base_event_select() -> str:
    """Общий SELECT для списка и страницы подробностей."""
    return """
        SELECT
            e.id,
            e.created_at,
            e.user_id,
            e.user_login,
            e.user_role,
            e.action,
            e.result,
            e.patient_id,
            e.appointment_id,
            e.entity_type,
            e.entity_id,
            e.ip_address::text AS ip_address,
            e.path,
            e.method,
            e.status_code,
            e.details,
            e.error_message,
            a.appointment_date,
            NULLIF(TRIM(CONCAT(
                p.last_name, ' ', p.first_name, ' ', COALESCE(p.patronymic, '')
            )), '') AS patient_name,
            EXISTS (
                SELECT 1 FROM audit_event_changes c WHERE c.audit_event_id = e.id
            ) AS has_changes,
            (
                EXISTS (SELECT 1 FROM audit_event_changes c WHERE c.audit_event_id = e.id)
                OR e.result IN ('error', 'denied')
                OR e.action IN ('save_error', 'login_failed', 'access_denied', 'server_error')
            ) AS has_details
        FROM audit_events e
        LEFT JOIN appointments a ON a.id = e.appointment_id
        LEFT JOIN patients p ON p.id = COALESCE(e.patient_id, a.patient_id)
    """


def _append_int_filter(where: list[str], params: list[Any], field_sql: str, value: Any) -> None:
    parsed = _parse_int(value)
    if parsed is not None:
        where.append(f"{field_sql} = %s")
        params.append(parsed)


def _append_category_filter(where: list[str], params: list[Any], action_category: str | None) -> None:
    if not action_category:
        return
    actions = sorted(CATEGORY_ACTIONS.get(action_category, set()))
    if not actions:
        return
    placeholders = ", ".join(["%s"] * len(actions))
    where.append(f"e.action IN ({placeholders})")
    params.extend(actions)


def get_audit_events(
    *,
    limit: int = 200,
    offset: int = 0,
    action: str | None = None,
    result: str | None = None,
    user_login: str | None = None,
    user_role: str | None = None,
    patient_id: int | str | None = None,
    appointment_id: int | str | None = None,
    action_category: str | None = None,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
    only_errors: bool = False,
) -> list[dict[str, Any]]:
    """Возвращает события аудита с расширенными фильтрами для админки."""
    limit = max(1, min(int(limit or 200), 5000))
    offset = max(0, int(offset or 0))

    where = ["1=1"]
    params: list[Any] = []

    if action:
        where.append("e.action = %s")
        params.append(action)
    if result:
        where.append("e.result = %s")
        params.append(result)
    if user_login:
        where.append("e.user_login ILIKE %s")
        params.append(f"%{user_login}%")
    if user_role:
        where.append("e.user_role = %s")
        params.append(user_role)

    _append_int_filter(where, params, "COALESCE(e.patient_id, a.patient_id)", patient_id)
    _append_int_filter(where, params, "e.appointment_id", appointment_id)
    _append_category_filter(where, params, action_category)

    parsed_from = _parse_datetime_start(date_from)
    if parsed_from:
        where.append("e.created_at >= %s")
        params.append(parsed_from)

    parsed_to = _parse_datetime_end(date_to)
    if parsed_to:
        where.append("e.created_at <= %s")
        params.append(parsed_to)

    if only_errors:
        where.append(
            "(e.result IN ('error', 'denied') OR e.action IN ('save_error', 'login_failed', 'access_denied', 'server_error'))"
        )

    params.extend([limit, offset])
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                {_base_event_select()}
                WHERE {' AND '.join(where)}
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT %s OFFSET %s
                """,
                params,
            )
            rows = cur.fetchall()
    return [_decorate_event(dict(row)) for row in rows]


def get_audit_event(event_id: int) -> dict[str, Any] | None:
    """Возвращает одно событие аудита для страницы подробностей."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                {_base_event_select()}
                WHERE e.id = %s
                LIMIT 1
                """,
                (event_id,),
            )
            row = cur.fetchone()
    return _decorate_event(dict(row)) if row else None


def get_audit_event_changes(event_id: int) -> list[dict[str, Any]]:
    """Возвращает подробные изменения по событию аудита."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    audit_event_id,
                    section,
                    section_label,
                    field_name,
                    field_label,
                    change_type,
                    old_value,
                    new_value,
                    details,
                    sort_order,
                    created_at
                FROM audit_event_changes
                WHERE audit_event_id = %s
                ORDER BY sort_order, id
                """,
                (event_id,),
            )
            rows = cur.fetchall()
    return [_decorate_change(dict(row)) for row in rows]


def get_audit_events_for_appointment(appointment_id: int, *, limit: int = 500) -> list[dict[str, Any]]:
    """Возвращает цепочку событий вокруг одного приёма."""
    return get_audit_events(appointment_id=appointment_id, limit=limit, offset=0)


def get_audit_events_for_patient(patient_id: int, *, limit: int = 500) -> list[dict[str, Any]]:
    """Возвращает цепочку событий вокруг одного пациента."""
    return get_audit_events(patient_id=patient_id, limit=limit, offset=0)


def get_audit_changes_for_events(event_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Возвращает изменения сразу по нескольким событиям для протокола приёма."""
    if not event_ids:
        return {}
    placeholders = ", ".join(["%s"] * len(event_ids))
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    id,
                    audit_event_id,
                    section,
                    section_label,
                    field_name,
                    field_label,
                    change_type,
                    old_value,
                    new_value,
                    details,
                    sort_order,
                    created_at
                FROM audit_event_changes
                WHERE audit_event_id IN ({placeholders})
                ORDER BY audit_event_id, sort_order, id
                """,
                event_ids,
            )
            rows = cur.fetchall()

    result: dict[int, list[dict[str, Any]]] = {event_id: [] for event_id in event_ids}
    for row in rows:
        change = _decorate_change(dict(row))
        result.setdefault(int(change["audit_event_id"]), []).append(change)
    return result


def group_audit_changes_by_section(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Группирует изменения по разделам для шаблона подробностей."""
    grouped: list[dict[str, Any]] = []
    by_section: dict[str, dict[str, Any]] = {}
    for change in changes:
        key = change.get("section") or "other"
        if key not in by_section:
            section = {
                "section": key,
                "section_label": change.get("section_label") or key,
                "changes": [],
                "count": 0,
            }
            by_section[key] = section
            grouped.append(section)
        by_section[key]["changes"].append(change)
        by_section[key]["count"] += 1
    return grouped


def _summary_group_for_change(change_type: str | None) -> str:
    for group_key, group in SUMMARY_CHANGE_GROUPS.items():
        if change_type in group["types"]:
            return group_key
    return "other"


def build_audit_protocol_summary(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Строит краткую сводку протокола: добавлено/изменено/системно/без изменений."""
    summary: list[dict[str, Any]] = []
    for group_key, group in SUMMARY_CHANGE_GROUPS.items():
        items = []
        for change in changes:
            if change.get("change_type") not in group["types"]:
                continue
            label = change.get("field_label") or change.get("field_name") or "Изменение"
            value = change.get("new_value") or change.get("old_value") or change.get("details")
            items.append(f"{label}: {value}" if value else label)
        if items:
            summary.append(
                {
                    "key": group_key,
                    "label": group["label"],
                    "short_label": group.get("short_label") or group["label"],
                    "count": len(items),
                    "items": items,
                }
            )
    other_items = []
    known_types = set().union(*(group["types"] for group in SUMMARY_CHANGE_GROUPS.values()))
    for change in changes:
        if change.get("change_type") in known_types:
            continue
        label = change.get("field_label") or change.get("field_name") or "Изменение"
        value = change.get("new_value") or change.get("old_value") or change.get("details")
        other_items.append(f"{label}: {value}" if value else label)
    if other_items:
        summary.append(
            {
                "key": "other",
                "label": "Прочее",
                "short_label": "Прочее",
                "count": len(other_items),
                "items": other_items,
            }
        )
    return summary


def build_audit_change_counters(changes: list[dict[str, Any]]) -> dict[str, int]:
    """Считает изменения по рабочим группам для карточек протокола."""
    counters = {key: 0 for key in SUMMARY_CHANGE_GROUPS}
    counters["other"] = 0
    counters["total"] = len(changes)
    for change in changes:
        counters[_summary_group_for_change(change.get("change_type"))] += 1
    return counters


def get_audit_summary(
    *,
    date_from: str | date | datetime | None = None,
    date_to: str | date | datetime | None = None,
) -> dict[str, Any]:
    """Возвращает короткую статистику для верхних карточек страницы аудита."""
    where: list[str] = []
    params: list[Any] = []

    parsed_from = _parse_datetime_start(date_from)
    parsed_to = _parse_datetime_end(date_to)
    if parsed_from:
        where.append("created_at >= %s")
        params.append(parsed_from)
    if parsed_to:
        where.append("created_at <= %s")
        params.append(parsed_to)
    if not where:
        where.append("created_at >= now() - interval '24 hours'")

    where_sql = " AND ".join(where)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_events,
                    COUNT(*) FILTER (WHERE result = 'success') AS success_events,
                    COUNT(*) FILTER (WHERE result = 'error') AS error_events,
                    COUNT(*) FILTER (WHERE result = 'denied') AS denied_events,
                    COUNT(*) FILTER (WHERE action IN ('download_word_report', 'export_audit_log')) AS export_events,
                    COUNT(*) FILTER (WHERE action IN ('login_failed', 'access_denied')) AS security_events,
                    COUNT(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL) AS active_users
                FROM audit_events
                WHERE {where_sql}
                """,
                params,
            )
            row = cur.fetchone() or {}
    return dict(row)


def get_audit_action_choices() -> list[tuple[str, str]]:
    """Возвращает список действий для фильтра в интерфейсе."""
    return sorted(ACTION_LABELS.items(), key=lambda item: item[1])


def get_audit_action_category_choices() -> list[tuple[str, str]]:
    """Возвращает категории действий для фильтра в интерфейсе."""
    order = ["auth", "view", "patient", "appointment", "export", "admin", "security", "error", "other"]
    return [(key, ACTION_CATEGORY_LABELS[key]) for key in order if key in ACTION_CATEGORY_LABELS]


def get_audit_role_choices() -> list[tuple[str, str]]:
    """Возвращает роли, которые сейчас используются в фильтрах журнала."""
    return [("admin", "Администратор"), ("doctor", "Врач")]
