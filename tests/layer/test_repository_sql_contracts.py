"""
Назначение файла: тесты SQL-контрактов repository-слоя.

Что тестируется:
- repository-функции вызывают cur.execute(...);
- INSERT/SELECT идут в ожидаемые таблицы;
- параметры передаются в правильном порядке;
- create_patient/create_appointment возвращают id из RETURNING id;
- старой таблицы свободных диагнозов diagnoses больше нет в repository-контракте.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app.repositories.additional_studies import upsert_appointment_additional_studies
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
            "phone": "+7 900 000-00-00",
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
        "+7 900 000-00-00",
    )


def test_create_appointment_sql_contract():
    cur = FakeCursor({"id": 202})
    appointment_id = create_appointment(
        cur, 101, 1, 2, datetime(2026, 7, 4, 10, 30), 46
    )

    assert appointment_id == 202
    assert "insert into appointments" in _normalized_sql(cur.last_query)
    assert cur.last_params == (101, 1, 2, datetime(2026, 7, 4, 10, 30), 46)


def test_get_patient_for_appointment_sql_contract():
    cur = FakeCursor({"id": 101, "birth_date": date(1980, 1, 15), "gender": True})
    row = get_patient_for_appointment(cur, 101)

    assert row["id"] == 101
    assert "from patients" in _normalized_sql(cur.last_query)
    assert cur.last_params == (101,)


def test_appointments_queries_do_not_select_removed_heredity_flag():
    source = Path("app/repositories/appointments.py").read_text(encoding="utf-8")
    assert "s.heredity," not in source
    assert "s.heredity_description" in source


def test_insert_survey_sql_contract():
    cur = FakeCursor()
    survey = {
        "complaints": "complaints",
        "education_and_professional_history": "education",
        "housing_conditions": "housing",
        "past_diseases": "past",
        "habitual_intoxications": "intoxications",
        "gynecological_history": "gynecology",
        "heredity_description": "desc",
        "family_life": "family",
        "allergological_history": "allergy",
        "epidemiological_history": "epidemiology",
        "insurance_history": "insurance",
        "disease_onset": "onset",
        "disease_course": "course",
    }
    insert_survey(cur, 202, survey)

    normalized = _normalized_sql(cur.last_query)
    assert "insert into surveys" in normalized
    assert "life_anamnesis" not in normalized
    assert "disease_anamnesis" not in normalized
    assert "comorbidities" not in normalized
    assert " heredity," not in normalized
    assert cur.last_params == (
        202,
        "complaints",
        "education",
        "housing",
        "past",
        "intoxications",
        "gynecology",
        "desc",
        "family",
        "allergy",
        "epidemiology",
        "insurance",
        "onset",
        "course",
    )


def test_insert_examination_sql_contract():
    cur = FakeCursor()
    examination = {
        "general_condition": "moderate",
        "consciousness": "clear",
        "bed_position": "forced",
        "bed_position_details": "полусидя",
        "body_build": "правильное",
        "height": "170",
        "weight": "70",
        "bmi": 24.22,
        "constitution_type": "normosthenic",
        "skin_and_mucous_membranes": "кожа бледная",
        "edema_location": "edema",
        "lymph_nodes": "не увеличены",
        "thyroid_gland": "не увеличена",
        "musculoskeletal_system": "без особенностей",
        "body_temperature": "36.6",
        "systolic_pressure": "130",
        "diastolic_pressure": "80",
        "bp_note": "сидя",
        "heart_rate": "72",
        "veins_condition": "без особенностей",
        "lung_auscultation": "дыхание везикулярное",
        "abdomen": "мягкий",
        "kidney_palpation": "palpable",
        "kidney_palpation_details": "правая",
        "pasternatsky_result": "negative",
        "pasternatsky_side": "bilateral",
    }
    insert_examination(cur, 202, examination)

    normalized = _normalized_sql(cur.last_query)
    assert "insert into examinations" in normalized
    assert "skin_condition" not in normalized
    assert "skin_and_mucous_membranes" in normalized
    # Блок АД сохраняет прежний контракт, включая примечание.
    assert ("130", "80", "сидя", "72") == cur.last_params[16:20]
    assert cur.last_params[6:9] == ("170", "70", 24.22)


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

    insert_albuminuria_result(
        cur,
        202,
        date(2026, 7, 3),
        "30",
        "mg_l",
        "10",
        "mmol_l",
        "45",
        3.0,
        "A2",
    )
    assert "insert into albuminuria_results" in _normalized_sql(cur.last_query)
    assert "daily_albumin_excretion" in _normalized_sql(cur.last_query)
    assert cur.last_params[-3:] == ("45", 3.0, "A2")

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


def test_additional_studies_repository_contract():
    cur = FakeCursor()

    upsert_appointment_additional_studies(
        cur,
        202,
        {
            "other_laboratory_studies": "Иммунологические исследования",
            "other_instrumental_studies": "КТ почек",
        },
    )

    normalized = _normalized_sql(cur.last_query)
    assert "insert into appointment_additional_studies" in normalized
    assert "on conflict (appointment_id) do update" in normalized
    assert cur.last_params == (
        202,
        "Иммунологические исследования",
        "КТ почек",
    )


def test_appointments_repository_reads_additional_studies():
    source = Path("app/repositories/appointments.py").read_text(encoding="utf-8")
    normalized = _normalized_sql(source)

    assert "left join appointment_additional_studies" in normalized
    assert "ast.other_laboratory_studies" in normalized
    assert "ast.other_instrumental_studies" in normalized
