"""
Назначение файла: административные страницы МИС.

Как работает:
- подключает страницу /admin/audit со списком событий;
- подключает страницу /admin/audit/{event_id} с подробностями одного события;
- пускает сюда только пользователя с ролью admin;
- читает журнал действий и подробности из app.repositories.audit_log;
- не даёт врачу открыть административный журнал.

Что редактировать здесь:
- маршруты административного раздела;
- параметры фильтров журнала;
- лимиты вывода событий;
- состав контекста для шаблонов admin/audit*.html.

Что не редактировать здесь:
- SQL таблиц audit_events/audit_event_changes — он в app/repositories/audit_log.py;
- ролевые helper-функции — они в app/security/permissions.py;
- дизайн общей навигации — он в app/templates/base.html.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.audit_log import (
    get_audit_action_choices,
    get_audit_event,
    get_audit_event_changes,
    get_audit_events,
    get_audit_summary,
    group_audit_changes_by_section,
    build_audit_protocol_summary,
)
from app.security.permissions import require_admin


router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/audit", response_class=HTMLResponse)
def admin_audit_page(
    request: Request,
    action: str | None = None,
    result: str | None = None,
    user_login: str | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Показывает журнал действий пользователей. Доступно только admin."""
    require_admin(request)

    events = get_audit_events(
        limit=limit,
        offset=offset,
        action=action or None,
        result=result or None,
        user_login=user_login or None,
    )
    summary = get_audit_summary()

    return templates.TemplateResponse(
        "admin/audit.html",
        {
            "request": request,
            "events": events,
            "summary": summary,
            "action_choices": get_audit_action_choices(),
            "selected_action": action or "",
            "selected_result": result or "",
            "user_login": user_login or "",
            "limit": limit,
            "offset": offset,
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
    grouped_changes = group_audit_changes_by_section(changes)


    return templates.TemplateResponse(
        "admin/audit_event_detail.html",
        {
            "request": request,
            "event": event,
            "changes": changes,
            "grouped_changes": grouped_changes,
        },
    )
