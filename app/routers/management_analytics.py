"""Административная аналитика по отделениям, врачам и расписанию."""
from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.repositories.audit_log import (
    ACTION_CATEGORIES,
    ACTION_LABELS,
    CATEGORY_ACTIONS,
    log_audit_event,
)
from app.repositories.management_analytics import AnalyticsFilters
from app.security.permissions import (
    ROLE_ADMIN,
    ROLE_CHIEF_PHYSICIAN,
    ROLE_DEPARTMENT_HEAD,
    require_roles,
)
from app.services.management_analytics_service import (
    REPORT_LABELS,
    build_analytics_xlsx,
    build_dashboard,
)

router = APIRouter(tags=["management_analytics"])
templates = Jinja2Templates(directory="app/templates")

_ANALYTICS_ACTIONS = {
    "open_management_analytics": "Открыл аналитику",
    "filter_management_analytics": "Применил фильтры аналитики",
    "export_management_analytics": "Выгрузил аналитический отчёт",
}
ACTION_LABELS.update(_ANALYTICS_ACTIONS)
ACTION_CATEGORIES.update(
    {
        "open_management_analytics": "admin",
        "filter_management_analytics": "admin",
        "export_management_analytics": "export",
    }
)
CATEGORY_ACTIONS.setdefault("admin", set()).update(
    {"open_management_analytics", "filter_management_analytics"}
)
CATEGORY_ACTIONS.setdefault("export", set()).add("export_management_analytics")


def _require_access(request: Request) -> None:
    require_roles(request, ROLE_ADMIN, ROLE_CHIEF_PHYSICIAN, ROLE_DEPARTMENT_HEAD)


def _filters(request: Request) -> AnalyticsFilters:
    return AnalyticsFilters.from_mapping(request.query_params)


def _filter_details(filters: AnalyticsFilters) -> str:
    parts = [f"период {filters.date_from:%d.%m.%Y}–{filters.date_to:%d.%m.%Y}"]
    if filters.location_id:
        parts.append(f"отделение id={filters.location_id}")
    if filters.doctor_id:
        parts.append(f"врач id={filters.doctor_id}")
    return "; ".join(parts)


@router.get("/analytics", response_class=HTMLResponse)
def management_analytics_page(request: Request):
    _require_access(request)
    filters = _filters(request)
    dashboard = build_dashboard(filters)
    action = "filter_management_analytics" if request.query_params else "open_management_analytics"
    log_audit_event(
        request,
        action,
        entity_type="management_analytics",
        details=_filter_details(filters),
    )
    return templates.TemplateResponse(
        request=request,
        name="management_analytics.html",
        context={
            "request": request,
            "dashboard": dashboard,
            "report_labels": REPORT_LABELS,
        },
    )


@router.get("/analytics/export.xlsx")
def management_analytics_export(request: Request, report: str = "all"):
    _require_access(request)
    filters = _filters(request)
    report = report if report in REPORT_LABELS else "all"
    generated_by = (
        request.session.get("display_name")
        or request.session.get("login")
        or "Пользователь МИС"
    )
    content, filename = build_analytics_xlsx(
        filters,
        report,
        generated_by=str(generated_by),
    )
    log_audit_event(
        request,
        "export_management_analytics",
        entity_type="management_analytics",
        details=f"{REPORT_LABELS[report]}; {_filter_details(filters)}",
    )
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
