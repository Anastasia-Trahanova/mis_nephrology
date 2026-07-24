"""
Назначение файла: контрактные тесты автоподстановки диагноза по стадии ХБП.

Что тестируется:
- свободные текстовые диагнозы удалены из формы заключения;
- основной диагноз прошлого приёма подставляется прямо в поле врача;
- техническое предложение по стадии ХБП ставится первым осложнением;
- системное осложнение обновляется при изменении креатинина;
- перенесённые диагнозы выделяются отдельно от системного осложнения;
- жёлтая подсветка снимается после редактирования перенесённого диагноза;
- щелчок по перенесённому диагнозу выделяет текст целиком;
- таблица diagnoses удаляется миграцией и больше не используется в коде сохранения.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_conclusion_no_longer_has_free_text_diagnosis_fields():
    content = read("app/templates/appointment_form/_conclusion.html")

    assert 'name="main_diagnosis"' not in content
    assert 'name="complications"' not in content
    assert 'name="comorbidities_diag"' not in content
    assert '{% include "icd10_diagnosis_block.html" %}' in content


def test_ckd_stage_diagnosis_is_first_live_complication():
    block = read("app/templates/icd10_diagnosis_block.html")
    form_js = read("app/static/js/history_studies_form.js")
    new_patient = read("app/templates/new_patient.html")
    new_appointment = read("app/templates/new_appointment.html")

    # Исходный блок по-прежнему содержит поиск МКБ-10 и расчёт диагноза
    # по текущему креатинину. Слой history_studies_form.js меняет только
    # место отображения системного предложения.
    assert 'name="icd10_main_diagnosis"' in block
    assert 'data-autofill-ckd-main="true"' in block
    assert "updateMainIcd10DiagnosisFromCkdStage" in block

    assert "prefillMainDiagnosisFromPreviousVisit" in form_js
    assert "extractPreviousMainDiagnosis" in form_js
    assert 'input.classList.add("prefilled-field")' in form_js

    assert "ensureAutomaticComplicationInput" in form_js
    assert "container.prepend(row)" in form_js
    assert "updateAutomaticCkdComplication" in form_js
    assert "scheduleDiagnosisSync" in form_js
    assert 'input.classList.remove("prefilled-field")' in form_js
    assert "Осложнение основного диагноза проставляется автоматически" in form_js

    # Изменение креатинина и даты биохимии должно запускать обновление
    # первого системного осложнения.
    assert '[name="creatinine"]' in form_js
    assert '[name="biochemistry_investigation_date"]' in form_js
    assert "scheduleDiagnosisSync();" in form_js

    script_tag = '<script src="/static/js/history_studies_form.js"></script>'
    assert script_tag in new_patient
    assert script_tag in new_appointment


def test_parser_and_save_service_do_not_use_text_diagnoses_section():
    parser = read("app/services/appointment_form_parser.py")
    save_service = read("app/services/appointment_save_service.py")
    diagnoses_repo = read("app/repositories/diagnoses.py")

    assert '"diagnoses"' not in parser
    assert 'main_diagnosis' not in parser
    assert 'comorbidities_diag' not in parser

    assert 'insert_text_diagnoses' not in save_service
    assert 'save_diagnoses' not in save_service
    assert 'appointment_data["diagnoses"]' not in save_service

    assert 'insert_text_diagnoses' not in diagnoses_repo
    assert 'INSERT INTO diagnoses' not in diagnoses_repo


def test_appointments_repository_does_not_use_dropped_text_diagnoses_table():
    content = read("app/repositories/appointments.py")
    normalized = " ".join(content.lower().split())

    # Диагнозы МКБ-10 читаются отдельным repository. Старую таблицу diagnoses
    # нельзя возвращать ни через JOIN, ни через прямой SELECT.
    assert "left join diagnoses" not in normalized
    assert "from diagnoses" not in normalized


def test_drop_text_diagnoses_alembic_migration_exists_in_versions():
    content = read("migrations/versions/0004_drop_text_diagnoses.py")
    normalized = " ".join(content.lower().split())

    assert 'revision = "0004_drop_text_diagnoses"' in content
    assert 'down_revision = "0003_kdigo_risk_sources"' in content
    assert "drop table if exists diagnoses cascade" in normalized
    assert "op.create_table" in content
    assert '"diagnoses"' in content


def test_prefilled_diagnosis_is_selected_and_confirmed_on_edit():
    form_js = read("app/static/js/history_studies_form.js")

    assert "isPrefilledDiagnosisInput" in form_js
    assert "selectWholePrefilledDiagnosis" in form_js
    assert 'document.addEventListener("pointerdown", selectWholePrefilledDiagnosis)' in form_js
    assert "target.select();" in form_js

    assert "confirmEditedPrefilledValue" in form_js
    assert 'target.classList.remove("prefilled-field")' in form_js
    assert "confirmEditedPrefilledValue(target);" in form_js
