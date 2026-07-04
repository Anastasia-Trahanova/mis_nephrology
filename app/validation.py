from datetime import date, datetime
from typing import Any, Dict, List, Optional


ValidationError = Dict[str, Any]


def _empty_to_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _to_float(value: Any) -> Optional[float]:
    value = _empty_to_none(value)
    if value is None:
        return None
    try:
        return float(value.replace(" ", "").replace(",", "."))
    except ValueError:
        return None

def _normalize_numeric_value_for_validation(field_name: str, value: Any) -> Any:
    """
    Нормализует безопасные альтернативные форматы перед валидацией.

    Важно:
    эта функция НЕ должна делать опасные догадки.
    Например:
    - креатинин 100 не превращаем ни во что другое;
    - глюкозу 55 не делим на 10;
    - ферритин 1200 не меняем;
    - тромбоциты 250 не меняем.

    Сейчас здесь есть только однозначная нормализация удельного веса мочи:
    - 1015 -> 1.015
    - 1005 -> 1.005
    - 1050 -> 1.050

    Это нужно потому, что врачи могут вводить удельный вес мочи в обоих форматах:
    лабораторном десятичном 1.015 и коротком привычном 1015.
    Внутренний формат хранения и проверки — десятичный: 1.015.
    """
    value_text = _empty_to_none(value)
    if value_text is None:
        return value

    if field_name != "specific_gravity":
        return value

    normalized_text = str(value_text).strip().replace(" ", "").replace(",", ".")

    try:
        number = float(normalized_text)
    except ValueError:
        return value

    # Уже правильный формат: 1.015, 1.020, 1.030.
    if 1.000 <= number <= 1.050:
        return normalized_text

    # Альтернативный формат: 1000–1050.
    # Нормализуем только этот узкий и однозначный диапазон.
    # Не нормализуем 1500, 900, 9999 и другие странные значения.
    if number.is_integer() and 1000 <= number <= 1050:
        return f"{number / 1000:.3f}"

    return value

def _to_date(value: Any) -> Optional[date]:
    value = _empty_to_none(value)
    if value is None:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _getlist(form, field_name: str) -> List[Any]:
    if hasattr(form, "getlist"):
        return list(form.getlist(field_name))
    value = form.get(field_name)
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _add_error(errors: List[ValidationError], field: str, message: str, index: Optional[int] = None) -> None:
    errors.append({
        "field": field,
        "message": message,
        "index": index,
    })


# Диапазоны ниже — не референсные интервалы нормы, а широкие технические пределы,
# чтобы не сохранять очевидно невозможные / ошибочно введённые значения.
NUMERIC_RULES = {
    # Осмотр
    "height": (50, 250, "Рост должен быть в диапазоне 50–250 см."),
    "weight": (30, 300, "Вес должен быть в диапазоне 30–300 кг."),
    "systolic_pressure": (50, 300, "Систолическое АД должно быть в диапазоне 50–300 мм рт. ст."),
    "diastolic_pressure": (30, 200, "Диастолическое АД должно быть в диапазоне 30–200 мм рт. ст."),
    "heart_rate": (20, 250, "ЧСС должна быть в диапазоне 20–250 уд/мин."),

    # ОАК
    "hemoglobin": (20, 250, "Гемоглобин должен быть в диапазоне 20–250 г/л."),
    "erythrocytes": (0.5, 10, "Эритроциты должны быть в диапазоне 0,5–10."),
    "leukocytes": (0.1, 300, "Лейкоциты должны быть в диапазоне 0,1–300."),
    "platelets": (5, 1500, "Тромбоциты должны быть в диапазоне 5–1500."),
    "esr": (0, 150, "СОЭ должна быть в диапазоне 0–150 мм/ч."),
    "mcv": (40, 140, "MCV должен быть в диапазоне 40–140 фл."),
    "hematocrit": (5, 70, "Гематокрит должен быть в диапазоне 5–70 %."),

    # Биохимия
    "creatinine": (15, 3000, "Неверное значение креатинина крови: допустимо 15–3000 мкмоль/л."),
    "urea": (0.5, 80, "Мочевина должна быть в диапазоне 0,5–80 ммоль/л."),
    "uric_acid": (50, 1500, "Мочевая кислота должна быть в диапазоне 50–1500 мкмоль/л."),
    "glucose": (0.5, 40, "Глюкоза должна быть в диапазоне 0,5–40 ммоль/л."),
    "total_protein": (20, 120, "Общий белок должен быть в диапазоне 20–120 г/л."),
    "albumin": (10, 70, "Альбумин крови должен быть в диапазоне 10–70 г/л."),
    "potassium": (1, 10, "Калий должен быть в диапазоне 1–10 ммоль/л."),
    "calcium": (1, 4, "Кальций должен быть в диапазоне 1–4 ммоль/л."),
    "phosphorus": (0.2, 5, "Фосфор должен быть в диапазоне 0,2–5 ммоль/л."),
    "ferritin": (0, 10000, "Ферритин должен быть в диапазоне 0–10000."),
    "ptg": (0, 10000, "ПТГ должен быть в диапазоне 0–10000."),

    # ОАМ
    "specific_gravity": (1.000, 1.050, "Удельный вес мочи должен быть в диапазоне 1,000–1,050."),
    "urine_protein": (0, 20, "Белок в моче должен быть в диапазоне 0–20 г/л."),
    "urine_leukocytes": (0, 10000, "Лейкоциты в моче должны быть неотрицательным числом до 10000."),
    "urine_erythrocytes": (0, 10000, "Эритроциты в моче должны быть неотрицательным числом до 10000."),
    "bacteria": (0, 100, "Бактерии должны быть неотрицательным числом."),

    # Альбуминурия
    "urine_albumin": (0, 100000, "Недопустимое значение"),
    "urine_creatinine": (0.000001, 1000000, "Недопустимое значение"),

    # УЗИ
    "left_parenchyma": (1, 50, "Толщина паренхимы левой почки должна быть в диапазоне 1–50 мм."),
    "right_parenchyma": (1, 50, "Толщина паренхимы правой почки должна быть в диапазоне 1–50 мм."),
}

DATE_FIELDS = [
    "cbc_investigation_date",
    "biochemistry_investigation_date",
    "urinalysis_investigation_date",
    "albuminuria_investigation_date",
    "ultrasound_investigation_date",
]

ALLOWED_UNITS = {
    "urine_albumin_unit": {"mg_l", "g_l"},
    "urine_creatinine_unit": {"mmol_l", "umol_l"},
}


def validate_appointment_form(form, appointment_date_value: Any) -> List[ValidationError]:
    """Проверяет медицинские числовые поля формы перед сохранением приёма.

    Функция не требует заполнения необязательных полей. Пустые поля считаются допустимыми.
    Если поле заполнено, оно должно быть числом и попадать в широкий технический диапазон.
    """
    errors: List[ValidationError] = []
    appointment_date = _to_date(appointment_date_value)

    for field_name, (min_value, max_value, message) in NUMERIC_RULES.items():
        values = _getlist(form, field_name)
        for index, raw_value in enumerate(values):
            value_text = _empty_to_none(raw_value)
            if value_text is None:
                continue

            normalized_value = _normalize_numeric_value_for_validation(field_name, value_text)

            number = _to_float(normalized_value)
            if number is None:
                _add_error(errors, field_name, f"Поле должно быть числом. {message}", index)
                continue

            if number < min_value or number > max_value:
                _add_error(errors, field_name, message, index)

    # АД: систолическое должно быть больше диастолического.
    systolic = _to_float(form.get("systolic_pressure"))
    diastolic = _to_float(form.get("diastolic_pressure"))
    if systolic is not None and diastolic is not None and systolic <= diastolic:
        _add_error(errors, "systolic_pressure", "Систолическое АД должно быть больше диастолического.")
        _add_error(errors, "diastolic_pressure", "Диастолическое АД должно быть меньше систолического.")

    # Даты исследований не должны быть позже даты приёма.
    if appointment_date:
        for field_name in DATE_FIELDS:
            for index, raw_value in enumerate(_getlist(form, field_name)):
                value_text = _empty_to_none(raw_value)
                if value_text is None:
                    continue
                investigation_date = _to_date(value_text)
                if investigation_date is None:
                    _add_error(errors, field_name, "Некорректная дата исследования.", index)
                    continue
                if investigation_date > appointment_date:
                    _add_error(errors, field_name, "Дата исследования не может быть позже даты приёма.", index)

        next_control_date = _to_date(form.get("next_control_date"))
        if next_control_date and next_control_date < appointment_date:
            _add_error(errors, "next_control_date", "Дата следующего контроля не должна быть раньше даты приёма.")

    # Единицы измерения — только из разрешённого списка.
    for field_name, allowed in ALLOWED_UNITS.items():
        for index, raw_value in enumerate(_getlist(form, field_name)):
            value = _empty_to_none(raw_value)
            if value is None:
                continue
            if value not in allowed:
                _add_error(errors, field_name, "Некорректная единица измерения.", index)

    # Для ACR нужны обе части: альбумин и креатинин мочи.
    urine_albumin_values = _getlist(form, "urine_albumin")
    urine_creatinine_values = _getlist(form, "urine_creatinine")
    max_len = max(len(urine_albumin_values), len(urine_creatinine_values))
    for index in range(max_len):
        albumin = _empty_to_none(urine_albumin_values[index] if index < len(urine_albumin_values) else None)
        creatinine = _empty_to_none(urine_creatinine_values[index] if index < len(urine_creatinine_values) else None)
        if albumin and not creatinine:
            _add_error(errors, "urine_creatinine", "Для расчёта ACR нужен креатинин мочи.", index)
        if creatinine and not albumin:
            _add_error(errors, "urine_albumin", "Для расчёта ACR нужен альбумин мочи.", index)

    return errors
