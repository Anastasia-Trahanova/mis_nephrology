"""
Роуты создания новых приёмов существующих пациентов.

Этот файл вынесен из patients.py, потому что повторный приём — отдельная операция: 
пациент уже существует, а создаётся только новая запись appointments и связанные с ней данные приёма.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..services.patient_appointment_service import create_appointment_for_existing_patient

router = APIRouter(tags=["appointments"])


@router.post("/api/patients/{patient_id}/appointments/new")
async def create_new_appointment_for_existing_patient(patient_id: int, request: Request):
    """Создаёт новый приём для уже существующего пациента."""
    form = await request.form()
    result = create_appointment_for_existing_patient(patient_id, form)

    return RedirectResponse(
        url=f"/patient/{result.patient_id}?appointment_id={result.appointment_id}",
        status_code=303,
    )
