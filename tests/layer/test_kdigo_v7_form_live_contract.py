"""Contract tests for the server-driven live kidney calculation block."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_html_keeps_form_contract_and_preserves_false_gender():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")
    assert 'id="kdigoRiskPreview"' in html
    assert 'id="kdigoCurrentVisitOptions"' in html
    assert 'id="kdigoSelectedConclusionText"' in html
    assert 'name="kdigo_selected_conclusion_text"' in html
    assert 'id="kdigoExcludedPairsContainer"' in html
    assert "patient.gender is not none" in html
    assert "kdigo-server-v1" in html


def test_browser_js_contains_no_medical_formula_duplicates():
    js = read("app/static/js/kdigo_risk_preview.js")
    assert 'fetch("/api/kidney-preview"' in js
    assert "AbortController" in js
    assert 'document.addEventListener("input"' in js
    assert 'document.addEventListener("change"' in js
    assert "replaceBiochemistryAddButton" in js
    assert "addBiochemistryColumn" in js
    assert "replaceAlbuminuriaAddButton" in js
    assert "addAlbuminuriaColumn" in js
    for forbidden in ("88.4", "8.84", "RISK_MATRIX", "Math.pow", "calculateCkdEpi", "categoryFromAcr", "MutationObserver"):
        assert forbidden not in js


def test_metrics_template_contains_no_ckd_formula_js():
    html = read("app/templates/appointment_form/_metrics.html")
    assert 'id="metricsTable"' in html
    assert 'id="egfrRow"' in html
    assert 'id="ckdStageRow"' in html
    assert "calculateCkdEpi" not in html
    assert "Math.pow" not in html
    assert "<script>" not in html


def test_lab_api_exposes_server_preview():
    router = read("app/routers/lab_api.py")
    assert '@router.post("/api/kidney-preview")' in router
    assert "build_kidney_preview(payload)" in router


def test_save_service_refuses_silent_loss_of_known_patient_egfr():
    service = read("app/services/appointment_save_service.py")
    assert "saved_metric_count" in service
    assert "saved_metric_count != len(metric_sources)" in service
    assert "Не удалось рассчитать СКФ CKD-EPI" in service


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_kdigo_live_js_is_syntactically_valid():
    subprocess.run(
        ["node", "--check", str(ROOT / "app/static/js/kdigo_risk_preview.js")],
        check=True,
    )
