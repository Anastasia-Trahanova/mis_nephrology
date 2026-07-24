"""
Назначение файла: контрактные проверки точечных исправлений формы приёма и
карточки пациента.

Что выполняет файл:
- проверяет локальную подсветку обязательного уточнения пальпации почек;
- проверяет кнопку открытия матрицы KDIGO в карточке;
- защищает от повторного заголовка «Заключение»;
- проверяет единое оформление подзаголовков диагнозов.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_kidney_palpation_has_inline_validation_target_and_message():
    template = _read("app/templates/appointment_form/_examination.html")
    guard = _read("app/static/js/simple_form_guard.js")

    assert 'id="kidneyPalpation"' in template
    assert 'id="kidneyPalpationDetails"' in template
    assert 'id="kidneyPalpationDetailsMessage"' in template
    assert "Уточните данные пальпации почек" in guard
    assert 'triggerName: "kidney_palpation"' in guard
    assert 'triggerValue: "palpable"' in guard
    assert 'targetName: "kidney_palpation_details"' in guard
    assert "event.preventDefault()" in guard
    assert '"invalid"' in guard


def test_kdigo_matrix_is_hidden_until_button_click():
    template = _read("app/templates/patient_card/_ckd_prognosis.html")

    assert "Посмотреть матрицу прогнозов по KDIGO" in template
    assert 'id="kdigoCardToggleMatrixButton"' in template
    assert 'id="kdigoCardMatrixPanel"' in template
    assert 'id="kdigoCardMatrixPanel" class="mt-3" hidden' in template
    assert "Скрыть матрицу прогнозов по KDIGO" in template


def test_kdigo_partial_does_not_repeat_conclusion_heading():
    template = _read("app/templates/patient_card/_ckd_prognosis.html")

    assert "Прогноз по KDIGO" in template
    assert "<h5>Заключение</h5>" not in template
    assert "<h4>Заключение</h4>" not in template


def test_diagnosis_subheadings_use_same_neutral_text_style():
    template = _read("app/templates/patient_card/_diagnoses.html")

    assert '<div class="fw-semibold mb-2">Основной диагноз</div>' in template
    assert '<div class="fw-semibold mb-2">Осложнения основного диагноза</div>' in template
    assert '<div class="fw-semibold mb-2">Сопутствующие заболевания</div>' in template
    assert "<h6" not in template
