"""
Назначение файла: роуты экспорта заключений и исходных архивных документов.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from app.repositories.appointments import get_archive_source_document_metadata
from app.services.archive_source_documents import (
    ArchiveSourceIntegrityError,
    ArchiveSourceNotConfiguredError,
    ArchiveSourceNotFoundError,
    media_type_for_path,
    resolve_archive_source_document,
)
from app.services.word_export import build_appointment_docx


router = APIRouter(tags=["exports"])


@router.get("/export/{appointment_id}/docx")
def export_appointment_docx(appointment_id: int):
    """Экспорт заключения приёма в сформированный Word-файл .docx."""
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


@router.get("/export/{appointment_id}/archive-source")
def export_archive_source_document(appointment_id: int):
    """Отдаёт оригинальный Word/PDF-файл, из которого импортирован приём."""
    metadata = get_archive_source_document_metadata(appointment_id)
    if not metadata:
        raise HTTPException(status_code=404, detail="Приём не найден")
    if not metadata.get("is_archive_import"):
        raise HTTPException(status_code=404, detail="Это не архивный приём")

    relative_path = metadata.get("archive_source_relative_path")
    if not relative_path:
        raise HTTPException(
            status_code=404,
            detail="Для этого приёма путь к исходному документу ещё не заполнен",
        )

    try:
        document_path = resolve_archive_source_document(
            str(relative_path),
            metadata.get("archive_import_key"),
        )
    except ArchiveSourceNotConfiguredError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ArchiveSourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ArchiveSourceIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return FileResponse(
        path=document_path,
        filename=document_path.name,
        media_type=media_type_for_path(document_path),
    )
