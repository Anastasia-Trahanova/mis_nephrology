"""
Публичный интерфейс папки medical_algorithms.

Этот файл позволяет импортировать медицинские расчетные функции из одной точки:

```python
from app.medical_algorithms import calculate_ckd_epi_2021
```

При этом сами функции физически разложены по отдельным файлам:
CKD-EPI, Cockcroft–Gault, стадии ХБП, альбуминурия, прогноз KDIGO.
"""

from .albuminuria import (
    calculate_albumin_creatinine_ratio,
    calculate_albuminuria_metrics,
    get_albuminuria_category,
    normalize_urine_albumin_to_mg_l,
    normalize_urine_creatinine_to_mmol_l,
)

from .ckd_stage import (
    ALLOWED_CKD_STAGES,
    get_ckd_stage,
    is_valid_ckd_stage,
    normalize_ckd_stage_for_storage,
)

from .common import (
    SERUM_CREATININE_MG_DL,
    SERUM_CREATININE_UMOL_L,
    SERUM_CREATININE_UNITS,
    UMOL_L_PER_MG_DL,
    calculate_age,
    is_female_gender,
    normalize_serum_creatinine_to_mg_dl,
    normalize_serum_creatinine_to_umol_l,
    to_float,
)

from .cockcroft_gault import calculate_cockcroft_gault
from .egfr import calculate_ckd_epi_2021
from .metrics import calculate_all_metrics
from .prognosis import calculate_ckd_prognosis


__all__ = [
    "ALLOWED_CKD_STAGES",
    "calculate_age",
    "calculate_all_metrics",
    "calculate_albumin_creatinine_ratio",
    "calculate_albuminuria_metrics",
    "calculate_ckd_epi_2021",
    "calculate_ckd_prognosis",
    "calculate_cockcroft_gault",
    "get_albuminuria_category",
    "get_ckd_stage",
    "is_female_gender",
    "is_valid_ckd_stage",
    "normalize_ckd_stage_for_storage",
    "normalize_urine_albumin_to_mg_l",
    "normalize_urine_creatinine_to_mmol_l",
    "to_float",
    "SERUM_CREATININE_MG_DL",
    "SERUM_CREATININE_UMOL_L",
    "SERUM_CREATININE_UNITS",
    "UMOL_L_PER_MG_DL",
    "normalize_serum_creatinine_to_mg_dl",
    "normalize_serum_creatinine_to_umol_l",
]
