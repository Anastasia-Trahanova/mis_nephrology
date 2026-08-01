from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "versions" / "0014_ckd_registry_and_management_roles.py"
USERS_SQL = ROOT / "database" / "07_create_doctor_users.sql"


def test_registry_migration_chain_and_tables():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "0014_ckd_registry_roles"' in source
    assert 'down_revision = "0013_schedule_stage2"' in source
    assert '"ckd_registry_entries"' in source
    assert '"ckd_registry_outcomes"' in source
    assert 'uq_ckd_registry_entries_patient' in source


def test_management_roles_and_named_users():
    migration = MIGRATION.read_text(encoding="utf-8")
    users_sql = USERS_SQL.read_text(encoding="utf-8")
    for role in ("chief_physician", "department_head"):
        assert role in migration
        assert role in users_sql
    assert "lobanova_n" in migration
    assert "chief_physician" in users_sql
    assert "vozova_a" in migration
    assert "department_head" in users_sql


def test_registry_outcomes_are_historical():
    source = MIGRATION.read_text(encoding="utf-8")
    for outcome in (
        "rrt_hemodialysis",
        "rrt_peritoneal_dialysis",
        "rrt_kidney_transplant",
        "death",
    ):
        assert outcome in source
    assert "registry_entry_id" in source
    assert "outcome_date" in source
    assert "created_by_user_id" in source
