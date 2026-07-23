"""
Нормализация клинических значений HTML-формы.

Зачем нужен файл:
- врач может вводить некоторые значения в привычном альтернативном формате;
- БД и расчёты должны получать один внутренний формат;
- валидация должна проверять уже нормализованные значения;
- при этом нельзя автоматически преобразовывать любые «странные» числа, потому
  что высокие значения по ряду показателей могут быть реальными критическими
  значениями, а не ошибкой единиц.

Главный принцип:
- нормализуем только однозначные случаи;
- не делим и не умножаем значение, если есть риск исказить реальный показатель;
- всё сомнительное оставляем как есть, чтобы медицинская валидация выдала
  понятную ошибку по диапазону.

Примеры:
- удельный вес мочи: 1015 -> 1.015, потому что это распространённая запись того
  же значения;
- гематокрит: 0.39 -> 39, потому что часто встречается долевая запись вместо %;
- креатинин 100 НЕ преобразуем, потому что 100 мкмоль/л — нормальный формат;
- глюкозу 55 НЕ делим на 10, потому что это может быть критическое значение,
  которое должна поймать валидация, а не тихая нормализация.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class NormalizationWarning:
    """
    Информационное сообщение о нормализации.

    Сейчас эти предупреждения используются в тестах и готовы для будущего вывода
    в интерфейсе. Они не блокируют сохранение. Блокировка остаётся задачей
    validate_appointment_form.
    """

    field: str
    message: str
    index: int | None = None
    original_value: Any = None
    normalized_value: Any = None


class NormalizedClinicalForm:
    """
    Обёртка над FormData/FakeForm.

    Нужна, чтобы не мутировать исходный request.form(), но отдавать сервисам,
    валидатору и парсеру уже нормализованные значения через привычные методы:

        form.get("field")
        form.getlist("field")

    Для полей без правил нормализации значения берутся из исходной формы.
    """

    def __init__(
        self,
        source_form: Any,
        normalized_values: dict[str, list[Any]],
        warnings: list[NormalizationWarning],
    ) -> None:
        self.source_form = source_form
        self.normalized_values = normalized_values
        self.normalization_warnings = warnings

    def get(self, key: str, default: Any = None) -> Any:
        values = self.getlist(key)
        if not values:
            return default
        first_value = values[0]
        return default if first_value is None else first_value

    def getlist(self, key: str) -> list[Any]:
        if key in self.normalized_values:
            return list(self.normalized_values[key])

        if hasattr(self.source_form, "getlist"):
            return list(self.source_form.getlist(key))

        value = self.source_form.get(key) if hasattr(self.source_form, "get") else None
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]


# Поля, где достаточно только привести десятичную запятую к точке и убрать пробелы.
# Эти поля НЕ получают скрытых пересчётов единиц.
GENERIC_NUMERIC_FIELDS: set[str] = {
    # Осмотр
    "height",
    "weight",
    "body_temperature",
    "systolic_pressure",
    "diastolic_pressure",
    "heart_rate",
    # ОАК
    "hemoglobin",
    "erythrocytes",
    "leukocytes",
    "platelets",
    "esr",
    "mcv",
    # Биохимия
    "creatinine",
    "urea",
    "uric_acid",
    "glucose",
    "total_protein",
    "albumin",
    "potassium",
    "calcium",
    "phosphorus",
    "ferritin",
    "ptg",
    # ОАМ
    "urine_protein",
    "urine_leukocytes",
    "urine_erythrocytes",
    "bacteria",
    # Альбуминурия
    "urine_albumin",
    "urine_creatinine",
    # УЗИ
    "left_parenchyma",
    "right_parenchyma",
}


SPECIAL_NUMERIC_FIELDS: set[str] = {
    "specific_gravity",
    "hematocrit",
}


ALL_NORMALIZED_FIELDS: set[str] = GENERIC_NUMERIC_FIELDS | SPECIAL_NUMERIC_FIELDS


def _empty_to_none(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    return text or None


def _clean_numeric_text(value: Any) -> str | None:
    """Приводит строковое число к техническому виду, но не меняет единицы."""
    text = _empty_to_none(value)
    if text is None:
        return None

    return text.replace(" ", "").replace(",", ".")


def _to_float(value: Any) -> float | None:
    text = _clean_numeric_text(value)
    if text is None:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _format_decimal(value: float, max_digits: int = 6) -> str:
    """Форматирует число без лишних нулей, но с точкой как разделителем."""
    text = f"{value:.{max_digits}f}".rstrip("0").rstrip(".")
    return text or "0"


def normalize_generic_numeric_value(value: Any) -> str | None:
    """
    Общая нормализация числового поля без пересчёта единиц.

    Примеры:
    - "5,1" -> "5.1";
    - "1 234,5" -> "1234.5";
    - "" -> None.
    """
    return _clean_numeric_text(value)


def normalize_specific_gravity_value(value: Any) -> str | None:
    """
    Нормализует удельный вес мочи.

    Допускаем два однозначных формата:
    - внутренний десятичный: 1.015;
    - привычный лабораторный: 1015.

    Безопасные преобразования:
    - 1000..1050 -> 1.000..1.050;
    - 1.000..1.050 -> 1.000..1.050.

    Не преобразуем:
    - 900;
    - 1500;
    - 1.5;
    - произвольные большие значения.

    Такие значения останутся как есть и будут отклонены validate_appointment_form.
    """
    text = _clean_numeric_text(value)
    if text is None:
        return None

    number = _to_float(text)
    if number is None:
        return text

    # Запись 1015, 1005, 1030 и т.п.
    if 1000 <= number <= 1050 and number.is_integer():
        return f"{number / 1000:.3f}"

    # Запись 1.015 или 1,015.
    if 1.000 <= number <= 1.050:
        return f"{number:.3f}"

    return text


def normalize_hematocrit_value(value: Any) -> str | None:
    """
    Нормализует гематокрит.

    Внутри проекта гематокрит хранится в процентах: 39.
    Врачи и лаборатории иногда указывают долю: 0.39.

    Безопасное преобразование:
    - 0.05..0.70 -> 5..70.

    Не преобразуем 1.2 -> 120, потому что это уже не типичная долевая запись
    гематокрита и должно обрабатываться валидацией как подозрительное значение.
    """
    text = _clean_numeric_text(value)
    if text is None:
        return None

    number = _to_float(text)
    if number is None:
        return text

    if 0.05 <= number <= 0.70:
        return _format_decimal(number * 100, max_digits=2)

    return text


FIELD_NORMALIZERS: dict[str, Callable[[Any], str | None]] = {
    **{field_name: normalize_generic_numeric_value for field_name in GENERIC_NUMERIC_FIELDS},
    "specific_gravity": normalize_specific_gravity_value,
    "hematocrit": normalize_hematocrit_value,
}


FIELD_LABELS: dict[str, str] = {
    "specific_gravity": "Удельный вес мочи",
    "hematocrit": "Гематокрит",
}


def _getlist(form: Any, field_name: str) -> list[Any]:
    if hasattr(form, "getlist"):
        return list(form.getlist(field_name))

    if not hasattr(form, "get"):
        return []

    value = form.get(field_name)
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def normalize_appointment_form_values(form: Any) -> NormalizedClinicalForm:
    """
    Возвращает форму-обёртку с нормализованными клиническими числовыми полями.

    Функция не мутирует исходную форму.
    Её можно безопасно вызывать несколько раз: нормализация идемпотентна.
    """
    if isinstance(form, NormalizedClinicalForm):
        return form

    normalized_values: dict[str, list[Any]] = {}
    warnings: list[NormalizationWarning] = []

    for field_name, normalizer in FIELD_NORMALIZERS.items():
        raw_values = _getlist(form, field_name)
        if not raw_values:
            continue

        normalized_list: list[Any] = []
        for index, raw_value in enumerate(raw_values):
            normalized_value = normalizer(raw_value)
            normalized_list.append(normalized_value)

            raw_text = _empty_to_none(raw_value)
            normalized_text = _empty_to_none(normalized_value)
            if raw_text is not None and normalized_text is not None and raw_text != normalized_text:
                label = FIELD_LABELS.get(field_name, field_name)
                warnings.append(
                    NormalizationWarning(
                        field=field_name,
                        index=index,
                        original_value=raw_value,
                        normalized_value=normalized_value,
                        message=f"{label}: значение {raw_value} будет сохранено как {normalized_value}.",
                    )
                )

        normalized_values[field_name] = normalized_list

    return NormalizedClinicalForm(form, normalized_values, warnings)


def get_normalization_warnings(form: Any) -> list[NormalizationWarning]:
    """Возвращает предупреждения нормализации для будущего вывода в интерфейсе."""
    return normalize_appointment_form_values(form).normalization_warnings
