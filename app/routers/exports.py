"""
Назначение файла: роуты экспорта заключений.

Что выполняет файл:
- отдаёт Word-файл .docx;
- не содержит сборку Word-документа: она вынесена в app.services.word_export.

Что редактировать:
- HTTP-поведение экспорта: имя файла, media_type, статус 404.

Что не редактировать здесь:
- структуру Word-заключения;
- медицинский текст заключения;
- SQL-запросы для экспорта.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.word_export import build_appointment_docx

router = APIRouter(tags=["exports"])


@router.get("/export/{appointment_id}/docx")
def export_appointment_docx(appointment_id: int):
    """Экспорт заключения приёма в Word-файл .docx."""
    result = build_appointment_docx(appointment_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Приём не найден")

    buffer, filename = result
    quoted_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quoted_filename}",
    }
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )
