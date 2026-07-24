"""
Назначение файла: разбор HTML-формы первичного и повторного приёма.

Что выполняет файл
-------------------
Преобразует значения формы в структурированные словари для сервисов сохранения.

Верхняя часть формы соответствует структуре миграции 0010. Начиная с
лабораторных исследований парсер также читает поля миграции 0011. Существующие
таблицы ОАК, ОАМ, биохимии, расчёты KDIGO и лекарства не перестраиваются.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from .appointment_diagnosis_service import parse_icd10_diagnoses_from_form
from .appointment_text_builder import build_edema_location
from .clinical_value_normalization import normalize_appointment_form_values
from .form_parsing import empty_to_none, get_numeric_list, get_text_list, parse_bool

try:
    from ..calculations import calculate_bmi
except ImportError:  # fallback для старого расположения функции
    from ..medical_algorithms.bmi import calculate_bmi


def parse_required_appointment_fields(form: Any) -> dict[str, Any]:
    """Читает обязательные данные приёма и собирает appointment_datetime."""
    location_id = empty_to_none(form.get("location_id"))
    appointment_date = empty_to_none(form.get("appointment_date"))
    appointment_time = empty_to_none(form.get("appointment_time"))

    if not location_id or not appointment_date or not appointment_time:
        raise HTTPException(status_code=400, detail="Не заполнены обязательные данные приёма")

    try:
        appointment_datetime = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата или время приёма")

    return {
        "location_id": int(location_id),
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_datetime": appointment_datetime,
    }


def parse_new_patient_form(form: Any) -> dict[str, Any]:
    """Читает паспортные данные нового пациента, включая телефон."""
    last_name = empty_to_none(form.get("last_name"))
    first_name = empty_to_none(form.get("first_name"))
    patronymic = empty_to_none(form.get("patronymic"))
    birth_date = empty_to_none(form.get("birth_date"))
    gender = parse_bool(form.get("gender", "true"))
    phone = empty_to_none(form.get("phone"))

    if not last_name or not first_name or not birth_date:
        raise HTTPException(status_code=400, detail="Не заполнены обязательные данные пациента")

    try:
        birth_date_obj = datetime.strptime(birth_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата рождения")

    return {
        "last_name": last_name,
        "first_name": first_name,
        "patronymic": patronymic,
        "birth_date": birth_date_obj,
        "gender": gender,
        "phone": phone,
    }


def parse_appointment_form(form: Any, appointment_datetime: datetime) -> dict[str, Any]:
    """Разбирает форму в словари, передаваемые сервису сохранения."""
    form = normalize_appointment_form_values(form)
    height = empty_to_none(form.get("height"))
    weight = empty_to_none(form.get("weight"))

    bed_position = empty_to_none(form.get("bed_position"))
    bed_position_details = (
        empty_to_none(form.get("bed_position_details"))
        if bed_position == "forced"
        else None
    )

    kidney_palpation = empty_to_none(form.get("kidney_palpation"))
    kidney_palpation_details = (
        empty_to_none(form.get("kidney_palpation_details"))
        if kidney_palpation == "palpable"
        else None
    )

    return {
        "survey": {
            "complaints": empty_to_none(form.get("complaints")),
            "education_and_professional_history": empty_to_none(
                form.get("education_and_professional_history")
            ),
            "housing_conditions": empty_to_none(form.get("housing_conditions")),
            "past_diseases": empty_to_none(form.get("past_diseases")),
            "habitual_intoxications": empty_to_none(form.get("habitual_intoxications")),
            "gynecological_history": empty_to_none(form.get("gynecological_history")),
            "heredity_description": empty_to_none(form.get("heredity_description")),
            "family_life": empty_to_none(form.get("family_life")),
            "allergological_history": empty_to_none(form.get("allergological_history")),
            "epidemiological_history": empty_to_none(form.get("epidemiological_history")),
            "insurance_history": empty_to_none(form.get("insurance_history")),
            "disease_onset": empty_to_none(form.get("disease_onset")),
            "disease_course": empty_to_none(form.get("disease_course")),
        },
        "examination": {
            "general_condition": empty_to_none(form.get("general_condition")),
            "consciousness": empty_to_none(form.get("consciousness")),
            "bed_position": bed_position,
            "bed_position_details": bed_position_details,
            "body_build": empty_to_none(form.get("body_build")),
            "height": height,
            "weight": weight,
            "bmi": calculate_bmi(height, weight),
            "constitution_type": empty_to_none(form.get("constitution_type")),
            "skin_and_mucous_membranes": empty_to_none(
                form.get("skin_and_mucous_membranes")
            ),
            "edema_location": build_edema_location(form),
            "lymph_nodes": empty_to_none(form.get("lymph_nodes")),
            "thyroid_gland": empty_to_none(form.get("thyroid_gland")),
            "musculoskeletal_system": empty_to_none(form.get("musculoskeletal_system")),
            "body_temperature": empty_to_none(form.get("body_temperature")),
            "systolic_pressure": empty_to_none(form.get("systolic_pressure")),
            "diastolic_pressure": empty_to_none(form.get("diastolic_pressure")),
            "bp_note": empty_to_none(form.get("bp_note")),
            "heart_rate": empty_to_none(form.get("heart_rate")),
            "veins_condition": empty_to_none(form.get("veins_condition")),
            "lung_auscultation": empty_to_none(form.get("lung_auscultation")),
            "abdomen": empty_to_none(form.get("abdomen")),
            "kidney_palpation": kidney_palpation,
            "kidney_palpation_details": kidney_palpation_details,
            "pasternatsky_result": empty_to_none(form.get("pasternatsky_result")),
            "pasternatsky_side": empty_to_none(form.get("pasternatsky_side")),
        },
        "cbc": {
            "dates": get_text_list(form, "cbc_investigation_date"),
            "hemoglobin": get_numeric_list(form, "hemoglobin"),
            "erythrocytes": get_numeric_list(form, "erythrocytes"),
            "leukocytes": get_numeric_list(form, "leukocytes"),
            "platelets": get_numeric_list(form, "platelets"),
            "esr": get_numeric_list(form, "esr"),
            "mcv": get_numeric_list(form, "mcv"),
            "hematocrit": get_numeric_list(form, "hematocrit"),
        },
        "biochemistry": {
            "dates": get_text_list(form, "biochemistry_investigation_date"),
            "creatinine": get_numeric_list(form, "creatinine"),
            "urea": get_numeric_list(form, "urea"),
            "uric_acid": get_numeric_list(form, "uric_acid"),
            "glucose": get_numeric_list(form, "glucose"),
            "total_protein": get_numeric_list(form, "total_protein"),
            "albumin": get_numeric_list(form, "albumin"),
            "potassium": get_numeric_list(form, "potassium"),
            "calcium": get_numeric_list(form, "calcium"),
            "phosphorus": get_numeric_list(form, "phosphorus"),
            "ferritin": get_numeric_list(form, "ferritin"),
            "ptg": get_numeric_list(form, "ptg"),
        },
        "urinalysis": {
            "dates": get_text_list(form, "urinalysis_investigation_date"),
            "specific_gravity": get_numeric_list(form, "specific_gravity"),
            "urine_protein": get_numeric_list(form, "urine_protein"),
            "urine_leukocytes": get_numeric_list(form, "urine_leukocytes"),
            "urine_erythrocytes": get_numeric_list(form, "urine_erythrocytes"),
            "bacteria": get_numeric_list(form, "bacteria"),
        },
        "albuminuria": {
            "dates": get_text_list(form, "albuminuria_investigation_date"),
            "urine_albumin": get_numeric_list(form, "urine_albumin"),
            "urine_albumin_unit": get_text_list(form, "urine_albumin_unit"),
            "urine_creatinine": get_numeric_list(form, "urine_creatinine"),
            "urine_creatinine_unit": get_text_list(form, "urine_creatinine_unit"),
            "daily_albumin_excretion": get_numeric_list(
                form,
                "daily_albumin_excretion",
            ),
        },
        "ultrasound": {
            "dates": get_text_list(form, "ultrasound_investigation_date"),
            "left_kidney_size": get_text_list(form, "left_kidney_size"),
            "right_kidney_size": get_text_list(form, "right_kidney_size"),
            "left_parenchyma": get_numeric_list(form, "left_parenchyma"),
            "right_parenchyma": get_numeric_list(form, "right_parenchyma"),
            "ultrasound_desc": get_text_list(form, "ultrasound_desc"),
        },
        "additional_studies": {
            "other_laboratory_studies": empty_to_none(
                form.get("other_laboratory_studies")
            ),
            "other_instrumental_studies": empty_to_none(
                form.get("other_instrumental_studies")
            ),
        },
        "icd10": parse_icd10_diagnoses_from_form(form),
        "diet": {
            "diet": empty_to_none(form.get("diet")),
            "next_control_date": empty_to_none(form.get("next_control_date")),
            "recommendations": empty_to_none(form.get("recommendations")),
        },
        "prescriptions": {
            "medications": form.getlist("medication"),
            "dosages": form.getlist("dosage"),
            "schedules": form.getlist("schedule"),
        },
        "appointment_date_default": appointment_datetime.date(),
        "kdigo_excluded_pairs": form.getlist("kdigo_excluded_pair"),
    }
