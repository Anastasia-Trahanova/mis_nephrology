from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_form_has_current_visit_selection_and_history_button():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "Выберите вариант прогноза" in html
    assert "kdigoCurrentRiskOptions" in html
    assert "kdigoSelectedPair" in html
    assert "kdigoSelectedRiskText" in html
    assert "Посмотреть историю прогнозов по KDIGO" in html
    assert "kdigoHistoryPanel" in html
    assert "kdigoSavedRiskHistoryData" in html
    assert "✖" not in html


def test_kdigo_js_builds_one_current_option_per_gfr_and_radio_selection():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "buildCurrentVisitAssessments" in js
    assert "chooseDefaultSelected" in js
    assert "radio.type = \"radio\"" in js
    assert "kdigo_current_selected_option" in js
    assert "closestByDate(currentAlbuminuria, gfr.date)" in js
    assert "syncHiddenExcludedPairs" in js
    assert "allBackendPotentialCalculatedKeys" in js
    assert "renderHistoryMatrix" in js
    assert "kdigoHistoryToggleButton" in js
    assert "kdigo-risk-remove" not in js


def test_appointment_form_context_exposes_kdigo_history_for_repeat_visit():
    service = read("app/services/appointment_form_context_service.py")

    assert "_fetch_patient_ckd_prognosis_history" in service
    assert "ckd_prognosis_history" in service


def test_kdigo_css_has_current_options_and_history_matrix_styles():
    css = read("app/static/css/04_kdigo_risk.css")

    assert ".kdigo-current-option" in css
    assert ".kdigo-history-matrix-table" in css
    assert ".kdigo-history-cell-high" in css
