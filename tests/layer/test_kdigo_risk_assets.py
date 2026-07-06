"""
Тесты файлов KDIGO-патча.

Они не запускают браузер и БД. Проверяют, что в проекте есть нужные файлы и
ключевые фразы/селекторы, чтобы случайно не удалить live-блок или матрицу.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_kdigo_preview_template_contains_required_phrase_and_hidden_pairs():
    content = read("app/templates/appointment_form/_kdigo_risk_preview.html")

    assert "Оценка риска по KDIGO" in content
    assert "данные по альбуминурии и СКФ не предоставлены" in content
    assert "kdigoExcludedPairs" in content
    assert "kdigoPreviousGfrData" in content
    assert "kdigoPreviousAlbuminuriaData" in content


def test_kdigo_javascript_handles_fallback_stale_and_remove_button():
    content = read("app/static/js/kdigo_risk_preview.js")

    assert "latestPreviousBeforeOrOn" in content
    assert "данные по альбуминурии не предоставлены" in content
    assert "рекомендовано повторить исследование" in content
    assert "kdigo_excluded_pair" in content
    assert "✖" in content


def test_patient_card_template_contains_matrix_not_old_history_only():
    content = read("app/templates/patient_card/_ckd_prognosis.html")

    assert "Матрица риска по KDIGO" in content
    assert "ckd_prognosis_matrix" in content
    assert "СКФ \\ Альбуминурия" in content
    assert "display_text" in content


def test_css_file_contains_block_and_matrix_classes():
    content = read("app/static/css/04_kdigo_risk.css")

    assert ".kdigo-risk-preview" in content
    assert ".kdigo-risk-high" in content
    assert ".kdigo-risk-matrix" in content
