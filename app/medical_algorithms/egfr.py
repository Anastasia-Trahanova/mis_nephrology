"""
Расчет расчетной скорости клубочковой фильтрации eGFR по формуле CKD-EPI 2021 creatinine.
Функция `calculate_ckd_epi_2021` рассчитывает eGFR по креатинину крови, возрасту и полу пациента.

Используемая формула CKD-EPI 2021 creatinine equation, без расового коэффициента:
eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^-1.200 × 0.9938^Age × sex_factor
где:
- Scr — креатинин крови в mg/dL;
- κ = 0.7 для женщин, 0.9 для мужчин;
- α = -0.241 для женщин, -0.302 для мужчин;
- sex_factor = 1.012 для женщин, 1.0 для мужчин;
- Age — возраст в годах.

В проекте креатинин вводится в мкмоль/л, поэтому перед расчетом выполняется перевод:
Scr mg/dL = creatinine_umol_l / 88.4

Какие значения ожидаются
------------------------
`creatinine_umol_l`: - креатинин крови в мкмоль/л; должен быть больше 0.
`age`: - возраст пациента в полных годах; должен быть больше 0.
`gender`: - пол пациента; поддерживаются старые варианты проекта: True/False, "Мужской", "Женский", "female", "male" и похожие строки.


Функция возвращает eGFR:
- единицы измерения: мл/мин/1,73 м²;
- тип: float;
- округление: до 2 знаков после запятой.
Если входных данных недостаточно или они некорректны, возвращается None.
"""

from __future__ import annotations
from typing import Optional
from .common import is_female_gender, normalize_serum_creatinine_to_mg_dl


def calculate_ckd_epi_2021(creatinine_umol_l, age, gender, serum_creatinine_unit: str = "umol_l",) -> Optional[float]:
    scr = normalize_serum_creatinine_to_mg_dl(creatinine_umol_l, serum_creatinine_unit,)

    if scr is None or age is None or gender is None:
        return None

    if age <= 0:
        return None

    if is_female_gender(gender):
        kappa = 0.7
        alpha = -0.241
        sex_factor = 1.012
    else:
        kappa = 0.9
        alpha = -0.302
        sex_factor = 1.0

    egfr = (
        142
        * (min(scr / kappa, 1) ** alpha)
        * (max(scr / kappa, 1) ** -1.200)
        * (0.9938 ** age)
        * sex_factor
    )

    return round(egfr, 2)
