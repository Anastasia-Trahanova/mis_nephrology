from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_kdigo_preview_template_contains_saved_matrix_contract():
    template = (ROOT / "app/templates/appointment_form/_kdigo_risk_preview.html").read_text(encoding="utf-8")

    assert "kdigoRiskMatrixContainer" in template
    assert "kdigoSavedRiskPairsData" in template
    assert "kdigo_saved_risk_pairs" in template
    assert "kdigoRefreshMatrix" in template
    assert "kdigoConclusionText" in template


def test_kdigo_javascript_renders_saved_pairs_and_not_theoretical_matrix():
    js = (ROOT / "app/static/js/kdigo_risk_preview.js").read_text(encoding="utf-8")

    assert "loadSavedRiskPairs" in js
    assert "renderRiskMatrix" in js
    assert "savedPairs.concat(activeCurrentPairs)" in js
    assert "Нет рассчитанных пар для отображения в матрице" in js
    assert "Обновить матрицу" not in js  # текст кнопки живёт в шаблоне, не в JS


def test_appointment_context_passes_kdigo_saved_pairs_to_form():
    service = (ROOT / "app/services/appointment_form_context_service.py").read_text(encoding="utf-8")

    assert "_fetch_patient_ckd_prognosis_history" in service
    assert "_serialize_saved_kdigo_pairs" in service
    assert '"kdigo_saved_risk_pairs"' in service
    assert '"kdigo_previous_gfr_data"' in service
    assert '"kdigo_previous_albuminuria_data"' in service
