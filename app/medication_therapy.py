"""Группы медикаментозной терапии для формы приёма и карточки пациента."""

from __future__ import annotations

from typing import Any, Iterable


MEDICATION_THERAPY_GROUPS = (
    {
        "code": "bp_hr",
        "value": "Коррекция АД, ЧСС",
        "title": "Препараты для коррекции АД, ЧСС",
        "medications": (
            "Лозартан",
            "Бисопролол",
            "Метопролол",
            "Карведилол",
            "Амлодипин",
            "Лерканидипин",
            "Нифедипин",
            "Нифедипин с модифицированным высвобождением",
            "Спиронолактон",
            "Индапамид",
            "Торасемид",
            "Фуросемид",
            "Моксонидин",
        ),
    },
    {
        "code": "nephroprotection",
        "value": "Нефропротекция",
        "title": "Нефропротекторные препараты",
        "medications": (
            "Лозартан",
            "Дапаглифлозин",
            "Эмпаглифлозин",
            "Финеренон",
        ),
    },
    {
        "code": "lipid",
        "value": "Коррекция гиперлипидемии",
        "title": "Препараты для коррекции гиперлипидемии",
        "medications": (
            "Аторвастатин",
            "Розувастатин",
            "Питавастатин",
            "Эзетимиб",
        ),
    },
    {
        "code": "anemia",
        "value": "Коррекция анемии",
        "title": "Препараты для коррекции анемии",
        "medications": (
            "Железа III гидроксид полимальтозат",
            "Железа III гидроксид полисахарозный комплекс",
            "Эпоэтин альфа",
            "Эпоэтин бета",
            "Метоксиполиэтиленгликоль-эпоэтин бета",
        ),
    },
    {
        "code": "additional",
        "value": "Другие препараты",
        "title": "Дополнительно",
        "medications": (
            "Аллопуринол",
            "Фебуксостат",
        ),
    },
)

DEFAULT_THERAPY_GROUP = "Другие препараты"
_ALLOWED_GROUPS = {group["value"] for group in MEDICATION_THERAPY_GROUPS}


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def normalize_therapy_group(value: Any) -> str:
    """Возвращает допустимую русскую группу назначения."""
    normalized = str(value or "").strip()
    return normalized if normalized in _ALLOWED_GROUPS else DEFAULT_THERAPY_GROUP


def build_medication_therapy_groups(
    medications_dictionary: Iterable[Any] | None = None,
    prescriptions: Iterable[Any] | None = None,
) -> list[dict[str, Any]]:
    """Готовит пять групп с подсказками и назначениями для шаблонов."""
    available_names = {
        str(_row_get(item, "display_name") or "").strip()
        for item in (medications_dictionary or [])
        if str(_row_get(item, "display_name") or "").strip()
    }
    grouped_prescriptions: dict[str, list[Any]] = {
        group["value"]: [] for group in MEDICATION_THERAPY_GROUPS
    }
    for prescription in prescriptions or []:
        group_value = normalize_therapy_group(_row_get(prescription, "therapy_group"))
        grouped_prescriptions[group_value].append(prescription)

    result: list[dict[str, Any]] = []
    for group in MEDICATION_THERAPY_GROUPS:
        suggestions = [
            name for name in group["medications"] if name in available_names
        ]
        result.append(
            {
                "code": group["code"],
                "value": group["value"],
                "title": group["title"],
                "suggestions": suggestions,
                "prescriptions": grouped_prescriptions[group["value"]],
            }
        )
    return result
