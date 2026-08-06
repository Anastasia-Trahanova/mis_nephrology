# Проверяет итоговый контракт KDIGO в SQL-файлах базы данных 2.0.

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = ROOT / "database" / "01 создание таблиц.sql"
CONSTRAINTS_SQL = ROOT / "database" / "02 настройка связей ключей и ограничений.sql"


def _schema_text() -> str:
    return SCHEMA_SQL.read_text(encoding="utf-8")


def _constraints_text() -> str:
    return CONSTRAINTS_SQL.read_text(encoding="utf-8")


def test_kdigo_final_schema_contains_prognosis_table():
    text = _schema_text()
    assert "CREATE TABLE IF NOT EXISTS ckd_prognosis_results" in text
    assert "gfr_metric_id INTEGER" in text
    assert "albuminuria_result_id INTEGER" in text


def test_kdigo_final_schema_removes_one_result_per_appointment_limit():
    text = _constraints_text()
    normalized = "".join(text.split())

    assert "CONSTRAINT uq_ckd_prognosis_appointment" not in text
    assert "CREATEUNIQUEINDEXuq_ckd_prognosis_active_source_pair" in normalized
    assert "(appointment_id,gfr_metric_id,albuminuria_result_id)" in normalized


def test_kdigo_final_schema_stores_strict_source_data():
    text = _schema_text()
    required_columns = (
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
    )

    for column_name in required_columns:
        assert column_name in text


def test_kdigo_final_constraints_keep_source_compatibility_trigger():
    text = _constraints_text()
    assert "CREATE OR REPLACE FUNCTION set_ckd_prognosis_source_fields" in text
    assert "CREATE TRIGGER trg_set_ckd_prognosis_source_fields" in text
    assert "BEFORE INSERT OR UPDATE ON ckd_prognosis_results" in text


def test_kdigo_final_constraints_require_calculated_sources():
    text = _constraints_text()
    assert "chk_ckd_prognosis_calculated_sources" in text
    assert "calculation_status <> 'calculated'" in text
    assert "gfr_metric_id IS NOT NULL" in text
    assert "albuminuria_result_id IS NOT NULL" in text
    assert "combined_category IS NOT NULL" in text
    assert "prognosis_level IS NOT NULL" in text
