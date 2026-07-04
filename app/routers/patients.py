"""
Роуты создания нового пациента.

После дробления этот файл больше не содержит:
- API фильтров главной страницы;
- создание повторного приёма;
- SQL сохранения анализов;
- медицинские расчёты;
- разбор всех полей формы.

Он принимает форму нового пациента, передаёт её в сервис и делает redirect на
карточку пациента.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from ..services.patient_appointment_service import create_patient_with_first_appointment

router = APIRouter(tags=["patients"])


@router.post("/api/patients/new")
async def create_new_patient(request: Request):
    """Создаёт нового пациента и первый приём."""
    form = await request.form()
    result = create_patient_with_first_appointment(form)

    return RedirectResponse(
        url=f"/patient/{result.patient_id}?appointment_id={result.appointment_id}",
        status_code=303,
    )
