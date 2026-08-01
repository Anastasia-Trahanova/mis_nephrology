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
from decimal import Decimal, InvalidOperation

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


def _query_int(request: Request, name: str) -> int | None:
    """Безопасно читает положительный integer из query string."""
    value = request.query_params.get(name)
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


_PATIENT_LIST_INDICATORS = {
    "hemoglobin": "гемоглобин",
    "potassium": "калий",
    "ptg": "ПТГ",
    "egfr": "СКФ",
}
_PATIENT_LIST_OPERATORS = {"lt": "ниже", "gt": "выше", "between": "от–до"}
_PATIENT_LIST_PERIODS = {
    "0": "за всё время",
    "1": "за 1 месяц",
    "3": "за 3 месяца",
    "6": "за 6 месяцев",
    "12": "за 1 год",
}
_PATIENT_LIST_CATEGORIES = {"С1", "С2", "С3а", "С3б", "С4", "С5"}


def _safe_query_number(request: Request, name: str) -> str | None:
    """Возвращает только безопасное неотрицательное число из фильтра."""
    raw = str(request.query_params.get(name) or "").strip().replace(",", ".")
    if not raw or len(raw) > 20:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    if not value.is_finite() or value < 0 or value > 1_000_000:
        return None
    return format(value.normalize(), "f")


def _patient_list_details(request: Request, *, export: bool = False) -> str:
    """Формирует краткое описание выборки без ФИО и медицинских текстов."""
    indicator_key = str(request.query_params.get("indicator") or "hemoglobin")
    indicator = _PATIENT_LIST_INDICATORS.get(indicator_key, "гемоглобин")
    parts = [
        "выгружен список" if export else "сформирован список",
        f"показатель: {indicator}",
    ]

    mode = str(request.query_params.get("mode") or "manual")
    category = str(request.query_params.get("egfr_category") or "")
    if (
        indicator_key == "egfr"
        and mode == "category"
        and category in _PATIENT_LIST_CATEGORIES
    ):
        parts.append(f"категория: {category}")
    else:
        operator = _PATIENT_LIST_OPERATORS.get(
            str(request.query_params.get("operator") or "lt"),
            "ниже",
        )
        value_from = _safe_query_number(request, "value_from")
        value_to = _safe_query_number(request, "value_to")
        condition = operator
        if value_from is not None:
            condition += f" {value_from}"
        if operator == "от–до" and value_to is not None:
            condition += f"–{value_to}"
        parts.append(f"условие: {condition}")

    period = _PATIENT_LIST_PERIODS.get(
        str(request.query_params.get("period_months") or "6")
    )
    if period:
        parts.append(period)
    return "; ".join(parts)


def classify_request(request: Request, status_code: int) -> AuditAction | None:
    """
    Определяет, какое событие записать для запроса.
    В журнал попадают только безопасные факты: открытие карточки, списка, расписания,
    Word-экспорта и ошибки доступа/сервера.
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
            appointment_id = _query_int(request, "appointment_id")
            if appointment_id is not None:
                return AuditAction(
                    action="open_patient_appointment",
                    patient_id=patient_id,
                    appointment_id=appointment_id,
                    details="открыт конкретный приём в карточке пациента",
                )
            return AuditAction(
                action="open_patient_card",
                patient_id=patient_id,
                details="открыта карточка пациента",
            )

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

    if method == "GET" and path == "/patient-lists":
        if request.query_params:
            return AuditAction(
                action="filter_patient_lists",
                details=_patient_list_details(request),
            )
        return AuditAction(
            action="open_patient_lists",
            details="открыта страница списков пациентов",
        )

    if method == "GET" and path == "/patient-lists/export.csv":
        return AuditAction(
            action="export_patient_lists",
            details=_patient_list_details(request, export=True),
        )

    if method == "GET" and path == "/ckd-registry":
        return AuditAction(
            action="filter_local_ckd_registry" if request.query_params else "open_local_ckd_registry",
            details="открыт локальный регистр ХБП с фильтрами" if request.query_params else "открыт локальный регистр ХБП",
        )

    if method == "GET" and path == "/ckd-registry/export.xlsx":
        return AuditAction(
            action="export_local_ckd_registry",
            details="выгружен локальный регистр ХБП в Excel",
        )

    if method == "POST":
        patient_id = _match_int(r"/ckd-registry/patient/(\d+)/include", path)
        if patient_id is not None:
            return AuditAction(
                action="include_local_ckd_registry_patient",
                patient_id=patient_id,
                details="пациент включён в локальный регистр ХБП",
            )

        patient_id = _match_int(r"/ckd-registry/patient/(\d+)/outcome", path)
        if patient_id is not None:
            return AuditAction(
                action="add_local_ckd_registry_outcome",
                patient_id=patient_id,
                details="добавлен исход в локальном регистре ХБП",
            )

    if method == "GET" and path == "/schedule":
        return AuditAction(action="open_schedule", details="открыто расписание")

    if method == "GET" and path == "/admin/audit":
        return AuditAction(
            action="open_admin_audit",
            details="открыт журнал работы МИС",
        )

    # Выгрузка и страницы подробностей создают точные события в admin.py.
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
