"""Локальный регистр пациентов с ХБП."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from urllib.parse import parse_qsl, urlencode

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from app.repositories.ckd_registry import (
    CkdRegistryFilters,
    OUTCOME_LABELS,
    STAGES,
    RegistryConflictError,
    RegistryValidationError,
    add_patient_to_registry,
    add_registry_outcome,
    build_ckd_registry_xlsx,
    get_ckd_registry,
    remove_patient_from_registry,
)
from app.security.permissions import (
    ROLE_ADMIN,
    ROLE_CHIEF_PHYSICIAN,
    ROLE_DEPARTMENT_HEAD,
    require_doctor_with_id,
    require_roles,
)

router = APIRouter(tags=["ckd_registry"])
templates = Jinja2Templates(directory="app/templates")


def require_ckd_registry_access(request: Request) -> None:
    """Страница доступна администратору, главному врачу и заведующему."""
    require_roles(request, ROLE_ADMIN, ROLE_CHIEF_PHYSICIAN, ROLE_DEPARTMENT_HEAD)


def _session_user_id(request: Request) -> int:
    require_doctor_with_id(request)
    try:
        user_id = int(request.session.get("user_id"))
    except (TypeError, ValueError) as exc:
        raise RegistryValidationError("Не удалось определить пользователя") from exc
    if user_id <= 0:
        raise RegistryValidationError("Не удалось определить пользователя")
    return user_id


def _patient_redirect(patient_id: int, *, status: str | None = None, error: str | None = None):
    params: dict[str, str] = {}
    if status:
        params["registry_status"] = status
    if error:
        params["registry_error"] = error[:300]
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(url=f"/patient/{patient_id}{suffix}", status_code=303)


def _registry_redirect(*, return_query: str = "", status: str | None = None, error: str | None = None):
    """Возвращает на регистр, сохраняя только известные параметры фильтра."""
    allowed = {
        "search", "stage", "egfr_operator", "egfr_from", "egfr_to", "outcome",
        "included_from", "included_to", "page", "page_size",
    }
    params = {
        key: value
        for key, value in parse_qsl(str(return_query or "")[:2000], keep_blank_values=False)
        if key in allowed
    }
    if status:
        params["registry_status"] = status
    if error:
        params["registry_error"] = error[:300]
    suffix = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(url=f"/ckd-registry{suffix}", status_code=303)


@router.get("/ckd-registry", response_class=HTMLResponse)
def ckd_registry_page(request: Request):
    require_ckd_registry_access(request)
    filters = CkdRegistryFilters.from_mapping(request.query_params)
    result = get_ckd_registry(filters)
    return templates.TemplateResponse(
        request=request,
        name="ckd_registry.html",
        context={
            "request": request,
            "filters": filters,
            "result": result,
            "stages": STAGES,
            "outcomes": OUTCOME_LABELS,
        },
    )


@router.get("/ckd-registry/export.xlsx")
def export_ckd_registry(request: Request):
    require_ckd_registry_access(request)
    filters = CkdRegistryFilters.from_mapping(request.query_params)
    content, filename = build_ckd_registry_xlsx(filters)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/ckd-registry/patient/{patient_id}/include")
def include_patient_in_registry(
    request: Request,
    patient_id: int,
    last_name: str = Form(...),
    first_name: str = Form(...),
    patronymic: str = Form(""),
    birth_date: date = Form(...),
    phone: str = Form(""),
    diagnosis: str = Form(...),
    egfr: str = Form(""),
    stage: str = Form(""),
    outcome: str = Form("observed"),
    comment: str = Form(""),
):
    try:
        user_id = _session_user_id(request)
        add_patient_to_registry(
            patient_id=patient_id,
            user_id=user_id,
            last_name=last_name,
            first_name=first_name,
            patronymic=patronymic,
            birth_date=birth_date,
            phone=phone,
            diagnosis=diagnosis,
            egfr=egfr,
            stage=stage,
            outcome=outcome,
            comment=comment,
        )
    except (RegistryValidationError, RegistryConflictError) as exc:
        return _patient_redirect(patient_id, error=str(exc))
    return _patient_redirect(patient_id, status="included")



@router.post("/ckd-registry/patient/{patient_id}/remove")
def remove_patient_from_ckd_registry(
    request: Request,
    patient_id: int,
    return_query: str = Form(""),
):
    try:
        require_ckd_registry_access(request)
        try:
            user_id = int(request.session.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise RegistryValidationError("Не удалось определить пользователя") from exc
        remove_patient_from_registry(patient_id=patient_id, user_id=user_id)
    except RegistryValidationError as exc:
        return _registry_redirect(return_query=return_query, error=str(exc))
    return _registry_redirect(return_query=return_query, status="removed")


@router.post("/ckd-registry/patient/{patient_id}/outcome")
def add_patient_registry_outcome(
    request: Request,
    patient_id: int,
    outcome: str = Form(...),
    comment: str = Form(""),
):
    try:
        user_id = _session_user_id(request)
        add_registry_outcome(
            patient_id=patient_id,
            user_id=user_id,
            outcome=outcome,
            comment=comment,
        )
    except RegistryValidationError as exc:
        return _patient_redirect(patient_id, error=str(exc))
    return _patient_redirect(patient_id, status="outcome_added")
