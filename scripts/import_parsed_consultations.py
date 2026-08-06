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

EXPECTED_REVISION = "0018_archive_source_path"
LEGACY_IMPORT_KEY_PREFIX = "nephro-v110:"
STABLE_IMPORT_KEY_PREFIX = "nephro-archive-v1:"
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
    source_text: str | None = None


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
    source_sha256: str
    source_ordinal: int
    source_relative_path: str
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
    import_keys_to_upgrade: int = 0
    import_keys_upgraded: int = 0
    source_paths_to_backfill: int = 0
    source_paths_backfilled: int = 0
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
    laboratory_values_ignored_as_artifact: int = 0
    laboratory_values_not_loaded: int = 0
    laboratory_units_inferred: int = 0
    egfr_values_mapped: int = 0
    laboratory_appointments_to_repair: int = 0
    laboratory_appointments_repaired: int = 0
    laboratory_rows_to_delete: int = 0
    laboratory_rows_deleted: int = 0
    laboratory_rows_to_insert: int = 0
    instrumental_studies_imported: int = 0
    instrumental_appointments_cleaned: int = 0
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


@dataclass
class LabBuildStats:
    ignored_as_artifact: int = 0
    inferred_units: int = 0
    egfr_mapped: int = 0
    not_loaded: int = 0
    issues: list[str] = field(default_factory=list)


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
    ("МАУ", "Микроальбуминурия"): LabRule("albuminuria_results", "urine_albumin", ("мг/л", "г/л"), True, "albumin_unit"),
    ("МАУ", "Креатинин мочи"): LabRule("albuminuria_results", "urine_creatinine", ("ммоль/л", "мкмоль/л"), False, "urine_creatinine_unit"),
    ("МАУ", "Альбумин-креатининовое соотношение"): LabRule("albuminuria_results", "albumin_creatinine_ratio", ("мг/ммоль",), True),
    ("Расчет", "рСКФ CKD-EPI"): LabRule("calculated_metrics", "egfr_ckdepi", ("мл/мин/1.73м2", "мл/мин")),
}

# Единицы, подтверждённые по форме МИС. Они подставляются только тогда,
# когда в исходном заключении единица отсутствует. Явно указанная другая
# единица никогда не заменяется молча.
DEFAULT_UNITS: dict[tuple[str, str], str] = {
    ("Биохимия", "Креатинин"): "мкмоль/л",
    ("Биохимия", "Мочевина"): "ммоль/л",
    ("Биохимия", "Мочевая кислота"): "мкмоль/л",
    ("Биохимия", "Глюкоза крови"): "ммоль/л",
    ("Биохимия", "Общий белок"): "г/л",
    ("Биохимия", "Альбумин"): "г/л",
    ("Биохимия", "Калий"): "ммоль/л",
    ("Биохимия", "Кальций"): "ммоль/л",
    ("Биохимия", "Фосфор"): "ммоль/л",
    ("ОАК", "Гемоглобин"): "г/л",
    ("ОАК", "СОЭ"): "мм/ч",
    ("ОАК", "MCV"): "фл",
    ("ОАМ", "Белок"): "г/л",
    ("МАУ", "Микроальбуминурия"): "мг/л",
    ("МАУ", "Альбумин-креатининовое соотношение"): "мг/ммоль",
    ("Расчет", "рСКФ CKD-EPI"): "мл/мин/1.73м2",
}

# Нормализация вариантов, реально найденных в архивной выгрузке.
URINALYSIS_LEUKOCYTE_ALIASES = {
    "le", "wbc", "л", "лей", "лейк", "лейкоцит", "лейкоциты",
    "лейкоцитывпзр", "лейкоцитывполезрения",
}

URINALYSIS_ERYTHROCYTE_ALIASES = {
    "er", "rbc", "эр", "эрит", "эритр", "эритроцит", "эритроциты",
    "эритроцитывпзр", "эритроцитывполезрения",
}


BIOCHEMISTRY_ALIASES: dict[str, str] = {
    "креат": "Креатинин",
    "контролькреатинина": "Креатинин",
    "глюк": "Глюкоза крови",
    "альб": "Альбумин",
    "альбуин": "Альбумин",
    "альбумиин": "Альбумин",
    "мочевая": "Мочевая кислота",
    "мочкта": "Мочевая кислота",
    "мочкисл": "Мочевая кислота",
    "мочкислота": "Мочевая кислота",
    "наприемекалий": "Калий",
    "наприемеk": "Калий",
    "калийммольл": "Калий",
    "кальцийобщ": "Кальций",
    "сакоррект": "Кальций",
    "сакрви": "Кальций",
    "сакрови": "Кальций",
    "саммольл": "Кальций",
    "ферр": "Ферритин",
    "сословферритин": "Ферритин",
}

APPROVED_RESIDUAL_UNITS: dict[tuple[str, str], str] = {
    ("биохимия", "кальцийионизированный"): "ммоль/л",
    ("биохимия", "аионниз"): "ммоль/л",
    ("биохимия", "кальцийиониз"): "ммоль/л",
    ("биохимия", "ттгмкмемлnдо"): "мкМЕ/мл",
}

LAB_TABLES = (
    "cbc_results",
    "biochemistry_results",
    "urinalysis_results",
    "albuminuria_results",
    "calculated_metrics",
)


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
        "is_archive_import", "archive_import_key", "archive_source_relative_path",
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


def stable_import_key(item: SourceConsultation) -> str:
    """Устойчивый ключ: контрольная сумма исходного файла + номер приёма в нём."""
    sha256 = item.source_sha256.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ImportValidationError(
            f"Некорректная SHA-256 исходного файла для {item.consultation_id}: {item.source_sha256!r}"
        )
    if item.source_ordinal < 1:
        raise ImportValidationError(
            f"Некорректный номер консультации в файле для {item.consultation_id}: "
            f"{item.source_ordinal}"
        )
    return f"{STABLE_IMPORT_KEY_PREFIX}{sha256}:{item.source_ordinal}"


def legacy_import_key(item: SourceConsultation) -> str:
    """Ключ, которым была загружена первая партия из старого импортёра."""
    return LEGACY_IMPORT_KEY_PREFIX + item.consultation_id


def classify_existing_import_keys(
    consultations: Sequence[SourceConsultation],
    existing_key_to_appointment_id: Mapping[str, int],
) -> tuple[set[str], dict[str, str]]:
    """Находит уже загруженные приёмы и старые ключи, которые надо обновить."""
    already_present: set[str] = set()
    upgrades: dict[str, str] = {}
    conflicts: list[str] = []

    for item in consultations:
        stable_key = stable_import_key(item)
        legacy_key = legacy_import_key(item)
        stable_id = existing_key_to_appointment_id.get(stable_key)
        legacy_id = existing_key_to_appointment_id.get(legacy_key)

        if stable_id is not None and legacy_id is not None and stable_id != legacy_id:
            conflicts.append(
                f"{item.consultation_id}: устойчивый и старый ключи принадлежат "
                f"разным приёмам МИС ({stable_id} и {legacy_id})"
            )
            continue
        if stable_id is not None:
            already_present.add(stable_key)
            continue
        if legacy_id is not None:
            already_present.add(stable_key)
            upgrades[legacy_key] = stable_key

    if conflicts:
        raise ImportValidationError(
            "Обнаружены конфликтующие ключи архивного импорта:\n"
            + "\n".join(conflicts[:30])
        )
    return already_present, upgrades




def normalize_source_relative_path(value: Any) -> str:
    """Нормализует относительный путь из SQLite и запрещает выход из корня архива."""
    text = str(value or "").strip().replace("\\", "/")
    text = re.sub(r"/+", "/", text)
    if not text:
        raise ImportValidationError("Не указан относительный путь исходного документа")
    if re.match(r"^[A-Za-z]:", text) or text.startswith("/"):
        raise ImportValidationError(
            f"Путь исходного документа должен быть относительным: {value!r}"
        )
    parts = [part for part in text.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ImportValidationError(
            f"Недопустимый относительный путь исходного документа: {value!r}"
        )
    return "/".join(parts)

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


def canonical_lab_key(lab: LaboratoryFinding) -> tuple[str, str]:
    """Возвращает каноническое исследование и показатель для полей МИС."""
    study = clean_text(lab.study_type) or ""
    indicator = clean_text(lab.indicator_normalized) or clean_text(lab.indicator_raw) or ""
    study_key = normalize_word(study)
    indicator_key = normalize_word(indicator)
    raw_key = normalize_word(lab.indicator_raw)
    combined = f"{indicator_key}{raw_key}"

    if "скф" in combined or "egfr" in combined or "ckdepi" in combined:
        return "Расчет", "рСКФ CKD-EPI"
    if "птг" in combined or "паратгормон" in combined:
        return "ПТГ", "Паратгормон"
    if study_key in {"оам", "общийанализмочи"}:
        urine_key = indicator_key or raw_key
        if (
            urine_key in URINALYSIS_LEUKOCYTE_ALIASES
            or (urine_key.startswith("лейкоцит") and "эстераз" not in urine_key)
        ):
            return "ОАМ", "Лейкоциты"
        if (
            urine_key in URINALYSIS_ERYTHROCYTE_ALIASES
            or urine_key.startswith("эритроцит")
        ):
            return "ОАМ", "Эритроциты"
    if study_key == "биохимия":
        if indicator_key == "мау":
            return "МАУ", "Микроальбуминурия"
        alias = BIOCHEMISTRY_ALIASES.get(indicator_key)
        if alias:
            return "Биохимия", alias
    return study, indicator


def _looks_like_calendar_value(value: str | None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if re.fullmatch(r"(?:19|20)\d{2}-\d{1,2}-\d{1,2}", text):
        return True
    if re.fullmatch(r"\d{1,2}[./-]\d{1,2}[./-](?:19|20)?\d{2}", text):
        return True
    if re.fullmatch(r"\d{1,2}[./-](?:19|20)\d{2}", text):
        return True
    return False


def is_obvious_lab_artifact(
    lab: LaboratoryFinding,
    canonical_key: tuple[str, str],
    numeric: Decimal | None,
) -> bool:
    """Отсекает даты, заголовки и явные обрывки текста, а не результаты."""
    raw_value = lab.numeric_value or lab.text_value
    if _looks_like_calendar_value(raw_value):
        return True

    indicator_text = clean_text(lab.indicator_normalized) or clean_text(lab.indicator_raw) or ""
    indicator_key = normalize_word(indicator_text)
    canonical_known = canonical_key in LAB_RULES

    if numeric is not None and Decimal("30000") <= numeric <= Decimal("60000"):
        return True  # серийное число даты Excel
    if canonical_key == ("Расчет", "рСКФ CKD-EPI") and numeric is not None:
        if numeric <= 0 or numeric > Decimal("500"):
            return True

    if canonical_known:
        return False

    if indicator_key in {
        "биохимия", "общийрезультатоам", "осадок", "действителенвтечение",
    }:
        return True
    suspicious_words = (
        "действителен", "вконцемарта", "контрольчерез", "гормоныщжнорма",
        "дата", "анализкрови", "биохимическийанализ",
    )
    if any(word in indicator_key for word in suspicious_words):
        return True
    if numeric is not None and Decimal("1900") <= numeric <= Decimal("2100"):
        return True
    if len(indicator_text) > 80:
        return True
    return False


def approved_residual_unit(lab: LaboratoryFinding) -> str:
    study_key = normalize_word(lab.study_type)
    indicator_key = normalize_word(lab.indicator_normalized or lab.indicator_raw)
    return APPROVED_RESIDUAL_UNITS.get((study_key, indicator_key), "")


def resolved_lab_unit(
    lab: LaboratoryFinding,
    canonical_key: tuple[str, str],
) -> tuple[str, bool]:
    explicit = normalize_unit(lab.unit)
    if explicit:
        return explicit, False
    default = DEFAULT_UNITS.get(canonical_key)
    if default:
        return normalize_unit(default), True
    return "", False


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


def _source_value(lab: LaboratoryFinding, display_unit: str | None = None) -> str:
    value = lab.numeric_value if lab.numeric_value is not None else lab.text_value
    value = value or "не указано"
    shown_unit = display_unit if display_unit is not None else lab.unit
    unit = f" {shown_unit}" if shown_unit else ""
    date_text = lab.analysis_date.isoformat() if lab.analysis_date else "дата не указана"
    artificial = " (15-е число установлено искусственно)" if lab.day_is_artificial else ""
    note = f"; {lab.note}" if lab.note else ""
    return (
        f"{date_text}{artificial} | {lab.study_type} | "
        f"{lab.indicator_normalized}: {value}{unit}{note}"
    )


TECHNICAL_TEXT_PATTERNS = (
    r"\(?\s*15[- ]?е\s+число\s+установлено\s+искусственно\s*\)?",
    r"\bдень\s+15\s+установлен(?:о)?\s+искусственно\b",
    r"\[\s*единица\s+принята\s+по\s+форме\s+МИС\s*\]",
    r"\[\s*загружено\s+как[^\]]*\]",
    r"\[\s*пересчитано[^\]]*\]",
    r"\[\s*не\s+загружено:[^\]]*\]",
)


def clean_technical_text(value: str | None) -> str:
    """Удаляет только служебные пометки парсера, не меняя медицинский текст."""
    text = clean_text(value) or ""
    for pattern in TECHNICAL_TEXT_PATTERNS:
        text = re.sub(pattern, " ", text, flags=re.I)
    text = re.sub(r"\s*;\s*;\s*", "; ", text)
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip(" ;,|")
    return text


def display_study_date(
    value: date | None,
    *,
    date_precision: str = "",
    day_is_artificial: bool = False,
) -> str:
    """Показывает точную дату, а для искусственного дня — только месяц и год."""
    if value is None:
        return "дата не указана"
    precision = normalize_word(date_precision)
    if day_is_artificial or precision in {"месяц", "month", "месяцгод"}:
        return value.strftime("%m.%Y")
    return value.strftime("%d.%m.%Y")


def _clean_lab_note(note: str | None, value: str) -> tuple[str, str]:
    """Сохраняет клиническую пометку, но переводит знак сравнения к значению."""
    text = clean_technical_text(note)
    sign = ""
    if re.search(r"со\s+знаком\s*>|значение\s+указано\s+со\s+знаком\s*>", text, re.I):
        sign = ">"
        text = re.sub(
            r"(?:значение\s+указано\s+)?со\s+знаком\s*>", " ", text, flags=re.I
        )
    elif re.search(r"со\s+знаком\s*<|значение\s+указано\s+со\s+знаком\s*<", text, re.I):
        sign = "<"
        text = re.sub(
            r"(?:значение\s+указано\s+)?со\s+знаком\s*<", " ", text, flags=re.I
        )
    text = re.sub(r"\s*;\s*", "; ", text).strip(" ;,")
    if sign and not value.lstrip().startswith((">", "<")):
        value = sign + value
    return value, text


def residual_lab_parameter(lab: LaboratoryFinding, display_unit: str = "") -> str:
    indicator = (
        clean_text(lab.indicator_normalized)
        or clean_text(lab.indicator_raw)
        or "Показатель"
    )
    value = clean_text(lab.numeric_value) or clean_text(lab.text_value) or "не указано"
    value, note = _clean_lab_note(lab.note, value)
    unit = clean_text(display_unit or lab.unit) or ""
    parts = [f"{indicator}: {value}{(' ' + unit) if unit else ''}"]
    if note:
        parts.append(note)
    return "; ".join(parts)


def format_residual_laboratory(
    items: Sequence[tuple[LaboratoryFinding, str]],
) -> list[str]:
    """Группирует только неподдерживаемые показатели по дате и типу анализа."""
    groups: dict[tuple[str, str], list[str]] = {}
    order: list[tuple[str, str]] = []
    for lab, display_unit in items:
        date_text = display_study_date(
            lab.analysis_date,
            date_precision=lab.date_precision,
            day_is_artificial=lab.day_is_artificial,
        )
        study_type = clean_text(lab.study_type) or "Другие исследования"
        key = (date_text, study_type)
        if key not in groups:
            groups[key] = []
            order.append(key)
        parameter = residual_lab_parameter(lab, display_unit)
        if parameter and parameter not in groups[key]:
            groups[key].append(parameter)
    return [
        f"{date_text}, {study_type}: {'; '.join(groups[(date_text, study_type)])}"
        for date_text, study_type in order
        if groups[(date_text, study_type)]
    ]


def record_lab_issue(stats: LabBuildStats, lab: LaboratoryFinding, reason: str) -> None:
    stats.not_loaded += 1
    if len(stats.issues) < 100:
        stats.issues.append(f"{_source_value(lab)} [{reason}]")


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
    stats: LabBuildStats | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], list[str], int]:
    """Преобразует распарсенные показатели в строки таблиц МИС.

    В свободное поле попадают только показатели, для которых в МИС нет
    отдельной колонки. Служебные пометки парсера туда не записываются.
    """
    grouped: dict[tuple[str, date | None], dict[str, Any]] = {}
    residual_items: list[tuple[LaboratoryFinding, str]] = []
    mapped = 0
    stats = stats or LabBuildStats()

    for lab in sorted(consultation.laboratory, key=lambda x: x.source_order):
        canonical_key = canonical_lab_key(lab)
        rule = LAB_RULES.get(canonical_key)
        numeric = decimal_value(lab.numeric_value)

        if is_obvious_lab_artifact(lab, canonical_key, numeric):
            stats.ignored_as_artifact += 1
            continue

        unit, inferred_unit = resolved_lab_unit(lab, canonical_key)
        if inferred_unit:
            stats.inferred_units += 1

        if rule is None:
            residual_unit = approved_residual_unit(lab)
            if residual_unit and not lab.unit:
                stats.inferred_units += 1
            residual_items.append((lab, residual_unit))
            continue

        if rule.transform == "text":
            text_result = clean_technical_text(lab.text_value) or clean_technical_text(lab.numeric_value)
            if not text_result:
                record_lab_issue(stats, lab, "пустое значение стандартного показателя")
                continue
            key = (rule.table, lab.analysis_date)
            if TABLE_DATE_REQUIRED[rule.table] and lab.analysis_date is None:
                record_lab_issue(stats, lab, "нет даты для стандартной таблицы МИС")
                continue
            payload = grouped.setdefault(key, {"investigation_date": lab.analysis_date})
            if rule.column in payload and payload[rule.column] != text_result:
                record_lab_issue(stats, lab, "повторное отличающееся значение")
                continue
            payload[rule.column] = text_result[:100]
            mapped += 1
            continue

        if numeric is None:
            record_lab_issue(stats, lab, "значение стандартного показателя не является числом")
            continue
        if TABLE_DATE_REQUIRED[rule.table] and lab.analysis_date is None:
            record_lab_issue(stats, lab, "нет даты для стандартной таблицы МИС")
            continue
        if not _unit_allowed(unit, rule):
            record_lab_issue(stats, lab, "единица не соответствует стандартному полю МИС")
            continue
        if numeric < 0:
            record_lab_issue(stats, lab, "отрицательное числовое значение")
            continue

        numeric, extras = _transform_lab_value(numeric, unit, rule)
        spec = (numeric_specs or {}).get((rule.table, rule.column))
        if spec is not None and not numeric_value_fits(numeric, spec):
            record_lab_issue(
                stats,
                lab,
                f"значение {numeric} не помещается в {rule.table}.{rule.column} "
                f"NUMERIC({spec.precision},{spec.scale})",
            )
            continue

        key = (rule.table, lab.analysis_date)
        payload = grouped.setdefault(key, {"investigation_date": lab.analysis_date})
        if rule.column in payload:
            if payload[rule.column] == numeric:
                continue
            record_lab_issue(stats, lab, "повторное отличающееся значение")
            continue
        payload[rule.column] = numeric
        payload.update(extras)
        mapped += 1
        if canonical_key == ("Расчет", "рСКФ CKD-EPI"):
            stats.egfr_mapped += 1

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
    residual = format_residual_laboratory(residual_items)
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


def load_source(path: Path, expected_count: int | None = None) -> list[SourceConsultation]:
    if not path.is_file():
        raise ImportValidationError(f"Не найден файл SQLite: {path}")

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        _require_sqlite_columns(
            connection,
            "source_documents",
            {"document_id", "relative_path", "sha256"},
        )
        _require_sqlite_columns(
            connection,
            "consultations",
            {
                "consultation_id", "document_id", "ordinal", "resolved_name",
                "birth_date", "appointment_date", "doctor_name", "status",
                "complaints", "history_of_present_illness", "history_of_life",
                "diagnosis", "comments", "recommendations",
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
                "text_value", "unit", "source_order", "note", "source_text",
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
            SELECT c.consultation_id, c.document_id, c.ordinal, d.sha256, d.relative_path,
                   c.resolved_name, c.birth_date, c.appointment_date,
                   c.doctor_name, c.complaints, c.history_of_present_illness,
                   c.history_of_life, c.diagnosis, c.comments, c.recommendations
            FROM consultations AS c
            JOIN source_documents AS d ON d.document_id = c.document_id
            WHERE c.status = ?
            ORDER BY c.appointment_date, c.consultation_id
            """,
            (CLEAN_STATUS,),
        ).fetchall()
        if expected_count is not None and len(rows) != expected_count:
            raise ImportValidationError(
                f"Ожидалось {expected_count} чистых приёмов, найдено {len(rows)}. "
                "Импорт остановлен, потому что задана контрольная численность."
            )
        if not rows:
            raise ImportValidationError("В источнике нет чистых приёмов для импорта")

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
                    source_sha256=str(row["sha256"]),
                    source_ordinal=int(row["ordinal"]),
                    source_relative_path=normalize_source_relative_path(row["relative_path"]),
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
                   text_value, unit, source_order, note, source_text
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
                    source_text=clean_text(row["source_text"]),
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

        result = list(consultations.values())
        stable_keys: dict[str, str] = {}
        duplicate_keys: list[str] = []
        for item in result:
            key = stable_import_key(item)
            previous = stable_keys.get(key)
            if previous is not None and previous != item.consultation_id:
                duplicate_keys.append(
                    f"{previous} и {item.consultation_id}: {key}"
                )
            stable_keys[key] = item.consultation_id
        if duplicate_keys:
            raise ImportValidationError(
                "В источнике повторяются одинаковые файлы и номера консультаций:\n"
                + "\n".join(duplicate_keys[:30])
            )
        return result
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
            "Схема МИС не готова к импорту. Проверьте миграцию 0018:\n" + "\n".join(errors)
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
    """Собирает исходные инструментальные исследования без служебных пометок."""
    lines: list[str] = []
    for study in sorted(item.instrumental, key=lambda x: x.source_order):
        result_text = clean_technical_text(study.result_text)
        note = clean_technical_text(study.note)
        if not result_text and not note:
            continue
        date_text = display_study_date(
            study.study_date,
            date_precision=study.date_precision,
            day_is_artificial=study.day_is_artificial,
        )
        study_type = clean_text(study.study_type) or "Инструментальное исследование"
        details = result_text
        if note and note not in details:
            details = f"{details}; {note}" if details else note
        line = f"{date_text}, {study_type}: {details}"
        if line not in lines:
            lines.append(line)
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

    stable_keys = [stable_import_key(item) for item in consultations]
    legacy_keys = [legacy_import_key(item) for item in consultations]
    keys = list(dict.fromkeys([*stable_keys, *legacy_keys]))
    cursor.execute(
        "SELECT id, archive_import_key, archive_source_relative_path FROM appointments "
        "WHERE archive_import_key = ANY(%s)",
        (keys,),
    )
    existing_rows = cursor.fetchall()
    existing_key_to_id = {str(row[1]): int(row[0]) for row in existing_rows}
    existing_path_by_id = {int(row[0]): row[2] for row in existing_rows}
    existing_import_keys, key_upgrades = classify_existing_import_keys(
        consultations, existing_key_to_id
    )
    source_path_updates: dict[int, str] = {}
    for item in consultations:
        appointment_id = (
            existing_key_to_id.get(stable_import_key(item))
            or existing_key_to_id.get(legacy_import_key(item))
        )
        if appointment_id is None:
            continue
        source_path = normalize_source_relative_path(item.source_relative_path)
        current_path = existing_path_by_id.get(appointment_id)
        if current_path != source_path:
            source_path_updates[appointment_id] = source_path
    report.consultations_already_present = len(existing_import_keys)
    report.consultations_to_insert = len(consultations) - len(existing_import_keys)
    report.import_keys_to_upgrade = len(key_upgrades)
    report.source_paths_to_backfill = len(source_path_updates)
    return (
        doctor_map, existing_patients, existing_import_keys, key_upgrades,
        source_path_updates,
    )


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
        (
            doctor_map, patient_map, existing_import_keys, key_upgrades,
            source_path_updates,
        ) = prepare_context(cursor, consultations, report)
        if not apply:
            connection.rollback()
            return

        for legacy_key, stable_key in key_upgrades.items():
            cursor.execute(
                "UPDATE appointments SET archive_import_key = %s "
                "WHERE archive_import_key = %s",
                (stable_key, legacy_key),
            )
            if cursor.rowcount != 1:
                raise ImportValidationError(
                    f"Не удалось обновить старый ключ импорта {legacy_key}"
                )
            report.import_keys_upgraded += 1

        for appointment_id, source_path in source_path_updates.items():
            cursor.execute(
                "UPDATE appointments SET archive_source_relative_path = %s WHERE id = %s",
                (source_path, appointment_id),
            )
            if cursor.rowcount != 1:
                raise ImportValidationError(
                    f"Не удалось сохранить путь исходного документа для приёма {appointment_id}"
                )
            report.source_paths_backfilled += 1

        for item in consultations:
            import_key = stable_import_key(item)
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
                    "archive_source_relative_path": normalize_source_relative_path(
                        item.source_relative_path
                    ),
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
            lab_stats = LabBuildStats()
            lab_payloads, residual_labs, mapped_count = build_lab_payloads(
                item, age=age, weight=weight, numeric_specs=numeric_specs, stats=lab_stats
            )
            report.laboratory_values_mapped += mapped_count
            report.laboratory_values_left_as_other += len(residual_labs)
            report.laboratory_values_ignored_as_artifact += lab_stats.ignored_as_artifact
            report.laboratory_values_not_loaded += lab_stats.not_loaded
            report.laboratory_units_inferred += lab_stats.inferred_units
            report.egfr_values_mapped += lab_stats.egfr_mapped
            if lab_stats.issues:
                free_slots = max(0, 100 - len(report.warnings))
                report.warnings.extend(lab_stats.issues[:free_slots])

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

        current_source_keys = [stable_import_key(item) for item in consultations]
        cursor.execute(
            "SELECT COUNT(*) FROM appointments WHERE archive_import_key = ANY(%s)",
            (current_source_keys,),
        )
        final_count = int(cursor.fetchone()[0])
        if final_count != len(current_source_keys):
            raise ImportValidationError(
                f"После импорта для текущего источника найдено {final_count} приёмов "
                f"вместо {len(current_source_keys)}"
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def source_appointment_ids(
    cursor,
    consultations: Sequence[SourceConsultation],
) -> dict[str, int]:
    """Сопоставляет консультации источника с уже импортированными приёмами."""
    stable_keys = [stable_import_key(item) for item in consultations]
    legacy_keys = [legacy_import_key(item) for item in consultations]
    all_keys = list(dict.fromkeys([*stable_keys, *legacy_keys]))
    cursor.execute(
        "SELECT id, archive_import_key FROM appointments "
        "WHERE is_archive_import IS TRUE AND archive_import_key = ANY(%s)",
        (all_keys,),
    )
    existing = {str(key): int(appointment_id) for appointment_id, key in cursor.fetchall()}

    result: dict[str, int] = {}
    missing: list[str] = []
    conflicts: list[str] = []
    for item in consultations:
        stable_key = stable_import_key(item)
        stable_id = existing.get(stable_key)
        legacy_id = existing.get(legacy_import_key(item))
        if stable_id is not None and legacy_id is not None and stable_id != legacy_id:
            conflicts.append(item.consultation_id)
            continue
        appointment_id = stable_id or legacy_id
        if appointment_id is None:
            missing.append(item.consultation_id)
            continue
        result[stable_key] = appointment_id

    if conflicts:
        raise ImportValidationError(
            "Для части консультаций устойчивый и старый ключи принадлежат разным приёмам: "
            + ", ".join(conflicts[:20])
        )
    if missing:
        raise ImportValidationError(
            "Исправление лаборатории возможно только для уже импортированных приёмов. "
            "Не найдены в МИС: " + ", ".join(missing[:20])
        )
    return result


def _count_lab_rows(cursor, appointment_ids: Sequence[int]) -> int:
    total = 0
    for table_name in LAB_TABLES:
        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE appointment_id = ANY(%s)",
            (list(appointment_ids),),
        )
        total += int(cursor.fetchone()[0])
    return total


def _delete_lab_rows(cursor, appointment_ids: Sequence[int]) -> int:
    from psycopg2 import sql

    deleted = 0
    for table_name in LAB_TABLES:
        query = sql.SQL("DELETE FROM {} WHERE appointment_id = ANY(%s)").format(
            sql.Identifier(table_name)
        )
        cursor.execute(query, (list(appointment_ids),))
        deleted += max(cursor.rowcount, 0)
    return deleted


def run_laboratory_repair(
    connection,
    consultations: Sequence[SourceConsultation],
    report: ImportReport,
    *,
    apply: bool,
) -> None:
    """Пересобирает лабораторные таблицы и очищает свободные поля исследований.

    Пациенты, приёмы, анамнезы, осмотр, диагноз и рекомендации не изменяются.
    Инструментальные исследования не разбираются на поля: из их текста только
    удаляются служебные пометки парсера.
    """
    cursor = connection.cursor()
    try:
        report.database_revision = validate_target_schema(cursor)
        numeric_specs = target_numeric_specs(cursor)
        appointment_by_key = source_appointment_ids(cursor, consultations)
        appointment_ids = list(appointment_by_key.values())
        report.laboratory_appointments_to_repair = len(appointment_ids)
        report.laboratory_rows_to_delete = _count_lab_rows(cursor, appointment_ids)

        cursor.execute(
            "SELECT appointment_id, weight FROM examinations WHERE appointment_id = ANY(%s)",
            (appointment_ids,),
        )
        weight_by_appointment = {
            int(appointment_id): weight for appointment_id, weight in cursor.fetchall()
        }

        plans: list[tuple[int, dict[str, list[dict[str, Any]]], list[str], str | None]] = []
        for item in consultations:
            appointment_id = appointment_by_key[stable_import_key(item)]
            stats = LabBuildStats()
            payloads, residual, mapped = build_lab_payloads(
                item,
                age=age_on_date(item.birth_date, item.appointment_date),
                weight=weight_by_appointment.get(appointment_id),
                numeric_specs=numeric_specs,
                stats=stats,
            )
            instrumental_text = build_instrumental_text(item)
            plans.append((appointment_id, payloads, residual, instrumental_text))
            report.laboratory_values_mapped += mapped
            report.laboratory_values_left_as_other += len(residual)
            report.laboratory_values_ignored_as_artifact += stats.ignored_as_artifact
            report.laboratory_values_not_loaded += stats.not_loaded
            report.laboratory_units_inferred += stats.inferred_units
            report.egfr_values_mapped += stats.egfr_mapped
            report.laboratory_rows_to_insert += sum(len(rows) for rows in payloads.values())
            if stats.issues:
                free_slots = max(0, 100 - len(report.warnings))
                report.warnings.extend(stats.issues[:free_slots])

        if not apply:
            connection.rollback()
            return

        report.laboratory_rows_deleted = _delete_lab_rows(cursor, appointment_ids)
        counter_by_table = {
            "cbc_results": "cbc_rows_inserted",
            "biochemistry_results": "biochemistry_rows_inserted",
            "urinalysis_results": "urinalysis_rows_inserted",
            "albuminuria_results": "albuminuria_rows_inserted",
            "calculated_metrics": "calculated_metrics_rows_inserted",
        }

        for appointment_id, payloads, residual, instrumental_text in plans:
            for table_name, rows in payloads.items():
                for payload in rows:
                    _insert_row(
                        cursor,
                        table_name,
                        {"appointment_id": appointment_id, **payload},
                    )
                    counter_name = counter_by_table[table_name]
                    setattr(report, counter_name, getattr(report, counter_name) + 1)

            other_laboratory = multiline_text(residual)
            cursor.execute(
                "UPDATE appointment_additional_studies "
                "SET other_laboratory_studies = %s, other_instrumental_studies = %s "
                "WHERE appointment_id = %s",
                (other_laboratory, instrumental_text, appointment_id),
            )
            if cursor.rowcount > 1:
                raise ImportValidationError(
                    f"У приёма {appointment_id} найдено несколько строк дополнительных исследований"
                )
            if cursor.rowcount == 0 and (other_laboratory or instrumental_text):
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
            report.laboratory_appointments_repaired += 1
            report.instrumental_appointments_cleaned += 1

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()


def resolve_source_path(path: Path) -> Path:
    """Принимает либо сам приемы.sqlite, либо папку, где он находится."""
    candidate = path.expanduser()
    if candidate.is_dir():
        candidate = candidate / "приемы.sqlite"
    return candidate.resolve()


def default_source_path(project_root: Path) -> Path:
    return (
        project_root.parent
        / "nephro_consultation_preparer"
        / "prepared_consultations"
        / "приемы.sqlite"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Импорт любого количества распарсенных консультаций в PostgreSQL МИС"
    )
    parser.add_argument(
        "--source",
        type=Path,
        help="Путь к приемы.sqlite или к папке с ним; по умолчанию берётся соседний проект парсера",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=None,
        help="Необязательная контрольная численность чистых приёмов",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать данные. Без флага выполняется только проверка.",
    )
    parser.add_argument(
        "--repair-labs",
        action="store_true",
        help=(
            "Пересобрать лабораторные таблицы и очистить свободные поля "
            "лабораторных и инструментальных исследований уже импортированных "
            "архивных приёмов. Без --apply показывает план и не изменяет базу."
        ),
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
    source = resolve_source_path(args.source or default_source_path(project_root))
    if args.repair_labs:
        mode = "ИСПРАВЛЕНИЕ_ИССЛЕДОВАНИЙ" if args.apply else "ПРОВЕРКА_ИССЛЕДОВАНИЙ"
    else:
        mode = "ЗАПИСЬ" if args.apply else "ПРОВЕРКА_БЕЗ_ЗАПИСИ"
    report = ImportReport(mode=mode, source_database=str(source))

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
            if args.repair_labs:
                run_laboratory_repair(connection, consultations, report, apply=args.apply)
            else:
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
    if args.repair_labs:
        print(
            "Проверка исследований завершена."
            if not args.apply
            else "Лаборатория и свободные поля исследований исправлены."
        )
        print(f"Архивных приёмов для исправления: {report.laboratory_appointments_to_repair}")
        print(f"Существующих лабораторных строк будет удалено: {report.laboratory_rows_to_delete}")
        print(f"Новых лабораторных строк будет создано: {report.laboratory_rows_to_insert}")
        print(f"Показателей в стандартных полях: {report.laboratory_values_mapped}")
        print(f"Единиц принято по форме МИС: {report.laboratory_units_inferred}")
        print(f"Значений СКФ перенесено в CKD-EPI: {report.egfr_values_mapped}")
        print(f"Дат и посторонних фрагментов отброшено: {report.laboratory_values_ignored_as_artifact}")
        print(f"Стандартных показателей не загружено из-за формата: {report.laboratory_values_not_loaded}")
        print(f"Непредусмотренных показателей осталось в поле 'Другие': {report.laboratory_values_left_as_other}")
        if args.apply:
            print(f"Исправлено приёмов: {report.laboratory_appointments_repaired}")
            print(f"Очищено полей инструментальных исследований: {report.instrumental_appointments_cleaned}")
            print(f"Удалено старых лабораторных строк: {report.laboratory_rows_deleted}")
        else:
            print("База данных не изменялась. Для исправления добавьте --apply")
    else:
        print("Проверка завершена." if not args.apply else "Импорт завершён.")
        print(f"Чистых приёмов в источнике: {report.source_clean_consultations}")
        print(f"Уже были в МИС: {report.consultations_already_present}")
        print(f"Нужно добавить: {report.consultations_to_insert}")
        print(f"Пути исходных документов нужно заполнить: {report.source_paths_to_backfill}")
        if report.import_keys_to_upgrade:
            print(f"Старых ключей импорта нужно обновить: {report.import_keys_to_upgrade}")
        if args.apply:
            print(f"Добавлено приёмов: {report.appointments_inserted}")
            print(f"Пути исходных документов заполнены: {report.source_paths_backfilled}")
            if report.import_keys_upgraded:
                print(f"Обновлено старых ключей импорта: {report.import_keys_upgraded}")
            print(f"Создано пациентов: {report.patients_created}")
            print(f"Лабораторных значений в стандартных полях: {report.laboratory_values_mapped}")
            print(f"Лабораторных значений в поле 'Другие': {report.laboratory_values_left_as_other}")
            print(f"Единиц принято по форме МИС: {report.laboratory_units_inferred}")
            print(f"Значений СКФ перенесено в CKD-EPI: {report.egfr_values_mapped}")
            print(f"Дат и посторонних фрагментов отброшено: {report.laboratory_values_ignored_as_artifact}")
            print(f"Стандартных показателей не загружено из-за формата: {report.laboratory_values_not_loaded}")
        else:
            print("База данных не изменялась. Для записи добавьте --apply")
    print(f"Отчёт: {args.report.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
