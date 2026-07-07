"""
Назначение файла: HTML-страницы пациентов.

Что выполняет файл:
- показывает список пациентов;
- показывает карточку конкретного пациента;
- собирает только параметры запроса и передаёт работу context-сервисам;
- не содержит SQL, сохранение форм и экспорт документов.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.repositories.patients import get_all_patients
from app.services.patient_card_context_service import get_patient_card_context

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/patients", response_class=HTMLResponse)
def patients_list(
    request: Request,
    search: str | None = None,
    limit: int = 500,
    offset: int = 0,
):
    """Страница списка пациентов."""
    patients = get_all_patients(search=search, limit=limit, offset=offset)
    return templates.TemplateResponse(
        "patients_list.html",
        {
            "request": request,
            "patients": patients,
            "search": search or "",
            "limit": limit,
            "offset": offset,
        },
    )


@router.get("/patient/{patient_id}", response_class=HTMLResponse)
def patient_card(request: Request, patient_id: int):
    """Карточка пациента."""
    show_form = request.query_params.get("show_form") == "true"
    show_previous_labs = request.query_params.get("show_previous_labs") == "true"
    selected_appointment_id = request.query_params.get("appointment_id")

    if selected_appointment_id:
        try:
            selected_appointment_id = int(selected_appointment_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Некорректный appointment_id") from exc
    else:
        selected_appointment_id = None

    context = get_patient_card_context(
        patient_id=patient_id,
        selected_appointment_id=selected_appointment_id,
        show_previous_labs=show_previous_labs,
        show_form=show_form,
    )

    if not context:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    if context.get("forbidden"):
        raise HTTPException(
            status_code=403,
            detail="Этот приём не принадлежит данному пациенту",
        )

    now = datetime.now()
    context.update(
        {
            "request": request,
            "now_date": now.strftime("%Y-%m-%d"),
            "now_time": now.strftime("%H:%M"),
            "show_form": show_form,
        }
    )
    return templates.TemplateResponse("patient_card.html", context)
