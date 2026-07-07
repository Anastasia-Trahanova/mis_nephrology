"""
Назначение файла: сохранение деталей приёма в БД.

Что редактировать:
- порядок сохранения разделов приёма;
- правила пропуска пустых строк анализов;
- вызовы repository-функций при добавлении новых клинических блоков.

Что не редактировать здесь:
- SQL-запросы;
- HTML-форму;
- медицинские формулы расчёта СКФ, ACR и KDIGO.
"""

from __future__ import annotations

from typing import Any

from ..calculations import (
    calculate_age,
    calculate_albuminuria_metrics,
    calculate_all_metrics,
)
from app.repositories.ckd_prognosis import save_ckd_prognosis_for_appointment
from ..repositories.examinations import insert_examination
from ..repositories.labs import (
    insert_albuminuria_result,
    insert_biochemistry_result,
    insert_calculated_metric,
    insert_cbc_result,
    insert_ultrasound_result,
    insert_urinalysis_result,
)
from ..repositories.prescriptions import (
    insert_diet_and_recommendations,
    insert_prescription,
)
from ..repositories.surveys import insert_survey
from .appointment_diagnosis_service import save_appointment_icd10_diagnoses
from .form_parsing import (
    date_at,
    empty_to_none,
    has_any_indexed_value,
    max_list_length,
    parse_date_or_default,
    value_at,
)


def save_survey(cur: Any, appointment_id: int, survey_data: dict[str, Any]) -> None:
    """Сохраняет раздел «Опрос» в таблицу surveys."""
    insert_survey(cur, appointment_id, survey_data)


def save_examination(cur: Any, appointment_id: int, examination_data: dict[str, Any]) -> None:
    """Сохраняет раздел «Осмотр» в таблицу examinations."""
    insert_examination(cur, appointment_id, examination_data)


def save_cbc_results(
    cur: Any,
    appointment_id: int,
    appointment_date_default: Any,
    cbc_data: dict[str, list[Any]],
) -> None:
    """Сохраняет все заполненные столбцы общего анализа крови."""
    value_lists = [
        cbc_data.get("hemoglobin", []),
        cbc_data.get("erythrocytes", []),
        cbc_data.get("leukocytes", []),
        cbc_data.get("platelets", []),
        cbc_data.get("esr", []),
        cbc_data.get("mcv", []),
        cbc_data.get("hematocrit", []),
    ]
    max_count = max_list_length(cbc_data.get("dates", []), *value_lists)

    for index in range(max_count):
        if not has_any_indexed_value(value_lists, index):
            continue

        insert_cbc_result(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=date_at(cbc_data.get("dates"), index, appointment_date_default),
            hemoglobin=value_at(cbc_data.get("hemoglobin"), index),
            erythrocytes=value_at(cbc_data.get("erythrocytes"), index),
            leukocytes=value_at(cbc_data.get("leukocytes"), index),
            platelets=value_at(cbc_data.get("platelets"), index),
            esr=value_at(cbc_data.get("esr"), index),
            mcv=value_at(cbc_data.get("mcv"), index),
            hematocrit=value_at(cbc_data.get("hematocrit"), index),
        )


def save_biochemistry_results(
    cur: Any,
    appointment_id: int,
    appointment_date_default: Any,
    biochemistry_data: dict[str, list[Any]],
) -> list[dict[str, Any]]:
    """
    Сохраняет все заполненные столбцы биохимии.

    Возвращает список биохимических исследований с креатинином, по которым затем
    нужно посчитать eGFR / Cockcroft-Gault / стадию ХБП.
    """
    value_lists = [
        biochemistry_data.get("creatinine", []),
        biochemistry_data.get("urea", []),
        biochemistry_data.get("uric_acid", []),
        biochemistry_data.get("glucose", []),
        biochemistry_data.get("total_protein", []),
        biochemistry_data.get("albumin", []),
        biochemistry_data.get("potassium", []),
        biochemistry_data.get("calcium", []),
        biochemistry_data.get("phosphorus", []),
        biochemistry_data.get("ferritin", []),
        biochemistry_data.get("ptg", []),
    ]
    max_count = max_list_length(biochemistry_data.get("dates", []), *value_lists)
    metric_sources: list[dict[str, Any]] = []

    for index in range(max_count):
        if not has_any_indexed_value(value_lists, index):
            continue

        current_biochemistry_date = date_at(
            biochemistry_data.get("dates"),
            index,
            appointment_date_default,
        )
        current_creatinine = value_at(biochemistry_data.get("creatinine"), index)

        insert_biochemistry_result(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=current_biochemistry_date,
            creatinine=current_creatinine,
            urea=value_at(biochemistry_data.get("urea"), index),
            uric_acid=value_at(biochemistry_data.get("uric_acid"), index),
            glucose=value_at(biochemistry_data.get("glucose"), index),
            total_protein=value_at(biochemistry_data.get("total_protein"), index),
            albumin=value_at(biochemistry_data.get("albumin"), index),
            potassium=value_at(biochemistry_data.get("potassium"), index),
            calcium=value_at(biochemistry_data.get("calcium"), index),
            phosphorus=value_at(biochemistry_data.get("phosphorus"), index),
            ferritin=value_at(biochemistry_data.get("ferritin"), index),
            ptg=value_at(biochemistry_data.get("ptg"), index),
        )

        if current_creatinine:
            metric_sources.append(
                {
                    "creatinine": current_creatinine,
                    "investigation_date": current_biochemistry_date,
                }
            )

    return metric_sources


def save_calculated_metrics(
    cur: Any,
    appointment_id: int,
    birth_date: Any,
    gender: bool,
    weight: Any,
    metric_sources: list[dict[str, Any]],
    appointment_date_default: Any,
) -> None:
    """Сохраняет расчётные показатели по всем новым креатининам."""
    for metric_source in metric_sources:
        metric_date = parse_date_or_default(
            metric_source.get("investigation_date"),
            appointment_date_default,
        )
        current_creatinine = metric_source.get("creatinine")
        metrics = calculate_all_metrics(
            creatinine_umol_l=current_creatinine,
            birth_date=birth_date,
            appointment_date=metric_date,
            gender=gender,
            weight_kg=weight,
        )

        if not (
            metrics.get("egfr_ckdepi") is not None
            or metrics.get("crcl_cockcroft_gault") is not None
            or metrics.get("ckd_stage") is not None
        ):
            continue

        insert_calculated_metric(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=metric_date,
            creatinine=current_creatinine,
            age=calculate_age(birth_date, metric_date),
            gender=gender,
            weight_at_appointment=weight,
            egfr_ckdepi=metrics.get("egfr_ckdepi"),
            crcl_cockcroft_gault=metrics.get("crcl_cockcroft_gault"),
            ckd_stage=metrics.get("ckd_stage"),
        )


def save_urinalysis_results(
    cur: Any,
    appointment_id: int,
    appointment_date_default: Any,
    urinalysis_data: dict[str, list[Any]],
) -> None:
    """Сохраняет все заполненные столбцы общего анализа мочи."""
    value_lists = [
        urinalysis_data.get("specific_gravity", []),
        urinalysis_data.get("urine_protein", []),
        urinalysis_data.get("urine_leukocytes", []),
        urinalysis_data.get("urine_erythrocytes", []),
        urinalysis_data.get("bacteria", []),
    ]
    max_count = max_list_length(urinalysis_data.get("dates", []), *value_lists)

    for index in range(max_count):
        if not has_any_indexed_value(value_lists, index):
            continue

        insert_urinalysis_result(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=date_at(urinalysis_data.get("dates"), index, appointment_date_default),
            specific_gravity=value_at(urinalysis_data.get("specific_gravity"), index),
            protein=value_at(urinalysis_data.get("urine_protein"), index),
            leukocytes=value_at(urinalysis_data.get("urine_leukocytes"), index),
            erythrocytes=value_at(urinalysis_data.get("urine_erythrocytes"), index),
            bacteria=value_at(urinalysis_data.get("bacteria"), index),
        )


def save_albuminuria_results(
    cur: Any,
    appointment_id: int,
    appointment_date_default: Any,
    albuminuria_data: dict[str, list[Any]],
) -> None:
    """Сохраняет альбуминурию и серверный расчёт ACR / категории A1-A3."""
    value_lists = [
        albuminuria_data.get("urine_albumin", []),
        albuminuria_data.get("urine_creatinine", []),
    ]
    max_count = max_list_length(
        albuminuria_data.get("dates", []),
        albuminuria_data.get("urine_albumin", []),
        albuminuria_data.get("urine_albumin_unit", []),
        albuminuria_data.get("urine_creatinine", []),
        albuminuria_data.get("urine_creatinine_unit", []),
    )

    for index in range(max_count):
        if not has_any_indexed_value(value_lists, index):
            continue

        current_albumin = value_at(albuminuria_data.get("urine_albumin"), index)
        current_albumin_unit = value_at(albuminuria_data.get("urine_albumin_unit"), index) or "mg_l"
        current_creatinine = value_at(albuminuria_data.get("urine_creatinine"), index)
        current_creatinine_unit = value_at(albuminuria_data.get("urine_creatinine_unit"), index) or "mmol_l"

        if current_albumin is None or current_creatinine is None:
            continue

        albuminuria_metrics = calculate_albuminuria_metrics(
            urine_albumin=current_albumin,
            urine_albumin_unit=current_albumin_unit,
            urine_creatinine=current_creatinine,
            urine_creatinine_unit=current_creatinine_unit,
        )

        insert_albuminuria_result(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=date_at(albuminuria_data.get("dates"), index, appointment_date_default),
            urine_albumin=current_albumin,
            urine_albumin_unit=current_albumin_unit,
            urine_creatinine=current_creatinine,
            urine_creatinine_unit=current_creatinine_unit,
            albumin_creatinine_ratio=albuminuria_metrics["albumin_creatinine_ratio"],
            albuminuria_category=albuminuria_metrics["albuminuria_category"],
        )


def save_ultrasound_results(
    cur: Any,
    appointment_id: int,
    appointment_date_default: Any,
    ultrasound_data: dict[str, list[Any]],
) -> None:
    """Сохраняет все заполненные столбцы УЗИ почек."""
    value_lists = [
        ultrasound_data.get("left_kidney_size", []),
        ultrasound_data.get("right_kidney_size", []),
        ultrasound_data.get("left_parenchyma", []),
        ultrasound_data.get("right_parenchyma", []),
        ultrasound_data.get("ultrasound_desc", []),
    ]
    max_count = max_list_length(ultrasound_data.get("dates", []), *value_lists)

    for index in range(max_count):
        if not has_any_indexed_value(value_lists, index):
            continue

        insert_ultrasound_result(
            cur=cur,
            appointment_id=appointment_id,
            investigation_date=date_at(ultrasound_data.get("dates"), index, appointment_date_default),
            left_kidney_size=value_at(ultrasound_data.get("left_kidney_size"), index),
            right_kidney_size=value_at(ultrasound_data.get("right_kidney_size"), index),
            left_parenchyma=value_at(ultrasound_data.get("left_parenchyma"), index),
            right_parenchyma=value_at(ultrasound_data.get("right_parenchyma"), index),
            description=value_at(ultrasound_data.get("ultrasound_desc"), index),
        )


def save_diet_and_recommendations(cur: Any, appointment_id: int, diet_data: dict[str, Any]) -> None:
    """Сохраняет диету, рекомендации и дату следующего контроля."""
    insert_diet_and_recommendations(cur, appointment_id, diet_data)


def save_prescriptions(cur: Any, appointment_id: int, prescriptions_data: dict[str, list[Any]]) -> None:
    """Сохраняет лекарственные назначения."""
    medications = prescriptions_data.get("medications", [])
    dosages = prescriptions_data.get("dosages", [])
    schedules = prescriptions_data.get("schedules", [])
    max_count = max_list_length(medications, dosages, schedules)

    for index in range(max_count):
        medication = empty_to_none(value_at(medications, index))
        dosage = empty_to_none(value_at(dosages, index))
        schedule = empty_to_none(value_at(schedules, index))

        if not (medication or dosage or schedule):
            continue

        insert_prescription(
            cur=cur,
            appointment_id=appointment_id,
            medication=medication,
            dosage=dosage,
            schedule=schedule,
        )


def save_appointment_details(
    cur: Any,
    appointment_id: int,
    appointment_data: dict[str, Any],
    patient_birth_date: Any,
    patient_gender: bool,
) -> None:
    """Главная функция сохранения содержимого приёма."""
    appointment_date_default = appointment_data["appointment_date_default"]
    examination_data = appointment_data["examination"]

    save_survey(cur, appointment_id, appointment_data["survey"])
    save_examination(cur, appointment_id, examination_data)
    save_cbc_results(cur, appointment_id, appointment_date_default, appointment_data["cbc"])

    metric_sources = save_biochemistry_results(
        cur,
        appointment_id,
        appointment_date_default,
        appointment_data["biochemistry"],
    )
    save_calculated_metrics(
        cur=cur,
        appointment_id=appointment_id,
        birth_date=patient_birth_date,
        gender=patient_gender,
        weight=examination_data.get("weight"),
        metric_sources=metric_sources,
        appointment_date_default=appointment_date_default,
    )

    save_urinalysis_results(
        cur,
        appointment_id,
        appointment_date_default,
        appointment_data["urinalysis"],
    )
    save_albuminuria_results(
        cur,
        appointment_id,
        appointment_date_default,
        appointment_data["albuminuria"],
    )
    save_ultrasound_results(
        cur,
        appointment_id,
        appointment_date_default,
        appointment_data["ultrasound"],
    )

    # Единственный источник диагнозов — структурированный МКБ-10 блок.
    save_appointment_icd10_diagnoses(cur, appointment_id, appointment_data["icd10"])
    save_diet_and_recommendations(cur, appointment_id, appointment_data["diet"])
    save_prescriptions(cur, appointment_id, appointment_data["prescriptions"])

    # Пересчитываем прогноз после сохранения метрик и альбуминурии.
    save_ckd_prognosis_for_appointment(
        appointment_id,
        cur=cur,
        excluded_pairs=appointment_data.get("kdigo_excluded_pairs", []),
    )
