"""
Назначение файла: роуты экспорта заключений.

Что выполняет файл:
- отдаёт старый HTML/text export;
- отдаёт Word-файл .docx;
- не содержит внутреннюю сборку Word-документа: она вынесена в app.services.word_export.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse

from app.repositories.appointments import get_appointment_full_data
from app.repositories.reference_data import get_location_info
from app.services.word_export import build_appointment_docx

router = APIRouter(tags=["exports"])


@router.get("/export/{appointment_id}")
def export_appointment(appointment_id: int):
    """Экспорт заключения в старом HTML/text-виде."""
    appointment = get_appointment_full_data(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Приём не найден")

    location_info = None
    if appointment.get("location_id"):
        location_info = get_location_info(appointment["location_id"])

    if location_info:
        company_name = location_info.get("company_name") or "ООО «КОМПАНИЯ «ФЕСФАРМ»"
        location_name = location_info.get("location_name") or ""
        location_address = location_info.get("location_address") or ""
        branch_phone = location_info.get("branch_phone") or ""
        company_phone = location_info.get("company_phone") or ""
        phone = branch_phone or company_phone or ""
        branch_email = location_info.get("branch_email") or ""
        company_email = location_info.get("company_email") or ""
        email = branch_email or company_email or ""
        header_text = f"""
{company_name}
{location_name}
{location_address}
Тел: {phone}{' | Email: ' + email if email else ''}
"""
    else:
        header_text = "ООО «КОМПАНИЯ «ФЕСФАРМ»\n\n"

    appointment_date = appointment.get("appointment_date")
    next_control_date = appointment.get("next_control_date")
    report = f"""{header_text}
ЗАКЛЮЧЕНИЕ ПО РЕЗУЛЬТАТАМ ПРИЁМА

Дата приёма: {appointment_date.strftime('%d.%m.%Y %H:%M') if appointment_date else '—'}
Врач: {appointment['doctor_name']}
Отделение: {appointment.get('location_name', '—')} ({appointment.get('branch_name', '—')})

Пациент: {appointment.get('patient_last_name', '')} {appointment.get('patient_first_name', '')} {appointment.get('patient_patronymic', '')}

Жалобы: {appointment.get('complaints', '—')}

Диагноз: {appointment.get('main_diagnosis', '—')}

Лечение: {appointment.get('medication', '—')} {appointment.get('dosage', '')} {appointment.get('schedule', '')}

Дата следующего контроля: {next_control_date.strftime('%d.%m.%Y') if next_control_date else '—'}
"""
    return HTMLResponse(
        content=f"<pre>{report}</pre>",
        media_type="text/html; charset=utf-8",
    )


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
