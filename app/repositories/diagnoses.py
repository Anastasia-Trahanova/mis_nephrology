"""
Назначение файла: repository для структурированных диагнозов приёма по МКБ-10.

Что редактировать:
- SQL для поиска активного диагноза в справочнике icd10_diagnoses;
- SQL для сохранения связи appointment -> icd10_diagnosis.

Что не редактировать здесь:
- разбор HTML-формы;
- автоподстановку диагноза по стадии СКФ;
- свободные текстовые диагнозы: таблица diagnoses удалена отдельной миграцией.
"""

from __future__ import annotations

from typing import Any


def find_active_icd10_diagnosis_id(cur: Any, diagnosis_text: str) -> int | None:
    """Ищет активный диагноз МКБ-10 по тексту из формы и возвращает его id."""
    cur.execute(
        """
        SELECT id
        FROM icd10_diagnoses
        WHERE diagnosis = %s
          AND is_active = TRUE
        LIMIT 1
        """,
        (diagnosis_text,),
    )
    row = cur.fetchone()
    return row["id"] if row else None


def insert_appointment_icd10_diagnosis_row(
    cur: Any,
    appointment_id: int,
    diagnosis_type: str,
    icd10_diagnosis_id: int,
    doctor_note: str | None,
    sort_order: int,
) -> None:
    """Сохраняет связь приёма с диагнозом из справочника МКБ-10."""
    cur.execute(
        """
        INSERT INTO appointment_icd10_diagnoses (
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            doctor_note,
            sort_order
        )
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            doctor_note,
            sort_order,
        ),
    )
