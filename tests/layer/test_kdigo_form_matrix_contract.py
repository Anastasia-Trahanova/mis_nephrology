"""
Проверяет, что KDIGO live-блок действительно встроен в форму приёма.

Эти тесты не проверяют медицинскую матрицу целиком: для этого есть отдельные
тесты kdigo_risk_logic. Здесь защищаем именно HTML/JS-контракт формы:
- include стоит в блоке заключения;
- в preview есть матрица, кнопка обновления и поле с полной формулировкой;
- JS умеет строить матрицу;
- CSS содержит классы подсветки.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_conclusion_includes_kdigo_preview_before_diagnoses():
    content = read("app/templates/appointment_form/_conclusion.html")
    include_pos = content.index('{% include "appointment_form/_kdigo_risk_preview.html" %}')
    diagnoses_pos = content.index('{% include "icd10_diagnosis_block.html" %}')
    assert include_pos < diagnoses_pos
    assert "ckdPrognosisBlock" not in content


def test_kdigo_preview_has_matrix_refresh_button_and_conclusion_field():
    content = read("app/templates/appointment_form/_kdigo_risk_preview.html")
    assert "id=\"kdigoRiskPreview\"" in content
    assert "id=\"kdigoRiskRefreshBtn\"" in content
    assert "id=\"kdigoRiskMatrix\"" in content
    assert "id=\"kdigoConclusionText\"" in content
    assert "name=\"kdigo_conclusion_text\"" in content
    assert "kdigoPreviousGfrData" in content
    assert "kdigoPreviousAlbuminuriaData" in content


def test_kdigo_preview_js_builds_form_matrix():
    content = read("app/static/js/kdigo_risk_preview.js")
    assert "function renderMatrix" in content
    assert "kdigoRiskMatrix" in content
    assert "kdigoRiskRefreshBtn" in content
    assert "СКФ \\\\ альбуминурия" in content
    assert "riskPhrase" in content
    assert "kdigo_excluded_pair" in content


def test_kdigo_css_contains_risk_classes():
    content = read("app/static/css/04_kdigo_risk.css")
    assert ".kdigo-risk-preview" in content
    assert ".kdigo-risk-matrix" in content
    assert ".kdigo-risk-low" in content
    assert ".kdigo-risk-moderate" in content
    assert ".kdigo-risk-high" in content
    assert ".kdigo-risk-very_high" in content
