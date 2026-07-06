"""
Проверяет контракт миграции KDIGO без подключения к БД.

Этот тест нужен как быстрый предохранитель: он подтверждает, что migration-файл
не потерял ключевые части новой модели ckd_prognosis_results.
Саму БД тест не меняет и не требует PostgreSQL.
"""

from pathlib import Path


MIGRATION_PATH = Path("migrations/versions/0003_kdigo_risk_assessment_sources.py")


def _migration_text() -> str:
    assert MIGRATION_PATH.exists(), f"Не найден файл миграции: {MIGRATION_PATH}"
    return MIGRATION_PATH.read_text(encoding="utf-8")


def test_kdigo_migration_has_correct_revision_chain():
    text = _migration_text()

    assert 'revision = "0003_kdigo_risk_sources"' in text
    assert 'down_revision = "0002_bmi_medications"' in text


def test_kdigo_migration_removes_one_result_per_appointment_limit():
    text = _migration_text()

    assert "DROP CONSTRAINT IF EXISTS uq_ckd_prognosis_appointment" in text
    assert "uq_ckd_prognosis_active_source_pair" in text
    assert "appointment_id, gfr_metric_id, albuminuria_result_id" in text


def test_kdigo_migration_stores_strict_source_data():
    text = _migration_text()

    required_columns = [
        "gfr_metric_id",
        "albuminuria_result_id",
        "gfr_investigation_date",
        "albuminuria_investigation_date",
        "gfr_source_type",
        "albuminuria_source_type",
        "source_interval_days",
        "calculation_status",
        "display_order",
        "is_active",
    ]

    for column_name in required_columns:
        assert column_name in text


def test_kdigo_migration_keeps_backward_compatibility_trigger():
    text = _migration_text()

    assert "CREATE OR REPLACE FUNCTION set_ckd_prognosis_source_fields" in text
    assert "CREATE TRIGGER trg_set_ckd_prognosis_source_fields" in text
    assert "BEFORE INSERT OR UPDATE ON ckd_prognosis_results" in text


def test_kdigo_migration_has_calculated_source_check():
    text = _migration_text()

    assert "chk_ckd_prognosis_calculated_sources" in text
    assert "calculation_status <> 'calculated'" in text
    assert "gfr_metric_id IS NOT NULL" in text
    assert "albuminuria_result_id IS NOT NULL" in text
    assert "combined_category IS NOT NULL" in text
    assert "prognosis_level IS NOT NULL" in text
