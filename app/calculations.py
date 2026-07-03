"""
Мостик совместимости для старого кода.

Раньше медицинские расчетные функции лежали прямо в app/calculations.py.

Теперь сами алгоритмы вынесены в папку:

    app/medical_algorithms/

Но старые импорты пока оставляем рабочими:

    from app.calculations import calculate_all_metrics
    from app.calculations import calculate_ckd_prognosis
    from app.calculations import normalize_ckd_stage_for_storage

Поэтому этот файл не содержит самостоятельных формул. Он только переэкспортирует функции из новых модулей.

Это переходный этап рефакторинга.

Мы не переписываем сразу app/database.py, app/routers/patients.py и другие старые файлы. Они продолжают импортировать функции из calculations.py,
а calculations.py уже берет настоящую реализацию из app/medical_algorithms. Так меньше риск сломать приложение.
"""

from .medical_algorithms import (
    calculate_age,
    calculate_all_metrics,
    calculate_albumin_creatinine_ratio,
    calculate_albuminuria_metrics,
    calculate_ckd_epi_2021,
    calculate_ckd_prognosis,
    calculate_cockcroft_gault,
    get_albuminuria_category,
    get_ckd_stage,
    normalize_ckd_stage_for_storage,
    normalize_urine_albumin_to_mg_l,
    normalize_urine_creatinine_to_mmol_l,
    to_float,
    normalize_serum_creatinine_to_mg_dl,
    normalize_serum_creatinine_to_umol_l,
    SERUM_CREATININE_MG_DL,
    SERUM_CREATININE_UMOL_L,
)


__all__ = [
    "calculate_age",
    "calculate_all_metrics",
    "calculate_albumin_creatinine_ratio",
    "calculate_albuminuria_metrics",
    "calculate_ckd_epi_2021",
    "calculate_ckd_prognosis",
    "calculate_cockcroft_gault",
    "get_albuminuria_category",
    "get_ckd_stage",
    "normalize_ckd_stage_for_storage",
    "normalize_urine_albumin_to_mg_l",
    "normalize_urine_creatinine_to_mmol_l",
    "to_float",
    "normalize_serum_creatinine_to_mg_dl",
    "normalize_serum_creatinine_to_umol_l",
    "SERUM_CREATININE_MG_DL",
    "SERUM_CREATININE_UMOL_L",
]