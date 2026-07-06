from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_kdigo_preview_template_contains_conclusion_and_matrix():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert 'id="kdigoRiskPreview"' in html
    assert 'id="kdigoRiskLines"' in html
    assert 'id="kdigoRiskMatrix"' in html
    assert 'id="kdigoRiskRefreshMatrix"' in html
    assert 'kdigoPreviousGfrData' in html
    assert 'kdigoPreviousAlbuminuriaData' in html


def test_kdigo_preview_is_included_before_diagnosis_block():
    html = read("app/templates/appointment_form/_conclusion.html")

    include_pos = html.find('appointment_form/_kdigo_risk_preview.html')
    diagnosis_pos = html.find('icd10_diagnosis_block.html')

    assert include_pos != -1
    assert diagnosis_pos != -1
    assert include_pos < diagnosis_pos
    assert '<strong>{% include "appointment_form/_kdigo_risk_preview.html" %}</strong>' not in html
    assert 'ckdPrognosisBlock' not in html


def test_kdigo_javascript_builds_matrix_and_deduplicates_phrases():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert 'function renderMatrix()' in js
    assert 'function renderConclusion()' in js
    assert 'uniqueByKey' in js
    assert 'kdigoRiskRefreshMatrix' in js
    assert 'kdigoRiskMatrix' in js
    assert 'kdigo_assessment_phrase' in js


def test_kdigo_css_has_matrix_risk_classes():
    css = read("app/static/css/04_kdigo_risk.css")

    assert '.kdigo-risk-preview' in css
    assert '.kdigo-matrix-low' in css
    assert '.kdigo-matrix-moderate' in css
    assert '.kdigo-matrix-high' in css
    assert '.kdigo-matrix-very_high' in css
