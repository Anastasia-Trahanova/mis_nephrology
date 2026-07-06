"""
Назначение файла: чистая медицинская логика оценки риска по KDIGO.

Что выполняет файл:
- нормализует категорию СКФ и категорию альбуминурии;
- считает сочетание вида "С3аA2" по матрице KDIGO;
- возвращает уровень риска: low / moderate / high / very_high;
- формирует короткие фразы для врача без лишнего текста;
- проверяет, можно ли использовать две даты анализов вместе;
- формирует сообщения, если данных недостаточно или показатель устарел.

Что редактировать здесь:
- матрицу KDIGO, если потребуется клиническая корректировка;
- максимальные интервалы между датами СКФ и альбуминурии;
- точные русские формулировки, которые видит врач.

Что не редактировать здесь:
- SQL-запросы и сохранение в БД;
- HTML-шаблоны;
- JavaScript live-предпросмотра.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .ckd_stage import normalize_ckd_stage_for_storage

RISK_MATRIX: dict[str, dict[str, tuple[str, str]]] = {
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

# Консервативные интервалы для совместного использования СКФ и альбуминурии.
# KDIGO рекомендует чаще контролировать показатели при более высоком риске.
# Для high/very_high здесь используется 90 дней: если одно значение старше,
# врач увидит рекомендацию повторить исследование, а не цветной риск.
MAX_INTERVAL_DAYS_BY_RISK_LEVEL: dict[str, int] = {
    "low": 365,
    "moderate": 180,
    "high": 90,
    "very_high": 90,
}

RISK_SEVERITY_ORDER: dict[str, int] = {
    "low": 1,
    "moderate": 2,
    "high": 3,
    "very_high": 4,
}


@dataclass(frozen=True)
class KdigoSource:
    """Один источник данных для KDIGO: СКФ или альбуминурия."""

    id: int | None
    category: str | None
    investigation_date: date | None
    source_type: str = "current_appointment"


def to_date(value: Any) -> date | None:
    """Аккуратно приводит дату из БД/формы к datetime.date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d").date()
        except ValueError:
            return None
    return None


def normalize_albuminuria_category(value: Any) -> str | None:
    """Приводит альбуминурию к A1/A2/A3."""
    if value is None:
        return None
    value = str(value).strip().upper().replace("А", "A")
    if value in {"A1", "A2", "A3"}:
        return value
    return None


def calculate_kdigo_risk(gfr_category: Any, albuminuria_category: Any) -> dict[str, Any]:
    """Возвращает структурированный риск по матрице KDIGO."""
    normalized_gfr = normalize_ckd_stage_for_storage(gfr_category)
    normalized_albuminuria = normalize_albuminuria_category(albuminuria_category)

    if not normalized_gfr or not normalized_albuminuria:
        return {
            "gfr_category": normalized_gfr,
            "albuminuria_category": normalized_albuminuria,
            "combined_category": None,
            "prognosis_level": None,
            "prognosis_text": None,
            "status": "missing",
        }

    risk = RISK_MATRIX.get(normalized_gfr, {}).get(normalized_albuminuria)
    if not risk:
        return {
            "gfr_category": normalized_gfr,
            "albuminuria_category": normalized_albuminuria,
            "combined_category": None,
            "prognosis_level": None,
            "prognosis_text": None,
            "status": "unknown_combination",
        }

    prognosis_level, prognosis_text = risk
    return {
        "gfr_category": normalized_gfr,
        "albuminuria_category": normalized_albuminuria,
        "combined_category": f"{normalized_gfr}{normalized_albuminuria}",
        "prognosis_level": prognosis_level,
        "prognosis_text": prognosis_text,
        "status": "calculated",
    }


def calculate_ckd_prognosis(gfr_category: Any, albuminuria_category: Any) -> dict[str, Any]:
    """
    Совместимость со старым кодом.

    Старое название оставлено, но новая логика внутри говорит именно о
    категории риска по KDIGO, а не об индивидуальном процентном прогнозе.
    """
    result = calculate_kdigo_risk(gfr_category, albuminuria_category)
    return {
        "level": result.get("prognosis_level"),
        "text": result.get("prognosis_text"),
        "combined": result.get("combined_category"),
        **result,
    }


def source_interval_days(gfr_date: Any, albuminuria_date: Any) -> int | None:
    """Возвращает абсолютный интервал между датами анализов в днях."""
    gfr_date = to_date(gfr_date)
    albuminuria_date = to_date(albuminuria_date)
    if not gfr_date or not albuminuria_date:
        return None
    return abs((gfr_date - albuminuria_date).days)


def max_interval_days_for_risk(prognosis_level: str | None) -> int:
    """Максимальный допустимый интервал между СКФ и альбуминурией."""
    if not prognosis_level:
        return 90
    return MAX_INTERVAL_DAYS_BY_RISK_LEVEL.get(prognosis_level, 90)


def is_interval_allowed(prognosis_level: str | None, interval_days: int | None) -> bool:
    """True, если даты СКФ и альбуминурии можно использовать вместе."""
    if interval_days is None:
        return False
    return interval_days <= max_interval_days_for_risk(prognosis_level)


def _russian_month_word(months: int) -> str:
    """Склоняет слово месяц для коротких врачебных сообщений."""
    if 11 <= months % 100 <= 14:
        return "месяцев"
    last = months % 10
    if last == 1:
        return "месяц"
    if 2 <= last <= 4:
        return "месяца"
    return "месяцев"


def format_elapsed_months(interval_days: int | None) -> str:
    """Преобразует интервал в человекочитаемые месяцы."""
    if interval_days is None:
        return "давно"
    months = max(1, round(interval_days / 30.44))
    return f"{months} {_russian_month_word(months)} назад"


def format_risk_phrase(assessment: dict[str, Any]) -> str:
    """Формирует основную фразу для заключения врача."""
    gfr_date = to_date(assessment.get("gfr_investigation_date"))
    albuminuria_date = to_date(assessment.get("albuminuria_investigation_date"))
    gfr_date_text = gfr_date.strftime("%d.%m.%Y") if gfr_date else "—"
    albuminuria_date_text = albuminuria_date.strftime("%d.%m.%Y") if albuminuria_date else "—"

    return (
        f"По KDIGO: {assessment.get('combined_category')} — "
        f"{assessment.get('prognosis_text')} прогрессирования ХБП и развития ХПН "
        f"(рассчитано по СКФ от {gfr_date_text}, "
        f"альбуминурия от {albuminuria_date_text})"
    )


def format_missing_phrase(missing: str) -> str:
    """Фраза, если одного или обоих показателей нет."""
    if missing == "both":
        return (
            "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
            "данные по альбуминурии и СКФ не предоставлены."
        )
    if missing == "gfr":
        return (
            "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
            "данные по СКФ не предоставлены."
        )
    return (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        "данные по альбуминурии не предоставлены."
    )


def format_stale_phrase(stale_source: str, interval_days: int | None) -> str:
    """Фраза, если найденный предыдущий показатель слишком старый."""
    elapsed = format_elapsed_months(interval_days)
    if stale_source == "gfr":
        return (
            "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
            f"данные по СКФ были получены {elapsed}, рекомендовано повторить исследование."
        )
    return (
        "Невозможно оценить риск прогрессирования ХБП и развития ХПН, "
        f"данные по альбуминурии были получены {elapsed}, рекомендовано повторить исследование."
    )


def build_source_pair_key(
    gfr_date: Any,
    gfr_category: Any,
    albuminuria_date: Any,
    albuminuria_category: Any,
) -> str:
    """
    Ключ пары СКФ × альбуминурия.

    Такой же ключ использует JavaScript: если врач нажал крестик у лишней
    строки в форме, backend не сохраняет эту пару в ckd_prognosis_results.
    """
    gfr_date_obj = to_date(gfr_date)
    albuminuria_date_obj = to_date(albuminuria_date)
    gfr_date_text = gfr_date_obj.isoformat() if gfr_date_obj else ""
    albuminuria_date_text = albuminuria_date_obj.isoformat() if albuminuria_date_obj else ""
    gfr_category_text = normalize_ckd_stage_for_storage(gfr_category) or ""
    albuminuria_category_text = normalize_albuminuria_category(albuminuria_category) or ""
    return "|".join(
        [gfr_date_text, gfr_category_text, albuminuria_date_text, albuminuria_category_text]
    )
