"""Административные страницы МИС: журнал, протокол события и протокол приёма."""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.repositories.audit_log import (
    get_audit_action_category_choices,
    get_audit_action_choices,
    get_audit_changes_for_events,
    get_audit_event,
    get_audit_event_changes,
    get_audit_events,
    get_audit_events_for_appointment,
    get_audit_role_choices,
    get_audit_summary,
    log_audit_event,
)
from app.security.permissions import require_admin
from app.services.audit_view_service import (
    build_appointment_audit_view_model,
    build_audit_event_view_model,
)


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


def _bool_from_query(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on", "да"}


def _int_or_none(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _audit_filters(
    *,
    action: str | None = None,
    result: str | None = None,
    user_login: str | None = None,
    user_role: str | None = None,
    patient_id: str | int | None = None,
    appointment_id: str | int | None = None,
    action_category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    only_errors: str | bool | None = None,
) -> dict[str, Any]:
    """Единая сборка фильтров для страницы и CSV."""
    return {
        "action": action or None,
        "result": result or None,
        "user_login": user_login or None,
        "user_role": user_role or None,
        "patient_id": _int_or_none(patient_id),
        "appointment_id": _int_or_none(appointment_id),
        "action_category": action_category or None,
        "date_from": date_from or None,
        "date_to": date_to or None,
        "only_errors": _bool_from_query(only_errors),
    }


def _filters_state(filters: dict[str, Any]) -> dict[str, Any]:
    return {
        "selected_action": filters.get("action") or "",
        "selected_result": filters.get("result") or "",
        "selected_user_role": filters.get("user_role") or "",
        "selected_action_category": filters.get("action_category") or "",
        "user_login": filters.get("user_login") or "",
        "patient_id": filters.get("patient_id") or "",
        "appointment_id": filters.get("appointment_id") or "",
        "date_from": filters.get("date_from") or "",
        "date_to": filters.get("date_to") or "",
        "only_errors": bool(filters.get("only_errors")),
    }


@router.get("/audit", response_class=HTMLResponse)
def admin_audit_page(
    request: Request,
    action: str | None = None,
    result: str | None = None,
    user_login: str | None = None,
    user_role: str | None = None,
    patient_id: str | None = None,
    appointment_id: str | None = None,
    action_category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    only_errors: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Показывает журнал действий пользователей. Доступно только admin."""
    require_admin(request)
    filters = _audit_filters(
        action=action,
        result=result,
        user_login=user_login,
        user_role=user_role,
        patient_id=patient_id,
        appointment_id=appointment_id,
        action_category=action_category,
        date_from=date_from,
        date_to=date_to,
        only_errors=only_errors,
    )
    safe_limit = max(1, min(int(limit or 200), 500))
    safe_offset = max(0, int(offset or 0))

    events = get_audit_events(limit=safe_limit, offset=safe_offset, **filters)
    summary = get_audit_summary(date_from=filters.get("date_from"), date_to=filters.get("date_to"))

    log_audit_event(request, "open_admin_audit", details="Открыт журнал аудита", entity_type="audit")

    return templates.TemplateResponse(
        "admin/audit.html",
        {
            "request": request,
            "events": events,
            "summary": summary,
            "action_choices": get_audit_action_choices(),
            "action_category_choices": get_audit_action_category_choices(),
            "role_choices": get_audit_role_choices(),
            "limit": safe_limit,
            "offset": safe_offset,
            **_filters_state(filters),
        },
    )


@router.get("/audit/export.csv")
def admin_audit_export_csv(
    request: Request,
    action: str | None = None,
    result: str | None = None,
    user_login: str | None = None,
    user_role: str | None = None,
    patient_id: str | None = None,
    appointment_id: str | None = None,
    action_category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    only_errors: str | None = None,
):
    """Выгружает журнал аудита в CSV для проверки/внутреннего контроля."""
    require_admin(request)
    filters = _audit_filters(
        action=action,
        result=result,
        user_login=user_login,
        user_role=user_role,
        patient_id=patient_id,
        appointment_id=appointment_id,
        action_category=action_category,
        date_from=date_from,
        date_to=date_to,
        only_errors=only_errors,
    )
    events = get_audit_events(limit=5000, offset=0, **filters)

    output = StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "id",
            "created_at",
            "user_login",
            "user_role",
            "category",
            "action",
            "action_label",
            "result",
            "patient_id",
            "patient_name",
            "appointment_id",
            "ip_address",
            "method",
            "path",
            "status_code",
            "details",
            "error_message",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.get("id"),
                event.get("created_at"),
                event.get("user_login"),
                event.get("user_role"),
                event.get("action_category_label"),
                event.get("action"),
                event.get("action_label"),
                event.get("result_label") or event.get("result"),
                event.get("patient_id"),
                event.get("patient_name"),
                event.get("appointment_id"),
                event.get("ip_address"),
                event.get("method"),
                event.get("path"),
                event.get("status_code"),
                event.get("details"),
                event.get("error_message"),
            ]
        )

    log_audit_event(
        request,
        "export_audit_log",
        details=f"CSV выгрузка журнала аудита: {len(events)} строк",
        entity_type="audit",
    )

    csv_text = "\ufeff" + output.getvalue()
    headers = {"Content-Disposition": 'attachment; filename="mis_audit_log.csv"'}
    return StreamingResponse(iter([csv_text]), media_type="text/csv; charset=utf-8", headers=headers)


@router.get("/audit/appointment/{appointment_id}", response_class=HTMLResponse)
def admin_appointment_audit_page(request: Request, appointment_id: int):
    """Показывает рабочий протокол аудита всего приёма."""
    require_admin(request)
    events = get_audit_events_for_appointment(appointment_id)
    if not events:
        raise HTTPException(status_code=404, detail="События аудита по этому приёму не найдены")

    changes_by_event = get_audit_changes_for_events([int(event["id"]) for event in events])
    view_model = build_appointment_audit_view_model(appointment_id, events, changes_by_event)

    log_audit_event(
        request,
        "open_admin_appointment_audit",
        appointment_id=appointment_id,
        entity_type="appointment",
        entity_id=appointment_id,
        details="Открыт протокол аудита приёма",
    )

    return templates.TemplateResponse(
        "admin/audit_appointment_protocol.html",
        {
            "request": request,
            "protocol": view_model,
        },
    )


@router.get("/audit/{event_id}", response_class=HTMLResponse)
def admin_audit_detail_page(request: Request, event_id: int):
    """Показывает подробности одного события аудита. Доступно только admin."""
    require_admin(request)
    event = get_audit_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Событие аудита не найдено")

    changes = get_audit_event_changes(event_id)
    related_events = []
    if event.get("appointment_id"):
        related_events = [
            related
            for related in get_audit_events_for_appointment(int(event["appointment_id"]), limit=20)
            if int(related["id"]) != int(event_id)
        ]
    view_model = build_audit_event_view_model(event, changes, related_events=related_events)

    log_audit_event(
        request,
        "open_admin_audit_event",
        appointment_id=event.get("appointment_id"),
        patient_id=event.get("patient_id"),
        entity_type="audit_event",
        entity_id=event_id,
        details=f"Открыт протокол события аудита №{event_id}",
    )

    return templates.TemplateResponse(
        "admin/audit_event_detail.html",
        {
            "request": request,
            **view_model,
        },
    )
