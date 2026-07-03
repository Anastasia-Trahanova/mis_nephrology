"""
Определение и нормализация категории СКФ при хронической болезни почек.

Что происходит в этом файле
---------------------------
Здесь лежат функции, которые:

1. определяют категорию СКФ по значению eGFR;
2. приводят разные варианты записи стадии к единому формату хранения;
3. проверяют, является ли стадия допустимой.

Используемая классификация
--------------------------
Категории СКФ:

- С1  — eGFR ≥ 90 мл/мин/1,73 м²
- С2  — eGFR 60–89 мл/мин/1,73 м²
- С3а — eGFR 45–59 мл/мин/1,73 м²
- С3б — eGFR 30–44 мл/мин/1,73 м²
- С4  — eGFR 15–29 мл/мин/1,73 м²
- С5  — eGFR < 15 мл/мин/1,73 м²

Важное соглашение проекта
-------------------------
В базе и интерфейсе используем русскую букву `С`:

```text
С1, С2, С3а, С3б, С4, С5
```

Не используем для хранения:
- латинскую `C`;
- старый вариант `G`.

Функция нормализации принимает случайный ввод вроде `G4`, `C4`, `с4`, `C3a`, `G3b` и приводит его к формату с русской `С`.

Какие значения ожидаются
------------------------
`get_ckd_stage`: - принимает eGFR в мл/мин/1,73 м².

`normalize_ckd_stage_for_storage`: - принимает строку стадии, например "С3б", "C3b", "G4".

Что дает на выход
-----------------
`get_ckd_stage` возвращает категорию СКФ: "С1", "С2", "С3а", "С3б", "С4", "С5".

`normalize_ckd_stage_for_storage` возвращает стадию в формате хранения с русской буквой `С`.

Если данных нет, возвращается None.
"""

from __future__ import annotations

from typing import Optional

from .common import to_float


ALLOWED_CKD_STAGES = {"С1", "С2", "С3а", "С3б", "С4", "С5"}


def normalize_ckd_stage_for_storage(stage) -> Optional[str]:
    if stage is None:
        return None

    normalized = str(stage).strip()

    if not normalized:
        return None

    # Первая буква: латинская C/c или старый G/g -> русская С
    first = normalized[0]
    if first in {"C", "c", "G", "g", "С", "с"}:
        normalized = "С" + normalized[1:]

    # Подстадии С3а/С3б: латинские a/b -> русские а/б
    normalized = normalized.replace("3a", "3а").replace("3A", "3а").replace("3А", "3а")
    normalized = normalized.replace("3b", "3б").replace("3B", "3б").replace("3Б", "3б")

    return normalized


def is_valid_ckd_stage(stage) -> bool:
    return normalize_ckd_stage_for_storage(stage) in ALLOWED_CKD_STAGES


def get_ckd_stage(egfr) -> Optional[str]:
    egfr = to_float(egfr)

    if egfr is None:
        return None

    if egfr >= 90:
        return "С1"

    if egfr >= 60:
        return "С2"

    if egfr >= 45:
        return "С3а"

    if egfr >= 30:
        return "С3б"

    if egfr >= 15:
        return "С4"

    return "С5"
