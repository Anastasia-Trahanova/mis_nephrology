from __future__ import annotations

import importlib.util
import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "import_parsed_consultations.py"
SPEC = importlib.util.spec_from_file_location("archive_import", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_split_person_name_with_initials():
    parsed = MODULE.split_person_name("Белокопытов А.Д.")
    assert parsed.last_name == "Белокопытов"
    assert parsed.first_name == "А."
    assert parsed.patronymic == "Д."


def test_doctor_alias_and_initials_match():
    doctors = [MODULE.DoctorRow(7, "Возова", "Анна", "Михайловна")]
    matched = MODULE.match_doctor("Врач-нефролог: Возва А.М.", doctors)
    assert matched.doctor_id == 7


def test_bp_keeps_source_note_and_parses_numbers():
    systolic, diastolic, note = MODULE.parse_bp(["120/70 мм рт.ст."])
    assert (systolic, diastolic) == (120, 70)
    assert note == "120/70 мм рт.ст."


def test_specific_gravity_is_normalized_for_mis_column():
    consultation = MODULE.SourceConsultation(
        consultation_id="C1",
        patient_name="Иванова Анна Ивановна",
        birth_date=date(1980, 1, 1),
        appointment_date=date(2024, 1, 1),
        doctor_name="Возова А.М.",
        complaints=None,
        disease_anamnesis=None,
        life_anamnesis=None,
        diagnosis=None,
        diagnosis_comment=None,
        recommendations=None,
        laboratory=[
            MODULE.LaboratoryFinding(
                analysis_date=date(2024, 1, 1),
                date_precision="точная",
                day_is_artificial=False,
                study_type="ОАМ",
                indicator_raw="уд.вес",
                indicator_normalized="Относительная плотность",
                numeric_value="1015",
                text_value=None,
                unit=None,
                source_order=1,
                note=None,
            )
        ],
    )
    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation, age=44, weight=None
    )
    assert mapped == 1
    assert payloads["urinalysis_results"][0]["specific_gravity"] == MODULE.Decimal("1.015")
    assert "загружено как относительная плотность 1.015" in residual[0]


def test_wrong_uric_acid_unit_is_not_put_into_standard_column():
    consultation = MODULE.SourceConsultation(
        consultation_id="C1",
        patient_name="Иванова Анна Ивановна",
        birth_date=date(1980, 1, 1),
        appointment_date=date(2024, 1, 1),
        doctor_name="Возова А.М.",
        complaints=None,
        disease_anamnesis=None,
        life_anamnesis=None,
        diagnosis=None,
        diagnosis_comment=None,
        recommendations=None,
        laboratory=[
            MODULE.LaboratoryFinding(
                analysis_date=date(2024, 1, 1),
                date_precision="точная",
                day_is_artificial=False,
                study_type="Биохимия",
                indicator_raw="мочевая кислота",
                indicator_normalized="Мочевая кислота",
                numeric_value="484.6",
                text_value=None,
                unit="ммоль/л",
                source_order=1,
                note=None,
            )
        ],
    )
    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation, age=44, weight=None
    )
    assert mapped == 0
    assert payloads == {}
    assert "единица не соответствует" in residual[0]


def _create_source_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE consultations (
            consultation_id TEXT, resolved_name TEXT, birth_date TEXT,
            appointment_date TEXT, doctor_name TEXT, status TEXT,
            complaints TEXT, history_of_present_illness TEXT,
            history_of_life TEXT, diagnosis TEXT, comments TEXT,
            recommendations TEXT
        );
        CREATE TABLE clinical_findings (
            consultation_id TEXT, field_name TEXT, extracted_value TEXT,
            source_text TEXT, source_order INTEGER
        );
        CREATE TABLE laboratory_results (
            consultation_id TEXT, analysis_date TEXT, date_precision TEXT,
            day_is_artificial INTEGER, study_type TEXT, indicator_raw TEXT,
            indicator_normalized TEXT, numeric_value TEXT, text_value TEXT,
            unit TEXT, source_order INTEGER, note TEXT
        );
        CREATE TABLE instrumental_studies (
            consultation_id TEXT, study_date TEXT, date_precision TEXT,
            day_is_artificial INTEGER, study_type TEXT, result_text TEXT,
            source_order INTEGER, note TEXT
        );
        """
    )
    connection.execute(
        """
        INSERT INTO consultations VALUES (
            'C1', 'Иванова Анна Ивановна', '1980-01-01', '2024-02-03',
            'Возова А.М.', 'ЧИСТАЯ_ЗАПИСЬ', 'жалоб нет', 'исходный анамнез',
            'исходный анамнез жизни', 'исходный диагноз', 'комментарий',
            'рекомендации'
        )
        """
    )
    connection.execute(
        "INSERT INTO clinical_findings VALUES ('C1', 'анамнез_заболевания', 'уточнённый анамнез', 'исходник', 1)"
    )
    connection.commit()
    connection.close()


def test_load_source_requires_exact_count_and_prefers_cleaned_anamnesis(tmp_path: Path):
    db = tmp_path / "приемы.sqlite"
    _create_source_db(db)
    rows = MODULE.load_source(db, expected_count=1)
    assert len(rows) == 1
    assert rows[0].disease_anamnesis == "уточнённый анамнез"
    with pytest.raises(MODULE.ImportValidationError, match="Ожидалось 2"):
        MODULE.load_source(db, expected_count=2)


def test_numeric_value_fits_postgresql_numeric_precision():
    spec = MODULE.NumericSpec(precision=5, scale=3)
    assert MODULE.numeric_value_fits(MODULE.Decimal("1.015"), spec)
    assert MODULE.numeric_value_fits(MODULE.Decimal("99.999"), spec)
    assert not MODULE.numeric_value_fits(MODULE.Decimal("100"), spec)
    assert not MODULE.numeric_value_fits(MODULE.Decimal("99.9999"), spec)


def test_out_of_range_specific_gravity_moves_to_other_laboratory_text():
    consultation = MODULE.SourceConsultation(
        consultation_id="C1",
        patient_name="Иванова Анна Ивановна",
        birth_date=date(1980, 1, 1),
        appointment_date=date(2024, 1, 1),
        doctor_name="Возова А.М.",
        complaints=None,
        disease_anamnesis=None,
        life_anamnesis=None,
        diagnosis=None,
        diagnosis_comment=None,
        recommendations=None,
        laboratory=[
            MODULE.LaboratoryFinding(
                analysis_date=date(2024, 1, 1),
                date_precision="точная",
                day_is_artificial=False,
                study_type="ОАМ",
                indicator_raw="уд.вес",
                indicator_normalized="Относительная плотность",
                numeric_value="10150",
                text_value=None,
                unit=None,
                source_order=1,
                note=None,
            )
        ],
    )
    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation,
        age=44,
        weight=None,
        numeric_specs={("urinalysis_results", "specific_gravity"): MODULE.NumericSpec(5, 3)},
    )
    assert mapped == 0
    assert payloads == {}
    assert "не помещается" in residual[0]
    assert "NUMERIC(5,3)" in residual[0]
