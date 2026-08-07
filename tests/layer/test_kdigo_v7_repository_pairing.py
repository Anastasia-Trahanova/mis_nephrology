"""KDIGO backend pairing tests for the current server-side workflow.

When current visit contains multiple GFR and albuminuria sources, every valid
GFR x albuminuria combination must be available for the doctor's selection.
Only the explicitly selected pair is persisted by the appointment workflow.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from app.repositories.ckd_prognosis import (
    build_kdigo_assessments_for_appointment,
    save_ckd_prognosis_for_appointment,
)


APPOINTMENT_ID = 777
APPOINTMENT_DATE = date(2026, 7, 4)
PATIENT_ID = 42


class FakeCursor:
    def __init__(
        self,
        *,
        current_gfr: list[dict[str, Any]] | None = None,
        current_albuminuria: list[dict[str, Any]] | None = None,
        previous_gfr: dict[str, Any] | None = None,
        previous_albuminuria: dict[str, Any] | None = None,
    ):
        self.current_gfr = current_gfr or []
        self.current_albuminuria = current_albuminuria or []
        self.previous_gfr = previous_gfr
        self.previous_albuminuria = previous_albuminuria
        self.queries: list[str] = []
        self.inserted: list[dict[str, Any]] = []
        self._one: dict[str, Any] | None = None
        self._many: list[dict[str, Any]] = []

    def execute(self, query: str, params=None):  # noqa: ANN001 - DB cursor imitation
        self.queries.append(query)
        compact = " ".join(query.lower().split())

        if "select a.id as appointment_id" in compact:
            self._one = {
                "appointment_id": APPOINTMENT_ID,
                "patient_id": PATIENT_ID,
                "appointment_date": APPOINTMENT_DATE,
            }
            self._many = []
            return
        if "from calculated_metrics cm" in compact and "where cm.appointment_id" in compact:
            self._many = list(self.current_gfr)
            self._one = None
            return
        if "from albuminuria_results ar" in compact and "where ar.appointment_id" in compact:
            self._many = list(self.current_albuminuria)
            self._one = None
            return
        if "from albuminuria_results ar" in compact and "where a.patient_id" in compact:
            self._one = self.previous_albuminuria
            self._many = []
            return
        if "from calculated_metrics cm" in compact and "where a.patient_id" in compact:
            self._one = self.previous_gfr
            self._many = []
            return
        if "delete from ckd_prognosis_results" in compact:
            self._one = None
            self._many = []
            return
        if "insert into ckd_prognosis_results" in compact:
            saved = {"id": len(self.inserted) + 1, **dict(params)}
            self.inserted.append(saved)
            self._one = saved
            self._many = []
            return

        raise AssertionError(f"FakeCursor does not know this SQL: {query}")

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


def gfr(source_id: int, category: str, investigation_date: date = APPOINTMENT_DATE):
    return {
        "id": source_id,
        "investigation_date": investigation_date,
        "category": category,
        "source_type": "current_appointment",
    }


def albuminuria(source_id: int, category: str, investigation_date: date = APPOINTMENT_DATE):
    return {
        "id": source_id,
        "investigation_date": investigation_date,
        "category": category,
        "source_type": "current_appointment",
    }


def previous_gfr(source_id: int, category: str, investigation_date: date):
    item = gfr(source_id, category, investigation_date)
    item["source_type"] = "previous_appointment"
    return item


def previous_albuminuria(source_id: int, category: str, investigation_date: date):
    item = albuminuria(source_id, category, investigation_date)
    item["source_type"] = "previous_appointment"
    return item


def build(cur: FakeCursor):
    return build_kdigo_assessments_for_appointment(cur, APPOINTMENT_ID)


def test_no_current_sources_returns_no_saved_assessments():
    assert build(FakeCursor()) == []


def test_two_gfr_and_two_albuminuria_create_all_four_combinations():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С1"), gfr(2, "С3а")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        )
    )

    assert len(assessments) == 4
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (1, 11),
        (2, 10),
        (2, 11),
    ]
    assert [a["combined_category"] for a in assessments] == [
        "С1A1",
        "С1A2",
        "С3аA1",
        "С3аA2",
    ]
    assert [a["selection_key"] for a in assessments] == [
        "gfr:current:0||albuminuria:current:0",
        "gfr:current:0||albuminuria:current:1",
        "gfr:current:1||albuminuria:current:0",
        "gfr:current:1||albuminuria:current:1",
    ]


def test_two_gfr_and_one_albuminuria_create_two_selectable_combinations():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С1"), gfr(2, "С3б")],
            current_albuminuria=[albuminuria(10, "A2")],
        )
    )
    assert len(assessments) == 2
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (2, 10),
    ]
    assert [a["combined_category"] for a in assessments] == ["С1A2", "С3бA2"]


def test_one_gfr_and_two_albuminuria_create_two_selectable_combinations():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С3а")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A3")],
        )
    )
    assert len(assessments) == 2
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (1, 11),
    ]
    assert [a["combined_category"] for a in assessments] == ["С3аA1", "С3аA3"]


def test_same_date_and_same_category_but_different_source_ids_keep_four_distinct_pairs():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С3а"), gfr(2, "С3а")],
            current_albuminuria=[albuminuria(10, "A2"), albuminuria(11, "A2")],
        )
    )
    assert len(assessments) == 4
    assert {(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments} == {
        (1, 10),
        (1, 11),
        (2, 10),
        (2, 11),
    }
    assert all(a["combined_category"] == "С3аA2" for a in assessments)


def test_excluded_pair_removes_only_that_pair_and_renumbers_display_order():
    all_assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С1"), gfr(2, "С3а")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        )
    )
    excluded_key = all_assessments[0]["selection_key"]

    filtered = build_kdigo_assessments_for_appointment(
        FakeCursor(
            current_gfr=[gfr(1, "С1"), gfr(2, "С3а")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        ),
        APPOINTMENT_ID,
        excluded_pairs=[excluded_key],
    )

    assert len(filtered) == 3
    assert excluded_key not in {item["selection_key"] for item in filtered}
    assert [item["display_order"] for item in filtered] == [0, 1, 2]
    assert [item["row_key"].split("|", 2)[1] for item in filtered] == ["0", "1", "2"]


def test_current_gfr_can_use_latest_previous_albuminuria_when_current_albuminuria_is_missing():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С1", date(2026, 7, 4))],
            previous_albuminuria=previous_albuminuria(10, "A1", date(2026, 6, 20)),
        )
    )
    assert len(assessments) == 1
    assert assessments[0]["combined_category"] == "С1A1"
    assert assessments[0]["albuminuria_source_type"] == "previous_appointment"


def test_current_albuminuria_can_use_latest_previous_gfr_when_current_gfr_is_missing():
    assessments = build(
        FakeCursor(
            current_albuminuria=[albuminuria(10, "A2", date(2026, 7, 4))],
            previous_gfr=previous_gfr(1, "С3а", date(2026, 6, 20)),
        )
    )
    assert len(assessments) == 1
    assert assessments[0]["combined_category"] == "С3аA2"
    assert assessments[0]["gfr_source_type"] == "previous_appointment"


def test_stale_high_risk_previous_source_is_not_saved_as_calculated_forecast():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "С3а", date(2026, 7, 4))],
            previous_albuminuria=previous_albuminuria(10, "A2", date(2026, 1, 1)),
        )
    )
    assert assessments == []


def test_save_with_selected_pair_inserts_only_the_doctors_choice():
    first_pass = build(
        FakeCursor(
            current_gfr=[gfr(1, "С1"), gfr(2, "С3а")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        )
    )
    chosen = first_pass[2]

    cur = FakeCursor(
        current_gfr=[gfr(1, "С1"), gfr(2, "С3а")],
        current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
    )
    saved = save_ckd_prognosis_for_appointment(
        APPOINTMENT_ID,
        cur=cur,
        selected_pair=chosen["selection_key"],
    )

    assert len(saved) == 1
    assert saved[0]["selection_key"] == chosen["selection_key"]
    assert saved[0]["gfr_metric_id"] == chosen["gfr_metric_id"]
    assert saved[0]["albuminuria_result_id"] == chosen["albuminuria_result_id"]
    assert len(cur.inserted) == 1
    assert any("DELETE FROM ckd_prognosis_results" in query for query in cur.queries)


def test_save_rejects_unknown_selected_pair_before_deleting_existing_rows():
    cur = FakeCursor(
        current_gfr=[gfr(1, "С1")],
        current_albuminuria=[albuminuria(10, "A1")],
    )

    with pytest.raises(ValueError, match="больше не соответствует"):
        save_ckd_prognosis_for_appointment(
            APPOINTMENT_ID,
            cur=cur,
            selected_pair="not-a-real-pair",
        )

    assert not any("DELETE FROM ckd_prognosis_results" in query for query in cur.queries)
    assert cur.inserted == []
