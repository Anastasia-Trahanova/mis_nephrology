from __future__ import annotations

from datetime import date, timedelta

import pytest

import app.repositories.ckd_prognosis as repo


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))


def _gfr(source_id: int, category: str, when: date):
    return {
        "id": source_id,
        "investigation_date": when,
        "category": category,
        "source_type": "current_appointment",
    }


def _alb(source_id: int, category: str, when: date):
    return {
        "id": source_id,
        "investigation_date": when,
        "category": category,
        "source_type": "current_appointment",
    }


def _patch_meta(monkeypatch, *, patient_id=10, appointment_date=date(2026, 8, 7)):
    monkeypatch.setattr(
        repo,
        "_fetch_appointment_patient_and_date",
        lambda cur, appointment_id: {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "appointment_date": appointment_date,
        },
    )


def test_repository_builds_cartesian_product_for_two_by_two_current_sources(monkeypatch):
    when = date(2026, 8, 7)
    _patch_meta(monkeypatch, appointment_date=when)
    monkeypatch.setattr(
        repo,
        "_fetch_current_gfr_sources",
        lambda cur, appointment_id: [_gfr(101, "С2", when), _gfr(102, "С5", when)],
    )
    monkeypatch.setattr(
        repo,
        "_fetch_current_albuminuria_sources",
        lambda cur, appointment_id: [_alb(201, "A1", when), _alb(202, "A3", when)],
    )

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    assert len(result) == 4
    assert {(item["gfr_metric_id"], item["albuminuria_result_id"]) for item in result} == {
        (101, 201),
        (101, 202),
        (102, 201),
        (102, 202),
    }
    assert {item["selection_key"] for item in result} == {
        "gfr:current:0||albuminuria:current:0",
        "gfr:current:0||albuminuria:current:1",
        "gfr:current:1||albuminuria:current:0",
        "gfr:current:1||albuminuria:current:1",
    }


def test_repository_current_selection_ordinals_follow_insert_ids_not_dates(monkeypatch):
    later = date(2026, 8, 7)
    earlier = date(2026, 8, 6)
    _patch_meta(monkeypatch, appointment_date=later)

    # Simulate SQL returning date order; the repository must re-sort by id so
    # selection_key keeps the same order as the form/live preview.
    monkeypatch.setattr(
        repo,
        "_fetch_current_gfr_sources",
        lambda cur, appointment_id: [_gfr(102, "С5", earlier), _gfr(101, "С2", later)],
    )
    monkeypatch.setattr(
        repo,
        "_fetch_current_albuminuria_sources",
        lambda cur, appointment_id: [_alb(202, "A3", earlier), _alb(201, "A1", later)],
    )

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    by_key = {item["selection_key"]: item for item in result}
    assert by_key["gfr:current:0||albuminuria:current:0"]["gfr_metric_id"] == 101
    assert by_key["gfr:current:0||albuminuria:current:0"]["albuminuria_result_id"] == 201
    assert by_key["gfr:current:1||albuminuria:current:1"]["gfr_metric_id"] == 102
    assert by_key["gfr:current:1||albuminuria:current:1"]["albuminuria_result_id"] == 202


def test_repository_uses_previous_albuminuria_for_each_new_gfr(monkeypatch):
    when = date(2026, 8, 7)
    _patch_meta(monkeypatch, appointment_date=when)
    monkeypatch.setattr(
        repo,
        "_fetch_current_gfr_sources",
        lambda cur, appointment_id: [_gfr(101, "С2", when), _gfr(102, "С5", when)],
    )
    monkeypatch.setattr(repo, "_fetch_current_albuminuria_sources", lambda cur, appointment_id: [])
    monkeypatch.setattr(
        repo,
        "_fetch_latest_previous_albuminuria_source",
        lambda cur, patient_id, before_or_on, current_appointment_id: {
            "id": 301,
            "investigation_date": when - timedelta(days=5),
            "category": "A2",
            "source_type": "previous_appointment",
        },
    )

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    assert len(result) == 2
    assert {item["gfr_metric_id"] for item in result} == {101, 102}
    assert {item["albuminuria_result_id"] for item in result} == {301}
    assert all(item["albuminuria_source_type"] == "previous_appointment" for item in result)


def test_repository_uses_previous_gfr_for_each_new_albuminuria(monkeypatch):
    when = date(2026, 8, 7)
    _patch_meta(monkeypatch, appointment_date=when)
    monkeypatch.setattr(repo, "_fetch_current_gfr_sources", lambda cur, appointment_id: [])
    monkeypatch.setattr(
        repo,
        "_fetch_current_albuminuria_sources",
        lambda cur, appointment_id: [_alb(201, "A1", when), _alb(202, "A3", when)],
    )
    monkeypatch.setattr(
        repo,
        "_fetch_latest_previous_gfr_source",
        lambda cur, patient_id, before_or_on, current_appointment_id: {
            "id": 401,
            "investigation_date": when - timedelta(days=5),
            "category": "С3а",
            "source_type": "previous_appointment",
        },
    )

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    assert len(result) == 2
    assert {item["gfr_metric_id"] for item in result} == {401}
    assert {item["albuminuria_result_id"] for item in result} == {201, 202}
    assert all(item["gfr_source_type"] == "previous_appointment" for item in result)


def test_repository_does_not_create_kdigo_when_current_visit_has_no_new_sources(monkeypatch):
    _patch_meta(monkeypatch)
    monkeypatch.setattr(repo, "_fetch_current_gfr_sources", lambda cur, appointment_id: [])
    monkeypatch.setattr(repo, "_fetch_current_albuminuria_sources", lambda cur, appointment_id: [])

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    assert result == []


def test_repository_omits_stale_pair_from_persistable_candidates(monkeypatch):
    current = date(2026, 8, 7)
    _patch_meta(monkeypatch, appointment_date=current)
    monkeypatch.setattr(
        repo,
        "_fetch_current_gfr_sources",
        lambda cur, appointment_id: [_gfr(101, "С5", current)],
    )
    monkeypatch.setattr(repo, "_fetch_current_albuminuria_sources", lambda cur, appointment_id: [])
    monkeypatch.setattr(
        repo,
        "_fetch_latest_previous_albuminuria_source",
        lambda cur, patient_id, before_or_on, current_appointment_id: {
            "id": 301,
            "investigation_date": current - timedelta(days=91),
            "category": "A2",
            "source_type": "previous_appointment",
        },
    )

    result = repo.build_kdigo_assessments_for_appointment(FakeCursor(), 55)

    assert result == []


def test_save_repository_persists_only_explicitly_selected_pair(monkeypatch):
    cursor = FakeCursor()
    assessments = [
        {"selection_key": "pair-a", "appointment_id": 55},
        {"selection_key": "pair-b", "appointment_id": 55},
    ]
    inserted = []
    monkeypatch.setattr(
        repo,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id, excluded_pairs=None: list(assessments),
    )
    monkeypatch.setattr(
        repo,
        "_insert_kdigo_assessment",
        lambda cur, assessment: inserted.append(assessment) or assessment,
    )

    saved = repo.save_ckd_prognosis_for_appointment(55, cur=cursor, selected_pair="pair-b")

    assert saved == [assessments[1]]
    assert inserted == [assessments[1]]
    assert any("DELETE FROM ckd_prognosis_results" in query for query, _ in cursor.executed)


def test_save_repository_rejects_unknown_selected_pair_before_deleting_existing_rows(monkeypatch):
    cursor = FakeCursor()
    monkeypatch.setattr(
        repo,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id, excluded_pairs=None: [
            {"selection_key": "pair-a", "appointment_id": appointment_id}
        ],
    )

    with pytest.raises(ValueError, match="больше не соответствует"):
        repo.save_ckd_prognosis_for_appointment(55, cur=cursor, selected_pair="tampered")

    assert cursor.executed == []


def test_repository_legacy_call_without_selection_still_saves_all_candidates(monkeypatch):
    cursor = FakeCursor()
    assessments = [
        {"selection_key": "pair-a", "appointment_id": 55},
        {"selection_key": "pair-b", "appointment_id": 55},
    ]
    inserted = []
    monkeypatch.setattr(
        repo,
        "build_kdigo_assessments_for_appointment",
        lambda cur, appointment_id, excluded_pairs=None: list(assessments),
    )
    monkeypatch.setattr(
        repo,
        "_insert_kdigo_assessment",
        lambda cur, assessment: inserted.append(assessment) or assessment,
    )

    repo.save_ckd_prognosis_for_appointment(55, cur=cursor)

    assert inserted == assessments
