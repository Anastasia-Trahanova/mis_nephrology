from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METRICS_TEMPLATE = ROOT / "app" / "templates" / "appointment_form" / "_metrics.html"
LIVE_JS = ROOT / "app" / "static" / "js" / "kdigo_risk_preview.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_metrics_template_is_passive_server_render_target():
    html = _read(METRICS_TEMPLATE)

    for marker in ("metricsHeaderRow", "egfrRow", "cockcroftRow", "ckdStageRow", "metrics_history"):
        assert marker in html

    assert "<script>" not in html
    assert "calculateCkdEpi" not in html
    assert "calculateCockcroftGault" not in html
    assert "Math.pow" not in html
    assert "creatinineUmol / 88.4" not in html


def test_live_js_adds_server_preview_columns_to_existing_metrics_table():
    js = _read(LIVE_JS)

    assert 'document.getElementById("metricsHeaderRow")' in js
    assert 'document.getElementById("egfrRow")' in js
    assert 'document.getElementById("cockcroftRow")' in js
    assert 'document.getElementById("ckdStageRow")' in js
    assert "kidney-preview-metrics" in js
    assert "appendMetricCell" in js
    assert "sortMetricsTable" in js


def test_live_js_watches_all_fields_that_change_server_metrics():
    js = _read(LIVE_JS)

    for field_name in (
        "birth_date",
        "gender",
        "weight",
        "appointment_date",
        "biochemistry_investigation_date",
        "creatinine",
    ):
        assert f'"{field_name}"' in js

    assert 'document.addEventListener("input"' in js
    assert 'document.addEventListener("change"' in js
    assert "scheduleRefresh" in js


def test_live_js_updates_after_dynamic_biochemistry_columns_are_added_or_removed():
    js = _read(LIVE_JS)

    assert "#addBiochemistryColumnBtn" in js
    assert "[data-add-lab]" in js
    assert ".remove-lab-card" in js
    assert "scheduleRefresh(80)" in js


def test_manual_metrics_action_is_routed_to_server_preview_not_local_formula():
    js = _read(LIVE_JS)

    assert "#updateMetricsTableBtn" in js
    assert "event.stopImmediatePropagation()" in js
    assert "scheduleRefresh(0)" in js
    assert 'fetch("/api/kidney-preview"' in js


def test_browser_has_no_duplicate_medical_gfr_formula():
    js = _read(LIVE_JS)

    for forbidden in (
        "calculateCkdEpi",
        "calculateCockcroftGault",
        "creatinineUmol / 88.4",
        "Math.pow",
        "RISK_MATRIX",
    ):
        assert forbidden not in js
