"""Static contracts for the server-driven kidney preview and selected KDIGO pair."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_template_exposes_server_preview_and_single_selected_pair_contract():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert 'id="kdigoRiskPreview"' in html
    assert 'id="kdigoCurrentVisitOptions"' in html
    assert 'id="kdigoSelectedConclusionText"' in html
    assert 'id="kdigoSelectedPair"' in html
    assert 'name="kdigo_selected_pair"' in html
    assert 'id="kdigoToggleHistoryButton"' in html
    assert 'id="kdigoHistoryPanel"' in html
    assert "patient.gender is not none" in html
    assert "kdigo-server-v2" in html


def test_initial_template_text_states_that_current_kdigo_needs_new_kidney_data():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "Текущий прогноз появляется после ввода новых почечных показателей" in html
    assert "Если вариантов несколько, выберите один вариант для сохранения" in html


def test_browser_js_is_only_transport_rendering_and_selection_layer():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert 'fetch("/api/kidney-preview"' in js
    assert "AbortController" in js
    assert "JSON.stringify(payload)" in js
    assert "renderMetrics" in js
    assert "renderAlbuminuria" in js
    assert "renderKdigo" in js
    assert "selection_key" in js
    assert "kdigo_selected_pair" in js

    for forbidden in (
        "88.4",
        "8.84",
        "RISK_MATRIX",
        "Math.pow",
        "calculateCkdEpi",
        "calculateCockcroftGault",
        "categoryFromAcr",
    ):
        assert forbidden not in js


def test_browser_js_does_not_request_preview_until_new_kidney_input_exists():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "function hasKidneyInput" in js
    assert "if (!hasKidneyInput(payload))" in js
    assert "clearCurrentPreview()" in js


def test_browser_js_auto_selects_only_single_calculated_candidate():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "calculated.length === 1" in js
    assert "writeSelection(calculated[0])" in js
    assert "calculated.length > 1 && !selectedPair" in js
    assert "Выберите один вариант прогноза" in js


def test_browser_js_blocks_submit_when_multiple_candidates_have_no_selection():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert 'form.addEventListener("submit"' in js
    assert "event.preventDefault()" in js
    assert "calculated.length > 1 && !selectedPair" in js
    assert "scrollIntoView" in js


def test_browser_js_recalculates_on_all_kidney_inputs_and_units():
    js = read("app/static/js/kdigo_risk_preview.js")

    for name in (
        "creatinine",
        "biochemistry_investigation_date",
        "urine_albumin",
        "urine_albumin_unit",
        "urine_creatinine",
        "urine_creatinine_unit",
        "daily_albumin_excretion",
        "albuminuria_investigation_date",
    ):
        assert f'"{name}"' in js


def test_parser_reads_selected_pair_but_does_not_trust_client_medical_result():
    parser = read("app/services/appointment_form_parser.py")

    assert '"kdigo_selected_pair": empty_to_none(form.get("kdigo_selected_pair"))' in parser


def test_save_service_rebuilds_candidates_and_requires_choice_for_multiple_results():
    service = read("app/services/appointment_save_service.py")

    assert "build_kdigo_assessments_for_appointment(cur, appointment_id)" in service
    assert 'selected_pair = appointment_data.get("kdigo_selected_pair")' in service
    assert "len(kdigo_assessments) == 1 and not selected_pair" in service
    assert "len(kdigo_assessments) > 1 and not selected_pair" in service
    assert "Выберите один вариант прогноза KDIGO" in service
    assert "item.get(\"selection_key\") == selected_pair" in service
    assert "save_ckd_prognosis_for_appointment(" in service
    assert "selected_pair=selected_pair" in service


def test_repository_builds_cartesian_current_source_combinations():
    repository = read("app/repositories/ckd_prognosis.py")

    assert "for gfr_source in current_gfr_sources:" in repository
    assert "for albuminuria_source in current_albuminuria_sources:" in repository
    assert 'source["selection_ref"] = f"gfr:current:{index}"' in repository
    assert 'source["selection_ref"] = f"albuminuria:current:{index}"' in repository
    assert 'assessment["selection_key"] = _selection_key' in repository


def test_repository_saves_only_selected_pair_when_form_provides_selection():
    repository = read("app/repositories/ckd_prognosis.py")

    assert "selected_pair: str | None = None" in repository
    assert "if selected_pair:" in repository
    assert 'item.get("selection_key") == selected_pair' in repository
    assert "Выбранный вариант KDIGO больше не соответствует сохранённым анализам" in repository


def test_server_preview_route_is_present():
    router = read("app/routers/lab_api.py")

    assert '@router.post("/api/kidney-preview")' in router
    assert "build_kidney_preview(payload)" in router


def test_history_matrix_in_form_is_rendered_from_saved_history_context_only():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "kdigo_previous_history_matrix" in html
    assert "history_matrix.rows" in html
    assert 'cell["items"]' in html
    assert "calculate" not in html.lower()


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_kdigo_live_js_is_syntactically_valid():
    subprocess.run(
        ["node", "--check", str(ROOT / "app/static/js/kdigo_risk_preview.js")],
        check=True,
    )
