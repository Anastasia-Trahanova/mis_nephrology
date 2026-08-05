from __future__ import annotations

"""Импорт распарсенных архивных консультаций в PostgreSQL МИС.

По умолчанию выполняется только проверка. Для записи нужен флаг ``--apply``.
Скрипт не меняет приложение и не удаляет существующие данные.
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EXPECTED_REVISION = "0016_archive_import_fields"
DEFAULT_EXPECTED_COUNT = 1518
IMPORT_KEY_PREFIX = "nephro-v110:"
CLEAN_STATUS = "ЧИСТАЯ_ЗАПИСЬ"


class ImportValidationError(RuntimeError):
    """Проверка входных данных или схемы не пройдена."""


@dataclass(frozen=True)
class ClinicalFinding:
    field_name: str
    value: str
    source_text: str
    source_order: int


@dataclass(frozen=True)
class LaboratoryFinding:
    analysis_date: date | None
    date_precision: str
    day_is_artificial: bool
    study_type: str
    indicator_raw: str
    indicator_normalized: str
    numeric_value: str | None
    text_value: str | None
    unit: str | None
    source_order: int
    note: str | None


@dataclass(frozen=True)
class InstrumentalFinding:
    study_date: date | None
    date_precision: str
    day_is_artificial: bool
    study_type: str
    result_text: str
    source_order: int
    note: str | None


@dataclass
class SourceConsultation:
    consultation_id: str
    patient_name: str
    birth_date: date
    appointment_date: date
    doctor_name: str
    complaints: str | None
    disease_anamnesis: str | None
    life_anamnesis: str | None
    diagnosis: str | None
    diagnosis_comment: str | None
    recommendations: str | None
    findings: list[ClinicalFinding] = field(default_factory=list)
    laboratory: list[LaboratoryFinding] = field(default_factory=list)
    instrumental: list[InstrumentalFinding] = field(default_factory=list)


@dataclass(frozen=True)
class PersonName:
    last_name: str
    first_name: str
    patronymic: str | None


@dataclass
class ImportReport:
    mode: str
    source_database: str
    source_clean_consultations: int = 0
    source_unique_patients: int = 0
    source_doctors: dict[str, int] = field(default_factory=dict)
    database_revision: str | None = None
    doctor_mapping: dict[str, str] = field(default_factory=dict)
    consultations_already_present: int = 0
    consultations_to_insert: int = 0
    patients_to_create: int = 0
    patients_reused: int = 0
    appointments_inserted: int = 0
    patients_created: int = 0
    surveys_inserted: int = 0
    examinations_inserted: int = 0
    recommendations_inserted: int = 0
    additional_studies_inserted: int = 0
    cbc_rows_inserted: int = 0
    biochemistry_rows_inserted: int = 0
    urinalysis_rows_inserted: int = 0
    albuminuria_rows_inserted: int = 0
    calculated_metrics_rows_inserted: int = 0
    laboratory_values_mapped: int = 0
    laboratory_values_left_as_other: int = 0
    instrumental_studies_imported: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DoctorRow:
    doctor_id: int
    last_name: str
    first_name: str
    patronymic: str | None

    @property
    def display_name(self) -> str:
        initials = self.first_name[:1] + "."
        if self.patronymic:
            initials += self.patronymic[:1] + "."
        return f"{self.last_name} {initials}"


@dataclass(frozen=True)
class PatientRow:
    patient_id: int
    last_name: str
    first_name: str
    patronymic: str | None
    birth_date: date


@dataclass(frozen=True)
class LabRule:
    table: str
    column: str
    units: tuple[str, ...] = ()
    allow_missing_unit: bool = True
    transform: str | None = None
    extra_columns: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NumericSpec:
    precision: int
    scale: int


LAB_RULES: dict[tuple[str, str], LabRule] = {
    ("ОАК", "Гемоглобин"): LabRule("cbc_results", "hemoglobin", ("г/л",)),
    ("ОАК", "Эритроциты"): LabRule("cbc_results", "erythrocytes", ("10^12/л",)),
    ("ОАК", "Лейкоциты"): LabRule("cbc_results", "leukocytes", ("10^9/л",)),
    ("ОАК", "Тромбоциты"): LabRule("cbc_results", "platelets", ("10^9/л",)),
    ("ОАК", "СОЭ"): LabRule("cbc_results", "esr", ("мм/ч",)),
    ("ОАК", "MCV"): LabRule("cbc_results", "mcv", ("фл",)),
    ("ОАК", "Гематокрит"): LabRule("cbc_results", "hematocrit", ("%",)),
    ("Биохимия", "Креатинин"): LabRule("biochemistry_results", "creatinine", ("мкмоль/л",)),
    ("Биохимия", "Мочевина"): LabRule("biochemistry_results", "urea", ("ммоль/л",)),
    ("Биохимия", "Мочевая кислота"): LabRule("biochemistry_results", "uric_acid", ("мкмоль/л",)),
    ("Биохимия", "Глюкоза крови"): LabRule("biochemistry_results", "glucose", ("ммоль/л",)),
    ("Биохимия", "Общий белок"): LabRule("biochemistry_results", "total_protein", ("г/л",)),
    ("Биохимия", "Альбумин"): LabRule("biochemistry_results", "albumin", ("г/л",)),
    ("Биохимия", "Калий"): LabRule("biochemistry_results", "potassium", ("ммоль/л",)),
    ("Биохимия", "Кальций"): LabRule("biochemistry_results", "calcium", ("ммоль/л",)),
    ("Биохимия", "Фосфор"): LabRule("biochemistry_results", "phosphorus", ("ммоль/л",)),
    ("Биохимия", "Ферритин"): LabRule("biochemistry_results", "ferritin", ("нг/мл", "мкг/л")),
    ("ПТГ", "Паратгормон"): LabRule("biochemistry_results", "ptg", ("пг/мл",)),
    ("ОАМ", "Относительная плотность"): LabRule("urinalysis_results", "specific_gravity", (), True, "specific_gravity"),
    ("ОАМ", "Белок"): LabRule("urinalysis_results", "protein", ("г/л", "мг/л"), True, "urine_protein"),
    ("ОАМ", "Лейкоциты"): LabRule("urinalysis_results", "leukocytes", ("вп/зр",), True),
    ("ОАМ", "Эритроциты"): LabRule("urinalysis_results", "erythrocytes", ("вп/зр",), True),
    ("ОАМ", "Бактерии"): LabRule("urinalysis_results", "bacteria", (), True, "text"),
    ("МАУ", "Микроальбуминурия"): LabRule("albuminuria_results", "urine_albumin", ("мг/л", "г/л"), False, "albumin_unit"),
    ("МАУ", "Креатинин мочи"): LabRule("albuminuria_results", "urine_creatinine", ("ммоль/л", "мкмоль/л"), False, "urine_creatinine_unit"),
    ("Расчет", "рСКФ CKD-EPI"): LabRule("calculated_metrics", "egfr_ckdepi", ("мл/мин/1.73м2", "мл/мин")),
}

TABLE_DATE_REQUIRED = {
    "cbc_results": True,
    "biochemistry_results": True,
    "urinalysis_results": True,
    "albuminuria_results": True,
    "calculated_metrics": False,
}

REQUIRED_TARGET_COLUMNS: dict[str, set[str]] = {
    "patients": {"id", "last_name", "first_name", "patronymic", "birth_date", "gender"},
    "doctors": {"id", "last_name", "first_name", "patronymic"},
    "appointments": {
        "id", "patient_id", "doctor_id", "location_id", "appointment_date",
        "age_at_appointment", "diagnosis_text", "diagnosis_comment_text",
        "is_archive_import", "archive_import_key",
    },
    "surveys": {
        "appointment_id", "complaints", "heredity_description",
        "disease_anamnesis_text", "life_anamnesis_text",
    },
    "examinations": {
        "appointment_id", "skin_and_mucous_membranes", "edema_location",
        "systolic_pressure", "diastolic_pressure", "bp_note", "heart_rate",
        "height", "weight", "bmi", "pasternatsky_result", "pasternatsky_side",
    },
    "appointment_diets": {"appointment_id", "recommendations"},
    "appointment_additional_studies": {
        "appointment_id", "other_laboratory_studies", "other_instrumental_studies",
    },
    "cbc_results": {"appointment_id", "investigation_date", "hemoglobin", "erythrocytes", "leukocytes", "platelets", "esr", "mcv", "hematocrit"},
    "biochemistry_results": {"appointment_id", "investigation_date", "creatinine", "urea", "uric_acid", "glucose", "total_protein", "albumin", "potassium", "calcium", "phosphorus", "ferritin", "ptg"},
    "urinalysis_results": {"appointment_id", "investigation_date", "specific_gravity", "protein", "leukocytes", "erythrocytes", "bacteria"},
    "albuminuria_results": {"appointment_id", "investigation_date", "urine_albumin", "urine_albumin_unit", "urine_creatinine", "urine_creatinine_unit", "albumin_creatinine_ratio", "daily_albumin_excretion"},
    "calculated_metrics": {"appointment_id", "investigation_date", "age", "gender", "weight_at_appointment", "egfr_ckdepi"},
}

DOCTOR_SURNAME_ALIASES = {
    "возва": "возова",
}


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def multiline_text(values: Iterable[str | None]) -> str | None:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return "\n".join(result) if result else None


def parse_iso_date(value: Any, *, field_name: str) -> date:
    text = clean_text(value)
    if not text:
        raise ImportValidationError(f"Не указано поле {field_name}")
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ImportValidationError(f"Некорректная дата {field_name}: {text}") from exc


def parse_optional_iso_date(value: Any) -> date | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def normalize_word(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^а-яёa-z0-9]", "", value.lower().replace("ё", "е"))


def split_person_name(value: str) -> PersonName:
    text = re.sub(r"\s+", " ", value.strip())
    parts = text.split(" ")
    if len(parts) < 2:
        raise ImportValidationError(f"Невозможно разделить ФИО пациента: {value!r}")

    last_name = parts[0].strip(" ,.;:")
    remaining = " ".join(parts[1:]).strip()
    initials = re.fullmatch(r"([А-ЯЁA-Z])\.?\s*([А-ЯЁA-Z])?\.?", remaining)
    if initials:
        first_name = initials.group(1) + "."
        patronymic = initials.group(2) + "." if initials.group(2) else None
        return PersonName(last_name, first_name, patronymic)

    first_name = parts[1].strip(" ,.;:")
    patronymic = " ".join(parts[2:]).strip(" ,.;:") if len(parts) > 2 else None
    return PersonName(last_name, first_name, patronymic or None)


def person_key(name: PersonName, birth_date: date) -> tuple[str, str, str, date]:
    return (
        normalize_word(name.last_name),
        normalize_word(name.first_name),
        normalize_word(name.patronymic),
        birth_date,
    )


def age_on_date(birth_date: date, appointment_date: date) -> int:
    years = appointment_date.year - birth_date.year
    if (appointment_date.month, appointment_date.day) < (birth_date.month, birth_date.day):
        years -= 1
    if not 0 <= years <= 130:
        raise ImportValidationError(
            f"Недопустимый возраст {years}: дата рождения {birth_date}, приём {appointment_date}"
        )
    return years


def normalize_doctor_source(value: str) -> tuple[str, str | None, str | None]:
    text = value.replace("ё", "е")
    text = re.sub(r"[–—−]", "-", text)
    text = re.sub(r"\b(?:врач|нефролог|врач-нефролог|к\s*\.?\s*м\s*\.?\s*н\s*\.?)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,:;-")

    match = re.search(
        r"([А-ЯЁA-Z][а-яёa-z-]+)\s+([А-ЯЁA-Z])\.?\s*([А-ЯЁA-Z])?\.?",
        text,
    )
    if match:
        surname = normalize_word(match.group(1))
        surname = DOCTOR_SURNAME_ALIASES.get(surname, surname)
        return surname, normalize_word(match.group(2)), normalize_word(match.group(3)) or None

    parts = text.split()
    if not parts:
        raise ImportValidationError(f"Не указано ФИО врача: {value!r}")
    surname = normalize_word(parts[0])
    surname = DOCTOR_SURNAME_ALIASES.get(surname, surname)
    first_initial = normalize_word(parts[1][:1]) if len(parts) > 1 else None
    patronymic_initial = normalize_word(parts[2][:1]) if len(parts) > 2 else None
    return surname, first_initial, patronymic_initial


def match_doctor(source_name: str, doctors: Sequence[DoctorRow]) -> DoctorRow:
    surname, first_initial, patronymic_initial = normalize_doctor_source(source_name)
    candidates = [d for d in doctors if normalize_word(d.last_name) == surname]
    if first_initial:
        candidates = [d for d in candidates if normalize_word(d.first_name[:1]) == first_initial]
    if patronymic_initial:
        candidates = [
            d for d in candidates
            if d.patronymic and normalize_word(d.patronymic[:1]) == patronymic_initial
        ]
    if len(candidates) != 1:
        options = ", ".join(d.display_name for d in candidates) or "нет совпадений"
        raise ImportValidationError(
            f"Врач {source_name!r} не сопоставлен однозначно: {options}"
        )
    return candidates[0]


def normalize_unit(value: str | None) -> str:
    if not value:
        return ""
    unit = value.lower().replace("ё", "е")
    unit = unit.replace("²", "2").replace("³", "3").replace("¹", "1")
    unit = unit.replace(",", ".")
    unit = re.sub(r"\s+", "", unit)
    unit = unit.replace("мкг/л", "мкг/л")
    unit = unit.replace("вп/зр", "вп/зр").replace("впзр", "вп/зр")
    unit = re.sub(r"^\*?10\^?12/л$", "10^12/л", unit)
    unit = re.sub(r"^\*?1012/л$", "10^12/л", unit)
    unit = re.sub(r"^\*?10\^?9/л$", "10^9/л", unit)
    unit = re.sub(r"^\*?109/л$", "10^9/л", unit)
    unit = unit.replace("мл/мин/1.73м²", "мл/мин/1.73м2")
    return unit


def decimal_value(value: str | None) -> Decimal | None:
    if value is None:
        return None
    text = value.strip().replace(",", ".")
    if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", text):
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _source_value(lab: LaboratoryFinding) -> str:
    value = lab.numeric_value if lab.numeric_value is not None else lab.text_value
    value = value or "не указано"
    unit = f" {lab.unit}" if lab.unit else ""
    date_text = lab.analysis_date.isoformat() if lab.analysis_date else "дата не указана"
    artificial = " (15-е число установлено искусственно)" if lab.day_is_artificial else ""
    note = f"; {lab.note}" if lab.note else ""
    return (
        f"{date_text}{artificial} | {lab.study_type} | "
        f"{lab.indicator_normalized}: {value}{unit}{note}"
    )


def _unit_allowed(unit: str, rule: LabRule) -> bool:
    if not unit:
        return rule.allow_missing_unit
    return unit in rule.units


def _transform_lab_value(value: Decimal, unit: str, rule: LabRule) -> tuple[Decimal, dict[str, Any]]:
    extras: dict[str, Any] = dict(rule.extra_columns)
    if rule.transform == "specific_gravity":
        if Decimal("100") <= value <= Decimal("2000"):
            value = value / Decimal("1000")
    elif rule.transform == "urine_protein" and unit == "мг/л":
        value = value / Decimal("1000")
    elif rule.transform == "albumin_unit":
        extras["urine_albumin_unit"] = "g_l" if unit == "г/л" else "mg_l"
    elif rule.transform == "urine_creatinine_unit":
        extras["urine_creatinine_unit"] = "umol_l" if unit == "мкмоль/л" else "mmol_l"
    return value, extras


def numeric_value_fits(value: Decimal, spec: NumericSpec) -> bool:
    """Проверяет, поместится ли число в NUMERIC(precision, scale)."""
    quantum = Decimal(1).scaleb(-spec.scale)
    rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
    integer_digits = spec.precision - spec.scale
    return abs(rounded) < (Decimal(10) ** integer_digits)


def build_lab_payloads(
    consultation: SourceConsultation,
    *,
    age: int,
    weight: Decimal | None,
    numeric_specs: Mapping[tuple[str, str], NumericSpec] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str], int]:
    """Преобразует распарсенные показатели в строки таблиц МИС.

    Возвращает payload-ы по таблицам, список неразмещённых значений и число
    успешно сопоставленных показателей.
    """
    grouped: dict[tuple[str, date | None], dict[str, Any]] = {}
    residual: list[str] = []
    mapped = 0

    for lab in sorted(consultation.laboratory, key=lambda x: x.source_order):
        rule = LAB_RULES.get((lab.study_type, lab.indicator_normalized))
        numeric = decimal_value(lab.numeric_value)
        unit = normalize_unit(lab.unit)

        if rule is None:
            residual.append(_source_value(lab))
            continue
        if rule.transform == "text":
            text_result = clean_text(lab.text_value) or clean_text(lab.numeric_value)
            if not text_result:
                residual.append(_source_value(lab))
                continue
            key = (rule.table, lab.analysis_date)
            if TABLE_DATE_REQUIRED[rule.table] and lab.analysis_date is None:
                residual.append(_source_value(lab) + " [не загружено: нет даты]")
                continue
            payload = grouped.setdefault(key, {"investigation_date": lab.analysis_date})
            if rule.column in payload and payload[rule.column] != text_result:
                residual.append(_source_value(lab) + " [не загружено: повторное отличающееся значение]")
                continue
            payload[rule.column] = text_result[:100]
            mapped += 1
            continue
        if numeric is None:
            residual.append(_source_value(lab))
            continue
        if TABLE_DATE_REQUIRED[rule.table] and lab.analysis_date is None:
            residual.append(_source_value(lab) + " [не загружено: нет даты]")
            continue
        if not _unit_allowed(unit, rule):
            residual.append(_source_value(lab) + " [не загружено: единица не соответствует полю МИС]")
            continue
        if numeric < 0:
            residual.append(_source_value(lab) + " [не загружено: отрицательное числовое значение]")
            continue

        original_numeric = numeric
        numeric, extras = _transform_lab_value(numeric, unit, rule)
        if rule.transform == "specific_gravity" and numeric != original_numeric:
            residual.append(
                _source_value(lab) + f" [загружено как относительная плотность {numeric}]"
            )
        elif rule.transform == "urine_protein" and unit == "мг/л":
            residual.append(
                _source_value(lab) + f" [пересчитано в {numeric} г/л для поля МИС]"
            )

        spec = (numeric_specs or {}).get((rule.table, rule.column))
        if spec is not None and not numeric_value_fits(numeric, spec):
            residual.append(
                _source_value(lab)
                + f" [не загружено: значение {numeric} не помещается в "
                + f"{rule.table}.{rule.column} NUMERIC({spec.precision},{spec.scale})]"
            )
            continue

        key = (rule.table, lab.analysis_date)
        payload = grouped.setdefault(
            key,
            {"investigation_date": lab.analysis_date},
        )
        if rule.column in payload:
            if payload[rule.column] == numeric:
                continue
            residual.append(_source_value(lab) + " [не загружено: повторное отличающееся значение]")
            continue
        payload[rule.column] = numeric
        payload.update(extras)
        if lab.day_is_artificial:
            residual.append(
                f"{lab.analysis_date.isoformat()} | {lab.study_type}: "
                "день 15 установлен искусственно"
            )
        if not unit and rule.units:
            residual.append(_source_value(lab) + " [загружено, но единица в источнике не указана]")
        mapped += 1

    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (table_name, _), payload in grouped.items():
        if table_name == "calculated_metrics":
            payload.setdefault("age", age)
            payload.setdefault("gender", None)
            payload.setdefault("weight_at_appointment", weight)
        if table_name == "albuminuria_results":
            payload.setdefault("urine_albumin_unit", "mg_l")
            payload.setdefault("urine_creatinine_unit", "mmol_l")
        result[table_name].append(payload)
    residual = list(dict.fromkeys(residual))
    return dict(result), residual, mapped


def parse_number_with_unit(values: Sequence[str], kind: str) -> Decimal | None:
    for value in values:
        match = re.search(r"([+-]?\d+(?:[.,]\d+)?)", value)
        if not match:
            continue
        number = Decimal(match.group(1).replace(",", "."))
        lower = value.lower()
        if kind == "height" and re.search(r"(?:^|\s)м(?:\s|$|\.)", lower) and "см" not in lower:
            number *= 100
        return number
    return None


def parse_bp(values: Sequence[str]) -> tuple[int | None, int | None, str | None]:
    if not values:
        return None, None, None
    note = multiline_text(values)
    for value in values:
        match = re.search(r"(\d{2,3})\s*/\s*(\d{2,3})", value)
        if not match:
            continue
        systolic, diastolic = int(match.group(1)), int(match.group(2))
        if 40 <= systolic <= 280 and 20 <= diastolic <= 200 and systolic > diastolic:
            return systolic, diastolic, note
    return None, None, note


def parse_heart_rate(values: Sequence[str]) -> int | None:
    for value in values:
        match = re.search(r"\b(\d{2,3})\b", value)
        if match:
            pulse = int(match.group(1))
            if 30 <= pulse <= 220:
                return pulse
    return None


def parse_pasternatsky(values: Sequence[str]) -> tuple[str | None, str | None]:
    text = " ".join(values).lower().replace("ё", "е")
    if not text:
        return None, None
    if "отриц" in text:
        result = "negative"
    elif "полож" in text:
        result = "positive"
    else:
        return None, None

    if re.search(r"обеих|двусторон|с\s+двух", text):
        side = "bilateral"
    elif "справа" in text or "правой" in text:
        side = "right"
    elif "слева" in text or "левой" in text:
        side = "left"
    else:
        return None, None
    return result, side


def _require_sqlite_columns(connection: sqlite3.Connection, table: str, required: set[str]) -> None:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    existing = {row[1] for row in rows}
    missing = required - existing
    if missing:
        raise ImportValidationError(
            f"В SQLite таблице {table} отсутствуют поля: {', '.join(sorted(missing))}"
        )


def load_source(path: Path, expected_count: int = DEFAULT_EXPECTED_COUNT) -> list[SourceConsultation]:
    if not path.is_file():
        raise ImportValidationError(f"Не найден файл SQLite: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        _require_sqlite_columns(
            connection,
            "consultations",
            {
                "consultation_id", "resolved_name", "birth_date", "appointment_date",
                "doctor_name", "status", "complaints", "history_of_present_illness",
                "history_of_life", "diagnosis", "comments", "recommendations",
            },
        )
        _require_sqlite_columns(
            connection,
            "clinical_findings",
            {"consultation_id", "field_name", "extracted_value", "source_text", "source_order"},
        )
        _require_sqlite_columns(
            connection,
            "laboratory_results",
            {
                "consultation_id", "analysis_date", "date_precision", "day_is_artificial",
                "study_type", "indicator_raw", "indicator_normalized", "numeric_value",
                "text_value", "unit", "source_order", "note",
            },
        )
        _require_sqlite_columns(
            connection,
            "instrumental_studies",
            {
                "consultation_id", "study_date", "date_precision", "day_is_artificial",
                "study_type", "result_text", "source_order", "note",
            },
        )

        rows = connection.execute(
            """
            SELECT consultation_id, resolved_name, birth_date, appointment_date,
                   doctor_name, complaints, history_of_present_illness,
                   history_of_life, diagnosis, comments, recommendations
            FROM consultations
            WHERE status = ?
            ORDER BY appointment_date, consultation_id
            """,
            (CLEAN_STATUS,),
        ).fetchall()
        if len(rows) != expected_count:
            raise ImportValidationError(
                f"Ожидалось {expected_count} чистых приёмов, найдено {len(rows)}. "
                "Импорт остановлен, чтобы не загрузить неполный или другой результат."
            )

        consultations: dict[str, SourceConsultation] = {}
        problems: list[str] = []
        for row in rows:
            consultation_id = str(row["consultation_id"])
            try:
                name = clean_text(row["resolved_name"])
                doctor = clean_text(row["doctor_name"])
                if not name:
                    raise ImportValidationError("не определено ФИО пациента")
                if not doctor:
                    raise ImportValidationError("не определено ФИО врача")
                item = SourceConsultation(
                    consultation_id=consultation_id,
                    patient_name=name,
                    birth_date=parse_iso_date(row["birth_date"], field_name="дата рождения"),
                    appointment_date=parse_iso_date(row["appointment_date"], field_name="дата приёма"),
                    doctor_name=doctor,
                    complaints=clean_text(row["complaints"]),
                    disease_anamnesis=clean_text(row["history_of_present_illness"]),
                    life_anamnesis=clean_text(row["history_of_life"]),
                    diagnosis=clean_text(row["diagnosis"]),
                    diagnosis_comment=clean_text(row["comments"]),
                    recommendations=clean_text(row["recommendations"]),
                )
                split_person_name(item.patient_name)
                age_on_date(item.birth_date, item.appointment_date)
                consultations[consultation_id] = item
            except ImportValidationError as exc:
                problems.append(f"{consultation_id}: {exc}")
        if problems:
            raise ImportValidationError("Ошибки чистых приёмов:\n" + "\n".join(problems[:30]))

        for row in connection.execute(
            """
            SELECT consultation_id, field_name, extracted_value, source_text, source_order
            FROM clinical_findings ORDER BY consultation_id, source_order
            """
        ):
            item = consultations.get(str(row["consultation_id"]))
            if item is None:
                continue
            item.findings.append(
                ClinicalFinding(
                    field_name=str(row["field_name"]),
                    value=str(row["extracted_value"]),
                    source_text=str(row["source_text"]),
                    source_order=int(row["source_order"]),
                )
            )

        for row in connection.execute(
            """
            SELECT consultation_id, analysis_date, date_precision, day_is_artificial,
                   study_type, indicator_raw, indicator_normalized, numeric_value,
                   text_value, unit, source_order, note
            FROM laboratory_results ORDER BY consultation_id, source_order
            """
        ):
            item = consultations.get(str(row["consultation_id"]))
            if item is None:
                continue
            item.laboratory.append(
                LaboratoryFinding(
                    analysis_date=parse_optional_iso_date(row["analysis_date"]),
                    date_precision=str(row["date_precision"]),
                    day_is_artificial=bool(row["day_is_artificial"]),
                    study_type=str(row["study_type"]),
                    indicator_raw=str(row["indicator_raw"]),
                    indicator_normalized=str(row["indicator_normalized"]),
                    numeric_value=clean_text(row["numeric_value"]),
                    text_value=clean_text(row["text_value"]),
                    unit=clean_text(row["unit"]),
                    source_order=int(row["source_order"]),
                    note=clean_text(row["note"]),
                )
            )

        for row in connection.execute(
            """
            SELECT consultation_id, study_date, date_precision, day_is_artificial,
                   study_type, result_text, source_order, note
            FROM instrumental_studies ORDER BY consultation_id, source_order
            """
        ):
            item = consultations.get(str(row["consultation_id"]))
            if item is None:
                continue
            item.instrumental.append(
                InstrumentalFinding(
                    study_date=parse_optional_iso_date(row["study_date"]),
                    date_precision=str(row["date_precision"]),
                    day_is_artificial=bool(row["day_is_artificial"]),
                    study_type=str(row["study_type"]),
                    result_text=str(row["result_text"]).strip(),
                    source_order=int(row["source_order"]),
                    note=clean_text(row["note"]),
                )
            )

        # Точнее выделенные анамнезы из clinical_findings имеют приоритет.
        for item in consultations.values():
            by_field: dict[str, list[str]] = defaultdict(list)
            for finding in sorted(item.findings, key=lambda x: x.source_order):
                by_field[finding.field_name].append(finding.value)
            item.disease_anamnesis = multiline_text(by_field["анамнез_заболевания"]) or item.disease_anamnesis
            item.life_anamnesis = multiline_text(by_field["анамнез_жизни"]) or item.life_anamnesis

        return list(consultations.values())
    finally:
        connection.close()


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def connect_postgresql(project_root: Path):
    load_env(project_root / ".env")
    try:
        import psycopg2
    except ImportError as exc:
        raise ImportValidationError(
            "Не установлен psycopg2. Выполните: pip install -r requirements.txt"
        ) from exc

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    required = ["DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise ImportValidationError(
            "В .env не заполнены параметры PostgreSQL: " + ", ".join(missing)
        )
    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ["DB_PORT"],
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def target_columns(cursor) -> dict[str, dict[str, str]]:
    cursor.execute(
        """
        SELECT table_name, column_name, is_nullable
        FROM information_schema.columns
        WHERE table_schema = current_schema()
        """
    )
    result: dict[str, dict[str, str]] = defaultdict(dict)
    for table_name, column_name, is_nullable in cursor.fetchall():
        result[str(table_name)][str(column_name)] = str(is_nullable)
    return dict(result)


def target_numeric_specs(cursor) -> dict[tuple[str, str], NumericSpec]:
    cursor.execute(
        """
        SELECT table_name, column_name, numeric_precision, numeric_scale
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND data_type = 'numeric'
          AND numeric_precision IS NOT NULL
          AND numeric_scale IS NOT NULL
        """
    )
    return {
        (str(table_name), str(column_name)): NumericSpec(int(precision), int(scale))
        for table_name, column_name, precision, scale in cursor.fetchall()
    }


def validate_target_schema(cursor) -> str | None:
    cursor.execute("SELECT version_num FROM alembic_version")
    revisions = [str(row[0]) for row in cursor.fetchall()]
    revision = ", ".join(revisions) if revisions else None

    columns = target_columns(cursor)
    errors: list[str] = []
    for table_name, required in REQUIRED_TARGET_COLUMNS.items():
        existing = set(columns.get(table_name, {}))
        missing = required - existing
        if missing:
            errors.append(f"{table_name}: нет {', '.join(sorted(missing))}")
    if errors:
        raise ImportValidationError(
            "Схема МИС не готова к импорту. Проверьте миграцию 0016:\n" + "\n".join(errors)
        )
    if columns["patients"].get("gender") != "YES":
        raise ImportValidationError("patients.gender всё ещё NOT NULL")
    if columns["appointments"].get("location_id") != "YES":
        raise ImportValidationError("appointments.location_id всё ещё NOT NULL")
    return revision


def fetch_doctors(cursor) -> list[DoctorRow]:
    cursor.execute("SELECT id, last_name, first_name, patronymic FROM doctors ORDER BY id")
    return [DoctorRow(int(row[0]), str(row[1]), str(row[2]), row[3]) for row in cursor.fetchall()]


def fetch_patients(cursor) -> list[PatientRow]:
    cursor.execute("SELECT id, last_name, first_name, patronymic, birth_date FROM patients ORDER BY id")
    return [
        PatientRow(int(row[0]), str(row[1]), str(row[2]), row[3], row[4])
        for row in cursor.fetchall()
    ]


def finding_values(item: SourceConsultation, field_name: str) -> list[str]:
    return [
        finding.value
        for finding in sorted(item.findings, key=lambda x: x.source_order)
        if finding.field_name == field_name and finding.value.strip()
    ]


def build_examination(item: SourceConsultation) -> dict[str, Any]:
    heights = finding_values(item, "рост")
    weights = finding_values(item, "вес")
    bmi_values = finding_values(item, "имт")
    bp_values = finding_values(item, "артериальное_давление")
    hr_values = finding_values(item, "частота_сердечных_сокращений")
    systolic, diastolic, bp_note = parse_bp(bp_values)
    pasternatsky_result, pasternatsky_side = parse_pasternatsky(
        finding_values(item, "симптом_пастернацкого")
    )

    height = parse_number_with_unit(heights, "height")
    weight = parse_number_with_unit(weights, "weight")
    bmi = parse_number_with_unit(bmi_values, "bmi")
    if height is not None and not Decimal("50") <= height <= Decimal("250"):
        height = None
    if weight is not None and not Decimal("20") <= weight <= Decimal("300"):
        weight = None
    if bmi is not None and not Decimal("5") <= bmi <= Decimal("100"):
        bmi = None

    return {
        "skin_and_mucous_membranes": multiline_text(finding_values(item, "кожные_покровы")),
        "edema_location": multiline_text(finding_values(item, "отеки")),
        "systolic_pressure": systolic,
        "diastolic_pressure": diastolic,
        "bp_note": bp_note,
        "heart_rate": parse_heart_rate(hr_values),
        "height": height,
        "weight": weight,
        "bmi": bmi,
        "pasternatsky_result": pasternatsky_result,
        "pasternatsky_side": pasternatsky_side,
    }


def build_instrumental_text(item: SourceConsultation) -> str | None:
    lines: list[str] = []
    for study in sorted(item.instrumental, key=lambda x: x.source_order):
        date_text = study.study_date.isoformat() if study.study_date else "дата не указана"
        artificial = " (15-е число установлено искусственно)" if study.day_is_artificial else ""
        note = f"; {study.note}" if study.note else ""
        lines.append(f"{date_text}{artificial} | {study.study_type}: {study.result_text}{note}")
    return multiline_text(lines)


def _insert_returning_id(cursor, table: str, values: Mapping[str, Any]) -> int:
    from psycopg2 import sql

    columns = list(values)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    cursor.execute(query, [values[column] for column in columns])
    return int(cursor.fetchone()[0])


def _insert_row(cursor, table: str, values: Mapping[str, Any]) -> None:
    from psycopg2 import sql

    columns = list(values)
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    cursor.execute(query, [values[column] for column in columns])


def _patient_display(row: PatientRow) -> str:
    return " ".join(x for x in (row.last_name, row.first_name, row.patronymic) if x)


def prepare_context(cursor, consultations: Sequence[SourceConsultation], report: ImportReport):
    doctors = fetch_doctors(cursor)
    source_doctor_names = sorted({item.doctor_name for item in consultations})
    doctor_map: dict[str, DoctorRow] = {}
    doctor_errors: list[str] = []
    for source_name in source_doctor_names:
        try:
            doctor_map[source_name] = match_doctor(source_name, doctors)
        except ImportValidationError as exc:
            doctor_errors.append(str(exc))
    if doctor_errors:
        raise ImportValidationError(
            "Не все врачи сопоставлены. База не изменена:\n" + "\n".join(doctor_errors)
        )
    report.doctor_mapping = {
        source: target.display_name for source, target in doctor_map.items()
    }

    existing_patients: dict[tuple[str, str, str, date], PatientRow] = {}
    duplicates: list[str] = []
    for patient in fetch_patients(cursor):
        key = person_key(
            PersonName(patient.last_name, patient.first_name, patient.patronymic),
            patient.birth_date,
        )
        if key in existing_patients:
            duplicates.append(
                f"{_patient_display(existing_patients[key])} и {_patient_display(patient)}, "
                f"дата рождения {patient.birth_date}"
            )
        existing_patients[key] = patient
    if duplicates:
        raise ImportValidationError(
            "В МИС есть неоднозначные дубли пациентов:\n" + "\n".join(duplicates[:30])
        )

    source_patient_keys: dict[tuple[str, str, str, date], PersonName] = {}
    for item in consultations:
        name = split_person_name(item.patient_name)
        source_patient_keys[person_key(name, item.birth_date)] = name
    report.patients_reused = sum(1 for key in source_patient_keys if key in existing_patients)
    report.patients_to_create = len(source_patient_keys) - report.patients_reused

    keys = [IMPORT_KEY_PREFIX + item.consultation_id for item in consultations]
    cursor.execute(
        "SELECT archive_import_key FROM appointments WHERE archive_import_key = ANY(%s)",
        (keys,),
    )
    existing_import_keys = {str(row[0]) for row in cursor.fetchall()}
    report.consultations_already_present = len(existing_import_keys)
    report.consultations_to_insert = len(consultations) - len(existing_import_keys)
    return doctor_map, existing_patients, existing_import_keys


def run_import(
    connection,
    consultations: Sequence[SourceConsultation],
    report: ImportReport,
    *,
    apply: bool,
) -> None:
    cursor = connection.cursor()
    try:
        report.database_revision = validate_target_schema(cursor)
        numeric_specs = target_numeric_specs(cursor)
        doctor_map, patient_map, existing_import_keys = prepare_context(
            cursor, consultations, report
        )
        if not apply:
            connection.rollback()
            return

        for item in consultations:
            import_key = IMPORT_KEY_PREFIX + item.consultation_id
            if import_key in existing_import_keys:
                continue

            name = split_person_name(item.patient_name)
            key = person_key(name, item.birth_date)
            patient = patient_map.get(key)
            if patient is None:
                patient_id = _insert_returning_id(
                    cursor,
                    "patients",
                    {
                        "last_name": name.last_name,
                        "first_name": name.first_name,
                        "patronymic": name.patronymic,
                        "birth_date": item.birth_date,
                        "gender": None,
                    },
                )
                patient = PatientRow(
                    patient_id, name.last_name, name.first_name, name.patronymic, item.birth_date
                )
                patient_map[key] = patient
                report.patients_created += 1

            age = age_on_date(item.birth_date, item.appointment_date)
            appointment_id = _insert_returning_id(
                cursor,
                "appointments",
                {
                    "patient_id": patient.patient_id,
                    "doctor_id": doctor_map[item.doctor_name].doctor_id,
                    "location_id": None,
                    "appointment_date": datetime.combine(item.appointment_date, time.min),
                    "age_at_appointment": age,
                    "diagnosis_text": item.diagnosis,
                    "diagnosis_comment_text": item.diagnosis_comment,
                    "is_archive_import": True,
                    "archive_import_key": import_key,
                },
            )
            report.appointments_inserted += 1

            heredity = multiline_text(finding_values(item, "наследственность"))
            _insert_row(
                cursor,
                "surveys",
                {
                    "appointment_id": appointment_id,
                    "complaints": item.complaints,
                    "heredity_description": heredity,
                    "disease_anamnesis_text": item.disease_anamnesis,
                    "life_anamnesis_text": item.life_anamnesis,
                },
            )
            report.surveys_inserted += 1

            examination = build_examination(item)
            _insert_row(
                cursor,
                "examinations",
                {"appointment_id": appointment_id, **examination},
            )
            report.examinations_inserted += 1

            _insert_row(
                cursor,
                "appointment_diets",
                {
                    "appointment_id": appointment_id,
                    "recommendations": item.recommendations,
                },
            )
            report.recommendations_inserted += 1

            weight = examination.get("weight")
            lab_payloads, residual_labs, mapped_count = build_lab_payloads(
                item, age=age, weight=weight, numeric_specs=numeric_specs
            )
            report.laboratory_values_mapped += mapped_count
            report.laboratory_values_left_as_other += len(residual_labs)

            for table_name, rows in lab_payloads.items():
                for payload in rows:
                    _insert_row(
                        cursor,
                        table_name,
                        {"appointment_id": appointment_id, **payload},
                    )
                    counter_name = {
                        "cbc_results": "cbc_rows_inserted",
                        "biochemistry_results": "biochemistry_rows_inserted",
                        "urinalysis_results": "urinalysis_rows_inserted",
                        "albuminuria_results": "albuminuria_rows_inserted",
                        "calculated_metrics": "calculated_metrics_rows_inserted",
                    }[table_name]
                    setattr(report, counter_name, getattr(report, counter_name) + 1)

            instrumental_text = build_instrumental_text(item)
            if instrumental_text:
                report.instrumental_studies_imported += len(item.instrumental)
            other_laboratory = multiline_text(residual_labs)
            if other_laboratory or instrumental_text:
                _insert_row(
                    cursor,
                    "appointment_additional_studies",
                    {
                        "appointment_id": appointment_id,
                        "other_laboratory_studies": other_laboratory,
                        "other_instrumental_studies": instrumental_text,
                    },
                )
                report.additional_studies_inserted += 1

        cursor.execute(
            "SELECT COUNT(*) FROM appointments WHERE archive_import_key LIKE %s",
            (IMPORT_KEY_PREFIX + "%",),
        )
        final_count = int(cursor.fetchone()[0])
        if final_count != len(consultations):
            raise ImportValidationError(
                f"После импорта найдено {final_count} архивных приёмов вместо {len(consultations)}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def default_source_path(project_root: Path) -> Path:
    return (
        project_root.parent
        / "nephro_consultation_preparer"
        / "prepared_consultations"
        / "приемы.sqlite"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Импорт 1518 распарсенных консультаций в PostgreSQL МИС"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Путь к приемы.sqlite; по умолчанию берётся соседний проект парсера",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=DEFAULT_EXPECTED_COUNT,
        help="Ожидаемое число чистых приёмов",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать данные. Без флага выполняется только проверка.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("archive_import_report.json"),
        help="Файл отчёта JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path.cwd()
    source = (args.source or default_source_path(project_root)).resolve()
    report = ImportReport(
        mode="ЗАПИСЬ" if args.apply else "ПРОВЕРКА_БЕЗ_ЗАПИСИ",
        source_database=str(source),
    )

    try:
        consultations = load_source(source, args.expected_count)
        report.source_clean_consultations = len(consultations)
        report.source_unique_patients = len(
            {
                person_key(split_person_name(item.patient_name), item.birth_date)
                for item in consultations
            }
        )
        report.source_doctors = dict(
            sorted(Counter(item.doctor_name for item in consultations).items())
        )

        connection = connect_postgresql(project_root)
        try:
            run_import(connection, consultations, report, apply=args.apply)
        finally:
            connection.close()
    except Exception as exc:
        report.warnings.append(str(exc))
        args.report.write_text(
            json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        print(f"Отчёт: {args.report.resolve()}", file=sys.stderr)
        return 1

    args.report.write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print("Проверка завершена." if not args.apply else "Импорт завершён.")
    print(f"Чистых приёмов в источнике: {report.source_clean_consultations}")
    print(f"Уже были в МИС: {report.consultations_already_present}")
    print(f"Нужно добавить: {report.consultations_to_insert}")
    if args.apply:
        print(f"Добавлено приёмов: {report.appointments_inserted}")
        print(f"Создано пациентов: {report.patients_created}")
        print(f"Лабораторных значений в стандартных полях: {report.laboratory_values_mapped}")
        print(f"Лабораторных значений в поле 'Другие': {report.laboratory_values_left_as_other}")
    else:
        print("База данных не изменялась. Для записи добавьте --apply")
    print(f"Отчёт: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
