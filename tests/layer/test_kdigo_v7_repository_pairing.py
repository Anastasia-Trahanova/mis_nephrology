"""
Тесты KDIGO v7: backend-сохранение должно повторять live-логику формы.

Критично: если на экране врач видит 2 строки прогноза, backend не должен
сохранять декартово произведение всех СКФ × всех альбуминурий.
"""

from __future__ import annotations

from datetime import date
from typing import Any

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

    def execute(self, query: str, params=None):  # noqa: ANN001 - имитация DB cursor
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


def test_two_gfr_and_two_albuminuria_are_saved_as_two_row_pairs_not_four_combinations():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C1"), gfr(2, "C3a")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        )
    )

    assert len(assessments) == 2
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (2, 11),
    ]
    assert [a["combined_category"] for a in assessments] == ["С1A1", "С3аA2"]


def test_two_gfr_and_one_albuminuria_create_second_selectable_row_with_first_albuminuria():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C1"), gfr(2, "C3b")],
            current_albuminuria=[albuminuria(10, "A2")],
        )
    )

    assert len(assessments) == 2
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (2, 10),
    ]
    assert [a["combined_category"] for a in assessments] == ["С1A2", "С3бA2"]


def test_one_gfr_and_two_albuminuria_create_second_selectable_row_with_first_gfr():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C3a")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A3")],
        )
    )

    assert len(assessments) == 2
    assert [(a["gfr_metric_id"], a["albuminuria_result_id"]) for a in assessments] == [
        (1, 10),
        (1, 11),
    ]
    assert [a["combined_category"] for a in assessments] == ["С3аA1", "С3аA3"]


def test_same_date_and_same_category_but_different_source_ids_are_not_collapsed():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C3a"), gfr(2, "C3a")],
            current_albuminuria=[albuminuria(10, "A2"), albuminuria(11, "A2")],
        )
    )

    assert len(assessments) == 2
    assert {a["gfr_metric_id"] for a in assessments} == {1, 2}
    assert {a["albuminuria_result_id"] for a in assessments} == {10, 11}
    assert all(a["combined_category"] == "С3аA2" for a in assessments)


def test_excluded_row_key_removes_unselected_forecast_and_renumbers_display_order():
    cur = FakeCursor(
        current_gfr=[gfr(1, "C1"), gfr(2, "C3a")],
        current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
    )
    all_assessments = build(cur)
    first_row_key = all_assessments[0]["row_key"]

    filtered = build_kdigo_assessments_for_appointment(
        FakeCursor(
            current_gfr=[gfr(1, "C1"), gfr(2, "C3a")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        ),
        APPOINTMENT_ID,
        excluded_pairs=[first_row_key],
    )

    assert len(filtered) == 1
    assert filtered[0]["combined_category"] == "С3аA2"
    assert filtered[0]["display_order"] == 0
    assert filtered[0]["row_key"].startswith("row|0|")


def test_current_gfr_can_use_latest_previous_albuminuria_when_current_albuminuria_is_missing():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C1", date(2026, 7, 4))],
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
            previous_gfr=previous_gfr(1, "C3a", date(2026, 6, 20)),
        )
    )

    assert len(assessments) == 1
    assert assessments[0]["combined_category"] == "С3аA2"
    assert assessments[0]["gfr_source_type"] == "previous_appointment"


def test_stale_high_risk_previous_source_is_not_saved_as_calculated_forecast():
    assessments = build(
        FakeCursor(
            current_gfr=[gfr(1, "C3a", date(2026, 7, 4))],
            previous_albuminuria=previous_albuminuria(10, "A2", date(2026, 1, 1)),
        )
    )

    assert assessments == []


def test_save_deletes_old_calculated_rows_and_inserts_only_visible_non_excluded_rows():
    first_pass = build(
        FakeCursor(
            current_gfr=[gfr(1, "C1"), gfr(2, "C3a")],
            current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
        )
    )
    excluded_first = first_pass[0]["row_key"]

    cur = FakeCursor(
        current_gfr=[gfr(1, "C1"), gfr(2, "C3a")],
        current_albuminuria=[albuminuria(10, "A1"), albuminuria(11, "A2")],
    )
    saved = save_ckd_prognosis_for_appointment(
        APPOINTMENT_ID,
        cur=cur,
        excluded_pairs=[excluded_first],
    )

    assert len(saved) == 1
    assert saved[0]["combined_category"] == "С3аA2"
    assert len(cur.inserted) == 1
    assert any("DELETE FROM ckd_prognosis_results" in query for query in cur.queries)
