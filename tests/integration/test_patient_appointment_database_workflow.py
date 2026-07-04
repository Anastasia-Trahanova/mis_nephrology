"""
ОПЦИОНАЛЬНЫЙ интеграционный тест реальной БД.

Что тестируется:
- создание нового пациента через create_patient_with_first_appointment;
- создание appointments;
- сохранение surveys, examinations, cbc_results, biochemistry_results;
- сохранение calculated_metrics по креатинину;
- сохранение urinalysis_results, albuminuria_results, ultrasound_results;
- сохранение diagnoses, appointment_diets, prescriptions;
- возможность прочитать созданные данные обратно SQL-запросами.

Зачем:
unit-тесты проверяют код без БД, но не гарантируют, что реальные таблицы и SQL
совпадают. Этот тест проверяет полный backend-сценарий на dev/test базе.

Как запускать:
    set RUN_DB_LAYER_TESTS=1
    pytest tests/integration/test_patient_appointment_database_workflow.py

Важно:
- тест создаёт пациента с фамилией вида AUTO_TEST_...;
- в конце пытается удалить созданные записи;
- запускать только на dev/test базе, не на продуктивной базе.
"""

from __future__ import annotations

import os
import uuid
from collections import defaultdict
from datetime import date
from typing import Any

import pytest


pytestmark = pytest.mark.db_layer


class FakeForm:
    """Минимальная FormData-замена для вызова сервисов без HTTP-запроса."""

    def __init__(self, data: dict[str, Any]):
        self._data: dict[str, list[Any]] = defaultdict(list)
        for key, value in data.items():
            if isinstance(value, list):
                self._data[key].extend(value)
            else:
                self._data[key].append(value)

    def get(self, key: str, default: Any = None) -> Any:
        values = self._data.get(key)
        return values[0] if values else default

    def getlist(self, key: str) -> list[Any]:
        return list(self._data.get(key, []))


def _skip_if_db_tests_disabled():
    if os.getenv("RUN_DB_LAYER_TESTS") != "1":
        pytest.skip("DB integration test is disabled. Set RUN_DB_LAYER_TESTS=1 to run it.")


def _fetch_one_id(cur, sql: str) -> int:
    cur.execute(sql)
    row = cur.fetchone()
    if not row:
        raise AssertionError(f"Не найдены обязательные справочные данные для теста: {sql}")
    return row["id"]


def _count(cur, table: str, appointment_id: int) -> int:
    cur.execute(f"SELECT COUNT(*) AS count FROM {table} WHERE appointment_id = %s", (appointment_id,))
    return cur.fetchone()["count"]


def _cleanup_patient(cur, patient_id: int) -> None:
    """
    Удаляет пациента и связанные записи после теста.

    Таблицы перечислены явно, чтобы не зависеть от ON DELETE CASCADE.
    Если в твоей БД уже настроен CASCADE, эти DELETE всё равно безопасны.
    """
    cur.execute("SELECT id FROM appointments WHERE patient_id = %s", (patient_id,))
    appointment_ids = [row["id"] for row in cur.fetchall()]

    if appointment_ids:
        for table in [
            "appointment_icd10_diagnoses",
            "ckd_prognosis",
            "prescriptions",
            "appointment_diets",
            "diagnoses",
            "ultrasound_results",
            "albuminuria_results",
            "urinalysis_results",
            "calculated_metrics",
            "biochemistry_results",
            "cbc_results",
            "examinations",
            "surveys",
        ]:
            # Некоторые таблицы могут называться иначе или ещё не существовать
            # в локальной dev-БД. Поэтому сначала проверяем наличие таблицы.
            cur.execute("SELECT to_regclass(%s) AS table_name", (table,))
            if cur.fetchone()["table_name"]:
                cur.execute(f"DELETE FROM {table} WHERE appointment_id = ANY(%s)", (appointment_ids,))

    cur.execute("DELETE FROM appointments WHERE patient_id = %s", (patient_id,))
    cur.execute("DELETE FROM patients WHERE id = %s", (patient_id,))


def test_create_patient_first_appointment_and_read_saved_data_from_db():
    _skip_if_db_tests_disabled()

    from app.database import get_db_connection
    from app.services.patient_appointment_service import create_patient_with_first_appointment

    marker = f"AUTO_TEST_{uuid.uuid4().hex[:8]}"
    patient_id = None

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            doctor_id = _fetch_one_id(cur, "SELECT id FROM doctors ORDER BY id LIMIT 1")
            location_id = _fetch_one_id(cur, "SELECT id FROM locations ORDER BY id LIMIT 1")

    form = FakeForm(
        {
            "last_name": marker,
            "first_name": "Пациент",
            "patronymic": "Интеграционный",
            "birth_date": "1980-01-15",
            "gender": "true",
            "doctor_id": str(doctor_id),
            "location_id": str(location_id),
            "appointment_date": "2026-07-04",
            "appointment_time": "10:30",
            "life_anamnesis": "Анамнез жизни интеграционного теста",
            "disease_anamnesis": "Анамнез заболевания интеграционного теста",
            "complaints": "Жалобы интеграционного теста",
            "heredity": "true",
            "heredity_description": "Наследственность тест",
            "comorbidities": "АГ",
            "skin_color": ["обычная"],
            "skin_moisture": ["нормальная"],
            "skin_rash": "нет",
            "edema_peripheral": ["голени"],
            "edema_serositis": ["нет"],
            "systolic_pressure": "130",
            "diastolic_pressure": "80",
            "heart_rate": "72",
            "height": "170",
            "weight": "70",
            "cbc_investigation_date": ["2026-07-03"],
            "hemoglobin": ["130"],
            "erythrocytes": ["4.5"],
            "leukocytes": ["6.1"],
            "platelets": ["250"],
            "esr": ["10"],
            "mcv": ["88"],
            "hematocrit": ["39"],
            "biochemistry_investigation_date": ["2026-07-03"],
            "creatinine": ["100"],
            "urea": ["6.2"],
            "uric_acid": ["320"],
            "glucose": ["5.1"],
            "total_protein": ["70"],
            "albumin": ["42"],
            "potassium": ["4.3"],
            "calcium": ["2.3"],
            "phosphorus": ["1.1"],
            "ferritin": ["90"],
            "ptg": ["45"],
            "urinalysis_investigation_date": ["2026-07-03"],
            "specific_gravity": ["1015"],
            "urine_protein": ["0.1"],
            "urine_leukocytes": ["2"],
            "urine_erythrocytes": ["1"],
            "bacteria": ["0"],
            "albuminuria_investigation_date": ["2026-07-03"],
            "urine_albumin": ["30"],
            "urine_albumin_unit": ["mg_l"],
            "urine_creatinine": ["10"],
            "urine_creatinine_unit": ["mmol_l"],
            "ultrasound_investigation_date": ["2026-07-03"],
            "left_kidney_size": ["110x55"],
            "right_kidney_size": ["108x54"],
            "left_parenchyma": ["16"],
            "right_parenchyma": ["15"],
            "ultrasound_desc": ["Интеграционный тест УЗИ"],
            "main_diagnosis": "Хроническая болезнь почек",
            "complications": "Нет",
            "comorbidities_diag": "АГ",
            "icd10_main_diagnosis": "",
            "icd10_main_note": "",
            "icd10_complication_diagnosis": [""],
            "icd10_complication_note": [""],
            "icd10_comorbidity_diagnosis": [""],
            "icd10_comorbidity_note": [""],
            "diet": "Ограничение соли",
            "next_control_date": "2026-10-04",
            "recommendations": "Контроль креатинина и ACR",
            "medication": ["Лозартан"],
            "dosage": ["50 мг"],
            "schedule": ["1 раз в день"],
        }
    )

    try:
        result = create_patient_with_first_appointment(form)
        patient_id = result.patient_id
        appointment_id = result.appointment_id

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT last_name FROM patients WHERE id = %s", (patient_id,))
                assert cur.fetchone()["last_name"] == marker

                assert _count(cur, "surveys", appointment_id) == 1
                assert _count(cur, "examinations", appointment_id) == 1
                assert _count(cur, "cbc_results", appointment_id) == 1
                assert _count(cur, "biochemistry_results", appointment_id) == 1
                assert _count(cur, "calculated_metrics", appointment_id) >= 1
                assert _count(cur, "urinalysis_results", appointment_id) == 1
                assert _count(cur, "albuminuria_results", appointment_id) == 1
                assert _count(cur, "ultrasound_results", appointment_id) == 1
                assert _count(cur, "diagnoses", appointment_id) == 1
                assert _count(cur, "appointment_diets", appointment_id) == 1
                assert _count(cur, "prescriptions", appointment_id) == 1

                cur.execute("SELECT bmi FROM examinations WHERE appointment_id = %s", (appointment_id,))
                assert round(float(cur.fetchone()["bmi"]), 2) == 24.22

                cur.execute(
                    """
                    SELECT albumin_creatinine_ratio, albuminuria_category
                    FROM albuminuria_results
                    WHERE appointment_id = %s
                    """,
                    (appointment_id,),
                )
                albuminuria = cur.fetchone()
                assert albuminuria["albumin_creatinine_ratio"] is not None
                assert albuminuria["albuminuria_category"] in {"A1", "A2", "A3"}

    finally:
        if patient_id:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    _cleanup_patient(cur, patient_id)
                    conn.commit()
