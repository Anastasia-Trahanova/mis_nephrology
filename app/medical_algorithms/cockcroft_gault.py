"""
Расчет клиренса креатинина по формуле Cockcroft–Gault.

Что происходит в этом файле
---------------------------
Функция `calculate_cockcroft_gault` рассчитывает расчетный клиренс креатинина по креатинину крови, возрасту, массе тела и полу пациента.

Используемая формула
--------------------
Для мужчин:

CrCl = ((140 - age) × weight_kg) / (72 × Scr)

Для женщин результат дополнительно умножается на 0.85.

где:
- CrCl — клиренс креатинина;
- age — возраст в годах;
- weight_kg — масса тела в кг;
- Scr — креатинин крови в mg/dL.

Какие значения ожидаются
------------------------
`creatinine_umol_l`: - креатинин крови в мкмоль/л; должен быть больше 0.
`age`: - возраст пациента в полных годах; должен быть больше 0.
`weight_kg`: - масса тела в килограммах; должна быть больше 0.
`gender`: - пол пациента; для женского пола применяется коэффициент 0.85.


Функция возвращает расчетный клиренс креатинина:
- единицы измерения: мл/мин;
- тип: float;
- округление: до 2 знаков после запятой.
Если входных данных недостаточно или они некорректны, возвращается None.
"""

from __future__ import annotations
from typing import Optional
from .common import is_female_gender, normalize_serum_creatinine_to_mg_dl, to_float


def calculate_cockcroft_gault(creatinine_umol_l, age, weight_kg, gender, serum_creatinine_unit: str = "umol_l",) -> Optional[float]:
    scr = normalize_serum_creatinine_to_mg_dl(creatinine_umol_l,serum_creatinine_unit, )
    weight = to_float(weight_kg)

    if scr is None or age is None or weight is None or gender is None:
        return None

    if age <= 0 or weight <= 0:
        return None

    crcl = ((140 - age) * weight) / (72 * scr)

    if is_female_gender(gender):
        crcl *= 0.85

    return round(crcl, 2)
