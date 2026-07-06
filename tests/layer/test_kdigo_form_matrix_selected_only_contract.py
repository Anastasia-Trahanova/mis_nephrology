"""
Назначение файла: контрактные тесты live-блока KDIGO в форме приёма.

Что проверяется:
- в форме есть кнопка обновления матрицы;
- в форме есть поле полной формулировки для заключения;
- JavaScript строит матрицу только по активным рассчитанным парам, а не по всем теоретическим пересечениям;
- JavaScript очищает и пересобирает selected-пары при каждом обновлении.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "app" / "templates" / "appointment_form" / "_kdigo_risk_preview.html"
JS = ROOT / "app" / "static" / "js" / "kdigo_risk_preview.js"
CSS = ROOT / "app" / "static" / "css" / "04_kdigo_risk.css"


def test_kdigo_form_preview_contains_matrix_and_refresh_button():
    text = TEMPLATE.read_text(encoding="utf-8")

    assert 'id="kdigoRiskPreview"' in text
    assert 'id="kdigoRefreshMatrixButton"' in text
    assert 'id="kdigoConclusionText"' in text
    assert 'id="kdigoFormMatrix"' in text
    assert 'id="kdigoSelectedPairs"' in text
    assert "Матрица рассчитанных пар СКФ × альбуминурия" in text


def test_kdigo_javascript_renders_matrix_from_active_assessments_only():
    text = JS.read_text(encoding="utf-8")

    assert "function renderMatrix(assessments)" in text
    assert "const calculated = assessments.filter" in text
    assert "matrix.set(`${rowKey}||${colKey}`, item);" in text
    assert "const assessment = matrix.get" in text
    assert "kdigo-matrix-empty-cell" in text
    assert "clearSelectedPairs();" in text
    assert "calculated.forEach(addSelectedPair);" in text


def test_kdigo_refresh_button_is_wired_to_render_all():
    text = JS.read_text(encoding="utf-8")

    assert "#kdigoRefreshMatrixButton" in text
    assert "renderAll();" in text
    assert "MutationObserver" in text


def test_kdigo_css_has_empty_cell_style():
    text = CSS.read_text(encoding="utf-8")

    assert ".kdigo-matrix-empty-cell" in text
    assert ".kdigo-form-matrix-container" in text
