"""
Общие вспомогательные функции для медицинских расчетов.
Здесь лежат функции, которые сами по себе не являются отдельной медицинской формулой, но нужны разным расчетным модулям:
1. `to_float` — переводит введенное значение в число.
2. `calculate_age` — рассчитывает возраст пациента на дату приема.
3. `is_female_gender` — определяет, что пациент женского пола, по тем форматам, которые сейчас встречаются в приложении.
4. `normalize_serum_creatinine_to_mg_dl` — приводит креатинин крови/плазмы к mg/dL для формул CKD-EPI и Cockcroft–Gault.
5. `normalize_serum_creatinine_to_umol_l` — приводит креатинин крови/плазмы к мкмоль/л, то есть к текущему основному формату хранения в базе.


Креатинин крови используется сразу в двух расчетах:
- CKD-EPI 2021 creatinine;
- Cockcroft–Gault.
Обе формулы внутри используют креатинин крови в mg/dL.
Но в российских лабораториях и в текущей базе проекта основной формат — мкмоль/л.
Чтобы не дублировать один и тот же пересчет в `egfr.py` и `cockcroft_gault.py`, общий перевод креатинина крови вынесен сюда.

Поддерживаемые единицы креатинина крови/плазмы
- `umol_l` — мкмоль/л;
- `mg_dl`  — мг/дл.

Пересчет
1 mg/dL = 88.4 мкмоль/л
То есть:
    mg/dL = мкмоль/л / 88.4
    мкмоль/л = mg/dL × 88.4

Какие значения ожидаются
------------------------
`to_float`:
- принимает число, строку, пустую строку или None;
- допускает запятую вместо точки, например "123,4";
- возвращает float или None.

`calculate_age`:
- birth_date — дата рождения пациента;
- appointment_date — дата приема;
- принимает даты в формате date/datetime или строку "YYYY-MM-DD";
- возвращает возраст в полных годах.

`is_female_gender`:
- принимает пол в старых форматах проекта:
  False, "false", "False", "Женский", "женский", "female", "Female";
- возвращает True для женского пола, False для остальных вариантов.

`normalize_serum_creatinine_to_mg_dl`:
- принимает значение креатинина крови/плазмы и единицу измерения;
- возвращает креатинин в mg/dL.

`normalize_serum_creatinine_to_umol_l`:
- принимает значение креатинина крови/плазмы и единицу измерения;
- возвращает креатинин в мкмоль/л.

Что дает на выход
-----------------
Эти функции возвращают подготовленные значения, которые дальше используются в формулах CKD-EPI, Cockcroft–Gault, ACR и других расчетах.
Если значение пустое, отрицательное, равно нулю или единица измерения неизвестна, функции нормализации креатинина возвращают None.

Важно. 
База данных пока может продолжать хранить креатинин крови в одном формате — мкмоль/л.
Новый параметр единицы измерения нужен для расчетного слоя. Старые вызовы без указания единицы продолжают работать, потому что по умолчанию используется `umol_l`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional


SERUM_CREATININE_UMOL_L = "umol_l"
SERUM_CREATININE_MG_DL = "mg_dl"

SERUM_CREATININE_UNITS = {
    SERUM_CREATININE_UMOL_L,
    SERUM_CREATININE_MG_DL,
}

UMOL_L_PER_MG_DL = 88.4


def to_float(value) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def calculate_age(birth_date, appointment_date) -> Optional[int]:
    if not birth_date or not appointment_date:
        return None

    if isinstance(birth_date, datetime):
        birth_date = birth_date.date()
    elif isinstance(birth_date, str):
        birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()

    if isinstance(appointment_date, datetime):
        appointment_date = appointment_date.date()
    elif isinstance(appointment_date, str):
        appointment_date = datetime.strptime(appointment_date, "%Y-%m-%d").date()

    if not isinstance(birth_date, date) or not isinstance(appointment_date, date):
        return None

    age = appointment_date.year - birth_date.year

    if (appointment_date.month, appointment_date.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age


def is_female_gender(gender) -> bool:
    return gender in [False, "false", "False", "Женский", "женский", "female", "Female"]


def normalize_serum_creatinine_to_mg_dl(
    value,
    unit: str = SERUM_CREATININE_UMOL_L,
) -> Optional[float]:
    """
    Приводит креатинин крови/плазмы к mg/dL.
    Используется перед расчетом CKD-EPI и Cockcroft–Gault.
    """
    creatinine = to_float(value)

    if creatinine is None or creatinine <= 0:
        return None

    if unit == SERUM_CREATININE_UMOL_L:
        return creatinine / UMOL_L_PER_MG_DL

    if unit == SERUM_CREATININE_MG_DL:
        return creatinine

    return None


def normalize_serum_creatinine_to_umol_l(
    value,
    unit: str = SERUM_CREATININE_UMOL_L,
) -> Optional[float]:
    """
    Приводит креатинин крови/плазмы к мкмоль/л.
    """
    creatinine = to_float(value)

    if creatinine is None or creatinine <= 0:
        return None

    if unit == SERUM_CREATININE_UMOL_L:
        return creatinine

    if unit == SERUM_CREATININE_MG_DL:
        return creatinine * UMOL_L_PER_MG_DL

    return None
