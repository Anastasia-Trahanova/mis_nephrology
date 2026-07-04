"""
Мостик совместимости для старого кода.

Раньше медицинские расчетные функции лежали прямо в app/calculations.py.
Теперь сами алгоритмы вынесены в папку:

    app/medical_algorithms/

Но старые импорты пока оставляем рабочими:

    from app.calculations import calculate_all_metrics
    from app.calculations import calculate_ckd_prognosis
    from app.calculations import normalize_ckd_stage_for_storage

Поэтому этот файл не содержит самостоятельных формул.
Он только переэкспортирует функции из новых модулей.
"""

from .medical_algorithms import (
    SERUM_CREATININE_MG_DL,
    SERUM_CREATININE_UMOL_L,
    calculate_age,
    calculate_all_metrics,
    calculate_albumin_creatinine_ratio,
    calculate_albuminuria_metrics,
    calculate_bmi,
    calculate_ckd_epi_2021,
    calculate_ckd_prognosis,
    calculate_cockcroft_gault,
    get_albuminuria_category,
    get_ckd_stage,
    normalize_ckd_stage_for_storage,
    normalize_serum_creatinine_to_mg_dl,
    normalize_serum_creatinine_to_umol_l,
    normalize_urine_albumin_to_mg_l,
    normalize_urine_creatinine_to_mmol_l,
    to_float,
)


__all__ = [
    "SERUM_CREATININE_MG_DL",
    "SERUM_CREATININE_UMOL_L",
    "calculate_age",
    "calculate_all_metrics",
    "calculate_albumin_creatinine_ratio",
    "calculate_albuminuria_metrics",
    "calculate_bmi",
    "calculate_ckd_epi_2021",
    "calculate_ckd_prognosis",
    "calculate_cockcroft_gault",
    "get_albuminuria_category",
    "get_ckd_stage",
    "normalize_ckd_stage_for_storage",
    "normalize_serum_creatinine_to_mg_dl",
    "normalize_serum_creatinine_to_umol_l",
    "normalize_urine_albumin_to_mg_l",
    "normalize_urine_creatinine_to_mmol_l",
    "to_float",
]