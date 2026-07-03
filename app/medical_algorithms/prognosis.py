"""
Прогноз ХБП по матрице KDIGO: категория СКФ + категория альбуминурии.

Что происходит в этом файле
---------------------------
Функция `calculate_ckd_prognosis` принимает:

1. категорию СКФ: С1, С2, С3а, С3б, С4, С5;
2. категорию альбуминурии: A1, A2, A3.

На основании сочетания этих категорий функция возвращает уровень риска.

Используемая логика
-------------------
Используется матрица прогноза KDIGO для ХБП:

- низкий риск;
- умеренно повышенный риск;
- высокий риск;
- очень высокий риск.

Внутри кода это хранится как словарь `risk_matrix`.

Какие значения ожидаются
------------------------
`gfr_category`:
- строка категории СКФ;
- допускаются варианты "С3б", "C3b", "G3b";
- перед расчетом категория приводится к формату хранения с русской `С`.

`albuminuria_category`:
- строка категории альбуминурии;
- ожидаемые значения: A1, A2, A3.

Что дает на выход
-----------------
Функция возвращает словарь.

Старые ключи оставлены для совместимости со старым кодом:

```text
level
text
combined
```

Новые более явные ключи:

```text
gfr_category
albuminuria_category
combined_category
prognosis_level
prognosis_text
```

Если входных данных недостаточно или сочетание категорий неизвестно,
возвращаются None-значения.
"""

from __future__ import annotations

from .ckd_stage import normalize_ckd_stage_for_storage


RISK_MATRIX = {
    "С1": {
        "A1": ("low", "низкий риск"),
        "A2": ("moderate", "умеренно повышенный риск"),
        "A3": ("high", "высокий риск"),
    },
    "С2": {
        "A1": ("low", "низкий риск"),
        "A2": ("moderate", "умеренно повышенный риск"),
        "A3": ("high", "высокий риск"),
    },
    "С3а": {
        "A1": ("moderate", "умеренно повышенный риск"),
        "A2": ("high", "высокий риск"),
        "A3": ("very_high", "очень высокий риск"),
    },
    "С3б": {
        "A1": ("high", "высокий риск"),
        "A2": ("very_high", "очень высокий риск"),
        "A3": ("very_high", "очень высокий риск"),
    },
    "С4": {
        "A1": ("very_high", "очень высокий риск"),
        "A2": ("very_high", "очень высокий риск"),
        "A3": ("very_high", "очень высокий риск"),
    },
    "С5": {
        "A1": ("very_high", "очень высокий риск"),
        "A2": ("very_high", "очень высокий риск"),
        "A3": ("very_high", "очень высокий риск"),
    },
}


def _empty_prognosis(gfr_category=None, albuminuria_category=None):
    return {
        "level": None,
        "text": None,
        "combined": None,
        "gfr_category": gfr_category,
        "albuminuria_category": albuminuria_category,
        "combined_category": None,
        "prognosis_level": None,
        "prognosis_text": None,
    }


def calculate_ckd_prognosis(gfr_category, albuminuria_category):
    gfr_category = normalize_ckd_stage_for_storage(gfr_category)

    if albuminuria_category is not None:
        albuminuria_category = str(albuminuria_category).strip().upper()

    if not gfr_category or not albuminuria_category:
        return _empty_prognosis(gfr_category, albuminuria_category)

    prognosis = RISK_MATRIX.get(gfr_category, {}).get(albuminuria_category)

    if not prognosis:
        return _empty_prognosis(gfr_category, albuminuria_category)

    prognosis_level, prognosis_text = prognosis
    combined_category = f"{gfr_category}{albuminuria_category}"

    return {
        # Старые ключи — чтобы не сломать существующий код.
        "level": prognosis_level,
        "text": prognosis_text,
        "combined": combined_category,

        # Новые понятные ключи.
        "gfr_category": gfr_category,
        "albuminuria_category": albuminuria_category,
        "combined_category": combined_category,
        "prognosis_level": prognosis_level,
        "prognosis_text": prognosis_text,
    }
