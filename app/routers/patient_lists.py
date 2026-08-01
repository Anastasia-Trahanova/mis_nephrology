"""Динамические списки пациентов по клиническим показателям."""

from __future__ import annotations

from io import BytesIO

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.security.permissions import CLINICAL_ROLES, ROLE_ADMIN, require_roles
from ..patient_list_queries import (
    EGFR_CATEGORIES,
    INDICATORS,
    OPERATOR_LABELS,
    PERIOD_LABELS,
    PatientListFilters,
    build_patient_list_csv,
    get_patient_indicator_history,
    get_patient_list,
)

router = APIRouter(tags=["patient_lists"])
templates = Jinja2Templates(directory="app/templates")


def require_patient_lists_access(request: Request) -> None:
    """Разрешает списки администратору и всем клиническим ролям."""
    require_roles(request, ROLE_ADMIN, *CLINICAL_ROLES)


@router.get("/patient-lists", response_class=HTMLResponse)
def patient_lists_page(request: Request):
    require_patient_lists_access(request)
    filters = PatientListFilters.from_mapping(request.query_params)
    result = get_patient_list(filters)
    return templates.TemplateResponse(
        request=request,
        name="patient_lists.html",
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


@router.get("/patient-lists/patient/{patient_id}/dynamics")
def patient_indicator_dynamics(request: Request, patient_id: int, indicator: str):
    require_patient_lists_access(request)
    if indicator not in INDICATORS:
        raise HTTPException(status_code=400, detail="Неизвестный показатель")

    result = get_patient_indicator_history(patient_id, indicator)
    if result is None:
        raise HTTPException(status_code=404, detail="Пациент не найден")
    return result


@router.get("/patient-lists/export.csv")
def export_patient_list(request: Request):
    require_patient_lists_access(request)
    filters = PatientListFilters.from_mapping(request.query_params)
    content, filename = build_patient_list_csv(filters)
    return StreamingResponse(
        BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
