"""
Назначение файла: middleware аудита действий пользователей.

Как работает:
- смотрит на уже обработанный HTTP-запрос и статус ответа;
- для важных страниц создаёт короткое событие audit_events;
- не читает тело форм и не пишет в журнал медицинские тексты;
- ошибки самого аудита не ломают работу МИС.

Что редактировать здесь:
- функцию classify_request(), если нужно добавить новое действие в журнал;
- список игнорируемых технических путей;
- текст details для безопасных служебных пояснений.

Что не редактировать здесь:
- SQL записи журнала — он в app/repositories/audit_log.py;
- права доступа — они в app/security/permissions.py;
- login/logout — они в app/routers/auth.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.repositories.audit_log import log_audit_event


@dataclass(frozen=True)
class AuditAction:
    """Описание события, которое нужно записать в audit_events."""

    action: str
    result: str = "success"
    patient_id: int | None = None
    appointment_id: int | None = None
    details: str | None = None


def _match_int(pattern: str, path: str) -> int | None:
    """Возвращает id из URL, если path полностью совпал с regex."""
    match = re.fullmatch(pattern, path)
    if not match:
        return None
    return int(match.group(1))


def should_ignore_path(path: str) -> bool:
    """Отбрасывает технические пути, которые не нужны в журнале действий."""
    return (
        path == "/login"
        or path.startswith("/static/")
        or path.startswith("/auth/session/")
        or path == "/favicon.ico"
    )


def classify_request(request: Request, status_code: int) -> AuditAction | None:
    """
    Определяет, какое событие записать для запроса.

    В журнал попадают только безопасные факты: открытие карточки, списка, Word-экспорта,
    административного журнала и ошибки доступа/сервера.
    """
    path = request.url.path
    method = request.method.upper()

    if should_ignore_path(path):
        return None

    if status_code == 403:
        return AuditAction(
            action="access_denied",
            result="denied",
            details=f"{method} {path}",
        )

    if status_code >= 500:
        return AuditAction(
            action="server_error",
            result="error",
            details=f"{method} {path}",
        )

    if status_code >= 400:
        return None

    if method == "GET" and path == "/patients":
        details = "открыт список"
        if request.url.query:
            details = "открыт список с фильтрами"
        return AuditAction(action="open_patient_list", details=details)

    if method == "GET":
        patient_id = _match_int(r"/patient/(\d+)", path)
        if patient_id is not None:
            return AuditAction(action="open_patient_card", patient_id=patient_id)

    if method == "GET" and path == "/new-patient":
        return AuditAction(action="open_new_patient_form")

    if method == "GET":
        patient_id = _match_int(r"/new-appointment/(\d+)", path)
        if patient_id is not None:
            return AuditAction(action="open_new_appointment_form", patient_id=patient_id)

    if method == "GET":
        appointment_id = _match_int(r"/export/(\d+)/docx", path)
        if appointment_id is not None:
            return AuditAction(action="download_word_report", appointment_id=appointment_id)

    if method == "GET" and path == "/ckd-registry":
        return AuditAction(action="open_ckd_registry")

    if method == "GET" and path == "/admin/audit":
        return AuditAction(action="open_admin_audit")

    return None


class AuditMiddleware(BaseHTTPMiddleware):
    """Записывает события аудита после обработки защищённых запросов."""

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
        except Exception as exc:
            if request.session.get("user_id"):
                log_audit_event(
                    request,
                    "server_error",
                    result="error",
                    details=f"{request.method} {request.url.path}",
                    error_message=repr(exc),
                )
            raise

        if request.session.get("user_id"):
            event = classify_request(request, response.status_code)
            if event is not None:
                log_audit_event(
                    request,
                    event.action,
                    result=event.result,
                    patient_id=event.patient_id,
                    appointment_id=event.appointment_id,
                    details=event.details,
                    status_code=response.status_code,
                )

        return response
