"""
Назначение файла: небольшие API для лабораторных данных, используемые интерфейсом.

Что выполняет файл:
- отдаёт историю биохимии пациента для AJAX-интерфейса;
- не отвечает за HTML-страницы, сохранение форм и экспорт документов.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.repositories.lab_history import get_patient_biochemistry_history

router = APIRouter(tags=["lab_api"])


@router.get("/api/patient/{patient_id}/biochemistry_history")
async def api_biochemistry_history(patient_id: int):
    """Возвращает историю биохимических анализов пациента."""
    return get_patient_biochemistry_history(patient_id)
