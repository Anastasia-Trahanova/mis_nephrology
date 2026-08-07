from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.kidney_preview_service import (
    _assessment,
    build_kidney_preview,
)


BASE_DATE = "2026-08-07"


def payload(
    *,
    creatinine="123",
    albumin="234",
    urine_creatinine="43",
    albumin_unit="mg_l",
    urine_creatinine_unit="mmol_l",
    daily_albumin_excretion="",
    biochemistry_date=BASE_DATE,
    albuminuria_date=BASE_DATE,
    previous_gfr=None,
    previous_albuminuria=None,
    birth_date="1966-01-01",
    gender=False,
    weight_kg="70",
):
    biochemistry = []
    if creatinine is not None:
        biochemistry.append(
            {
                "key": "biochemistry-0",
                "investigation_date": biochemistry_date,
                "creatinine": creatinine,
            }
        )

    albuminuria = []
    if any(value is not None for value in (albumin, urine_creatinine, daily_albumin_excretion)):
        albuminuria.append(
            {
                "key": "albuminuria-0",
                "investigation_date": albuminuria_date,
                "urine_albumin": "" if albumin is None else albumin,
                "urine_albumin_unit": albumin_unit,
                "urine_creatinine": "" if urine_creatinine is None else urine_creatinine,
                "urine_creatinine_unit": urine_creatinine_unit,
                "daily_albumin_excretion": "" if daily_albumin_excretion is None else daily_albumin_excretion,
            }
        )

    return {
        "birth_date": birth_date,
        "gender": gender,
        "weight_kg": weight_kg,
        "appointment_date": BASE_DATE,
        "biochemistry": biochemistry,
        "albuminuria": albuminuria,
        "previous_gfr": previous_gfr or [],
        "previous_albuminuria": previous_albuminuria or [],
    }


def test_no_new_kidney_data_does_not_create_current_kdigo_even_with_history():
    data = payload(creatinine=None, albumin=None, urine_creatinine=None, daily_albumin_excretion=None)
    data["previous_gfr"] = [{"date": "2026-08-01", "category": "С3а"}]
    data["previous_albuminuria"] = [{"date": "2026-08-01", "category": "A2"}]

    result = build_kidney_preview(data)

    assert result == {"metrics": [], "albuminuria": [], "kdigo_assessments": []}


def test_regression_creatinine_acr_and_kdigo_are_calculated_together():
    result = build_kidney_preview(payload())

    metric = result["metrics"][0]
    assert metric["egfr_ckdepi"] == 43.39
    assert metric["ckd_stage"] == "С3б"

    albuminuria = result["albuminuria"][0]
    assert albuminuria["albumin_creatinine_ratio"] == 5.44
    assert albuminuria["albuminuria_category"] == "A2"
    assert albuminuria["category_source"] == "acr"

    kdigo = result["kdigo_assessments"][0]
    assert kdigo["status"] == "calculated"
    assert kdigo["combined_category"] == "С3бA2"
    assert kdigo["prognosis_level"] == "very_high"
    assert kdigo["selection_key"] == "gfr:current:0||albuminuria:current:0"


def test_creatinine_only_calculates_metrics_but_reports_missing_albuminuria_without_history():
    result = build_kidney_preview(
        payload(albumin=None, urine_creatinine=None, daily_albumin_excretion=None)
    )

    assert len(result["metrics"]) == 1
    assert result["metrics"][0]["ckd_stage"] == "С3б"
    assert result["albuminuria"] == []
    assert result["kdigo_assessments"][0]["status"] == "missing"
    assert "альбуминурии" in result["kdigo_assessments"][0]["display_text"]


def test_albuminuria_only_calculates_acr_but_reports_missing_gfr_without_history():
    result = build_kidney_preview(payload(creatinine=None))

    assert result["metrics"] == []
    assert result["albuminuria"][0]["albumin_creatinine_ratio"] == 5.44
    assert result["albuminuria"][0]["albuminuria_category"] == "A2"
    assert result["kdigo_assessments"][0]["status"] == "missing"
    assert "СКФ" in result["kdigo_assessments"][0]["display_text"]


def test_new_gfr_uses_latest_previous_albuminuria_on_or_before_gfr_date():
    result = build_kidney_preview(
        payload(
            albumin=None,
            urine_creatinine=None,
            daily_albumin_excretion=None,
            previous_albuminuria=[
                {"date": "2026-06-01", "category": "A1"},
                {"date": "2026-08-01", "category": "A2"},
                {"date": "2026-08-08", "category": "A3"},
            ],
        )
    )

    kdigo = result["kdigo_assessments"][0]
    assert kdigo["status"] == "calculated"
    assert kdigo["albuminuria_category"] == "A2"
    assert kdigo["albuminuria_investigation_date"].isoformat() == "2026-08-01"
    assert kdigo["albuminuria_source_type"] == "previous_appointment"


def test_new_albuminuria_uses_latest_previous_gfr_on_or_before_albuminuria_date():
    result = build_kidney_preview(
        payload(
            creatinine=None,
            previous_gfr=[
                {"date": "2026-06-01", "category": "С1"},
                {"date": "2026-08-01", "category": "С2"},
                {"date": "2026-08-08", "category": "С5"},
            ],
        )
    )

    kdigo = result["kdigo_assessments"][0]
    assert kdigo["status"] == "calculated"
    assert kdigo["gfr_category"] == "С2"
    assert kdigo["gfr_investigation_date"].isoformat() == "2026-08-01"
    assert kdigo["gfr_source_type"] == "previous_appointment"


def test_future_previous_value_is_not_used_as_fallback():
    result = build_kidney_preview(
        payload(
            albumin=None,
            urine_creatinine=None,
            daily_albumin_excretion=None,
            previous_albuminuria=[{"date": "2026-08-08", "category": "A2"}],
        )
    )

    assert result["kdigo_assessments"][0]["status"] == "missing"


def test_current_values_take_priority_over_previous_history():
    data = payload()
    data["previous_gfr"] = [{"date": "2026-08-06", "category": "С1"}]
    data["previous_albuminuria"] = [{"date": "2026-08-06", "category": "A3"}]

    result = build_kidney_preview(data)

    assert len(result["kdigo_assessments"]) == 1
    kdigo = result["kdigo_assessments"][0]
    assert kdigo["gfr_source_type"] == "current_appointment"
    assert kdigo["albuminuria_source_type"] == "current_appointment"
    assert kdigo["combined_category"] == "С3бA2"


def test_two_gfr_by_two_albuminuria_builds_four_distinct_combinations():
    data = payload()
    data["biochemistry"] = [
        {"key": "biochemistry-0", "investigation_date": BASE_DATE, "creatinine": "80"},
        {"key": "biochemistry-1", "investigation_date": BASE_DATE, "creatinine": "400"},
    ]
    data["albuminuria"] = [
        {
            "key": "albuminuria-0",
            "investigation_date": BASE_DATE,
            "urine_albumin": "20",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
        {
            "key": "albuminuria-1",
            "investigation_date": BASE_DATE,
            "urine_albumin": "2000",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
    ]

    result = build_kidney_preview(data)
    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]

    assert len(result["metrics"]) == 2
    assert len(result["albuminuria"]) == 2
    assert len(calculated) == 4
    assert {item["combined_category"] for item in calculated} == {
        "С2A1",
        "С2A3",
        "С5A1",
        "С5A3",
    }
    assert {item["selection_key"] for item in calculated} == {
        "gfr:current:0||albuminuria:current:0",
        "gfr:current:0||albuminuria:current:1",
        "gfr:current:1||albuminuria:current:0",
        "gfr:current:1||albuminuria:current:1",
    }


def test_two_gfr_by_one_albuminuria_builds_two_candidates():
    data = payload()
    data["biochemistry"] = [
        {"key": "biochemistry-0", "investigation_date": BASE_DATE, "creatinine": "80"},
        {"key": "biochemistry-1", "investigation_date": BASE_DATE, "creatinine": "400"},
    ]

    result = build_kidney_preview(data)

    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]
    assert len(calculated) == 2
    assert [item["selection_key"] for item in calculated] == [
        "gfr:current:0||albuminuria:current:0",
        "gfr:current:1||albuminuria:current:0",
    ]


def test_one_gfr_by_two_albuminuria_builds_two_candidates():
    data = payload()
    data["albuminuria"] = [
        {
            "key": "albuminuria-0",
            "investigation_date": BASE_DATE,
            "urine_albumin": "20",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
        {
            "key": "albuminuria-1",
            "investigation_date": BASE_DATE,
            "urine_albumin": "2000",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
    ]

    result = build_kidney_preview(data)

    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]
    assert len(calculated) == 2
    assert [item["selection_key"] for item in calculated] == [
        "gfr:current:0||albuminuria:current:0",
        "gfr:current:0||albuminuria:current:1",
    ]


def test_distinct_current_sources_are_not_collapsed_when_date_and_category_match():
    data = payload()
    data["biochemistry"] = [
        {"key": "biochemistry-0", "investigation_date": BASE_DATE, "creatinine": "123"},
        {"key": "biochemistry-1", "investigation_date": BASE_DATE, "creatinine": "123"},
    ]
    data["albuminuria"] = [
        {
            "key": "albuminuria-0",
            "investigation_date": BASE_DATE,
            "urine_albumin": "234",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
        {
            "key": "albuminuria-1",
            "investigation_date": BASE_DATE,
            "urine_albumin": "234",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
    ]

    result = build_kidney_preview(data)
    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]

    assert len(calculated) == 4
    assert len({item["selection_key"] for item in calculated}) == 4


def test_changing_creatinine_recalculates_egfr_stage_and_kdigo():
    lower = build_kidney_preview(payload(creatinine="80"))
    higher = build_kidney_preview(payload(creatinine="400"))

    assert lower["metrics"][0]["egfr_ckdepi"] == 72.7
    assert lower["metrics"][0]["ckd_stage"] == "С2"
    assert higher["metrics"][0]["egfr_ckdepi"] == 10.54
    assert higher["metrics"][0]["ckd_stage"] == "С5"
    assert lower["kdigo_assessments"][0]["combined_category"] == "С2A2"
    assert higher["kdigo_assessments"][0]["combined_category"] == "С5A2"


def test_changing_albuminuria_recalculates_acr_category_and_kdigo():
    a1 = build_kidney_preview(payload(albumin="20"))
    a2 = build_kidney_preview(payload(albumin="234"))
    a3 = build_kidney_preview(payload(albumin="2000"))

    assert a1["albuminuria"][0]["albuminuria_category"] == "A1"
    assert a2["albuminuria"][0]["albuminuria_category"] == "A2"
    assert a3["albuminuria"][0]["albuminuria_category"] == "A3"
    assert a1["kdigo_assessments"][0]["combined_category"] == "С3бA1"
    assert a2["kdigo_assessments"][0]["combined_category"] == "С3бA2"
    assert a3["kdigo_assessments"][0]["combined_category"] == "С3бA3"


def test_albuminuria_unit_conversion_stays_mg_per_mmol():
    data = payload(
        albumin="0.234",
        urine_creatinine="43000",
        albumin_unit="g_l",
        urine_creatinine_unit="umol_l",
    )
    result = build_kidney_preview(data)

    assert result["albuminuria"][0]["albumin_creatinine_ratio"] == 5.44
    assert result["albuminuria"][0]["albuminuria_category"] == "A2"


@pytest.mark.parametrize(
    ("daily", "expected_category"),
    [
        ("0", "A1"),
        ("29.99", "A1"),
        ("30", "A2"),
        ("300", "A2"),
        ("300.01", "A3"),
    ],
)
def test_daily_albumin_excretion_is_used_when_acr_cannot_be_calculated(daily, expected_category):
    result = build_kidney_preview(
        payload(albumin=None, urine_creatinine=None, daily_albumin_excretion=daily)
    )

    row = result["albuminuria"][0]
    assert row["albumin_creatinine_ratio"] is None
    assert row["albuminuria_category"] == expected_category
    assert row["category_source"] == "daily"


def test_acr_category_has_priority_over_daily_excretion_category():
    result = build_kidney_preview(
        payload(albumin="20", urine_creatinine="43", daily_albumin_excretion="500")
    )

    row = result["albuminuria"][0]
    assert row["albuminuria_category"] == "A1"
    assert row["category_source"] == "acr"


def test_zero_urine_creatinine_falls_back_to_daily_excretion():
    result = build_kidney_preview(
        payload(albumin="234", urine_creatinine="0", daily_albumin_excretion="100")
    )

    row = result["albuminuria"][0]
    assert row["albumin_creatinine_ratio"] is None
    assert row["albuminuria_category"] == "A2"
    assert row["category_source"] == "daily"


def test_invalid_albuminuria_without_daily_value_does_not_become_kdigo_source():
    result = build_kidney_preview(
        payload(albumin="234", urine_creatinine="0", daily_albumin_excretion="")
    )

    assert result["albuminuria"][0]["albuminuria_category"] is None
    assert result["kdigo_assessments"][0]["status"] == "missing"
    assert "альбуминурии" in result["kdigo_assessments"][0]["display_text"]


def test_blank_rows_are_ignored_and_do_not_shift_valid_source_ordinals():
    data = payload()
    data["biochemistry"] = [
        {"key": "biochemistry-0", "investigation_date": BASE_DATE, "creatinine": ""},
        {"key": "biochemistry-1", "investigation_date": BASE_DATE, "creatinine": "80"},
    ]
    data["albuminuria"] = [
        {
            "key": "albuminuria-0",
            "investigation_date": BASE_DATE,
            "urine_albumin": "",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
        {
            "key": "albuminuria-1",
            "investigation_date": BASE_DATE,
            "urine_albumin": "234",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
    ]

    result = build_kidney_preview(data)

    assert [row["key"] for row in result["metrics"]] == ["biochemistry-1"]
    assert [row["key"] for row in result["albuminuria"]] == ["albuminuria-1"]
    assert result["kdigo_assessments"][0]["selection_key"] == (
        "gfr:current:0||albuminuria:current:0"
    )


def test_missing_investigation_dates_fall_back_to_appointment_date():
    data = payload(biochemistry_date="", albuminuria_date="")
    result = build_kidney_preview(data)

    assert result["metrics"][0]["investigation_date"].isoformat() == BASE_DATE
    assert result["albuminuria"][0]["investigation_date"].isoformat() == BASE_DATE
    assert result["kdigo_assessments"][0]["source_interval_days"] == 0


def test_missing_weight_does_not_block_ckd_epi_or_kdigo_but_cockcroft_is_empty():
    result = build_kidney_preview(payload(weight_kg=""))

    metric = result["metrics"][0]
    assert metric["egfr_ckdepi"] == 43.39
    assert metric["ckd_stage"] == "С3б"
    assert metric["crcl_cockcroft_gault"] is None
    assert result["kdigo_assessments"][0]["status"] == "calculated"


@pytest.mark.parametrize("missing_field", ["birth_date", "gender"])
def test_missing_patient_demographics_prevent_gfr_source_and_kdigo(missing_field):
    kwargs = {missing_field: None}
    result = build_kidney_preview(payload(**kwargs))

    metric = result["metrics"][0]
    assert metric["egfr_ckdepi"] is None
    assert metric["ckd_stage"] is None
    assert result["kdigo_assessments"][0]["status"] == "missing"
    assert "СКФ" in result["kdigo_assessments"][0]["display_text"]


@pytest.mark.parametrize(
    ("gfr_category", "albuminuria_category", "expected_level"),
    [
        ("С1", "A1", "low"),
        ("С1", "A2", "moderate"),
        ("С1", "A3", "high"),
        ("С2", "A1", "low"),
        ("С2", "A2", "moderate"),
        ("С2", "A3", "high"),
        ("С3а", "A1", "moderate"),
        ("С3а", "A2", "high"),
        ("С3а", "A3", "very_high"),
        ("С3б", "A1", "high"),
        ("С3б", "A2", "very_high"),
        ("С3б", "A3", "very_high"),
        ("С4", "A1", "very_high"),
        ("С4", "A2", "very_high"),
        ("С4", "A3", "very_high"),
        ("С5", "A1", "very_high"),
        ("С5", "A2", "very_high"),
        ("С5", "A3", "very_high"),
    ],
)
def test_preview_assessment_covers_every_kdigo_matrix_cell(
    gfr_category,
    albuminuria_category,
    expected_level,
):
    source_date = date(2026, 8, 7)
    result = _assessment(
        {
            "investigation_date": source_date,
            "category": gfr_category,
            "source_type": "current_appointment",
            "selection_ref": "gfr:current:0",
        },
        {
            "investigation_date": source_date,
            "category": albuminuria_category,
            "source_type": "current_appointment",
            "selection_ref": "albuminuria:current:0",
        },
        0,
    )

    assert result["status"] == "calculated"
    assert result["combined_category"] == f"{gfr_category}{albuminuria_category}"
    assert result["prognosis_level"] == expected_level


@pytest.mark.parametrize(
    ("gfr_category", "albuminuria_category", "allowed_days"),
    [
        ("С1", "A1", 365),
        ("С1", "A2", 180),
        ("С1", "A3", 90),
        ("С3а", "A3", 90),
    ],
)
def test_interval_limit_is_inclusive_and_next_day_is_stale(
    gfr_category,
    albuminuria_category,
    allowed_days,
):
    gfr_date = date(2026, 8, 7)
    base_gfr = {
        "investigation_date": gfr_date,
        "category": gfr_category,
        "source_type": "current_appointment",
        "selection_ref": "gfr:current:0",
    }

    allowed = _assessment(
        base_gfr,
        {
            "investigation_date": gfr_date - timedelta(days=allowed_days),
            "category": albuminuria_category,
            "source_type": "previous_appointment",
        },
        0,
    )
    stale = _assessment(
        base_gfr,
        {
            "investigation_date": gfr_date - timedelta(days=allowed_days + 1),
            "category": albuminuria_category,
            "source_type": "previous_appointment",
        },
        0,
    )

    assert allowed["status"] == "calculated"
    assert allowed["source_interval_days"] == allowed_days
    assert stale["status"] == "stale"
    assert stale["prognosis_level"] is None
    assert "рекомендовано повторить исследование" in stale["display_text"]

@pytest.mark.parametrize("creatinine", ["0", "-1", "abc"])
def test_invalid_serum_creatinine_never_becomes_gfr_or_kdigo_source(creatinine):
    result = build_kidney_preview(payload(creatinine=creatinine))

    assert len(result["metrics"]) == 1
    assert result["metrics"][0]["egfr_ckdepi"] is None
    assert result["metrics"][0]["ckd_stage"] is None
    assert result["kdigo_assessments"][0]["status"] == "missing"
    assert "СКФ" in result["kdigo_assessments"][0]["display_text"]


def test_decimal_comma_values_are_accepted_by_server_preview():
    result = build_kidney_preview(
        payload(creatinine="123,0", albumin="234,0", urine_creatinine="43,0")
    )

    assert result["metrics"][0]["egfr_ckdepi"] == 43.39
    assert result["metrics"][0]["ckd_stage"] == "С3б"
    assert result["albuminuria"][0]["albumin_creatinine_ratio"] == 5.44
    assert result["albuminuria"][0]["albuminuria_category"] == "A2"
    assert result["kdigo_assessments"][0]["combined_category"] == "С3бA2"


@pytest.mark.parametrize(
    ("albumin_unit", "urine_creatinine_unit"),
    [("unsupported", "mmol_l"), ("mg_l", "unsupported")],
)
def test_unsupported_albuminuria_units_do_not_create_false_category_or_kdigo(
    albumin_unit,
    urine_creatinine_unit,
):
    result = build_kidney_preview(
        payload(
            albumin_unit=albumin_unit,
            urine_creatinine_unit=urine_creatinine_unit,
            daily_albumin_excretion="",
        )
    )

    row = result["albuminuria"][0]
    assert row["albumin_creatinine_ratio"] is None
    assert row["albuminuria_category"] is None
    assert result["kdigo_assessments"][0]["status"] == "missing"


def test_three_by_three_scales_to_full_cartesian_product_without_hardcoded_limit():
    data = payload()
    data["biochemistry"] = [
        {"key": f"biochemistry-{index}", "investigation_date": BASE_DATE, "creatinine": value}
        for index, value in enumerate(("80", "123", "400"))
    ]
    data["albuminuria"] = [
        {
            "key": f"albuminuria-{index}",
            "investigation_date": BASE_DATE,
            "urine_albumin": value,
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        }
        for index, value in enumerate(("20", "234", "2000"))
    ]

    result = build_kidney_preview(data)
    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]

    assert len(result["metrics"]) == 3
    assert len(result["albuminuria"]) == 3
    assert len(calculated) == 9
    assert len({item["selection_key"] for item in calculated}) == 9


def test_each_new_gfr_uses_latest_previous_albuminuria_available_on_its_own_date():
    data = payload(albumin=None, urine_creatinine=None, daily_albumin_excretion=None)
    data["biochemistry"] = [
        {"key": "biochemistry-0", "investigation_date": "2026-07-15", "creatinine": "80"},
        {"key": "biochemistry-1", "investigation_date": "2026-08-07", "creatinine": "400"},
    ]
    data["previous_albuminuria"] = [
        {"date": "2026-07-01", "category": "A1"},
        {"date": "2026-08-01", "category": "A2"},
    ]

    result = build_kidney_preview(data)
    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]

    assert len(calculated) == 2
    assert [item["albuminuria_category"] for item in calculated] == ["A1", "A2"]
    assert [item["albuminuria_investigation_date"].isoformat() for item in calculated] == [
        "2026-07-01",
        "2026-08-01",
    ]


def test_each_new_albuminuria_uses_latest_previous_gfr_available_on_its_own_date():
    data = payload(creatinine=None)
    data["albuminuria"] = [
        {
            "key": "albuminuria-0",
            "investigation_date": "2026-07-15",
            "urine_albumin": "20",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
        {
            "key": "albuminuria-1",
            "investigation_date": "2026-08-07",
            "urine_albumin": "234",
            "urine_albumin_unit": "mg_l",
            "urine_creatinine": "43",
            "urine_creatinine_unit": "mmol_l",
            "daily_albumin_excretion": "",
        },
    ]
    data["previous_gfr"] = [
        {"date": "2026-07-01", "category": "С2"},
        {"date": "2026-08-01", "category": "С3б"},
    ]

    result = build_kidney_preview(data)
    calculated = [item for item in result["kdigo_assessments"] if item["status"] == "calculated"]

    assert len(calculated) == 2
    assert [item["gfr_category"] for item in calculated] == ["С2", "С3б"]
    assert [item["gfr_investigation_date"].isoformat() for item in calculated] == [
        "2026-07-01",
        "2026-08-01",
    ]


def test_both_gender_paths_produce_server_side_gfr_and_cockcroft_values():
    female = build_kidney_preview(payload(gender=False))
    male = build_kidney_preview(payload(gender=True))

    for result in (female, male):
        assert result["metrics"][0]["egfr_ckdepi"] is not None
        assert result["metrics"][0]["crcl_cockcroft_gault"] is not None
        assert result["metrics"][0]["ckd_stage"] is not None
        assert result["kdigo_assessments"][0]["status"] == "calculated"

    assert female["metrics"][0]["egfr_ckdepi"] != male["metrics"][0]["egfr_ckdepi"]
