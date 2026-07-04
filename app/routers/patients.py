import json
from datetime import datetime, date, timedelta
from fastapi import APIRouter, Request, HTTPException, Form
from typing import List, Optional
from fastapi.responses import RedirectResponse
from ..database import (
    get_all_appointments,     get_branches,     get_locations_by_branch,
    get_doctors,     get_doctor_locations,     get_db_connection,
    get_doctors_for_filter, get_locations_for_filter, save_ckd_prognosis_for_appointment,
)
from ..calculations import calculate_all_metrics, calculate_age,  calculate_albuminuria_metrics, calculate_bmi
from ..validation import validate_appointment_form

router = APIRouter(tags=["patients"])

def empty_to_none(value):
    """Пустые строки превращаем в None, чтобы в БД не летели пустые значения."""
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value
def value_at(values, index, default=None):
    """
    Безопасно возвращает значение из списка по индексу.
    """
    if values is None:
        return default

    if index < 0 or index >= len(values):
        return default

    return values[index]


def get_form_list_keep_empty(form, field_name: str):
    """
    Возвращает список значений формы с сохранением порядка.
    Пустые значения превращает в None, но не удаляет.
    Это нужно, чтобы диагноз и уточнение врача не разъезжались.
    """
    return [empty_to_none(value) for value in form.getlist(field_name)]


def insert_appointment_icd10_diagnosis(
    cur,
    appointment_id,
    diagnosis_type,
    diagnosis_text,
    doctor_note=None,
    sort_order=1
):
    """
    Сохраняет один структурированный диагноз по МКБ-10.
    diagnosis_text должен точно совпадать со строкой из icd10_diagnoses.diagnosis.
    """

    diagnosis_text = empty_to_none(diagnosis_text)
    doctor_note = empty_to_none(doctor_note)

    if not diagnosis_text:
        return None

    cur.execute("""
        SELECT id
        FROM icd10_diagnoses
        WHERE diagnosis = %s
          AND is_active = TRUE
        LIMIT 1
    """, (diagnosis_text,))

    icd10_row = cur.fetchone()

    if not icd10_row:
        raise HTTPException(
            status_code=400,
            detail=f"Диагноз МКБ-10 не найден в справочнике: {diagnosis_text}"
        )

    cur.execute("""
        INSERT INTO appointment_icd10_diagnoses (
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            doctor_note,
            sort_order
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        appointment_id,
        diagnosis_type,
        icd10_row["id"],
        doctor_note,
        sort_order
    ))

    return icd10_row["id"]


def save_appointment_icd10_diagnoses_from_form(cur, appointment_id, form):
    """
    Сохраняет структурированные диагнозы по МКБ-10 из формы.
    Используется и для нового пациента, и для повторного приёма.
    """

    # Основной диагноз
    icd10_main_diagnosis = empty_to_none(form.get("icd10_main_diagnosis"))
    icd10_main_note = empty_to_none(form.get("icd10_main_note"))

    insert_appointment_icd10_diagnosis(
        cur=cur,
        appointment_id=appointment_id,
        diagnosis_type="main",
        diagnosis_text=icd10_main_diagnosis,
        doctor_note=icd10_main_note,
        sort_order=1
    )

    # Осложнения
    complication_diagnoses = get_form_list_keep_empty(
        form,
        "icd10_complication_diagnosis"
    )
    complication_notes = get_form_list_keep_empty(
        form,
        "icd10_complication_note"
    )

    for index, diagnosis_text in enumerate(complication_diagnoses, start=1):
        doctor_note = value_at(complication_notes, index - 1)

        insert_appointment_icd10_diagnosis(
            cur=cur,
            appointment_id=appointment_id,
            diagnosis_type="complication",
            diagnosis_text=diagnosis_text,
            doctor_note=doctor_note,
            sort_order=index
        )

    # Сопутствующие заболевания
    comorbidity_diagnoses = get_form_list_keep_empty(
        form,
        "icd10_comorbidity_diagnosis"
    )
    comorbidity_notes = get_form_list_keep_empty(
        form,
        "icd10_comorbidity_note"
    )

    for index, diagnosis_text in enumerate(comorbidity_diagnoses, start=1):
        doctor_note = value_at(comorbidity_notes, index - 1)

        insert_appointment_icd10_diagnosis(
            cur=cur,
            appointment_id=appointment_id,
            diagnosis_type="comorbidity",
            diagnosis_text=diagnosis_text,
            doctor_note=doctor_note,
            sort_order=index
        )
        
def numeric_to_db(value):
    """
    Готовит числовое значение для PostgreSQL:
    3,6 -> 3.6
    пустое значение -> None
    """
    value = empty_to_none(value)

    if value is None:
        return None

    return value.replace(" ", "").replace(",", ".")

def calculate_bmi_for_db(height, weight):
    """
    Совместимость для текущего patients.py.

    Саму формулу здесь больше не держим:
    медицинский расчёт вынесен в app/medical_algorithms/bmi.py.

    Важно: значение ИМТ из формы не используем как источник истины.
    Сервер всегда пересчитывает ИМТ по росту и весу.
    """
    return calculate_bmi(height, weight)

def parse_bool(value):
    """Преобразует значение из формы в boolean."""
    return str(value).lower() in ["true", "1", "yes", "on"]


def join_form_values(values, other_value=None):
    """
    Для чекбоксов:
    skin_condition = несколько выбранных вариантов + поле 'другое'
    """
    result = []

    for value in values:
        value = empty_to_none(value)
        if value:
            result.append(value)

    other_value = empty_to_none(other_value)
    if other_value:
        result.append(other_value)

    if not result:
        return None

    return ", ".join(result)


def has_any_value(form, field_names):
    """Проверяет, заполнено ли хоть одно поле из списка."""
    for field_name in field_names:
        if empty_to_none(form.get(field_name)):
            return True
    return False

def get_text_list(form, field_name):
    """Получает список текстовых значений из формы."""
    return [empty_to_none(value) for value in form.getlist(field_name)]


def get_numeric_list(form, field_name):
    """Получает список числовых значений из формы."""
    return [numeric_to_db(value) for value in form.getlist(field_name)]


def value_at(values, index):
    """Безопасно получает значение из списка по индексу."""
    if index < len(values):
        return values[index]
    return None


def has_any_indexed_value(lists, index):
    """Проверяет, есть ли хоть одно заполненное значение в конкретном новом столбце анализа."""
    for values in lists:
        if empty_to_none(value_at(values, index)):
            return True
    return False


def date_at(values, index, default_date):
    """Берёт дату исследования из столбца анализа или дату приёма по умолчанию."""
    value = empty_to_none(value_at(values, index))
    return value or default_date


def parse_date_or_default(value, default_date):
    """Преобразует дату из строки YYYY-MM-DD в date. Если даты нет — возвращает default_date."""
    value = empty_to_none(value)

    if not value:
        return default_date

    if hasattr(value, "year"):
        return value

    return datetime.strptime(value, "%Y-%m-%d").date()

def insert_appointment_icd10_diagnosis(
    cur,
    appointment_id,
    diagnosis_type,
    diagnosis_text,
    doctor_note=None,
    sort_order=1
):
    """
    Сохраняет структурированный диагноз приёма.

    diagnosis_text приходит из формы как строка:
    'N18.3 — Хроническая болезнь почек, стадия 3'

    В таблицу appointment_icd10_diagnoses сохраняется не текст,
    а ссылка на справочник icd10_diagnoses.id.
    """
    diagnosis_text = empty_to_none(diagnosis_text)
    doctor_note = empty_to_none(doctor_note)

    if not diagnosis_text:
        return None

    cur.execute("""
        SELECT id
        FROM icd10_diagnoses
        WHERE diagnosis = %s
          AND is_active = TRUE
        LIMIT 1
    """, (diagnosis_text,))

    icd10_row = cur.fetchone()

    if not icd10_row:
        raise HTTPException(
            status_code=400,
            detail=f"Диагноз МКБ-10 не найден в справочнике: {diagnosis_text}"
        )

    cur.execute("""
        INSERT INTO appointment_icd10_diagnoses (
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            doctor_note,
            sort_order
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        appointment_id,
        diagnosis_type,
        icd10_row["id"],
        doctor_note,
        sort_order
    ))

    return icd10_row["id"]

# ========== API МАРШРУТЫ (GET) ==========

@router.get("/api/appointments/filtered")
def api_appointments_filtered(
    branch_id: Optional[int] = None,
    location_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    search: Optional[str] = None,
    period: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    sort_order: str = "desc",
    limit: int = 200,
    offset: int = 0,
):
    """Возвращает отфильтрованный список приёмов в формате JSON."""

    # Поддержка фильтра "Период".
    # Если frontend передал date_from/date_to, используем их.
    # Если передал только period, рассчитываем даты здесь.
    today = date.today()

    if period == "today" and not date_from and not date_to:
        date_from = today
        date_to = today
    elif period == "week" and not date_from and not date_to:
        date_from = today - timedelta(days=7)
        date_to = today
    elif period == "month" and not date_from and not date_to:
        date_from = today - timedelta(days=30)
        date_to = today
    elif period == "year" and not date_from and not date_to:
        date_from = date(today.year - 1, today.month, today.day)
        date_to = today
    elif period == "oldest":
        sort_order = "asc"
    elif period == "newest":
        sort_order = "desc"

    filters = {
        "branch_id": branch_id,
        "location_id": location_id,
        "doctor_id": doctor_id,
        "search": search,
        "date_from": date_from,
        "date_to": date_to,
        "sort_order": sort_order,
        "limit": limit,
        "offset": offset,
    }

    appointments = get_all_appointments(filters)

    result = []
    for app in appointments:
        app_dict = dict(app)

        if app_dict.get("appointment_date"):
            app_dict["appointment_date"] = app_dict["appointment_date"].isoformat()

        if app_dict.get("birth_date"):
            app_dict["birth_date"] = app_dict["birth_date"].isoformat()

        result.append(app_dict)

    return result

@router.get("/api/branches")
def api_branches():
    """Возвращает список филиалов"""
    return get_branches()

@router.get("/api/locations")
def api_locations(
    branch_id: Optional[int] = None,
    doctor_id: Optional[int] = None
):
    """
    Возвращает список отделений для фильтра.
    Может учитывать выбранный филиал и/или выбранного врача.
    """
    if not branch_id and not doctor_id:
        return []

    return get_locations_for_filter(
        branch_id=branch_id,
        doctor_id=doctor_id
    )

@router.get("/api/doctors")
def api_doctors(
    branch_id: Optional[int] = None,
    location_id: Optional[int] = None
):
    """
    Возвращает список врачей для фильтра.
    Может учитывать выбранный филиал и/или выбранное отделение.
    """
    return get_doctors_for_filter(
        branch_id=branch_id,
        location_id=location_id
    )

@router.get("/api/doctor-locations/{doctor_id}")
def api_doctor_locations(doctor_id: int):
    """Возвращает отделения, где работает врач"""
    return get_doctor_locations(doctor_id)

@router.post("/api/patients/new")
async def create_new_patient(request: Request):
    """
    Создаёт нового пациента и первый приём.
    """

    form = await request.form()

    # =========================
    # ОБЯЗАТЕЛЬНЫЕ ПОЛЯ
    # =========================
    last_name = empty_to_none(form.get("last_name"))
    first_name = empty_to_none(form.get("first_name"))
    patronymic = empty_to_none(form.get("patronymic"))
    birth_date = empty_to_none(form.get("birth_date"))
    gender = parse_bool(form.get("gender", "true"))

    doctor_id = empty_to_none(form.get("doctor_id"))
    location_id = empty_to_none(form.get("location_id"))
    appointment_date = empty_to_none(form.get("appointment_date"))
    appointment_time = empty_to_none(form.get("appointment_time"))

    if not last_name or not first_name or not birth_date:
        raise HTTPException(status_code=400, detail="Не заполнены обязательные данные пациента")

    if not doctor_id or not location_id or not appointment_date or not appointment_time:
        raise HTTPException(status_code=400, detail="Не заполнены обязательные данные приёма")

    try:
        appointment_datetime = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата или время приёма")

    try:
        birth_date_obj = datetime.strptime(birth_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата рождения")

    validation_errors = validate_appointment_form(form, appointment_datetime.date())
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Форма содержит некорректные медицинские значения",
                "errors": validation_errors,
            },
        )

    # =========================
    # ПОЛЯ ФОРМЫ
    # =========================

    # Опрос
    life_anamnesis = empty_to_none(form.get("life_anamnesis"))
    disease_anamnesis = empty_to_none(form.get("disease_anamnesis"))
    complaints = empty_to_none(form.get("complaints"))
    heredity = form.get("heredity") == "true"
    heredity_description = empty_to_none(form.get("heredity_description"))
    comorbidities = empty_to_none(form.get("comorbidities"))

    # Осмотр
    # Осмотр — кожные покровы
    skin_color = join_form_values(
        form.getlist("skin_color"),
        form.get("skin_color_other")
    )

    skin_moisture = join_form_values(
        form.getlist("skin_moisture"),
        form.get("skin_moisture_other")
    )

    skin_rash = empty_to_none(form.get("skin_rash"))
    skin_rash_description = empty_to_none(form.get("skin_rash_description"))
    skin_other = empty_to_none(form.get("skin_other"))

    skin_parts = []

    if skin_color:
        skin_parts.append(f"Окраска: {skin_color}")

    if skin_moisture:
        skin_parts.append(f"Влажность: {skin_moisture}")

    if skin_rash:
        if skin_rash == "есть" and skin_rash_description:
            skin_parts.append(f"Высыпания: есть ({skin_rash_description})")
        else:
            skin_parts.append(f"Высыпания: {skin_rash}")

    if skin_other:
        skin_parts.append(f"Дополнительно: {skin_other}")

    skin_condition = "; ".join(skin_parts) if skin_parts else None


    # Осмотр — отёки
    edema_peripheral = join_form_values(
        form.getlist("edema_peripheral"),
        form.get("edema_peripheral_other")
    )

    edema_serositis = join_form_values(
        form.getlist("edema_serositis"),
        form.get("edema_serositis_other")
    )

    edema_other = empty_to_none(form.get("edema_other"))

    edema_parts = []

    if edema_peripheral:
        edema_parts.append(f"Периферические отёки: {edema_peripheral}")

    if edema_serositis:
        edema_parts.append(f"Серозиты: {edema_serositis}")

    if edema_other:
        edema_parts.append(f"Дополнительно: {edema_other}")

    edema_location = "; ".join(edema_parts) if edema_parts else None

    systolic_pressure = empty_to_none(form.get("systolic_pressure"))
    diastolic_pressure = empty_to_none(form.get("diastolic_pressure"))
    bp_note = empty_to_none(form.get("bp_note"))
    heart_rate = empty_to_none(form.get("heart_rate"))
    height = empty_to_none(form.get("height"))
    weight = empty_to_none(form.get("weight"))
    bmi = calculate_bmi_for_db(height, weight)

    # ОАК — может быть несколько анализов
    cbc_dates = get_text_list(form, "cbc_investigation_date")
    hemoglobin_list = get_numeric_list(form, "hemoglobin")
    erythrocytes_list = get_numeric_list(form, "erythrocytes")
    leukocytes_list = get_numeric_list(form, "leukocytes")
    platelets_list = get_numeric_list(form, "platelets")
    esr_list = get_numeric_list(form, "esr")
    mcv_list = get_numeric_list(form, "mcv")
    hematocrit_list = get_numeric_list(form, "hematocrit")

    # Биохимия — может быть несколько анализов
    biochemistry_dates = get_text_list(form, "biochemistry_investigation_date")
    creatinine_list = get_numeric_list(form, "creatinine")
    urea_list = get_numeric_list(form, "urea")
    uric_acid_list = get_numeric_list(form, "uric_acid")
    glucose_list = get_numeric_list(form, "glucose")
    total_protein_list = get_numeric_list(form, "total_protein")
    albumin_list = get_numeric_list(form, "albumin")
    potassium_list = get_numeric_list(form, "potassium")
    calcium_list = get_numeric_list(form, "calcium")
    phosphorus_list = get_numeric_list(form, "phosphorus")
    ferritin_list = get_numeric_list(form, "ferritin")
    ptg_list = get_numeric_list(form, "ptg")

    # ОАМ — может быть несколько анализов
    urinalysis_dates = get_text_list(form, "urinalysis_investigation_date")
    specific_gravity_list = get_numeric_list(form, "specific_gravity")
    urine_protein_list = get_numeric_list(form, "urine_protein")
    urine_leukocytes_list = get_numeric_list(form, "urine_leukocytes")
    urine_erythrocytes_list = get_numeric_list(form, "urine_erythrocytes")
    bacteria_list = get_numeric_list(form, "bacteria")

    # Альбуминурия — может быть несколько исследований
    albuminuria_dates = get_text_list(form, "albuminuria_investigation_date")
    urine_albumin_list = get_numeric_list(form, "urine_albumin")
    urine_albumin_unit_list = get_text_list(form, "urine_albumin_unit")
    urine_creatinine_list = get_numeric_list(form, "urine_creatinine")
    urine_creatinine_unit_list = get_text_list(form, "urine_creatinine_unit")

    # УЗИ — может быть несколько исследований
    ultrasound_dates = get_text_list(form, "ultrasound_investigation_date")
    left_kidney_size_list = get_text_list(form, "left_kidney_size")
    right_kidney_size_list = get_text_list(form, "right_kidney_size")
    left_parenchyma_list = get_numeric_list(form, "left_parenchyma")
    right_parenchyma_list = get_numeric_list(form, "right_parenchyma")
    ultrasound_desc_list = get_text_list(form, "ultrasound_desc")

    # Диагнозы
    main_diagnosis = empty_to_none(form.get("main_diagnosis"))
    complications = empty_to_none(form.get("complications"))
    comorbidities_diag = empty_to_none(form.get("comorbidities_diag"))

    # Назначения
    diet = empty_to_none(form.get("diet"))
    recommendations = empty_to_none(form.get("recommendations"))
    next_control_date = empty_to_none(form.get("next_control_date"))

    medications = form.getlist("medication")
    dosages = form.getlist("dosage")
    schedules = form.getlist("schedule")

    # Дату исследования пока берём равной дате приёма.
    # Позже можно добавить отдельные поля дат для ОАК, биохимии, ОАМ, УЗИ.
    cbc_investigation_date = empty_to_none(form.get("cbc_investigation_date")) or appointment_datetime.date()
    biochemistry_investigation_date = empty_to_none(form.get("biochemistry_investigation_date")) or appointment_datetime.date()
    urinalysis_investigation_date = empty_to_none(form.get("urinalysis_investigation_date")) or appointment_datetime.date()
    ultrasound_investigation_date = empty_to_none(form.get("ultrasound_investigation_date")) or appointment_datetime.date()

    # =========================
    # СОХРАНЕНИЕ В БД
    # =========================

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO patients (last_name, first_name, patronymic, birth_date, gender)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (last_name, first_name, patronymic, birth_date_obj, gender))
                patient_id = cur.fetchone()["id"]

                cur.execute("""
                    INSERT INTO appointments (patient_id, doctor_id, location_id, appointment_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (patient_id, int(doctor_id), int(location_id), appointment_datetime))
                appointment_id = cur.fetchone()["id"]

                cur.execute("""
                    INSERT INTO surveys (
                        appointment_id, life_anamnesis, disease_anamnesis, complaints,
                        heredity, heredity_description, comorbidities
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    appointment_id, life_anamnesis, disease_anamnesis, complaints,
                    heredity, heredity_description, comorbidities
                ))

                cur.execute("""
                    INSERT INTO examinations (
                        appointment_id, skin_condition, edema_location, systolic_pressure,
                        diastolic_pressure, bp_note, heart_rate, height, weight, bmi
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    appointment_id, skin_condition, edema_location, systolic_pressure,
                    diastolic_pressure, bp_note, heart_rate, height, weight, bmi
                ))

                # 5. ОАК — сохраняем все добавленные анализы
                cbc_value_lists = [
                    hemoglobin_list,
                    erythrocytes_list,
                    leukocytes_list,
                    platelets_list,
                    esr_list,
                    mcv_list,
                    hematocrit_list
                ]

                max_cbc_count = max(
                    len(cbc_dates),
                    len(hemoglobin_list),
                    len(erythrocytes_list),
                    len(leukocytes_list),
                    len(platelets_list),
                    len(esr_list),
                    len(mcv_list),
                    len(hematocrit_list)
                )

                for index in range(max_cbc_count):
                    if has_any_indexed_value(cbc_value_lists, index):
                        cur.execute("""
                            INSERT INTO cbc_results (
                                appointment_id, investigation_date, hemoglobin, erythrocytes,
                                leukocytes, platelets, esr, mcv, hematocrit
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(cbc_dates, index, appointment_datetime.date()),
                            value_at(hemoglobin_list, index),
                            value_at(erythrocytes_list, index),
                            value_at(leukocytes_list, index),
                            value_at(platelets_list, index),
                            value_at(esr_list, index),
                            value_at(mcv_list, index),
                            value_at(hematocrit_list, index)
                        ))


                # 6. Биохимия — сохраняем все добавленные анализы
                biochemistry_value_lists = [
                    creatinine_list,
                    urea_list,
                    uric_acid_list,
                    glucose_list,
                    total_protein_list,
                    albumin_list,
                    potassium_list,
                    calcium_list,
                    phosphorus_list,
                    ferritin_list,
                    ptg_list
                ]

                max_biochemistry_count = max(
                    len(biochemistry_dates),
                    len(creatinine_list),
                    len(urea_list),
                    len(uric_acid_list),
                    len(glucose_list),
                    len(total_protein_list),
                    len(albumin_list),
                    len(potassium_list),
                    len(calcium_list),
                    len(phosphorus_list),
                    len(ferritin_list),
                    len(ptg_list)
                )

                for index in range(max_biochemistry_count):
                    if has_any_indexed_value(biochemistry_value_lists, index):
                        current_biochemistry_date = date_at(
                            biochemistry_dates,
                            index,
                            appointment_datetime.date()
                        )

                        current_creatinine = value_at(creatinine_list, index)

                        cur.execute("""
                            INSERT INTO biochemistry_results (
                                appointment_id, investigation_date, creatinine, urea, uric_acid,
                                glucose, total_protein, albumin, potassium, calcium,
                                phosphorus, ferritin, ptg
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            current_biochemistry_date,
                            current_creatinine,
                            value_at(urea_list, index),
                            value_at(uric_acid_list, index),
                            value_at(glucose_list, index),
                            value_at(total_protein_list, index),
                            value_at(albumin_list, index),
                            value_at(potassium_list, index),
                            value_at(calcium_list, index),
                            value_at(phosphorus_list, index),
                            value_at(ferritin_list, index),
                            value_at(ptg_list, index)
                        ))

                        if current_creatinine:
                            metrics = calculate_all_metrics(
                                creatinine_umol_l=current_creatinine,
                                birth_date=birth_date_obj,
                                appointment_date=parse_date_or_default(current_biochemistry_date, appointment_datetime.date()),
                                gender=gender,
                                weight_kg=weight
                            )

                            if (
                                metrics.get("egfr_ckdepi") is not None
                                or metrics.get("crcl_cockcroft_gault") is not None
                                or metrics.get("ckd_stage") is not None
                            ):
                                age_for_metrics = calculate_age(
                                    birth_date_obj,
                                    parse_date_or_default(current_biochemistry_date, appointment_datetime.date())
                                )

                                cur.execute("""
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
                                """, (
                                    appointment_id,
                                    current_biochemistry_date,
                                    current_creatinine,
                                    age_for_metrics,
                                    gender,
                                    weight,
                                    metrics.get("egfr_ckdepi"),
                                    metrics.get("crcl_cockcroft_gault"),
                                    metrics.get("ckd_stage")
                                ))


                # 7. ОАМ — сохраняем все добавленные анализы
                urinalysis_value_lists = [
                    specific_gravity_list,
                    urine_protein_list,
                    urine_leukocytes_list,
                    urine_erythrocytes_list,
                    bacteria_list
                ]

                max_urinalysis_count = max(
                    len(urinalysis_dates),
                    len(specific_gravity_list),
                    len(urine_protein_list),
                    len(urine_leukocytes_list),
                    len(urine_erythrocytes_list),
                    len(bacteria_list)
                )

                for index in range(max_urinalysis_count):
                    if has_any_indexed_value(urinalysis_value_lists, index):
                        cur.execute("""
                            INSERT INTO urinalysis_results (
                                appointment_id, investigation_date, specific_gravity,
                                protein, leukocytes, erythrocytes, bacteria
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(urinalysis_dates, index, appointment_datetime.date()),
                            value_at(specific_gravity_list, index),
                            value_at(urine_protein_list, index),
                            value_at(urine_leukocytes_list, index),
                            value_at(urine_erythrocytes_list, index),
                            value_at(bacteria_list, index)
                        ))


                # 7.1. Альбуминурия — сохраняем все добавленные исследования
                albuminuria_value_lists = [
                    urine_albumin_list,
                    urine_creatinine_list
                ]

                max_albuminuria_count = max(
                    len(albuminuria_dates),
                    len(urine_albumin_list),
                    len(urine_albumin_unit_list),
                    len(urine_creatinine_list),
                    len(urine_creatinine_unit_list)
                )

                for index in range(max_albuminuria_count):
                    if has_any_indexed_value(albuminuria_value_lists, index):
                        current_albumin = value_at(urine_albumin_list, index)
                        current_albumin_unit = value_at(urine_albumin_unit_list, index) or "mg_l"

                        current_creatinine = value_at(urine_creatinine_list, index)
                        current_creatinine_unit = value_at(urine_creatinine_unit_list, index) or "mmol_l"

                        if current_albumin is not None and current_creatinine is not None:
                            albuminuria_metrics = calculate_albuminuria_metrics(
                                urine_albumin=current_albumin,
                                urine_albumin_unit=current_albumin_unit,
                                urine_creatinine=current_creatinine,
                                urine_creatinine_unit=current_creatinine_unit
                            )

                            cur.execute("""
                                INSERT INTO albuminuria_results (
                                    appointment_id,
                                    investigation_date,
                                    urine_albumin,
                                    urine_albumin_unit,
                                    urine_creatinine,
                                    urine_creatinine_unit,
                                    albumin_creatinine_ratio,
                                    albuminuria_category
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                appointment_id,
                                date_at(albuminuria_dates, index, appointment_datetime.date()),
                                current_albumin,
                                current_albumin_unit,
                                current_creatinine,
                                current_creatinine_unit,
                                albuminuria_metrics["albumin_creatinine_ratio"],
                                albuminuria_metrics["albuminuria_category"]
                            ))

                save_ckd_prognosis_for_appointment(appointment_id, cur=cur)

                # 8. УЗИ — сохраняем все добавленные исследования
                ultrasound_value_lists = [
                    left_kidney_size_list,
                    right_kidney_size_list,
                    left_parenchyma_list,
                    right_parenchyma_list,
                    ultrasound_desc_list
                ]

                max_ultrasound_count = max(
                    len(ultrasound_dates),
                    len(left_kidney_size_list),
                    len(right_kidney_size_list),
                    len(left_parenchyma_list),
                    len(right_parenchyma_list),
                    len(ultrasound_desc_list)
                )

                for index in range(max_ultrasound_count):
                    if has_any_indexed_value(ultrasound_value_lists, index):
                        cur.execute("""
                            INSERT INTO ultrasound_results (
                                appointment_id, investigation_date, left_kidney_size,
                                right_kidney_size, left_parenchyma, right_parenchyma, description
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(ultrasound_dates, index, appointment_datetime.date()),
                            value_at(left_kidney_size_list, index),
                            value_at(right_kidney_size_list, index),
                            value_at(left_parenchyma_list, index),
                            value_at(right_parenchyma_list, index),
                            value_at(ultrasound_desc_list, index)
                        ))

                cur.execute("""
                    INSERT INTO diagnoses (appointment_id, main_diagnosis, complications, comorbidities)
                    VALUES (%s, %s, %s, %s)
                """, (appointment_id, main_diagnosis, complications, comorbidities_diag))

                save_appointment_icd10_diagnoses_from_form(
                    cur=cur,
                    appointment_id=appointment_id,
                    form=form
                )

                cur.execute("""
                    INSERT INTO appointment_diets (appointment_id, diet, next_control_date, recommendations)
                    VALUES (%s, %s, %s, %s)
                """, (appointment_id, diet, next_control_date, recommendations))

                max_med_count = max(len(medications), len(dosages), len(schedules))

                for index in range(max_med_count):
                    medication = empty_to_none(medications[index]) if index < len(medications) else None
                    dosage = empty_to_none(dosages[index]) if index < len(dosages) else None
                    schedule = empty_to_none(schedules[index]) if index < len(schedules) else None

                    if medication or dosage or schedule:
                        cur.execute("""
                            INSERT INTO prescriptions (appointment_id, medication, dosage, schedule)
                            VALUES (%s, %s, %s, %s)
                        """, (appointment_id, medication, dosage, schedule))

                


            conn.commit()

        except Exception as error:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сохранении пациента и приёма: {error}"
            )

    return RedirectResponse(
        url=f"/patient/{patient_id}?appointment_id={appointment_id}",
        status_code=303
    )


@router.post("/api/patients/{patient_id}/appointments/new")
async def create_new_appointment_for_existing_patient(patient_id: int, request: Request):
    """
    Создаёт новый приём для уже существующего пациента.
    Пациент заново НЕ создаётся: используется patient_id из URL.
    """
    form = await request.form()

    doctor_id = empty_to_none(form.get("doctor_id"))
    location_id = empty_to_none(form.get("location_id"))
    appointment_date = empty_to_none(form.get("appointment_date"))
    appointment_time = empty_to_none(form.get("appointment_time"))

    if not doctor_id or not location_id or not appointment_date or not appointment_time:
        raise HTTPException(status_code=400, detail="Не заполнены обязательные данные приёма")

    try:
        appointment_datetime = datetime.strptime(
            f"{appointment_date} {appointment_time}",
            "%Y-%m-%d %H:%M"
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректная дата или время приёма")

    validation_errors = validate_appointment_form(form, appointment_datetime.date())
    if validation_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Форма содержит некорректные медицинские значения",
                "errors": validation_errors,
            },
        )

    # Опрос
    life_anamnesis = empty_to_none(form.get("life_anamnesis"))
    disease_anamnesis = empty_to_none(form.get("disease_anamnesis"))
    complaints = empty_to_none(form.get("complaints"))
    heredity = form.get("heredity") == "true"
    heredity_description = empty_to_none(form.get("heredity_description"))
    comorbidities = empty_to_none(form.get("comorbidities"))

    # Осмотр — кожные покровы
    skin_color = join_form_values(form.getlist("skin_color"), form.get("skin_color_other"))
    skin_moisture = join_form_values(form.getlist("skin_moisture"), form.get("skin_moisture_other"))
    skin_rash = empty_to_none(form.get("skin_rash"))
    skin_rash_description = empty_to_none(form.get("skin_rash_description"))
    skin_other = empty_to_none(form.get("skin_other"))

    skin_parts = []
    if skin_color:
        skin_parts.append(f"Окраска: {skin_color}")
    if skin_moisture:
        skin_parts.append(f"Влажность: {skin_moisture}")
    if skin_rash:
        if skin_rash == "есть" and skin_rash_description:
            skin_parts.append(f"Высыпания: есть ({skin_rash_description})")
        else:
            skin_parts.append(f"Высыпания: {skin_rash}")
    if skin_other:
        skin_parts.append(f"Дополнительно: {skin_other}")
    skin_condition = "; ".join(skin_parts) if skin_parts else None

    # Осмотр — отёки
    edema_peripheral = join_form_values(form.getlist("edema_peripheral"), form.get("edema_peripheral_other"))
    edema_serositis = join_form_values(form.getlist("edema_serositis"), form.get("edema_serositis_other"))
    edema_other = empty_to_none(form.get("edema_other"))

    edema_parts = []
    if edema_peripheral:
        edema_parts.append(f"Периферические отёки: {edema_peripheral}")
    if edema_serositis:
        edema_parts.append(f"Серозиты: {edema_serositis}")
    if edema_other:
        edema_parts.append(f"Дополнительно: {edema_other}")
    edema_location = "; ".join(edema_parts) if edema_parts else None

    systolic_pressure = empty_to_none(form.get("systolic_pressure"))

    diastolic_pressure = empty_to_none(form.get("diastolic_pressure"))
    bp_note = empty_to_none(form.get("bp_note"))
    heart_rate = empty_to_none(form.get("heart_rate"))
    height = empty_to_none(form.get("height"))
    weight = empty_to_none(form.get("weight"))
    bmi = calculate_bmi_for_db(height, weight)

    # ОАК — может быть несколько новых анализов
    cbc_dates = get_text_list(form, "cbc_investigation_date")
    hemoglobin_list = get_numeric_list(form, "hemoglobin")
    erythrocytes_list = get_numeric_list(form, "erythrocytes")
    leukocytes_list = get_numeric_list(form, "leukocytes")
    platelets_list = get_numeric_list(form, "platelets")
    esr_list = get_numeric_list(form, "esr")
    mcv_list = get_numeric_list(form, "mcv")
    hematocrit_list = get_numeric_list(form, "hematocrit")

    # Биохимия — может быть несколько новых анализов
    biochemistry_dates = get_text_list(form, "biochemistry_investigation_date")
    creatinine_list = get_numeric_list(form, "creatinine")
    urea_list = get_numeric_list(form, "urea")
    uric_acid_list = get_numeric_list(form, "uric_acid")
    glucose_list = get_numeric_list(form, "glucose")
    total_protein_list = get_numeric_list(form, "total_protein")
    albumin_list = get_numeric_list(form, "albumin")
    potassium_list = get_numeric_list(form, "potassium")
    calcium_list = get_numeric_list(form, "calcium")
    phosphorus_list = get_numeric_list(form, "phosphorus")
    ferritin_list = get_numeric_list(form, "ferritin")
    ptg_list = get_numeric_list(form, "ptg")

    # ОАМ — может быть несколько новых анализов
    urinalysis_dates = get_text_list(form, "urinalysis_investigation_date")
    specific_gravity_list = get_numeric_list(form, "specific_gravity")
    urine_protein_list = get_numeric_list(form, "urine_protein")
    urine_leukocytes_list = get_numeric_list(form, "urine_leukocytes")
    urine_erythrocytes_list = get_numeric_list(form, "urine_erythrocytes")
    bacteria_list = get_numeric_list(form, "bacteria")

    # Альбуминурия — может быть несколько новых исследований
    albuminuria_dates = get_text_list(form, "albuminuria_investigation_date")
    urine_albumin_list = get_numeric_list(form, "urine_albumin")
    urine_albumin_unit_list = get_text_list(form, "urine_albumin_unit")
    urine_creatinine_list = get_numeric_list(form, "urine_creatinine")
    urine_creatinine_unit_list = get_text_list(form, "urine_creatinine_unit")

    # УЗИ — может быть несколько новых исследований
    ultrasound_dates = get_text_list(form, "ultrasound_investigation_date")
    left_kidney_size_list = get_text_list(form, "left_kidney_size")
    right_kidney_size_list = get_text_list(form, "right_kidney_size")
    left_parenchyma_list = get_numeric_list(form, "left_parenchyma")
    right_parenchyma_list = get_numeric_list(form, "right_parenchyma")
    ultrasound_desc_list = get_text_list(form, "ultrasound_desc")

    # Диагнозы и назначения

    # Старые свободные текстовые поля — пока оставляем
    main_diagnosis = empty_to_none(form.get("main_diagnosis"))
    complications = empty_to_none(form.get("complications"))
    comorbidities_diag = empty_to_none(form.get("comorbidities_diag"))

    # Новые структурированные диагнозы по МКБ-10
    icd10_main_diagnosis = empty_to_none(form.get("icd10_main_diagnosis"))
    icd10_main_note = empty_to_none(form.get("icd10_main_note"))

    icd10_complication_diagnoses = get_text_list(form, "icd10_complication_diagnosis")
    icd10_complication_notes = get_text_list(form, "icd10_complication_note")

    icd10_comorbidity_diagnoses = get_text_list(form, "icd10_comorbidity_diagnosis")
    icd10_comorbidity_notes = get_text_list(form, "icd10_comorbidity_note")

    diet = empty_to_none(form.get("diet"))
    next_control_date = empty_to_none(form.get("next_control_date"))
    recommendations = empty_to_none(form.get("recommendations"))

    medications = form.getlist("medication")
    dosages = form.getlist("dosage")
    schedules = form.getlist("schedule")

    cbc_investigation_date = empty_to_none(form.get("cbc_investigation_date")) or appointment_datetime.date()
    biochemistry_investigation_date = empty_to_none(form.get("biochemistry_investigation_date")) or appointment_datetime.date()
    urinalysis_investigation_date = empty_to_none(form.get("urinalysis_investigation_date")) or appointment_datetime.date()
    ultrasound_investigation_date = empty_to_none(form.get("ultrasound_investigation_date")) or appointment_datetime.date()

    with get_db_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Проверяем, что пациент существует, и берём дату рождения/пол для расчётов
                cur.execute("""
                    SELECT id, birth_date, gender
                    FROM patients
                    WHERE id = %s
                """, (patient_id,))
                patient = cur.fetchone()

                if not patient:
                    raise HTTPException(status_code=404, detail="Пациент не найден")

                birth_date_obj = patient["birth_date"]
                gender = patient["gender"]

                cur.execute("""
                    INSERT INTO appointments (patient_id, doctor_id, location_id, appointment_date)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, (patient_id, int(doctor_id), int(location_id), appointment_datetime))
                appointment_id = cur.fetchone()["id"]

                cur.execute("""
                    INSERT INTO surveys (
                        appointment_id, life_anamnesis, disease_anamnesis, complaints,
                        heredity, heredity_description, comorbidities
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    appointment_id, life_anamnesis, disease_anamnesis, complaints,
                    heredity, heredity_description, comorbidities
                ))

                cur.execute("""
                    INSERT INTO examinations (
                        appointment_id, skin_condition, edema_location, systolic_pressure,
                        diastolic_pressure, bp_note, heart_rate, height, weight, bmi
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    appointment_id, skin_condition, edema_location, systolic_pressure,
                    diastolic_pressure, bp_note, heart_rate, height, weight, bmi
                ))

                # 5. ОАК — сохраняем все добавленные врачом новые столбцы
                cbc_value_lists = [
                    hemoglobin_list,
                    erythrocytes_list,
                    leukocytes_list,
                    platelets_list,
                    esr_list,
                    mcv_list,
                    hematocrit_list
                ]

                max_cbc_count = max(
                    len(cbc_dates),
                    len(hemoglobin_list),
                    len(erythrocytes_list),
                    len(leukocytes_list),
                    len(platelets_list),
                    len(esr_list),
                    len(mcv_list),
                    len(hematocrit_list)
                )

                for index in range(max_cbc_count):
                    if has_any_indexed_value(cbc_value_lists, index):
                        cur.execute("""
                            INSERT INTO cbc_results (
                                appointment_id, investigation_date, hemoglobin, erythrocytes,
                                leukocytes, platelets, esr, mcv, hematocrit
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(cbc_dates, index, appointment_datetime.date()),
                            value_at(hemoglobin_list, index),
                            value_at(erythrocytes_list, index),
                            value_at(leukocytes_list, index),
                            value_at(platelets_list, index),
                            value_at(esr_list, index),
                            value_at(mcv_list, index),
                            value_at(hematocrit_list, index)
                        ))


                # 6. Биохимия — сохраняем все добавленные врачом новые столбцы
                biochemistry_value_lists = [
                    creatinine_list,
                    urea_list,
                    uric_acid_list,
                    glucose_list,
                    total_protein_list,
                    albumin_list,
                    potassium_list,
                    calcium_list,
                    phosphorus_list,
                    ferritin_list,
                    ptg_list
                ]

                max_biochemistry_count = max(
                    len(biochemistry_dates),
                    len(creatinine_list),
                    len(urea_list),
                    len(uric_acid_list),
                    len(glucose_list),
                    len(total_protein_list),
                    len(albumin_list),
                    len(potassium_list),
                    len(calcium_list),
                    len(phosphorus_list),
                    len(ferritin_list),
                    len(ptg_list)
                )

                new_biochemistry_for_metrics = []

                for index in range(max_biochemistry_count):
                    if has_any_indexed_value(biochemistry_value_lists, index):
                        current_biochemistry_date = date_at(
                            biochemistry_dates,
                            index,
                            appointment_datetime.date()
                        )

                        current_creatinine = value_at(creatinine_list, index)

                        cur.execute("""
                            INSERT INTO biochemistry_results (
                                appointment_id, investigation_date, creatinine, urea, uric_acid,
                                glucose, total_protein, albumin, potassium, calcium,
                                phosphorus, ferritin, ptg
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            current_biochemistry_date,
                            current_creatinine,
                            value_at(urea_list, index),
                            value_at(uric_acid_list, index),
                            value_at(glucose_list, index),
                            value_at(total_protein_list, index),
                            value_at(albumin_list, index),
                            value_at(potassium_list, index),
                            value_at(calcium_list, index),
                            value_at(phosphorus_list, index),
                            value_at(ferritin_list, index),
                            value_at(ptg_list, index)
                        ))

                        if current_creatinine:
                            new_biochemistry_for_metrics.append({
                                "creatinine": current_creatinine,
                                "investigation_date": current_biochemistry_date
                            })


                # 7. ОАМ — сохраняем все добавленные врачом новые столбцы
                urinalysis_value_lists = [
                    specific_gravity_list,
                    urine_protein_list,
                    urine_leukocytes_list,
                    urine_erythrocytes_list,
                    bacteria_list
                ]

                max_urinalysis_count = max(
                    len(urinalysis_dates),
                    len(specific_gravity_list),
                    len(urine_protein_list),
                    len(urine_leukocytes_list),
                    len(urine_erythrocytes_list),
                    len(bacteria_list)
                )

                for index in range(max_urinalysis_count):
                    if has_any_indexed_value(urinalysis_value_lists, index):
                        cur.execute("""
                            INSERT INTO urinalysis_results (
                                appointment_id, investigation_date, specific_gravity,
                                protein, leukocytes, erythrocytes, bacteria
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(urinalysis_dates, index, appointment_datetime.date()),
                            value_at(specific_gravity_list, index),
                            value_at(urine_protein_list, index),
                            value_at(urine_leukocytes_list, index),
                            value_at(urine_erythrocytes_list, index),
                            value_at(bacteria_list, index)
                        ))

                # 7.1. Альбуминурия — сохраняем все добавленные врачом новые столбцы
                albuminuria_value_lists = [
                    urine_albumin_list,
                    urine_creatinine_list
                ]

                max_albuminuria_count = max(
                    len(albuminuria_dates),
                    len(urine_albumin_list),
                    len(urine_albumin_unit_list),
                    len(urine_creatinine_list),
                    len(urine_creatinine_unit_list)
                )

                for index in range(max_albuminuria_count):
                    if has_any_indexed_value(albuminuria_value_lists, index):
                        current_albumin = value_at(urine_albumin_list, index)
                        current_albumin_unit = value_at(urine_albumin_unit_list, index) or "mg_l"

                        current_creatinine = value_at(urine_creatinine_list, index)
                        current_creatinine_unit = value_at(urine_creatinine_unit_list, index) or "mmol_l"

                        if current_albumin is not None and current_creatinine is not None:
                            albuminuria_metrics = calculate_albuminuria_metrics(
                                urine_albumin=current_albumin,
                                urine_albumin_unit=current_albumin_unit,
                                urine_creatinine=current_creatinine,
                                urine_creatinine_unit=current_creatinine_unit
                            )

                            cur.execute("""
                                INSERT INTO albuminuria_results (
                                    appointment_id,
                                    investigation_date,
                                    urine_albumin,
                                    urine_albumin_unit,
                                    urine_creatinine,
                                    urine_creatinine_unit,
                                    albumin_creatinine_ratio,
                                    albuminuria_category
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                appointment_id,
                                date_at(albuminuria_dates, index, appointment_datetime.date()),
                                current_albumin,
                                current_albumin_unit,
                                current_creatinine,
                                current_creatinine_unit,
                                albuminuria_metrics["albumin_creatinine_ratio"],
                                albuminuria_metrics["albuminuria_category"]
                            ))
                
                # 8. УЗИ — сохраняем все добавленные врачом новые столбцы
                ultrasound_value_lists = [
                    left_kidney_size_list,
                    right_kidney_size_list,
                    left_parenchyma_list,
                    right_parenchyma_list,
                    ultrasound_desc_list
                ]

                max_ultrasound_count = max(
                    len(ultrasound_dates),
                    len(left_kidney_size_list),
                    len(right_kidney_size_list),
                    len(left_parenchyma_list),
                    len(right_parenchyma_list),
                    len(ultrasound_desc_list)
                )

                for index in range(max_ultrasound_count):
                    if has_any_indexed_value(ultrasound_value_lists, index):
                        cur.execute("""
                            INSERT INTO ultrasound_results (
                                appointment_id, investigation_date, left_kidney_size,
                                right_kidney_size, left_parenchyma, right_parenchyma, description
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            appointment_id,
                            date_at(ultrasound_dates, index, appointment_datetime.date()),
                            value_at(left_kidney_size_list, index),
                            value_at(right_kidney_size_list, index),
                            value_at(left_parenchyma_list, index),
                            value_at(right_parenchyma_list, index),
                            value_at(ultrasound_desc_list, index)
                        ))

                cur.execute("""
                    INSERT INTO diagnoses (appointment_id, main_diagnosis, complications, comorbidities)
                    VALUES (%s, %s, %s, %s)
                """, (appointment_id, main_diagnosis, complications, comorbidities_diag))

                cur.execute("""
                    INSERT INTO appointment_diets (appointment_id, diet, next_control_date, recommendations)
                    VALUES (%s, %s, %s, %s)
                """, (appointment_id, diet, next_control_date, recommendations))

                # Новая структурированная версия диагнозов по МКБ-10.
                # Старую таблицу diagnoses не трогаем — она сохраняется выше.

                insert_appointment_icd10_diagnosis(
                    cur=cur,
                    appointment_id=appointment_id,
                    diagnosis_type="main",
                    diagnosis_text=icd10_main_diagnosis,
                    doctor_note=icd10_main_note,
                    sort_order=1
                )

                for index, diagnosis_text in enumerate(icd10_complication_diagnoses, start=1):
                    doctor_note = value_at(icd10_complication_notes, index - 1)

                    insert_appointment_icd10_diagnosis(
                        cur=cur,
                        appointment_id=appointment_id,
                        diagnosis_type="complication",
                        diagnosis_text=diagnosis_text,
                        doctor_note=doctor_note,
                        sort_order=index
                    )

                for index, diagnosis_text in enumerate(icd10_comorbidity_diagnoses, start=1):
                    doctor_note = value_at(icd10_comorbidity_notes, index - 1)

                    insert_appointment_icd10_diagnosis(
                        cur=cur,
                        appointment_id=appointment_id,
                        diagnosis_type="comorbidity",
                        diagnosis_text=diagnosis_text,
                        doctor_note=doctor_note,
                        sort_order=index
                    )

                max_med_count = max(len(medications), len(dosages), len(schedules))

                for index in range(max_med_count):
                    medication = empty_to_none(medications[index]) if index < len(medications) else None
                    dosage = empty_to_none(dosages[index]) if index < len(dosages) else None
                    schedule = empty_to_none(schedules[index]) if index < len(schedules) else None

                    if medication or dosage or schedule:
                        cur.execute("""
                            INSERT INTO prescriptions (appointment_id, medication, dosage, schedule)
                            VALUES (%s, %s, %s, %s)
                        """, (appointment_id, medication, dosage, schedule))

                # 12. Расчёт СКФ и категории СКФ
                # Если врач добавил несколько биохимических анализов с креатинином,
                # сохраняем несколько расчётов — по одному на каждый новый креатинин.
                for metric_source in new_biochemistry_for_metrics:
                    metric_date = parse_date_or_default(
                        metric_source.get("investigation_date"),
                        appointment_datetime.date()
                    )

                    current_creatinine = metric_source.get("creatinine")

                    metrics = calculate_all_metrics(
                        creatinine_umol_l=current_creatinine,
                        birth_date=birth_date_obj,
                        appointment_date=metric_date,
                        gender=gender,
                        weight_kg=weight
                    )

                    if (
                        metrics.get("egfr_ckdepi") is not None
                        or metrics.get("crcl_cockcroft_gault") is not None
                        or metrics.get("ckd_stage") is not None
                    ):
                        cur.execute("""
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
                        """, (
                            appointment_id,
                            metric_date,
                            current_creatinine,
                            calculate_age(birth_date_obj, metric_date),
                            gender,
                            weight,
                            metrics.get("egfr_ckdepi"),
                            metrics.get("crcl_cockcroft_gault"),
                            metrics.get("ckd_stage")
                        ))
                save_ckd_prognosis_for_appointment(appointment_id, cur=cur)
            conn.commit()

        except HTTPException:
            conn.rollback()
            raise
        except Exception as error:
            conn.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Ошибка при сохранении нового приёма: {error}"
            )

    return RedirectResponse(
        url=f"/patient/{patient_id}?appointment_id={appointment_id}",
        status_code=303
    )

