"""
Назначение файла:
Контрактные тесты раздела исследований из утверждённой схемы истории болезни.

Что проверяется:
- миграция 0011 добавляет только согласованные поля;
- форма сохраняет старые таблицы и новый порядок разделов;
- в карточке явно разделены исследования и заключение;
- новые свободные поля подключены к форме и карточке;
- лекарства не переносятся и не переписываются этим этапом.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_migration_adds_daily_albumin_and_additional_studies_only():
    content = read("migrations/versions/0011_history_studies_fields.py")

    assert 'revision = "0011_history_studies_fields"' in content
    assert 'down_revision = "0010_remove_heredity_flag"' in content
    assert '"daily_albumin_excretion"' in content
    assert '"appointment_additional_studies"' in content
    assert '"other_laboratory_studies"' in content
    assert '"other_instrumental_studies"' in content

    assert '"cbc_results"' not in content
    assert '"urinalysis_results"' not in content
    assert '"biochemistry_results"' not in content
    assert '"prescriptions"' not in content


def test_primary_and_repeat_forms_follow_history_studies_order():
    expected = [
        'appointment_form/_cbc.html',
        'appointment_form/_urinalysis.html',
        'appointment_form/_biochemistry.html',
        'appointment_form/_metrics.html',
        'appointment_form/_albuminuria.html',
        'appointment_form/_other_laboratory_studies.html',
        'appointment_form/_ultrasound.html',
        'appointment_form/_other_instrumental_studies.html',
        'appointment_form/_conclusion.html',
    ]

    for template in ("app/templates/new_patient.html", "app/templates/new_appointment.html"):
        content = read(template)
        assert "Результаты проведённых ранее исследований" in content

        positions = [content.index(item) for item in expected]
        assert positions == sorted(positions)


def test_albuminuria_and_ultrasound_form_fields_match_scheme():
    albuminuria = read("app/templates/appointment_form/_albuminuria.html")
    ultrasound = read("app/templates/appointment_form/_ultrasound.html")

    assert 'name="daily_albumin_excretion"' in albuminuria
    assert "Экскреция альбумина суточная, мг/сут" in albuminuria

    expected_ultrasound_labels = [
        "Правая почка, размер, мм",
        "Паренхима справа, мм",
        "Левая почка, размер, мм",
        "Паренхима слева, мм",
        "Дополнительно",
    ]
    positions = [ultrasound.index(label) for label in expected_ultrasound_labels]
    assert positions == sorted(positions)


def test_patient_card_separates_studies_and_conclusion():
    card = read("app/templates/patient_card.html")

    studies_position = card.index("Результаты проведённых ранее исследований")
    conclusion_position = card.index(">Заключение<")
    kdigo_position = card.index('patient_card/_ckd_prognosis.html')
    diagnoses_position = card.index('patient_card/_diagnoses.html')
    prescriptions_position = card.index('patient_card/_prescriptions.html')

    assert studies_position < conclusion_position
    assert conclusion_position < kdigo_position < diagnoses_position < prescriptions_position

    assert "patient_card/_other_laboratory_studies.html" in card
    assert "patient_card/_other_instrumental_studies.html" in card


def test_ckd_stage_label_is_updated_without_changing_metric_fields():
    form_js = read("app/static/js/history_studies_form.js")
    card_metrics = read("app/templates/patient_card/_metrics_history.html")

    assert "Стадия ХБП по СКФ" in form_js
    assert "Стадия ХБП по СКФ" in card_metrics
    assert "item.egfr_ckdepi" in card_metrics
    assert "item.crcl_cockcroft_gault" in card_metrics
    assert "item.ckd_stage" in card_metrics


def test_medication_partial_is_not_replaced_by_this_contract():
    card = read("app/templates/patient_card.html")
    form_conclusion = read("app/templates/appointment_form/_conclusion.html")

    assert 'patient_card/_prescriptions.html' in card
    assert 'name="medication"' in form_conclusion
    assert 'name="dosage"' in form_conclusion
    assert 'name="schedule"' in form_conclusion
