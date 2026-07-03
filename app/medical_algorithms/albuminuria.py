"""
Расчет альбумин-креатининового отношения мочи и категории альбуминурии.

Что происходит в этом файле
---------------------------
Здесь рассчитывается ACR — отношение альбумина к креатинину в моче, а затем определяется категория альбуминурии A1/A2/A3.

Используемая формула
--------------------
Основная формула:

ACR мг/ммоль = альбумин мочи, мг/л / креатинин мочи, ммоль/л

Дополнительный пересчет для отображения:

ACR мг/г ≈ ACR мг/ммоль × 8.84

Какие значения ожидаются
------------------------
`urine_albumin`:
- альбумин мочи;
- поддерживаемые единицы:
  - `mg_l` — мг/л;
  - `g_l` — г/л.

`urine_creatinine`:
- креатинин мочи;
- поддерживаемые единицы:
  - `mmol_l` — ммоль/л;
  - `umol_l` — мкмоль/л.

Что дает на выход
-----------------
`calculate_albumin_creatinine_ratio`:
- возвращает ACR в мг/ммоль;
- округляет до 2 знаков после запятой.

`calculate_albuminuria_metrics`:
- возвращает словарь:
  - `albumin_creatinine_ratio` — ACR в мг/ммоль;
  - `albumin_creatinine_ratio_mg_g` — ACR в мг/г;
  - `albuminuria_category` — A1, A2 или A3.

Классификация
-------------
- A1: ACR < 3 мг/ммоль
- A2: ACR 3–30 мг/ммоль
- A3: ACR > 30 мг/ммоль

Если входных данных недостаточно или креатинин мочи равен 0, возвращается None для расчетных значений.
"""

from __future__ import annotations

from .common import to_float


def normalize_urine_albumin_to_mg_l(value, unit: str = "mg_l"):
    albumin = to_float(value)

    if albumin is None:
        return None

    if unit == "mg_l":
        return albumin

    if unit == "g_l":
        return albumin * 1000

    return None


def normalize_urine_creatinine_to_mmol_l(value, unit: str = "mmol_l"):
    creatinine = to_float(value)

    if creatinine is None or creatinine <= 0:
        return None

    if unit == "mmol_l":
        return creatinine

    if unit == "umol_l":
        return creatinine / 1000

    return None


def calculate_albumin_creatinine_ratio(
    urine_albumin,
    urine_albumin_unit="mg_l",
    urine_creatinine=None,
    urine_creatinine_unit="mmol_l",
):
    albumin_mg_l = normalize_urine_albumin_to_mg_l(
        urine_albumin,
        urine_albumin_unit,
    )

    creatinine_mmol_l = normalize_urine_creatinine_to_mmol_l(
        urine_creatinine,
        urine_creatinine_unit,
    )

    if albumin_mg_l is None or creatinine_mmol_l is None:
        return None

    if creatinine_mmol_l <= 0:
        return None

    acr_mg_mmol = albumin_mg_l / creatinine_mmol_l

    return round(acr_mg_mmol, 2)


def get_albuminuria_category(acr_mg_mmol):
    acr = to_float(acr_mg_mmol)

    if acr is None:
        return None

    if acr < 3:
        return "A1"

    if acr <= 30:
        return "A2"

    return "A3"


def calculate_albuminuria_metrics(
    urine_albumin,
    urine_albumin_unit,
    urine_creatinine,
    urine_creatinine_unit,
):
    acr_mg_mmol = calculate_albumin_creatinine_ratio(
        urine_albumin=urine_albumin,
        urine_albumin_unit=urine_albumin_unit,
        urine_creatinine=urine_creatinine,
        urine_creatinine_unit=urine_creatinine_unit,
    )

    if acr_mg_mmol is None:
        return {
            "albumin_creatinine_ratio": None,
            "albumin_creatinine_ratio_mg_g": None,
            "albuminuria_category": None,
        }

    acr_mg_g = round(acr_mg_mmol * 8.84, 2)
    category = get_albuminuria_category(acr_mg_mmol)

    return {
        "albumin_creatinine_ratio": acr_mg_mmol,
        "albumin_creatinine_ratio_mg_g": acr_mg_g,
        "albuminuria_category": category,
    }
