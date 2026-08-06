# Контракт итоговой схемы регистра ХБП в базе данных 2.0.

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_SQL = ROOT / "database" / "01 создание таблиц.sql"
CONSTRAINTS_SQL = ROOT / "database" / "02 настройка связей ключей и ограничений.sql"
USERS_SQL = ROOT / "database" / "04 справочник больницы и пользователи.sql"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_registry_tables_and_constraints_are_in_final_schema():
    schema = _read(SCHEMA_SQL)
    constraints = _read(CONSTRAINTS_SQL)

    assert "CREATE TABLE IF NOT EXISTS ckd_registry_entries" in schema
    assert "CREATE TABLE IF NOT EXISTS ckd_registry_outcomes" in schema
    assert "uq_ckd_registry_entries_patient" in constraints
    assert "ck_ckd_registry_entries_closure" in constraints


def test_management_roles_and_named_users_are_in_final_sql():
    constraints = _read(CONSTRAINTS_SQL)
    users_sql = _read(USERS_SQL)

    for role in ("chief_physician", "department_head"):
        assert role in constraints
        assert role in users_sql

    assert "lobanova_n" in users_sql
    assert "vozova_a" in users_sql


def test_registry_outcomes_are_historical():
    schema = _read(SCHEMA_SQL)
    constraints = _read(CONSTRAINTS_SQL)

    for outcome in (
        "rrt_hemodialysis",
        "rrt_peritoneal_dialysis",
        "rrt_kidney_transplant",
        "death",
    ):
        assert outcome in constraints

    for column in ("registry_entry_id", "outcome_date", "created_by_user_id"):
        assert column in schema
