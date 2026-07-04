"""
Сохранение структурированных диагнозов приёма по МКБ-10.

Этот модуль нужен, чтобы держать бизнес-логику МКБ-10 отдельно от роутеров:
- разобрать диагнозы из формы;
- проверить, что выбранный диагноз есть в активном справочнике;
- сохранить связи appointment -> icd10_diagnosis.

SQL вынесен в app/repositories/diagnoses.py.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from ..repositories.diagnoses import (
    find_active_icd10_diagnosis_id,
    insert_appointment_icd10_diagnosis_row,
)
from .form_parsing import empty_to_none, get_form_list_keep_empty, value_at


def insert_appointment_icd10_diagnosis(
    cur: Any,
    appointment_id: int,
    diagnosis_type: str,
    diagnosis_text: str | None,
    doctor_note: str | None = None,
    sort_order: int = 1,
) -> int | None:
    """
    Сохраняет один структурированный диагноз по МКБ-10.

    diagnosis_text приходит из формы как строка из справочника, например:
    "N18.3 — Хроническая болезнь почек, стадия 3".

    В appointment_icd10_diagnoses сохраняется не текст, а ссылка на
    icd10_diagnoses.id.
    """
    diagnosis_text = empty_to_none(diagnosis_text)
    doctor_note = empty_to_none(doctor_note)

    if not diagnosis_text:
        return None

    icd10_diagnosis_id = find_active_icd10_diagnosis_id(cur, diagnosis_text)

    if not icd10_diagnosis_id:
        raise HTTPException(
            status_code=400,
            detail=f"Диагноз МКБ-10 не найден в справочнике: {diagnosis_text}",
        )

    insert_appointment_icd10_diagnosis_row(
        cur=cur,
        appointment_id=appointment_id,
        diagnosis_type=diagnosis_type,
        icd10_diagnosis_id=icd10_diagnosis_id,
        doctor_note=doctor_note,
        sort_order=sort_order,
    )

    return icd10_diagnosis_id


def parse_icd10_diagnoses_from_form(form: Any) -> dict[str, Any]:
    """
    Забирает из формы структурированные диагнозы МКБ-10.

    Возвращает словарь, который потом можно передать в
    save_appointment_icd10_diagnoses().
    """
    return {
        "main_diagnosis": empty_to_none(form.get("icd10_main_diagnosis")),
        "main_note": empty_to_none(form.get("icd10_main_note")),
        "complication_diagnoses": get_form_list_keep_empty(
            form,
            "icd10_complication_diagnosis",
        ),
        "complication_notes": get_form_list_keep_empty(
            form,
            "icd10_complication_note",
        ),
        "comorbidity_diagnoses": get_form_list_keep_empty(
            form,
            "icd10_comorbidity_diagnosis",
        ),
        "comorbidity_notes": get_form_list_keep_empty(
            form,
            "icd10_comorbidity_note",
        ),
    }


def save_appointment_icd10_diagnoses(
    cur: Any,
    appointment_id: int,
    icd10_data: dict[str, Any],
) -> None:
    """Сохраняет структурированные диагнозы МКБ-10 для приёма."""
    insert_appointment_icd10_diagnosis(
        cur=cur,
        appointment_id=appointment_id,
        diagnosis_type="main",
        diagnosis_text=icd10_data.get("main_diagnosis"),
        doctor_note=icd10_data.get("main_note"),
        sort_order=1,
    )

    complication_diagnoses = icd10_data.get("complication_diagnoses") or []
    complication_notes = icd10_data.get("complication_notes") or []

    for index, diagnosis_text in enumerate(complication_diagnoses, start=1):
        insert_appointment_icd10_diagnosis(
            cur=cur,
            appointment_id=appointment_id,
            diagnosis_type="complication",
            diagnosis_text=diagnosis_text,
            doctor_note=value_at(complication_notes, index - 1),
            sort_order=index,
        )

    comorbidity_diagnoses = icd10_data.get("comorbidity_diagnoses") or []
    comorbidity_notes = icd10_data.get("comorbidity_notes") or []

    for index, diagnosis_text in enumerate(comorbidity_diagnoses, start=1):
        insert_appointment_icd10_diagnosis(
            cur=cur,
            appointment_id=appointment_id,
            diagnosis_type="comorbidity",
            diagnosis_text=diagnosis_text,
            doctor_note=value_at(comorbidity_notes, index - 1),
            sort_order=index,
        )


def save_appointment_icd10_diagnoses_from_form(
    cur: Any,
    appointment_id: int,
    form: Any,
) -> None:
    """
    Совместимая функция для старого кода.

    Её можно оставить на переходный период, если где-то ещё вызывается сохранение
    МКБ-10 прямо из формы.
    """
    icd10_data = parse_icd10_diagnoses_from_form(form)
    save_appointment_icd10_diagnoses(cur, appointment_id, icd10_data)
