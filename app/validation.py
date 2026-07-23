"""
Назначение файла: серверная проверка клинических полей перед сохранением приёма.

Главный принцип текущего этапа:
- врачу показываем только короткие сообщения: "Неверное значение" / "Некорректная дата";
- технические диапазоны остаются внутри приложения и не выводятся в интерфейс;
- нормализация безопасных форматов остаётся внутренней логикой;
- частично заполненная альбуминурия не блокирует сохранение и не показывает подсказки.

Важно: диапазоны ниже — это НЕ референсные интервалы нормы. Это широкие
технические пределы, чтобы не сохранять очевидно невозможные значения.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .services.clinical_value_normalization import normalize_appointment_form_values


ValidationError = Dict[str, Any]

ERROR_INVALID_VALUE = "Неверное значение"
ERROR_INVALID_DATE = "Некорректная дата"
ERROR_REQUIRED_FIELDS = "Не все обязательные поля заполнены"

DATE_OF_BIRTH_IN_FUTURE = "Дата рождения не может быть в будущем"
APPOINTMENT_BEFORE_BIRTH = "Дата приёма не может быть раньше даты рождения"
NEXT_VISIT_BEFORE_APPOINTMENT = "Дата следующего визита не может быть раньше даты приёма"
NEXT_VISIT_BEFORE_TODAY = "Дата следующего визита не может быть раньше текущей даты"
INVESTIGATION_AFTER_APPOINTMENT = "Дата исследования не может быть позже даты приёма"


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


def _add_error(
    errors: List[ValidationError],
    field: str,
    message: str,
    index: Optional[int] = None,
) -> None:
    errors.append(
        {
            "field": field,
            "message": message,
            "index": index,
        }
    )


# Технические пределы для отсечения абсурдных значений.
# Сообщение во всех случаях намеренно короткое: врач не должен видеть диапазоны.
NUMERIC_RULES = {
    # Осмотр
    "height": (50, 250, ERROR_INVALID_VALUE),
    "weight": (30, 300, ERROR_INVALID_VALUE),
    "systolic_pressure": (50, 300, ERROR_INVALID_VALUE),
    "diastolic_pressure": (30, 200, ERROR_INVALID_VALUE),
    "heart_rate": (20, 250, ERROR_INVALID_VALUE),
    "body_temperature": (25, 45, ERROR_INVALID_VALUE),

    # ОАК
    "hemoglobin": (20, 250, ERROR_INVALID_VALUE),
    "erythrocytes": (0.5, 10, ERROR_INVALID_VALUE),
    "leukocytes": (0.1, 300, ERROR_INVALID_VALUE),
    "platelets": (5, 1500, ERROR_INVALID_VALUE),
    "esr": (0, 150, ERROR_INVALID_VALUE),
    "mcv": (40, 140, ERROR_INVALID_VALUE),
    "hematocrit": (5, 70, ERROR_INVALID_VALUE),

    # Биохимия
    "creatinine": (15, 3000, ERROR_INVALID_VALUE),
    "urea": (0.5, 80, ERROR_INVALID_VALUE),
    "uric_acid": (50, 1500, ERROR_INVALID_VALUE),
    "glucose": (0.5, 40, ERROR_INVALID_VALUE),
    "total_protein": (20, 120, ERROR_INVALID_VALUE),
    "albumin": (10, 70, ERROR_INVALID_VALUE),
    "potassium": (1, 10, ERROR_INVALID_VALUE),
    "calcium": (1, 4, ERROR_INVALID_VALUE),
    "phosphorus": (0.2, 5, ERROR_INVALID_VALUE),
    "ferritin": (0, 10000, ERROR_INVALID_VALUE),
    "ptg": (0, 10000, ERROR_INVALID_VALUE),

    # ОАМ
    "specific_gravity": (1.000, 1.050, ERROR_INVALID_VALUE),
    "urine_protein": (0, 20, ERROR_INVALID_VALUE),
    "urine_leukocytes": (0, 10000, ERROR_INVALID_VALUE),
    "urine_erythrocytes": (0, 10000, ERROR_INVALID_VALUE),
    "bacteria": (0, 100, ERROR_INVALID_VALUE),

    # Альбуминурия
    "urine_albumin": (0, 100000, ERROR_INVALID_VALUE),
    "urine_creatinine": (0.000001, 1000000, ERROR_INVALID_VALUE),

    # УЗИ
    "left_parenchyma": (1, 50, ERROR_INVALID_VALUE),
    "right_parenchyma": (1, 50, ERROR_INVALID_VALUE),
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


def validate_patient_and_visit_dates(
    form,
    *,
    current_date: Optional[date] = None,
) -> List[ValidationError]:
    """
    Проверяет базовую связку дат пациента и визита.

    Функция отдельная, чтобы её можно было подключить к созданию нового пациента,
    не меняя медицинскую валидацию приёма. На фронте такие же проверки выполняет
    simple_form_guard.js, но серверная проверка нужна как второй рубеж защиты.
    """
    errors: List[ValidationError] = []
    today = current_date or date.today()

    birth_date = _to_date(form.get("birth_date"))
    appointment_date = _to_date(form.get("appointment_date"))
    next_control_date = _to_date(form.get("next_control_date"))

    if _empty_to_none(form.get("birth_date")) and birth_date is None:
        _add_error(errors, "birth_date", ERROR_INVALID_DATE)
    if _empty_to_none(form.get("appointment_date")) and appointment_date is None:
        _add_error(errors, "appointment_date", ERROR_INVALID_DATE)
    if _empty_to_none(form.get("next_control_date")) and next_control_date is None:
        _add_error(errors, "next_control_date", ERROR_INVALID_DATE)

    if birth_date and birth_date > today:
        _add_error(errors, "birth_date", DATE_OF_BIRTH_IN_FUTURE)

    if birth_date and appointment_date and appointment_date < birth_date:
        _add_error(errors, "appointment_date", APPOINTMENT_BEFORE_BIRTH)

    if next_control_date and appointment_date and next_control_date < appointment_date:
        _add_error(errors, "next_control_date", NEXT_VISIT_BEFORE_APPOINTMENT)

    if next_control_date and next_control_date < today:
        _add_error(errors, "next_control_date", NEXT_VISIT_BEFORE_TODAY)

    return errors


def validate_appointment_form(
    form,
    appointment_date_value: Any,
    *,
    birth_date_value: Any = None,
    current_date: Optional[date] = None,
) -> List[ValidationError]:
    """
    Проверяет медицинские поля формы перед сохранением приёма.

    Пустые необязательные поля допустимы. Если поле заполнено, оно должно быть
    числом и попадать в широкий технический диапазон. Наружу выводится только
    короткое сообщение "Неверное значение".

    Перед проверкой форма нормализуется:
    - 5,1 -> 5.1;
    - 1015 -> 1.015 для удельного веса мочи;
    - 0.39 -> 39 для гематокрита.
    """
    form = normalize_appointment_form_values(form)
    errors: List[ValidationError] = []
    appointment_date = _to_date(appointment_date_value)
    today = current_date or date.today()

    for field_name, (min_value, max_value, message) in NUMERIC_RULES.items():
        values = _getlist(form, field_name)
        for index, raw_value in enumerate(values):
            value_text = _empty_to_none(raw_value)
            if value_text is None:
                continue

            number = _to_float(value_text)
            if number is None:
                _add_error(errors, field_name, message, index)
                continue

            if number < min_value or number > max_value:
                _add_error(errors, field_name, message, index)

    # АД: если оба значения заполнены, систолическое должно быть больше диастолического.
    systolic = _to_float(form.get("systolic_pressure"))
    diastolic = _to_float(form.get("diastolic_pressure"))
    if systolic is not None and diastolic is not None and systolic <= diastolic:
        _add_error(errors, "systolic_pressure", ERROR_INVALID_VALUE)
        _add_error(errors, "diastolic_pressure", ERROR_INVALID_VALUE)

    # Дата рождения и дата приёма проверяются только если birth_date_value передан.
    birth_date = _to_date(birth_date_value)
    if birth_date_value is not None:
        if _empty_to_none(birth_date_value) and birth_date is None:
            _add_error(errors, "birth_date", ERROR_INVALID_DATE)
        elif birth_date and birth_date > today:
            _add_error(errors, "birth_date", DATE_OF_BIRTH_IN_FUTURE)

        if birth_date and appointment_date and appointment_date < birth_date:
            _add_error(errors, "appointment_date", APPOINTMENT_BEFORE_BIRTH)

    # Даты исследований не должны быть позже даты приёма.
    if appointment_date:
        for field_name in DATE_FIELDS:
            for index, raw_value in enumerate(_getlist(form, field_name)):
                value_text = _empty_to_none(raw_value)
                if value_text is None:
                    continue

                investigation_date = _to_date(value_text)
                if investigation_date is None:
                    _add_error(errors, field_name, ERROR_INVALID_DATE, index)
                    continue

                if investigation_date > appointment_date:
                    _add_error(errors, field_name, INVESTIGATION_AFTER_APPOINTMENT, index)

        next_control_date = _to_date(form.get("next_control_date"))
        if next_control_date and next_control_date < appointment_date:
            _add_error(errors, "next_control_date", NEXT_VISIT_BEFORE_APPOINTMENT)
        if next_control_date and next_control_date < today:
            _add_error(errors, "next_control_date", NEXT_VISIT_BEFORE_TODAY)

    # Единицы измерения — только из разрешённого списка.
    # Сообщение короткое, без перечисления внутренних значений.
    for field_name, allowed in ALLOWED_UNITS.items():
        for index, raw_value in enumerate(_getlist(form, field_name)):
            value = _empty_to_none(raw_value)
            if value is None:
                continue
            if value not in allowed:
                _add_error(errors, field_name, ERROR_INVALID_VALUE, index)


    # Структурированные поля верхней части формы (миграции 0009–0010).
    allowed_select_values = {
        "general_condition": {"satisfactory", "moderate", "severe"},
        "consciousness": {"clear", "confused", "sopor", "coma"},
        "bed_position": {"active", "passive", "forced"},
        "constitution_type": {"normosthenic", "asthenic", "hypersthenic"},
        "kidney_palpation": {"palpable", "not_palpable"},
        "pasternatsky_result": {"positive", "negative"},
        "pasternatsky_side": {"right", "left", "bilateral"},
    }
    for field_name, allowed in allowed_select_values.items():
        value = _empty_to_none(form.get(field_name))
        if value is not None and value not in allowed:
            _add_error(errors, field_name, ERROR_INVALID_VALUE)

    bed_position = _empty_to_none(form.get("bed_position"))
    bed_position_details = _empty_to_none(form.get("bed_position_details"))
    if bed_position == "forced" and not bed_position_details:
        _add_error(errors, "bed_position_details", ERROR_REQUIRED_FIELDS)

    kidney_palpation = _empty_to_none(form.get("kidney_palpation"))
    kidney_palpation_details = _empty_to_none(form.get("kidney_palpation_details"))
    if kidney_palpation == "palpable" and not kidney_palpation_details:
        _add_error(errors, "kidney_palpation_details", ERROR_REQUIRED_FIELDS)

    pasternatsky_result = _empty_to_none(form.get("pasternatsky_result"))
    pasternatsky_side = _empty_to_none(form.get("pasternatsky_side"))
    if bool(pasternatsky_result) != bool(pasternatsky_side):
        if not pasternatsky_result:
            _add_error(errors, "pasternatsky_result", ERROR_REQUIRED_FIELDS)
        if not pasternatsky_side:
            _add_error(errors, "pasternatsky_side", ERROR_REQUIRED_FIELDS)

    # ВАЖНО: частично заполненную альбуминурию больше не блокируем.
    # Если введён только альбумин или только креатинин мочи, форма сохраняется,
    # а ACR просто не рассчитывается. Врач увидит спокойную подсказку под таблицей,
    # какие поля нужны для расчёта.

    return errors
