"""Small laboratory APIs used by the appointment UI."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.repositories.lab_history import get_patient_biochemistry_history
from app.services.kidney_preview_service import build_kidney_preview

router = APIRouter(tags=["lab_api"])


@router.get("/api/patient/{patient_id}/biochemistry_history")
async def api_biochemistry_history(patient_id: int):
    return get_patient_biochemistry_history(patient_id)


@router.post("/api/kidney-preview")
async def api_kidney_preview(payload: dict[str, Any]):
    """Return server-calculated live kidney metrics for unsaved form values."""
    return build_kidney_preview(payload)
