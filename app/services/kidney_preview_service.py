"""Server-side live preview for kidney calculations in the appointment form.

Medical formulas are not duplicated here. This service only orchestrates existing
medical_algorithms modules so browser preview and persisted values use the same
Python calculations.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.medical_algorithms.albuminuria import (
    calculate_albuminuria_metrics,
    get_daily_albumin_excretion_category,
)
from app.medical_algorithms.kdigo_risk import (
    build_source_pair_key,
    calculate_kdigo_risk,
    format_missing_phrase,
    format_risk_phrase,
    format_stale_phrase,
    is_interval_allowed,
    normalize_albuminuria_category,
    source_interval_days,
    to_date,
)
from app.medical_algorithms.metrics import calculate_all_metrics
from app.medical_algorithms.ckd_stage import normalize_ckd_stage_for_storage


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _source_date(value: Any, fallback: Any) -> date | None:
    return to_date(value) or to_date(fallback)


def _latest_previous(items: list[dict[str, Any]], on_or_before: date | None) -> dict[str, Any] | None:
    if on_or_before is None:
        return None
    candidates = [item for item in items if item.get("investigation_date") and item["investigation_date"] <= on_or_before]
    return max(candidates, key=lambda item: item["investigation_date"], default=None)


def _normalize_previous(items: Any, *, kind: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in items or []:
        if not isinstance(raw, dict):
            continue
        investigation_date = to_date(raw.get("date") or raw.get("investigation_date"))
        if kind == "gfr":
            category = normalize_ckd_stage_for_storage(raw.get("category") or raw.get("gfr_category"))
        else:
            category = normalize_albuminuria_category(raw.get("category") or raw.get("albuminuria_category"))
        if investigation_date and category:
            result.append(
                {
                    "investigation_date": investigation_date,
                    "category": category,
                    "source_type": "previous_appointment",
                }
            )
    return result


def _missing(missing: str, order: int = 0) -> dict[str, Any]:
    return {
        "row_key": f"missing|{missing}|{order}",
        "pair_key": None,
        "status": "missing",
        "prognosis_level": None,
        "combined_category": None,
        "display_text": format_missing_phrase(missing),
        "display_order": order,
    }


def _assessment(
    gfr_source: dict[str, Any],
    albuminuria_source: dict[str, Any],
    order: int,
) -> dict[str, Any]:
    risk = calculate_kdigo_risk(gfr_source.get("category"), albuminuria_source.get("category"))
    if risk.get("status") != "calculated":
        return _missing("both", order)

    gfr_date = to_date(gfr_source.get("investigation_date"))
    albuminuria_date = to_date(albuminuria_source.get("investigation_date"))
    interval_days = source_interval_days(gfr_date, albuminuria_date)
    pair_key = build_source_pair_key(
        gfr_date,
        risk.get("gfr_category"),
        albuminuria_date,
        risk.get("albuminuria_category"),
    )

    if not is_interval_allowed(risk.get("prognosis_level"), interval_days):
        stale_source = "gfr" if gfr_date and albuminuria_date and gfr_date < albuminuria_date else "albuminuria"
        return {
            "row_key": f"stale|{order}|{pair_key}",
            "pair_key": pair_key,
            "status": "stale",
            "prognosis_level": None,
            "combined_category": risk.get("combined_category"),
            "display_text": format_stale_phrase(stale_source, interval_days),
            "display_order": order,
        }

    result = {
        "row_key": f"row|{order}|{pair_key}",
        "pair_key": pair_key,
        "status": "calculated",
        "gfr_investigation_date": gfr_date,
        "gfr_category": risk["gfr_category"],
        "gfr_source_type": gfr_source.get("source_type") or "current_appointment",
        "albuminuria_investigation_date": albuminuria_date,
        "albuminuria_category": risk["albuminuria_category"],
        "albuminuria_source_type": albuminuria_source.get("source_type") or "current_appointment",
        "source_interval_days": interval_days,
        "combined_category": risk["combined_category"],
        "prognosis_level": risk["prognosis_level"],
        "prognosis_text": risk["prognosis_text"],
        "display_order": order,
    }
    result["display_text"] = format_risk_phrase(result)
    return result


def _build_assessments(
    current_gfr: list[dict[str, Any]],
    current_albuminuria: list[dict[str, Any]],
    previous_gfr: list[dict[str, Any]],
    previous_albuminuria: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    assessments: list[dict[str, Any]] = []

    if current_gfr and current_albuminuria:
        rows_count = max(len(current_gfr), len(current_albuminuria))
        for index in range(rows_count):
            gfr_source = current_gfr[index] if index < len(current_gfr) else current_gfr[0]
            albuminuria_source = (
                current_albuminuria[index]
                if index < len(current_albuminuria)
                else current_albuminuria[0]
            )
            assessments.append(_assessment(gfr_source, albuminuria_source, len(assessments)))
    elif current_gfr:
        for gfr_source in current_gfr:
            previous = _latest_previous(previous_albuminuria, gfr_source.get("investigation_date"))
            assessments.append(
                _assessment(gfr_source, previous, len(assessments))
                if previous
                else _missing("albuminuria", len(assessments))
            )
    elif current_albuminuria:
        for albuminuria_source in current_albuminuria:
            previous = _latest_previous(previous_gfr, albuminuria_source.get("investigation_date"))
            assessments.append(
                _assessment(previous, albuminuria_source, len(assessments))
                if previous
                else _missing("gfr", len(assessments))
            )
    else:
        assessments.append(_missing("both"))

    # Do not show duplicate rows generated from exactly the same source pair.
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in assessments:
        key = (str(item.get("status")), str(item.get("pair_key") or item.get("display_text")))
        if key in seen:
            continue
        seen.add(key)
        item["display_order"] = len(result)
        if item.get("status") == "calculated":
            item["row_key"] = f"row|{len(result)}|{item.get('pair_key', '')}"
        result.append(item)
    return result or [_missing("both")]


def build_kidney_preview(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculate current eGFR/ACR/KDIGO preview from raw form values."""
    appointment_date = to_date(payload.get("appointment_date"))
    birth_date = payload.get("birth_date")
    gender = payload.get("gender")
    weight_kg = payload.get("weight_kg")

    metrics_rows: list[dict[str, Any]] = []
    current_gfr: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("biochemistry") or []):
        if not isinstance(raw, dict) or not _present(raw.get("creatinine")):
            continue
        investigation_date = _source_date(raw.get("investigation_date"), appointment_date)
        metrics = calculate_all_metrics(
            creatinine_umol_l=raw.get("creatinine"),
            birth_date=birth_date,
            appointment_date=investigation_date,
            gender=gender,
            weight_kg=weight_kg,
        )
        row = {
            "key": str(raw.get("key") or f"biochemistry-{index}"),
            "investigation_date": investigation_date,
            "creatinine": raw.get("creatinine"),
            "egfr_ckdepi": metrics.get("egfr_ckdepi"),
            "crcl_cockcroft_gault": metrics.get("crcl_cockcroft_gault"),
            "ckd_stage": normalize_ckd_stage_for_storage(metrics.get("ckd_stage")),
        }
        metrics_rows.append(row)
        if row["investigation_date"] and row["ckd_stage"]:
            current_gfr.append(
                {
                    "investigation_date": row["investigation_date"],
                    "category": row["ckd_stage"],
                    "source_type": "current_appointment",
                    "key": row["key"],
                }
            )

    albuminuria_rows: list[dict[str, Any]] = []
    current_albuminuria: list[dict[str, Any]] = []
    for index, raw in enumerate(payload.get("albuminuria") or []):
        if not isinstance(raw, dict):
            continue
        has_data = any(
            _present(raw.get(name))
            for name in ("urine_albumin", "urine_creatinine", "daily_albumin_excretion")
        )
        if not has_data:
            continue
        investigation_date = _source_date(raw.get("investigation_date"), appointment_date)
        calculated = {
            "albumin_creatinine_ratio": None,
            "albuminuria_category": None,
        }
        if _present(raw.get("urine_albumin")) and _present(raw.get("urine_creatinine")):
            calculated = calculate_albuminuria_metrics(
                urine_albumin=raw.get("urine_albumin"),
                urine_albumin_unit=raw.get("urine_albumin_unit") or "mg_l",
                urine_creatinine=raw.get("urine_creatinine"),
                urine_creatinine_unit=raw.get("urine_creatinine_unit") or "mmol_l",
            )
        category = calculated.get("albuminuria_category")
        category_source = "acr" if category else None
        if category is None and _present(raw.get("daily_albumin_excretion")):
            category = get_daily_albumin_excretion_category(raw.get("daily_albumin_excretion"))
            category_source = "daily" if category else None

        row = {
            "key": str(raw.get("key") or f"albuminuria-{index}"),
            "investigation_date": investigation_date,
            "albumin_creatinine_ratio": calculated.get("albumin_creatinine_ratio"),
            "albuminuria_category": normalize_albuminuria_category(category),
            "category_source": category_source,
            "daily_albumin_excretion": raw.get("daily_albumin_excretion"),
        }
        albuminuria_rows.append(row)
        if row["investigation_date"] and row["albuminuria_category"]:
            current_albuminuria.append(
                {
                    "investigation_date": row["investigation_date"],
                    "category": row["albuminuria_category"],
                    "source_type": "current_appointment",
                    "key": row["key"],
                }
            )

    previous_gfr = _normalize_previous(payload.get("previous_gfr"), kind="gfr")
    previous_albuminuria = _normalize_previous(payload.get("previous_albuminuria"), kind="albuminuria")

    return {
        "metrics": metrics_rows,
        "albuminuria": albuminuria_rows,
        "kdigo_assessments": _build_assessments(
            current_gfr,
            current_albuminuria,
            previous_gfr,
            previous_albuminuria,
        ),
    }
