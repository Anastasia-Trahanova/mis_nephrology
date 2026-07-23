"""Repository для данных объективного исследования пациента."""

from __future__ import annotations

from typing import Any


def insert_examination(
    cur: Any,
    appointment_id: int,
    examination_data: dict[str, Any],
) -> None:
    """Сохраняет объективный осмотр в структуру миграции 0009."""
    cur.execute(
        """
        INSERT INTO examinations (
            appointment_id,
            general_condition,
            consciousness,
            bed_position,
            bed_position_details,
            body_build,
            height,
            weight,
            bmi,
            constitution_type,
            skin_and_mucous_membranes,
            edema_location,
            lymph_nodes,
            thyroid_gland,
            musculoskeletal_system,
            body_temperature,
            systolic_pressure,
            diastolic_pressure,
            bp_note,
            heart_rate,
            veins_condition,
            lung_auscultation,
            abdomen,
            kidney_palpation,
            kidney_palpation_details,
            pasternatsky_result,
            pasternatsky_side
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s
        )
        """,
        (
            appointment_id,
            examination_data.get("general_condition"),
            examination_data.get("consciousness"),
            examination_data.get("bed_position"),
            examination_data.get("bed_position_details"),
            examination_data.get("body_build"),
            examination_data.get("height"),
            examination_data.get("weight"),
            examination_data.get("bmi"),
            examination_data.get("constitution_type"),
            examination_data.get("skin_and_mucous_membranes"),
            examination_data.get("edema_location"),
            examination_data.get("lymph_nodes"),
            examination_data.get("thyroid_gland"),
            examination_data.get("musculoskeletal_system"),
            examination_data.get("body_temperature"),
            examination_data.get("systolic_pressure"),
            examination_data.get("diastolic_pressure"),
            examination_data.get("bp_note"),
            examination_data.get("heart_rate"),
            examination_data.get("veins_condition"),
            examination_data.get("lung_auscultation"),
            examination_data.get("abdomen"),
            examination_data.get("kidney_palpation"),
            examination_data.get("kidney_palpation_details"),
            examination_data.get("pasternatsky_result"),
            examination_data.get("pasternatsky_side"),
        ),
    )
