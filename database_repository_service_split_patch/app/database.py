"""
Назначение файла: фасад совместимости старого app.database.

Раньше этот файл содержал всё сразу: подключение к БД, SQL-запросы,
истории анализов, справочники, прогноз ХБП и сборку context для страниц.
Теперь логика разнесена по понятным слоям:

- app/db/connection.py — техническое подключение к PostgreSQL;
- app/repositories/reference_data.py — справочники;
- app/repositories/patients.py — пациенты;
- app/repositories/appointments.py — приёмы;
- app/repositories/lab_history.py — чтение историй анализов;
- app/repositories/ckd_prognosis.py — сохранённый прогноз ХБП;
- app/services/patient_card_context_service.py — context карточки пациента;
- app/services/appointment_form_context_service.py — context форм.

Зачем файл оставлен:
старые роуты и сервисы всё ещё импортируют функции из app.database.
Чтобы не ломать проект одним большим рефакторингом, app.database теперь
только переэкспортирует функции из новых модулей.

Что редактировать здесь:
- только список импортов, если новая функция переезжает в новый модуль.

Что не редактировать здесь:
- SQL;
- медицинские расчёты;
- HTML context;
- подключение к БД.
"""

from app.db.connection import (
    DATABASE_URL,
    DB_POOL_MAX_CONN,
    DB_POOL_MIN_CONN,
    PooledConnection,
    get_db_connection,
)
from app.repositories.appointments import (
    _fetch_appointment_diet,
    _fetch_appointment_full_data,
    _fetch_appointment_medications,
    _fetch_last_appointment_data,
    _fetch_patient_appointments,
    create_appointment,
    get_all_appointments,
    get_appointment_diet,
    get_appointment_full_data,
    get_appointment_medications,
    get_last_appointment_data,
    get_patient_appointments,
)
from app.repositories.ckd_prognosis import (
    _fetch_appointment_ckd_prognosis,
    _fetch_latest_albuminuria_category_for_prognosis,
    _fetch_latest_gfr_category_for_prognosis,
    _fetch_patient_ckd_prognosis_history,
    get_appointment_ckd_prognosis,
    get_patient_ckd_prognosis_history,
    recalculate_ckd_prognosis_for_appointment,
    save_ckd_prognosis_for_appointment,
)
from app.repositories.lab_history import (
    _fetch_patient_albuminuria_history,
    _fetch_patient_biochemistry_history,
    _fetch_patient_cbc_history,
    _fetch_patient_metrics_history,
    _fetch_patient_ultrasound_history,
    _fetch_patient_urinalysis_history,
    get_patient_albuminuria_history,
    get_patient_biochemistry_history,
    get_patient_cbc_history,
    get_patient_metrics_history,
    get_patient_ultrasound_history,
    get_patient_urinalysis_history,
    save_calculated_metrics,
)
from app.repositories.patients import (
    _fetch_patient_by_id,
    create_patient,
    get_all_patients,
    get_patient_by_id,
    get_patient_contact_info,
    get_patient_for_appointment,
)
from app.repositories.reference_data import (
    _fetch_appointment_icd10_diagnoses,
    _fetch_branches,
    _fetch_doctors,
    _fetch_icd10_diagnoses,
    _fetch_locations_by_branch,
    _fetch_medications_dictionary,
    get_appointment_icd10_diagnoses,
    get_branches,
    get_doctor_locations,
    get_doctors,
    get_doctors_for_filter,
    get_icd10_diagnoses,
    get_location_info,
    get_locations_by_branch,
    get_locations_for_filter,
    get_medications_dictionary,
)
from app.services.appointment_form_context_service import (
    _group_icd10_diagnoses_for_form,
    get_new_appointment_context,
    get_new_patient_context,
)
from app.services.patient_card_context_service import get_patient_card_context

__all__ = [
    "DATABASE_URL",
    "DB_POOL_MAX_CONN",
    "DB_POOL_MIN_CONN",
    "PooledConnection",
    "get_db_connection",
    "create_patient",
    "get_patient_for_appointment",
    "get_all_patients",
    "get_patient_by_id",
    "get_patient_contact_info",
    "create_appointment",
    "get_all_appointments",
    "get_patient_appointments",
    "get_appointment_full_data",
    "get_last_appointment_data",
    "get_appointment_medications",
    "get_appointment_diet",
    "get_branches",
    "get_locations_by_branch",
    "get_doctors",
    "get_doctors_for_filter",
    "get_locations_for_filter",
    "get_doctor_locations",
    "get_location_info",
    "get_icd10_diagnoses",
    "get_appointment_icd10_diagnoses",
    "get_medications_dictionary",
    "get_patient_biochemistry_history",
    "get_patient_cbc_history",
    "get_patient_urinalysis_history",
    "get_patient_metrics_history",
    "get_patient_ultrasound_history",
    "get_patient_albuminuria_history",
    "save_calculated_metrics",
    "save_ckd_prognosis_for_appointment",
    "recalculate_ckd_prognosis_for_appointment",
    "get_appointment_ckd_prognosis",
    "get_patient_ckd_prognosis_history",
    "get_patient_card_context",
    "get_new_appointment_context",
    "get_new_patient_context",
]
