"""
Объединенный расчет основных показателей ХБП для приема пациента.

Что происходит в этом файле
---------------------------
Функция `calculate_all_metrics` объединяет несколько отдельных расчетов:

1. возраст пациента на дату приема;
2. eGFR по CKD-EPI 2021 creatinine;
3. клиренс креатинина по Cockcroft–Gault;
4. категорию СКФ: С1, С2, С3а, С3б, С4, С5.

Этот файл нужен как удобная точка для старого кода, где при сохранении приема сразу рассчитываются несколько показателей.

Какие значения ожидаются
------------------------
`creatinine_umol_l`: - креатинин крови, мкмоль/л.
`birth_date`: - дата рождения пациента.
`appointment_date`: - дата приема.
`gender`: - пол пациента в формате, который сейчас используется в приложении.
`weight_kg`: - масса тела пациента, кг.

Что дает на выход
-----------------
Функция возвращает словарь:

```text
egfr_ckdepi              — eGFR CKD-EPI, мл/мин/1,73 м²
crcl_cockcroft_gault     — клиренс Cockcroft–Gault, мл/мин
ckd_stage                — категория СКФ: С1, С2, С3а, С3б, С4, С5
```

Если входных данных недостаточно, отдельные значения могут быть None.
"""

from __future__ import annotations

from .ckd_stage import get_ckd_stage, normalize_ckd_stage_for_storage
from .cockcroft_gault import calculate_cockcroft_gault
from .common import calculate_age
from .egfr import calculate_ckd_epi_2021


def calculate_all_metrics(creatinine_umol_l, birth_date, appointment_date, gender, weight_kg, serum_creatinine_unit: str = "umol_l",):
    age = calculate_age(birth_date, appointment_date)

    egfr_ckdepi = calculate_ckd_epi_2021(
        creatinine_umol_l=creatinine_umol_l,
        age=age,
        gender=gender,
        serum_creatinine_unit=serum_creatinine_unit,
    )

    crcl_cockcroft_gault = calculate_cockcroft_gault(
        creatinine_umol_l=creatinine_umol_l,
        age=age,
        weight_kg=weight_kg,
        gender=gender,
        serum_creatinine_unit=serum_creatinine_unit,
    )

    ckd_stage = get_ckd_stage(egfr_ckdepi)
    ckd_stage = normalize_ckd_stage_for_storage(ckd_stage)

    return {
        "egfr_ckdepi": egfr_ckdepi,
        "crcl_cockcroft_gault": crcl_cockcroft_gault,
        "ckd_stage": ckd_stage,
    }
