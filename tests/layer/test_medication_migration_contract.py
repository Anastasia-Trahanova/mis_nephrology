"""Проверяет согласованность миграции 0015 с рабочим модулем групп."""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.medication_therapy import MEDICATION_THERAPY_GROUPS


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations" / "versions" / "0015_grouped_prescriptions_and_seed.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_0015_grouped_prescriptions", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_migration_groups_match_runtime_groups_exactly():
    migration = _load_migration()
    runtime_groups = tuple(group["value"] for group in MEDICATION_THERAPY_GROUPS)

    assert migration.THERAPY_GROUPS == runtime_groups
    assert set(migration.PRESCRIPTION_VARIANTS) == set(runtime_groups)


def test_migration_dictionary_matches_unique_runtime_suggestions():
    migration = _load_migration()
    seeded_names = [row[0] for row in migration.MEDICATIONS]
    runtime_names = {
        name
        for group in MEDICATION_THERAPY_GROUPS
        for name in group["medications"]
    }

    assert len(seeded_names) == 27
    assert len(set(seeded_names)) == 27
    assert set(seeded_names) == runtime_names
    assert [row[2] for row in migration.MEDICATIONS] == sorted(row[2] for row in migration.MEDICATIONS)


def test_every_seed_variant_belongs_to_its_group_and_is_complete():
    migration = _load_migration()
    runtime_by_group = {
        group["value"]: set(group["medications"])
        for group in MEDICATION_THERAPY_GROUPS
    }

    for group, variants in migration.PRESCRIPTION_VARIANTS.items():
        assert variants
        for medication, dosage, schedule in variants:
            assert medication in runtime_by_group[group]
            assert medication.strip()
            assert dosage.strip()
            assert schedule.strip()
