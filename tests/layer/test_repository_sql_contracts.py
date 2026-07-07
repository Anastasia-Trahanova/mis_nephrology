"""
Что тестируется:
- repository-функции вызывают cur.execute(...);
- INSERT/SELECT идут в ожидаемые таблицы;
- параметры передаются в правильном порядке;
- create_patient/create_appointment возвращают id из RETURNING id;
- старой таблицы свободных диагнозов diagnoses больше нет в repository-контракте.
"""

from __future__ import annotations

from datetime import date, datetime

from app.repositories.appointments import create_appointment
from app.repositories.diagnoses import (
    find_active_icd10_diagnosis_id,
    insert_appointment_icd10_diagnosis_row,
)
from app.repositories.examinations import insert_examination
from app.repositories.labs import (
    insert_albuminuria_result,
    insert_biochemistry_result,
    insert_calculated_metric,
    insert_cbc_result,
    insert_ultrasound_result,
    insert_urinalysis_result,
)
from app.repositories.patients import create_patient, get_patient_for_appointment
from app.repositories.prescriptions import insert_diet_and_recommendations, insert_prescription
from app.repositories.surveys import insert_survey

from .factories import FakeCursor


def _normalized_sql(sql: str) -> str:
    return " ".join(sql.split()).lower()


def test_create_patient_sql_contract():
    cur = FakeCursor({"id": 101})
    patient_id = create_patient(
        cur,
        {
            "last_name": "Тестова",
            "first_name": "Пациентка",
            "patronymic": "Автотестовна",
            "birth_date": date(1980, 1, 15),
            "gender": True,
        },
    )

    assert patient_id == 101
    assert "insert into patients" in _normalized_sql(cur.last_query)
    assert cur.last_params == (
        "Тестова",
        "Пациентка",
        "Автотестовна",
        date(1980, 1, 15),
        True,
    )


def test_create_appointment_sql_contract():
    cur = FakeCursor({"id": 202})
    appointment_id = create_appointment(cur, 101, 1, 2, datetime(2026, 7, 4, 10, 30))

    assert appointment_id == 202
    assert "insert into appointments" in _normalized_sql(cur.last_query)
    assert cur.last_params == (101, 1, 2, datetime(2026, 7, 4, 10, 30))


def test_get_patient_for_appointment_sql_contract():
    cur = FakeCursor({"id": 101, "birth_date": date(1980, 1, 15), "gender": True})
    row = get_patient_for_appointment(cur, 101)

    assert row["id"] == 101
    assert "from patients" in _normalized_sql(cur.last_query)
    assert cur.last_params == (101,)


def test_insert_survey_sql_contract():
    cur = FakeCursor()
    insert_survey(
        cur,
        202,
        {
            "life_anamnesis": "life",
            "disease_anamnesis": "disease",
            "complaints": "complaints",
            "heredity": True,
            "heredity_description": "desc",
            "comorbidities": "comorb",
        },
    )

    assert "insert into surveys" in _normalized_sql(cur.last_query)
    assert cur.last_params == (202, "life", "disease", "complaints", True, "desc", "comorb")


def test_insert_examination_sql_contract():
    cur = FakeCursor()
    insert_examination(
        cur,
        202,
        {
            "skin_condition": "skin",
            "edema_location": "edema",
            "systolic_pressure": "130",
            "diastolic_pressure": "80",
            "bp_note": "сидя",
            "heart_rate": "72",
            "height": "170",
            "weight": "70",
            "bmi": 24.22,
        },
    )

    assert "insert into examinations" in _normalized_sql(cur.last_query)
    assert cur.last_params[-3:] == ("170", "70", 24.22)


def test_insert_lab_sql_contracts():
    cur = FakeCursor()

    insert_cbc_result(cur, 202, date(2026, 7, 3), "130", "4.5", "6", "250", "10", "88", "39")
    assert "insert into cbc_results" in _normalized_sql(cur.last_query)

    insert_biochemistry_result(
        cur, 202, date(2026, 7, 3), "100", "6", "320", "5", "70", "42", "4.3", "2.3", "1.1", "90", "45"
    )
    assert "insert into biochemistry_results" in _normalized_sql(cur.last_query)

    insert_calculated_metric(cur, 202, date(2026, 7, 3), "100", 46, True, "70", 65.1, 80.2, "С2")
    assert "insert into calculated_metrics" in _normalized_sql(cur.last_query)

    insert_urinalysis_result(cur, 202, date(2026, 7, 3), "1015", "0.1", "2", "1", "0")
    assert "insert into urinalysis_results" in _normalized_sql(cur.last_query)

    insert_albuminuria_result(cur, 202, date(2026, 7, 3), "30", "mg_l", "10", "mmol_l", 3.0, "A1")
    assert "insert into albuminuria_results" in _normalized_sql(cur.last_query)

    insert_ultrasound_result(cur, 202, date(2026, 7, 3), "110x55", "108x54", "16", "15", "desc")
    assert "insert into ultrasound_results" in _normalized_sql(cur.last_query)


def test_insert_icd10_diagnoses_and_prescriptions_sql_contracts():
    cur = FakeCursor({"id": 501})

    diagnosis_id = find_active_icd10_diagnosis_id(cur, "N18 — ХБП")
    assert diagnosis_id == 501
    assert "from icd10_diagnoses" in _normalized_sql(cur.last_query)

    insert_appointment_icd10_diagnosis_row(cur, 202, "main", 501, "note", 1)
    assert "insert into appointment_icd10_diagnoses" in _normalized_sql(cur.last_query)
    assert "insert into diagnoses" not in _normalized_sql(cur.last_query)

    insert_diet_and_recommendations(
        cur,
        202,
        {"diet": "соль", "next_control_date": "2026-10-04", "recommendations": "контроль"},
    )
    assert "insert into appointment_diets" in _normalized_sql(cur.last_query)

    insert_prescription(cur, 202, "Лозартан", "50 мг", "1 раз")
    assert "insert into prescriptions" in _normalized_sql(cur.last_query)
