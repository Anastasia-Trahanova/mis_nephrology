"""
Что тестируется:
- свободные текстовые диагнозы удалены из формы заключения;
- основной диагноз МКБ-10 автозаполняется по категории СКФ;
- врач может редактировать основной диагноз вручную;
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


def test_icd10_main_diagnosis_is_editable_and_autofilled_from_ckd_stage():
    content = read("app/templates/icd10_diagnosis_block.html")

    assert 'name="icd10_main_diagnosis"' in content
    assert 'readonly' not in content
    assert 'disabled' not in content
    assert 'data-autofill-ckd-main="true"' in content
    assert 'updateMainIcd10DiagnosisFromCkdStage' in content
    assert 'getIcd10CodeForCkdStage' in content
    assert '"С2": "N18.2"' in content
    assert '"С3а": "N18.3"' in content
    assert '"С3б": "N18.3"' in content
    assert 'Врач может изменить диагноз вручную' in content
    assert 'В прошлом приёме' in content


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
