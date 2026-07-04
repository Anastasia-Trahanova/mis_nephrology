"""
Repository для диагнозов приёма.

Файл работает с двумя видами диагнозов:
- свободные текстовые диагнозы в таблице diagnoses;
- структурированные диагнозы МКБ-10 через справочник icd10_diagnoses и таблицу
  appointment_icd10_diagnoses.

Здесь нет разбора формы и нет проверки бизнес-правил. Сервис выше решает, какие
диагнозы сохранять, а repository только выполняет SQL.
"""

from __future__ import annotations

from typing import Any


def insert_text_diagnoses(cur: Any, appointment_id: int, diagnoses_data: dict[str, Any]) -> None:
    """Сохраняет старые свободные текстовые диагнозы для совместимости."""
    cur.execute(
        """
        INSERT INTO diagnoses (appointment_id, main_diagnosis, complications, comorbidities)
        VALUES (%s, %s, %s, %s)
        """,
        (
            appointment_id,
            diagnoses_data.get("main_diagnosis"),
            diagnoses_data.get("complications"),
            diagnoses_data.get("comorbidities"),
        ),
    )


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
