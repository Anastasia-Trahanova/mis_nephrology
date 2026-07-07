from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METRICS_TEMPLATE = ROOT / "app" / "templates" / "appointment_form" / "_metrics.html"


def _metrics_html() -> str:
    return METRICS_TEMPLATE.read_text(encoding="utf-8")


def test_metrics_table_has_no_manual_update_button():
    html = _metrics_html()

    assert "updateMetricsTableBtn" not in html
    assert "Обновить" not in html
    assert "Обновляется автоматически при вводе креатинина" in html


def test_metrics_table_keeps_existing_history_rows_and_live_column_marker():
    html = _metrics_html()

    assert "metricsHeaderRow" in html
    assert "egfrRow" in html
    assert "cockcroftRow" in html
    assert "ckdStageRow" in html
    assert "metrics_history" in html
    assert "new-metrics-column" in html


def test_metrics_table_recalculates_from_creatinine_and_patient_fields_live():
    html = _metrics_html()

    for selector in (
        '[name="creatinine"]',
        '[name="biochemistry_investigation_date"]',
        '[name="weight"]',
        '[name="birth_date"]',
        '[name="gender"]',
        '[name="appointment_date"]',
    ):
        assert selector in html

    assert "document.addEventListener('input'" in html
    assert "document.addEventListener('change'" in html
    assert "scheduleLiveMetricsTableUpdate" in html
    assert "requestAnimationFrame" in html


def test_metrics_table_updates_after_dynamic_biochemistry_column_is_added():
    html = _metrics_html()

    assert "#addBiochemistryColumnBtn" in html
    assert "event.target.closest('#addBiochemistryColumnBtn')" in html
    assert "scheduleLiveMetricsTableUpdate();" in html


def test_metrics_table_does_not_show_alert_for_empty_creatinine():
    html = _metrics_html()

    assert "alert(" not in html
    assert "Добавьте биохимический анализ и заполните креатинин" not in html


def test_metrics_table_contains_gfr_formulas_and_ckd_categories():
    html = _metrics_html()

    assert "calculateCkdEpi2021" in html
    assert "calculateCockcroftGault" in html
    assert "creatinineUmol / 88.4" in html
    assert "return 'С1'" in html
    assert "return 'С3a'" in html
    assert "return 'С3b'" in html
    assert "return 'С5'" in html
