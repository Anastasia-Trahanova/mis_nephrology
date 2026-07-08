"""seed demo ICD-10 diagnoses and recommendations for Word review

Revision ID: 0005_demo_icd10_seed
Revises: 0004_drop_text_diagnoses
Create Date: 2026-07-08

Назначение миграции
-------------------
Заполняет локальную dev/test базу структурированными диагнозами по МКБ-10
и нормальными русскими рекомендациями, чтобы можно было проверить карточку
пациента и Word-заключение на другом компьютере через alembic upgrade head.

Что делает:
- добавляет недостающие диагнозы в справочник icd10_diagnoses;
- основным диагнозом ставит N18.x по категории СКФ/ХБП из calculated_metrics;
- добавляет разные осложнения и сопутствующие диагнозы;
- перезаполняет appointment_diets.recommendations корректным Unicode-текстом;
- не использует внешние .sql-файлы, чтобы не было проблем с кодировкой psql
  на Windows.

Важно:
- это dev/test seed-миграция для демонстрационной базы;
- она не предназначена для production-данных;
- downgrade удаляет добавленные тестовые связи диагнозов и очищает рекомендации,
  если они равны одному из seed-текстов.
"""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from alembic import op

revision = "0005_demo_icd10_seed"
down_revision = "0004_drop_text_diagnoses"
branch_labels = None
depends_on = None

CKD_MAIN_BY_STAGE = {
    "С1": "N18.1",
    "C1": "N18.1",
    "G1": "N18.1",
    "С2": "N18.2",
    "C2": "N18.2",
    "G2": "N18.2",
    "С3а": "N18.3",
    "С3А": "N18.3",
    "C3a": "N18.3",
    "G3a": "N18.3",
    "С3б": "N18.3",
    "С3Б": "N18.3",
    "C3b": "N18.3",
    "G3b": "N18.3",
    "С4": "N18.4",
    "C4": "N18.4",
    "G4": "N18.4",
    "С5": "N18.5",
    "C5": "N18.5",
    "G5": "N18.5",
}

DIAGNOSES = {
    "N18.1": "Хроническая болезнь почек, стадия 1",
    "N18.2": "Хроническая болезнь почек, стадия 2",
    "N18.3": "Хроническая болезнь почек, стадия 3",
    "N18.4": "Хроническая болезнь почек, стадия 4",
    "N18.5": "Хроническая болезнь почек, стадия 5",
    "D63.8": "Анемия при других хронических болезнях, классифицированных в других рубриках",
    "I12.9": "Гипертензивная болезнь с поражением почек без почечной недостаточности",
    "E11.2": "Инсулиннезависимый сахарный диабет с поражением почек",
    "N25.0": "Почечная остеодистрофия",
    "E78.5": "Гиперлипидемия неуточненная",
    "N39.0": "Инфекция мочевыводящих путей без установленной локализации",
    "R80": "Изолированная протеинурия",
    "E79.0": "Гиперурикемия без признаков воспалительного артрита и подагрических узлов",
    "M10.3": "Подагра, обусловленная нарушением почечной функции",
    "I15.1": "Гипертензия вторичная по отношению к другим поражениям почек",
}

FALLBACK_STAGES = ["С1", "С2", "С3а", "С3б", "С4", "С5"]

COMPLICATION_PATTERNS = [
    ["D63.8"],
    ["I15.1"],
    ["D63.8", "N25.0"],
    ["R80", "E79.0"],
    ["D63.8", "N25.0", "R80"],
]

COMORBIDITY_PATTERNS = [
    ["I12.9"],
    ["M10.3"],
    ["E11.2", "E78.5"],
    ["I12.9", "N39.0"],
    ["I12.9", "E11.2", "E78.5"],
]

RECOMMENDATIONS_BY_GROUP = {
    "early": (
        "Контроль артериального давления ежедневно с ведением дневника. "
        "Контроль креатинина, мочевины, калия, общего анализа крови, общего анализа мочи "
        "и альбумин/креатинин мочи к следующему визиту. Соблюдать питьевой режим, "
        "избегать самостоятельного приема НПВП."
    ),
    "moderate": (
        "Контроль артериального давления ежедневно. Контроль креатинина, мочевины, калия, "
        "общего анализа крови, общего анализа мочи и альбумин/креатинин мочи к следующему визиту. "
        "Ограничить соль до 5 г/сут, избегать нефротоксичных препаратов."
    ),
    "advanced": (
        "Наблюдение нефролога в динамике. Контроль креатинина, мочевины, калия, кальция, фосфора, "
        "ПТГ, общего анализа крови, общего анализа мочи и альбумин/креатинин мочи к следующему визиту. "
        "Контроль артериального давления с дневником самоконтроля."
    ),
    "severe": (
        "Регулярное наблюдение нефролога. Контроль креатинина, мочевины, калия, натрия, кальция, "
        "фосфора, ПТГ, общего анализа крови и общего анализа мочи к следующему визиту. "
        "При ухудшении самочувствия, отеках или повышении артериального давления обратиться внепланово."
    ),
}

ALL_SEED_RECOMMENDATIONS = tuple(RECOMMENDATIONS_BY_GROUP.values())


def _table_columns(connection: Any, table_name: str) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        sa.text(
            """
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = :table_name
            """
        ),
        {"table_name": table_name},
    ).mappings()
    return {
        row["column_name"]: {
            "nullable": row["is_nullable"] == "YES",
            "default": row["column_default"],
        }
        for row in rows
    }


def _lookup_icd10_id(connection: Any, columns: dict[str, dict[str, Any]], code: str, name: str) -> int | None:
    full = f"{code} — {name}"

    if "code" in columns:
        row = connection.execute(
            sa.text("SELECT id FROM icd10_diagnoses WHERE code = :code ORDER BY id LIMIT 1"),
            {"code": code},
        ).first()
        if row:
            return int(row[0])

    if "diagnosis" in columns:
        row = connection.execute(
            sa.text("SELECT id FROM icd10_diagnoses WHERE diagnosis = :diagnosis ORDER BY id LIMIT 1"),
            {"diagnosis": full},
        ).first()
        if row:
            return int(row[0])

    if "name" in columns:
        row = connection.execute(
            sa.text("SELECT id FROM icd10_diagnoses WHERE name = :name ORDER BY id LIMIT 1"),
            {"name": name},
        ).first()
        if row:
            return int(row[0])

    return None


def _ensure_icd10_diagnosis(connection: Any, code: str, name: str) -> int:
    columns = _table_columns(connection, "icd10_diagnoses")
    existing_id = _lookup_icd10_id(connection, columns, code, name)
    if existing_id:
        return existing_id

    full = f"{code} — {name}"
    values: dict[str, Any] = {}

    if "code" in columns:
        values["code"] = code
    if "name" in columns:
        values["name"] = name
    if "diagnosis" in columns:
        values["diagnosis"] = full
    if "is_active" in columns:
        values["is_active"] = True

    for column_name, meta in columns.items():
        if column_name == "id" or column_name in values:
            continue
        if meta["nullable"] or meta["default"] is not None:
            continue
        if column_name in {"title", "description", "full_name"}:
            values[column_name] = name
        elif column_name in {"category", "section"}:
            values[column_name] = "demo"

    if not values:
        raise RuntimeError("Не удалось определить колонки для вставки в icd10_diagnoses")

    column_sql = ", ".join(values.keys())
    params_sql = ", ".join(f":{key}" for key in values.keys())
    row = connection.execute(
        sa.text(
            f"""
            INSERT INTO icd10_diagnoses ({column_sql})
            VALUES ({params_sql})
            RETURNING id
            """
        ),
        values,
    ).first()
    return int(row[0])


def _has_any_diagnosis_of_type(connection: Any, appointment_id: int, diagnosis_type: str) -> bool:
    row = connection.execute(
        sa.text(
            """
            SELECT 1
            FROM appointment_icd10_diagnoses
            WHERE appointment_id = :appointment_id
              AND diagnosis_type = :diagnosis_type
            LIMIT 1
            """
        ),
        {"appointment_id": appointment_id, "diagnosis_type": diagnosis_type},
    ).first()
    return row is not None


def _insert_appointment_diagnosis(
    connection: Any,
    appointment_id: int,
    diagnosis_type: str,
    icd10_diagnosis_id: int,
    sort_order: int,
) -> None:
    columns = _table_columns(connection, "appointment_icd10_diagnoses")
    values: dict[str, Any] = {
        "appointment_id": appointment_id,
        "diagnosis_type": diagnosis_type,
        "icd10_diagnosis_id": icd10_diagnosis_id,
    }
    if "sort_order" in columns:
        values["sort_order"] = sort_order
    if "doctor_note" in columns:
        values["doctor_note"] = None

    exists = connection.execute(
        sa.text(
            """
            SELECT 1
            FROM appointment_icd10_diagnoses
            WHERE appointment_id = :appointment_id
              AND diagnosis_type = :diagnosis_type
              AND icd10_diagnosis_id = :icd10_diagnosis_id
            LIMIT 1
            """
        ),
        {
            "appointment_id": appointment_id,
            "diagnosis_type": diagnosis_type,
            "icd10_diagnosis_id": icd10_diagnosis_id,
        },
    ).first()
    if exists:
        return

    column_sql = ", ".join(values.keys())
    params_sql = ", ".join(f":{key}" for key in values.keys())
    connection.execute(
        sa.text(
            f"""
            INSERT INTO appointment_icd10_diagnoses ({column_sql})
            VALUES ({params_sql})
            """
        ),
        values,
    )


def _appointment_rows(connection: Any):
    return connection.execute(
        sa.text(
            """
            SELECT
                a.id AS appointment_id,
                COALESCE(
                    (
                        SELECT cm.ckd_stage
                        FROM calculated_metrics cm
                        WHERE cm.appointment_id = a.id
                          AND cm.ckd_stage IS NOT NULL
                        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) DESC,
                                 cm.id DESC
                        LIMIT 1
                    ),
                    (
                        SELECT cm2.ckd_stage
                        FROM calculated_metrics cm2
                        JOIN appointments a2 ON a2.id = cm2.appointment_id
                        WHERE a2.patient_id = a.patient_id
                          AND a2.appointment_date <= a.appointment_date
                          AND cm2.ckd_stage IS NOT NULL
                        ORDER BY a2.appointment_date DESC,
                                 COALESCE(cm2.investigation_date, a2.appointment_date::date) DESC,
                                 cm2.id DESC
                        LIMIT 1
                    )
                ) AS ckd_stage
            FROM appointments a
            ORDER BY a.id
            """
        )
    ).mappings().fetchall()


def _recommendation_group_for_stage(stage: str | None, fallback_index: int) -> str:
    stage = (stage or FALLBACK_STAGES[fallback_index % len(FALLBACK_STAGES)]).strip()
    if stage in {"С1", "C1", "G1", "С2", "C2", "G2"}:
        return "early"
    if stage in {"С3а", "С3А", "C3a", "G3a", "С3б", "С3Б", "C3b", "G3b"}:
        return "moderate"
    if stage in {"С4", "C4", "G4"}:
        return "advanced"
    if stage in {"С5", "C5", "G5"}:
        return "severe"
    return ["early", "moderate", "advanced", "severe"][fallback_index % 4]


def _refill_recommendations(connection: Any, appointment_id: int, recommendation: str) -> None:
    updated = connection.execute(
        sa.text(
            """
            UPDATE appointment_diets
            SET recommendations = :recommendation
            WHERE appointment_id = :appointment_id
            """
        ),
        {"appointment_id": appointment_id, "recommendation": recommendation},
    )
    if updated.rowcount:
        return

    connection.execute(
        sa.text(
            """
            INSERT INTO appointment_diets (appointment_id, diet, next_control_date, recommendations)
            VALUES (:appointment_id, :diet, NULL, :recommendation)
            """
        ),
        {
            "appointment_id": appointment_id,
            "diet": "Стол №7 с ограничением соли до 5 г/сут",
            "recommendation": recommendation,
        },
    )


def upgrade() -> None:
    connection = op.get_bind()

    diagnosis_ids = {
        code: _ensure_icd10_diagnosis(connection, code, name)
        for code, name in DIAGNOSES.items()
    }

    appointments = _appointment_rows(connection)

    for index, appointment in enumerate(appointments):
        appointment_id = int(appointment["appointment_id"])
        ckd_stage = appointment["ckd_stage"] or FALLBACK_STAGES[index % len(FALLBACK_STAGES)]
        main_code = CKD_MAIN_BY_STAGE.get(ckd_stage) or CKD_MAIN_BY_STAGE.get(str(ckd_stage).strip())
        if not main_code:
            main_code = CKD_MAIN_BY_STAGE[FALLBACK_STAGES[index % len(FALLBACK_STAGES)]]

        if not _has_any_diagnosis_of_type(connection, appointment_id, "main"):
            _insert_appointment_diagnosis(
                connection=connection,
                appointment_id=appointment_id,
                diagnosis_type="main",
                icd10_diagnosis_id=diagnosis_ids[main_code],
                sort_order=1,
            )

        if not _has_any_diagnosis_of_type(connection, appointment_id, "complication"):
            for sort_order, code in enumerate(COMPLICATION_PATTERNS[index % len(COMPLICATION_PATTERNS)], start=1):
                _insert_appointment_diagnosis(
                    connection=connection,
                    appointment_id=appointment_id,
                    diagnosis_type="complication",
                    icd10_diagnosis_id=diagnosis_ids[code],
                    sort_order=sort_order,
                )

        if not _has_any_diagnosis_of_type(connection, appointment_id, "comorbidity"):
            for sort_order, code in enumerate(COMORBIDITY_PATTERNS[index % len(COMORBIDITY_PATTERNS)], start=1):
                _insert_appointment_diagnosis(
                    connection=connection,
                    appointment_id=appointment_id,
                    diagnosis_type="comorbidity",
                    icd10_diagnosis_id=diagnosis_ids[code],
                    sort_order=sort_order,
                )

        group = _recommendation_group_for_stage(ckd_stage, index)
        _refill_recommendations(connection, appointment_id, RECOMMENDATIONS_BY_GROUP[group])


def downgrade() -> None:
    connection = op.get_bind()
    columns = _table_columns(connection, "icd10_diagnoses")
    diagnosis_ids = []

    for code, name in DIAGNOSES.items():
        diagnosis_id = _lookup_icd10_id(connection, columns, code, name)
        if diagnosis_id:
            diagnosis_ids.append(diagnosis_id)

    if diagnosis_ids:
        connection.execute(
            sa.text(
                """
                DELETE FROM appointment_icd10_diagnoses
                WHERE icd10_diagnosis_id = ANY(:diagnosis_ids)
                  AND (doctor_note IS NULL OR doctor_note = '')
                """
            ),
            {"diagnosis_ids": diagnosis_ids},
        )

    connection.execute(
        sa.text(
            """
            UPDATE appointment_diets
            SET recommendations = NULL
            WHERE recommendations = ANY(:seed_recommendations)
            """
        ),
        {"seed_recommendations": list(ALL_SEED_RECOMMENDATIONS)},
    )
