"""
Назначение файла: импортные тесты для нового repository/db/service слоя.

Тесты проверяют, что важные старые импорты из app.database не сломались.
Они не вызывают функции, которые открывают соединение с PostgreSQL.
"""


def test_old_database_imports_still_exist():
    import app.database as database

    expected_names = [
        "get_db_connection",
        "get_all_patients",
        "get_patient_by_id",
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
        "get_patient_biochemistry_history",
        "get_patient_cbc_history",
        "get_patient_urinalysis_history",
        "get_patient_metrics_history",
        "get_patient_ultrasound_history",
        "get_patient_albuminuria_history",
        "get_appointment_ckd_prognosis",
        "get_patient_ckd_prognosis_history",
        "get_patient_card_context",
        "get_new_appointment_context",
        "get_new_patient_context",
    ]

    for name in expected_names:
        assert hasattr(database, name), name
        assert callable(getattr(database, name)), name


def test_new_modules_import_without_database_connection():
    from app.db import connection
    from app.repositories import appointments, ckd_prognosis, lab_history, patients, reference_data
    from app.services import appointment_form_context_service, patient_card_context_service

    assert callable(connection.get_db_connection)
    assert callable(patients.get_patient_by_id)
    assert callable(appointments.get_appointment_full_data)
    assert callable(reference_data.get_doctors)
    assert callable(lab_history.get_patient_cbc_history)
    assert callable(ckd_prognosis.get_appointment_ckd_prognosis)
    assert callable(patient_card_context_service.get_patient_card_context)
    assert callable(appointment_form_context_service.get_new_appointment_context)
