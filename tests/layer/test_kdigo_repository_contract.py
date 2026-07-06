"""
Текстовый контракт repository KDIGO.

Проверяет, что новая repository-логика больше не хранит только одну строку на
приём, а сохраняет источники СКФ и альбуминурии.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_repository_saves_source_ids_and_dates():
    content = (ROOT / "app/repositories/ckd_prognosis.py").read_text(encoding="utf-8")

    assert "gfr_metric_id" in content
    assert "albuminuria_result_id" in content
    assert "gfr_investigation_date" in content
    assert "albuminuria_investigation_date" in content
    assert "build_kdigo_assessments_for_appointment" in content
    assert "excluded_pairs" in content


def test_repository_no_longer_requires_single_result_per_appointment():
    content = (ROOT / "app/repositories/ckd_prognosis.py").read_text(encoding="utf-8")

    assert "DELETE FROM ckd_prognosis_results" in content
    assert "display_order" in content
    assert "ON CONFLICT (appointment_id, gfr_metric_id, albuminuria_result_id)" in content
