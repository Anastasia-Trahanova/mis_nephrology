from __future__ import annotations

from app.services.kidney_preview_service import build_kidney_preview


def payload(*, creatinine="123", albumin="234", urine_creatinine="43"):
    return {
        "birth_date": "1966-01-01",
        "gender": False,
        "weight_kg": "70",
        "appointment_date": "2026-08-07",
        "biochemistry": [
            {
                "key": "bio-0",
                "investigation_date": "2026-08-07",
                "creatinine": creatinine,
            }
        ],
        "albuminuria": [
            {
                "key": "alb-0",
                "investigation_date": "2026-08-07",
                "urine_albumin": albumin,
                "urine_albumin_unit": "mg_l",
                "urine_creatinine": urine_creatinine,
                "urine_creatinine_unit": "mmol_l",
                "daily_albumin_excretion": "",
            }
        ],
        "previous_gfr": [],
        "previous_albuminuria": [],
    }


def test_regression_creatinine_acr_and_kdigo_are_calculated_together():
    result = build_kidney_preview(payload())

    metric = result["metrics"][0]
    assert metric["egfr_ckdepi"] == 43.39
    assert metric["ckd_stage"] == "С3б"

    albuminuria = result["albuminuria"][0]
    assert albuminuria["albumin_creatinine_ratio"] == 5.44
    assert albuminuria["albuminuria_category"] == "A2"

    kdigo = result["kdigo_assessments"][0]
    assert kdigo["status"] == "calculated"
    assert kdigo["combined_category"] == "С3бA2"
    assert kdigo["prognosis_level"] == "very_high"


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
    data = payload(albumin="0.234", urine_creatinine="43000")
    data["albuminuria"][0]["urine_albumin_unit"] = "g_l"
    data["albuminuria"][0]["urine_creatinine_unit"] = "umol_l"
    result = build_kidney_preview(data)

    assert result["albuminuria"][0]["albumin_creatinine_ratio"] == 5.44
    assert result["albuminuria"][0]["albuminuria_category"] == "A2"
