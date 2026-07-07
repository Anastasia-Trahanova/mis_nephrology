"""
Назначение файла: HTML-страницы форм приёма.

Что выполняет файл:
- показывает форму нового пациента с первым приёмом;
- показывает форму повторного приёма существующего пациента;
- передаёт подготовку context в app.services.appointment_form_context_service;
- не сохраняет формы и не содержит SQL.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.services.appointment_form_context_service import (
    get_new_appointment_context,
    get_new_patient_context,
)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/new-patient", response_class=HTMLResponse)
def new_patient_form(request: Request):
    """Форма создания нового пациента и первого приёма."""
    context = get_new_patient_context()
    now = datetime.now()
    context.update(
        {
            "request": request,
            "now_date": now.strftime("%Y-%m-%d"),
            "now_time": now.strftime("%H:%M"),
        }
    )
    return templates.TemplateResponse("new_patient.html", context)


@router.get("/new-appointment/{patient_id}", response_class=HTMLResponse)
def new_appointment_form(request: Request, patient_id: int):
    """Форма повторного приёма."""
    context = get_new_appointment_context(patient_id)
    if not context:
        raise HTTPException(status_code=404, detail="Пациент не найден")

    now = datetime.now()
    context.update(
        {
            "request": request,
            "now_date": now.strftime("%Y-%m-%d"),
            "now_time": now.strftime("%H:%M"),
        }
    )
    return templates.TemplateResponse("new_appointment.html", context)
