"""
Назначение файла: защита порядка полей верхней части формы на втором этапе.

Тест не проверяет оформление и не требует браузера. Он гарантирует, что:
- медицинские разделы идут в утверждённом порядке;
- поля внутри анамнеза и осмотра не переставлены;
- блок АД сохраняет примечание bp_note;
- блок отёков сохраняет прежние checkbox-имена;
- старые checkbox кожи отсутствуют;
- в паспортной части присутствует телефон;
- изменения не требуют отдельного CSS-файла.
"""

from pathlib import Path


TEMPLATES = Path("app/templates")


def _assert_in_order(text: str, markers: list[str]) -> None:
    positions = [text.index(marker) for marker in markers]
    assert positions == sorted(positions), markers


def test_survey_fields_follow_approved_order():
    text = (TEMPLATES / "appointment_form/_survey.html").read_text(encoding="utf-8")
    _assert_in_order(
        text,
        [
            'name="complaints"',
            'name="education_and_professional_history"',
            'name="housing_conditions"',
            'name="past_diseases"',
            'name="habitual_intoxications"',
            'name="gynecological_history"',
            'name="heredity"',
            'name="heredity_description"',
            'name="family_life"',
            'name="allergological_history"',
            'name="epidemiological_history"',
            'name="insurance_history"',
            'name="disease_onset"',
            'name="disease_course"',
        ],
    )


def test_examination_fields_follow_approved_order_and_keep_bp_edema():
    text = (TEMPLATES / "appointment_form/_examination.html").read_text(encoding="utf-8")
    _assert_in_order(
        text,
        [
            'name="general_condition"',
            'name="consciousness"',
            'name="bed_position"',
            'name="bed_position_details"',
            'name="body_build"',
            'name="height"',
            'name="weight"',
            'name="bmi"',
            'name="constitution_type"',
            'name="skin_and_mucous_membranes"',
            'name="edema_peripheral"',
            'name="edema_serositis"',
            'name="lymph_nodes"',
            'name="thyroid_gland"',
            'name="musculoskeletal_system"',
            'name="body_temperature"',
            'name="systolic_pressure"',
            'name="diastolic_pressure"',
            'name="bp_note"',
            'name="heart_rate"',
            'name="veins_condition"',
            'name="lung_auscultation"',
            'name="abdomen"',
            'name="kidney_palpation"',
            'name="kidney_palpation_details"',
            'name="pasternatsky_result"',
            'name="pasternatsky_side"',
        ],
    )
    assert 'name="skin_color"' not in text
    assert 'name="skin_moisture"' not in text
    assert 'name="skin_rash"' not in text
    assert 'name="bp_note"' in text


def test_passport_sections_have_phone_and_stage2_adds_no_css_file():
    new_patient = (TEMPLATES / "new_patient.html").read_text(encoding="utf-8")
    new_appointment = (TEMPLATES / "new_appointment.html").read_text(encoding="utf-8")

    assert "Паспортная часть" in new_patient
    assert "Паспортная часть" in new_appointment
    assert 'name="phone"' in new_patient
    assert "patient.phone" in new_appointment
    assert not Path("app/static/css/07_stage2_previsit.css").exists()
