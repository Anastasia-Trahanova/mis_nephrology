"""
Назначение файла: repository лабораторных и инструментальных данных приёма.

Что выполняет файл
-------------------
Содержит INSERT-запросы существующих таблиц анализов и УЗИ.

Файл содержит только INSERT-запросы для таблиц:
- cbc_results;
- biochemistry_results;
- calculated_metrics;
- urinalysis_results;
- albuminuria_results, включая суточную экскрецию альбумина;
- ultrasound_results.

В этом файле нет циклов по форме и медицинских расчётов. Сервис выше решает,
какие строки считать заполненными, какие показатели рассчитать и сколько записей
сохранять.
"""

from __future__ import annotations

from typing import Any


def insert_cbc_result(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    hemoglobin: Any,
    erythrocytes: Any,
    leukocytes: Any,
    platelets: Any,
    esr: Any,
    mcv: Any,
    hematocrit: Any,
) -> None:
    """Сохраняет одну строку общего анализа крови."""
    cur.execute(
        """
        INSERT INTO cbc_results (
            appointment_id,
            investigation_date,
            hemoglobin,
            erythrocytes,
            leukocytes,
            platelets,
            esr,
            mcv,
            hematocrit
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            hemoglobin,
            erythrocytes,
            leukocytes,
            platelets,
            esr,
            mcv,
            hematocrit,
        ),
    )


def insert_biochemistry_result(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    creatinine: Any,
    urea: Any,
    uric_acid: Any,
    glucose: Any,
    total_protein: Any,
    albumin: Any,
    potassium: Any,
    calcium: Any,
    phosphorus: Any,
    ferritin: Any,
    ptg: Any,
) -> None:
    """Сохраняет одну строку биохимического анализа крови."""
    cur.execute(
        """
        INSERT INTO biochemistry_results (
            appointment_id,
            investigation_date,
            creatinine,
            urea,
            uric_acid,
            glucose,
            total_protein,
            albumin,
            potassium,
            calcium,
            phosphorus,
            ferritin,
            ptg
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            creatinine,
            urea,
            uric_acid,
            glucose,
            total_protein,
            albumin,
            potassium,
            calcium,
            phosphorus,
            ferritin,
            ptg,
        ),
    )


def insert_calculated_metric(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    creatinine: Any,
    age: Any,
    gender: bool,
    weight_at_appointment: Any,
    egfr_ckdepi: Any,
    crcl_cockcroft_gault: Any,
    ckd_stage: Any,
) -> None:
    """Сохраняет одну строку расчётных показателей по креатинину."""
    cur.execute(
        """
        INSERT INTO calculated_metrics (
            appointment_id,
            investigation_date,
            creatinine,
            age,
            gender,
            weight_at_appointment,
            egfr_ckdepi,
            crcl_cockcroft_gault,
            ckd_stage
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            creatinine,
            age,
            gender,
            weight_at_appointment,
            egfr_ckdepi,
            crcl_cockcroft_gault,
            ckd_stage,
        ),
    )


def insert_urinalysis_result(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    specific_gravity: Any,
    protein: Any,
    leukocytes: Any,
    erythrocytes: Any,
    bacteria: Any,
) -> None:
    """Сохраняет одну строку общего анализа мочи."""
    cur.execute(
        """
        INSERT INTO urinalysis_results (
            appointment_id,
            investigation_date,
            specific_gravity,
            protein,
            leukocytes,
            erythrocytes,
            bacteria
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            specific_gravity,
            protein,
            leukocytes,
            erythrocytes,
            bacteria,
        ),
    )


def insert_albuminuria_result(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    urine_albumin: Any,
    urine_albumin_unit: str,
    urine_creatinine: Any,
    urine_creatinine_unit: str,
    daily_albumin_excretion: Any,
    albumin_creatinine_ratio: Any,
    albuminuria_category: Any,
) -> None:
    """Сохраняет строку альбуминурии, суточную экскрецию и итоговую категорию."""
    cur.execute(
        """
        INSERT INTO albuminuria_results (
            appointment_id,
            investigation_date,
            urine_albumin,
            urine_albumin_unit,
            urine_creatinine,
            urine_creatinine_unit,
            daily_albumin_excretion,
            albumin_creatinine_ratio,
            albuminuria_category
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            urine_albumin,
            urine_albumin_unit,
            urine_creatinine,
            urine_creatinine_unit,
            daily_albumin_excretion,
            albumin_creatinine_ratio,
            albuminuria_category,
        ),
    )


def insert_ultrasound_result(
    cur: Any,
    appointment_id: int,
    investigation_date: Any,
    left_kidney_size: Any,
    right_kidney_size: Any,
    left_parenchyma: Any,
    right_parenchyma: Any,
    description: Any,
) -> None:
    """Сохраняет одну строку УЗИ почек."""
    cur.execute(
        """
        INSERT INTO ultrasound_results (
            appointment_id,
            investigation_date,
            left_kidney_size,
            right_kidney_size,
            left_parenchyma,
            right_parenchyma,
            description
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            investigation_date,
            left_kidney_size,
            right_kidney_size,
            left_parenchyma,
            right_parenchyma,
            description,
        ),
    )
