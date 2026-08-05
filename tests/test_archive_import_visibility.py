from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_appointments_without_location_are_visible():
    source = read("app/repositories/appointments.py")
    assert source.count("LEFT JOIN locations l ON a.location_id = l.id") >= 4


def test_archive_fields_are_selected_for_patient_card():
    source = read("app/repositories/appointments.py")
    for field in (
        "a.diagnosis_text",
        "a.diagnosis_comment_text",
        "a.is_archive_import",
        "s.disease_anamnesis_text",
        "s.life_anamnesis_text",
    ):
        assert field in source


def test_server_limits_appointment_page_to_100_rows():
    repository = read("app/repositories/appointments.py")
    router = read("app/routers/appointment_filters.py")
    assert "min(limit, 100)" in repository
    assert "MAX_PAGE_SIZE = 100" in router
    assert 'response.headers["X-Total-Count"]' in router
    assert "count_all_appointments(filters)" in router
    assert "5000" not in router


def test_main_page_has_server_pagination_controls():
    source = read("app/templates/index.html")
    assert "const PAGE_SIZE = 100" in source
    assert 'id="appointmentsPrevBtn"' in source
    assert 'id="appointmentsNextBtn"' in source
    assert "currentPage * PAGE_SIZE" in source
    assert "X-Total-Count" in source
    assert "Показаны ${start}–${end} из ${totalAppointments}" in source


def test_patient_card_displays_archive_text_fields():
    survey = read("app/templates/patient_card/_survey.html")
    diagnoses = read("app/templates/patient_card/_diagnoses.html")
    assert "selected_appointment.life_anamnesis_text" in survey
    assert "selected_appointment.disease_anamnesis_text" in survey
    assert "selected_appointment.diagnosis_text" in diagnoses
    assert "selected_appointment.diagnosis_comment_text" in diagnoses


def test_unknown_gender_is_not_displayed_as_female():
    source = read("app/repositories/patients.py")
    assert "WHEN gender IS TRUE THEN 'Мужской'" in source
    assert "WHEN gender IS FALSE THEN 'Женский'" in source
    assert "ELSE 'Не указан'" in source
