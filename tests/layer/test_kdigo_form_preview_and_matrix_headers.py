"""
Проверки интеграции KDIGO-preview и матрицы.

Зачем нужны:
- гарантируют, что live-блок KDIGO реально встроен в форму приёма, а не просто
  лежит отдельным файлом;
- фиксируют новый вид матрицы: категории СКФ/альбуминурии в заголовках,
  внутри ячеек только уровень риска без дублирования С3аA2.
"""

from datetime import date
from pathlib import Path

from app.services.kdigo_risk_matrix_service import build_kdigo_risk_matrix

ROOT = Path(__file__).resolve().parents[2]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_kdigo_preview_is_included_in_conclusion_before_diagnoses():
    content = read("app/templates/appointment_form/_conclusion.html")

    include = 'appointment_form/_kdigo_risk_preview.html'
    diagnosis_block = 'icd10_diagnosis_block.html'

    assert include in content
    assert diagnosis_block in content
    assert content.index(include) < content.index(diagnosis_block)


def test_patient_card_matrix_uses_headers_for_categories_and_risk_only_in_cells():
    content = read("app/templates/patient_card/_ckd_prognosis.html")

    assert "column.categories" in content
    assert "row.gfr_categories" in content
    assert "item.prognosis_text" in content

    matrix_part = content.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    assert "item.combined_category" not in matrix_part


def test_matrix_service_builds_date_and_category_headers():
    history = [
        {
            "gfr_investigation_date": date(2026, 7, 3),
            "gfr_category": "С3а",
            "albuminuria_investigation_date": date(2026, 6, 29),
            "albuminuria_category": "A2",
            "prognosis_text": "высокий риск",
            "prognosis_level": "high",
        }
    ]

    matrix = build_kdigo_risk_matrix(history)

    assert matrix["has_values"] is True
    assert matrix["rows"][0]["label"] == "03.07.2026 / С3а"
    assert matrix["albuminuria_columns"][0]["label"] == "29.06.2026 / A2"
    assert matrix["rows"][0]["cells"][0]["items"] == history
