"""
Назначение файла: совместимость старого имени модуля прогноза ХБП.

Раньше матрица KDIGO жила прямо здесь. Теперь полноценная логика вынесена в
app/medical_algorithms/kdigo_risk.py, потому что это уже не только матрица,
но и формулировки, допустимые интервалы между анализами и ключи пар
СКФ × альбуминурия.

Что редактировать здесь:
- обычно ничего;
- новые правила KDIGO редактируются в kdigo_risk.py.

Что не редактировать здесь:
- SQL и сохранение прогноза;
- шаблоны и JavaScript.
"""

from __future__ import annotations

from .kdigo_risk import (  # noqa: F401
    MAX_INTERVAL_DAYS_BY_RISK_LEVEL,
    RISK_MATRIX,
    RISK_SEVERITY_ORDER,
    build_source_pair_key,
    calculate_ckd_prognosis,
    calculate_kdigo_risk,
    format_missing_phrase,
    format_risk_phrase,
    format_stale_phrase,
    is_interval_allowed,
    max_interval_days_for_risk,
    normalize_albuminuria_category,
    source_interval_days,
)
