"""
Парсер HTML-формы приёма.

Этот модуль нужен, чтобы patients.py и appointments.py не знали имена всех
полей формы. Здесь собраны правила:
- какие поля относятся к опросу;
- какие поля относятся к осмотру;
- какие поля относятся к ОАК, биохимии, ОАМ, альбуминурии и УЗИ;
- какие поля относятся к диагнозам, диете, рекомендациям и лекарствам.

Здесь нет SQL. Модуль только читает форму и возвращает структурированный словарь.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from .appointment_diagnosis_service import parse_icd10_diagnoses_from_form
from .appointment_text_builder import build_edema_location, build_skin_condition
from .clinical_value_normalization import normalize_appointment_form_values
from .form_parsing import (
    empty_to_none,
    get_numeric_list,
    get_text_list,
    parse_bool,
)

try:
    from ..calculations import calculate_bmi
except ImportError:  # fallback на случай, если calculate_bmi ещё не переэкспортирован
    from ..medical_algorithms.bmi import calculate_bmi


def parse_required_appointment_fields(form: Any) -> dict[str, Any]:
    """
    Забирает обязательные поля приёма и формирует appointment_datetime.

    Используется и для первого приёма нового пациента, и для повторного приёма.
    """
    doctor_id = empty_to_none(form.get("doctor_id"))
    location_id = empty_to_none(form.get("location_id"))
    appointment_date = empty_to_none(form.get("appointment_date"))
    appointment_time = empty_to_none(form.get("appointment_time"))

    if not doctor_id or not location_id or not appointment_date or not appointment_time:
        raise HTTPException(
            status_code=400,
            detail="Не заполнены обязательные данные приёма",
        )

    try:
        appointment_datetime = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M",
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата или время приёма")

    return {
        "doctor_id": int(doctor_id),
        "location_id": int(location_id),
        "appointment_date": appointment_date,
        "appointment_time": appointment_time,
        "appointment_datetime": appointment_datetime,
    }


def parse_new_patient_form(form: Any) -> dict[str, Any]:
    """Забирает из формы обязательные данные нового пациента."""
    last_name = empty_to_none(form.get("last_name"))
    first_name = empty_to_none(form.get("first_name"))
    patronymic = empty_to_none(form.get("patronymic"))
    birth_date = empty_to_none(form.get("birth_date"))
    gender = parse_bool(form.get("gender", "true"))

    if not last_name or not first_name or not birth_date:
        raise HTTPException(
            status_code=400,
            detail="Не заполнены обязательные данные пациента",
        )

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
    }


def parse_appointment_form(form: Any, appointment_datetime: datetime) -> dict[str, Any]:
    """
    Разбирает все поля формы приёма в структурированный словарь.

    appointment_datetime нужен как дата по умолчанию для анализов, если врач не
    заполнил отдельную дату исследования.

    Перед разбором форма проходит нормализацию клинических числовых значений.
    Это важно для случаев вроде удельного веса мочи: врач может ввести 1015,
    а внутренняя модель хранит 1.015.
    """
    form = normalize_appointment_form_values(form)

    height = empty_to_none(form.get("height"))
    weight = empty_to_none(form.get("weight"))

    return {
        "survey": {
            "life_anamnesis": empty_to_none(form.get("life_anamnesis")),
            "disease_anamnesis": empty_to_none(form.get("disease_anamnesis")),
            "complaints": empty_to_none(form.get("complaints")),
            "heredity": form.get("heredity") == "true",
            "heredity_description": empty_to_none(form.get("heredity_description")),
            "comorbidities": empty_to_none(form.get("comorbidities")),
        },
        "examination": {
            "skin_condition": build_skin_condition(form),
            "edema_location": build_edema_location(form),
            "systolic_pressure": empty_to_none(form.get("systolic_pressure")),
            "diastolic_pressure": empty_to_none(form.get("diastolic_pressure")),
            "bp_note": empty_to_none(form.get("bp_note")),
            "heart_rate": empty_to_none(form.get("heart_rate")),
            "height": height,
            "weight": weight,
            # Значение из формы не используем как источник истины: сервер считает сам.
            "bmi": calculate_bmi(height, weight),
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
        },
        "ultrasound": {
            "dates": get_text_list(form, "ultrasound_investigation_date"),
            "left_kidney_size": get_text_list(form, "left_kidney_size"),
            "right_kidney_size": get_text_list(form, "right_kidney_size"),
            "left_parenchyma": get_numeric_list(form, "left_parenchyma"),
            "right_parenchyma": get_numeric_list(form, "right_parenchyma"),
            "ultrasound_desc": get_text_list(form, "ultrasound_desc"),
        },
        "diagnoses": {
            # Старые свободные текстовые поля пока оставляем для совместимости.
            "main_diagnosis": empty_to_none(form.get("main_diagnosis")),
            "complications": empty_to_none(form.get("complications")),
            "comorbidities": empty_to_none(form.get("comorbidities_diag")),
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
    }
