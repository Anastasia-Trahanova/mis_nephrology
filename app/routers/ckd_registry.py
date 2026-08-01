"""Страница динамических списков пациентов для врачей и администратора."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.security.permissions import CLINICAL_ROLES, ROLE_ADMIN, require_roles
from ..registry_queries import (
    EGFR_CATEGORIES,
    INDICATORS,
    OPERATOR_LABELS,
    PERIOD_LABELS,
    RegistryFilters,
    build_registry_csv,
    get_patient_indicator_history,
    get_patient_registry,
)

router = APIRouter(tags=["ckd_registry"])
templates = Jinja2Templates(directory="app/templates")

def require_registry_access(request: Request) -> None:
    """Разрешает раздел администратору и всем клиническим ролям."""
    require_roles(request, ROLE_ADMIN, *CLINICAL_ROLES)


@router.get("/ckd-registry", response_class=HTMLResponse)
def patient_lists_page(request: Request):
    require_registry_access(request)
    filters = RegistryFilters.from_mapping(request.query_params)
    result = get_patient_registry(filters)
    return templates.TemplateResponse(
        request=request,
        name="ckd_registry.html",
        context={
            "request": request,
            "filters": filters,
            "result": result,
            "indicators": INDICATORS,
            "egfr_categories": EGFR_CATEGORIES,
            "period_labels": PERIOD_LABELS,
            "operator_labels": OPERATOR_LABELS,
        },
    )


@router.get("/ckd-registry/patient/{patient_id}/dynamics")
def patient_indicator_dynamics(request: Request, patient_id: int, indicator: str):
    require_registry_access(request)
    if indicator not in INDICATORS:
        raise HTTPException(status_code=400, detail="Неизвестный показатель")

    result = get_patient_indicator_history(patient_id, indicator)
    if result is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return result


@router.get("/ckd-registry/export.csv")
def export_patient_list(request: Request):
    require_registry_access(request)
    filters = RegistryFilters.from_mapping(request.query_params)
    content, filename = build_registry_csv(filters)
    return StreamingResponse(
        BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
