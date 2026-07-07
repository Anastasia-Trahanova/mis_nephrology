"""
Тесты KDIGO v7: контракт live-блока формы.

Это не browser-тесты. Они быстро проверяют, что HTML/JS/CSS соответствуют текущему
ТЗ: строки прогноза, radio-выбор, история отдельно, без старого поля заключения
и без подсветки всего общего блока.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_html_has_current_forecast_rows_and_hidden_selected_text_only():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert 'id="kdigoRiskPreview"' in html
    assert 'id="kdigoCurrentVisitOptions"' in html
    assert 'id="kdigoSelectedConclusionText"' in html
    assert 'name="kdigo_selected_conclusion_text"' in html
    assert 'id="kdigoExcludedPairsContainer"' in html
    assert "Выбранный кружочком вариант будет сохранён" in html

    # Старое видимое дублирующее поле заключения больше не должно возвращаться.
    assert "Формулировка для заключения" not in html
    assert "kdigo_conclusion_text" not in html
    assert "kdigoConclusionText" not in html


def test_html_history_is_temporary_repeat_visit_panel_not_conclusion_text():
    html = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "form_mode == 'new_appointment'" in html
    assert 'id="kdigoToggleHistoryButton"' in html
    assert 'id="kdigoHistoryPanel"' in html
    assert "Посмотреть историю прогнозов по KDIGO" in html
    assert "Сохранённые прогнозы по прошлым приёмам отсутствуют" in html
    assert "kdigoPreviousGfrData" in html
    assert "kdigoPreviousAlbuminuriaData" in html


def test_js_starts_with_one_missing_phrase_and_does_not_accumulate_empty_rows():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "EMPTY_BOTH_TEXT" in js
    assert "return [missingAssessment(\"both\", 0, null)]" in js
    assert "compactMissingAssessments" in js
    assert "return assessments.length ? [assessments[0]]" in js


def test_js_builds_postrочный_forecast_rows_for_uneven_current_sources():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "function buildCurrentVisitAssessments" in js
    assert "const rowsCount = Math.max(currentGfr.length, currentAlbuminuria.length)" in js
    assert "const gfrSource = currentGfr[index] || currentGfr[0]" in js
    assert "const albuminuriaSource = currentAlbuminuria[index] || currentAlbuminuria[0]" in js
    assert "assessments.push(buildCalculatedAssessment(gfrSource, albuminuriaSource, index))" in js

    # Защита от старого поведения: не должна использоваться логика ближайшей даты
    # для текущих пар, потому что врач добавляет строки анализов построчно.
    assert "closestByDate(currentAlbuminuria, gfr.date)" not in js
    assert "allBackendPotentialCalculatedKeys" not in js


def test_js_radio_selects_one_calculated_forecast_and_excludes_other_calculated_rows():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert 'radio.type = "radio"' in js
    assert 'radio.name = "kdigo_selected_current_option"' in js
    assert "radio.disabled = assessment.status !== \"calculated\"" in js
    assert "function selectedAssessment" in js
    assert "return calculated[0]" in js
    assert "function writeExcludedPairs" in js
    assert 'input.name = "kdigo_excluded_pair"' in js
    assert ".filter((item) => item.status === \"calculated\" && item.key !== selectedKey)" in js


def test_js_updates_on_input_change_and_dynamic_analysis_rows():
    js = read("app/static/js/kdigo_risk_preview.js")

    assert "document.addEventListener(\"input\"" in js
    assert "document.addEventListener(\"change\"" in js
    assert "new MutationObserver" in js
    assert "observer.observe(document.body" in js
    assert "attributes: true" in js


def test_css_colors_only_forecast_rows_and_history_cells_not_whole_block():
    css = read("app/static/css/04_kdigo_risk.css")

    assert ".kdigo-current-option.kdigo-risk-low" in css
    assert ".kdigo-current-option.kdigo-risk-moderate" in css
    assert ".kdigo-current-option.kdigo-risk-high" in css
    assert ".kdigo-current-option.kdigo-risk-very_high" in css
    assert ".kdigo-history-risk.kdigo-risk-high" in css
    assert ".kdigo-current-option-neutral" in css

    # Общий контейнер не должен получать цветовой класс риска.
    assert ".kdigo-live-block.kdigo-risk" not in css


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_kdigo_live_js_is_syntactically_valid():
    subprocess.run(
        ["node", "--check", str(ROOT / "app/static/js/kdigo_risk_preview.js")],
        check=True,
    )
