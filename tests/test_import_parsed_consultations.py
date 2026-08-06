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
        source_sha256="a" * 64,
        source_ordinal=1,
        source_relative_path="patient.doc",
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
    assert residual == []


def test_wrong_uric_acid_unit_is_not_put_into_standard_column():
    consultation = MODULE.SourceConsultation(
        consultation_id="C1",
        source_sha256="a" * 64,
        source_ordinal=1,
        source_relative_path="patient.doc",
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
    assert residual == []


def _create_source_db(path: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE source_documents (
            document_id TEXT PRIMARY KEY, relative_path TEXT, sha256 TEXT
        );
        CREATE TABLE consultations (
            consultation_id TEXT, document_id TEXT, ordinal INTEGER,
            resolved_name TEXT, birth_date TEXT, appointment_date TEXT,
            doctor_name TEXT, status TEXT, complaints TEXT,
            history_of_present_illness TEXT, history_of_life TEXT,
            diagnosis TEXT, comments TEXT, recommendations TEXT
        );
        CREATE TABLE clinical_findings (
            consultation_id TEXT, field_name TEXT, extracted_value TEXT,
            source_text TEXT, source_order INTEGER
        );
        CREATE TABLE laboratory_results (
            consultation_id TEXT, analysis_date TEXT, date_precision TEXT,
            day_is_artificial INTEGER, study_type TEXT, indicator_raw TEXT,
            indicator_normalized TEXT, numeric_value TEXT, text_value TEXT,
            unit TEXT, source_order INTEGER, note TEXT, source_text TEXT
        );
        CREATE TABLE instrumental_studies (
            consultation_id TEXT, study_date TEXT, date_precision TEXT,
            day_is_artificial INTEGER, study_type TEXT, result_text TEXT,
            source_order INTEGER, note TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO source_documents VALUES (?, ?, ?)",
        ("DOC-1", "folder\\patient.doc", "b" * 64),
    )
    connection.execute(
        """
        INSERT INTO consultations VALUES (
            'C1', 'DOC-1', 1, 'Иванова Анна Ивановна', '1980-01-01',
            '2024-02-03', 'Возова А.М.', 'ЧИСТАЯ_ЗАПИСЬ', 'жалоб нет',
            'исходный анамнез', 'исходный анамнез жизни',
            'исходный диагноз', 'комментарий', 'рекомендации'
        )
        """
    )
    connection.execute(
        "INSERT INTO clinical_findings VALUES ('C1', 'анамнез_заболевания', 'уточнённый анамнез', 'исходник', 1)"
    )
    connection.commit()
    connection.close()


def test_load_source_accepts_any_count_and_optional_control_count(tmp_path: Path):
    db = tmp_path / "приемы.sqlite"
    _create_source_db(db)
    rows = MODULE.load_source(db)
    assert len(rows) == 1
    assert rows[0].source_sha256 == "b" * 64
    assert rows[0].source_ordinal == 1
    assert rows[0].source_relative_path == "folder/patient.doc"
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
        source_sha256="a" * 64,
        source_ordinal=1,
        source_relative_path="patient.doc",
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
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation,
        age=44,
        weight=None,
        numeric_specs={("urinalysis_results", "specific_gravity"): MODULE.NumericSpec(5, 3)},
        stats=stats,
    )
    assert mapped == 0
    assert payloads == {}
    assert residual == []
    assert stats.not_loaded == 1
    assert "NUMERIC(5,3)" in stats.issues[0]


def _consultation_for_key(consultation_id: str, sha256: str = "c" * 64, ordinal: int = 2):
    return MODULE.SourceConsultation(
        consultation_id=consultation_id,
        source_sha256=sha256,
        source_ordinal=ordinal,
        source_relative_path="patient.doc",
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
    )


def test_stable_key_does_not_depend_on_old_consultation_id_or_path():
    first = _consultation_for_key("DOC-OLD-C002")
    moved = _consultation_for_key("DOC-NEW-C002")
    assert MODULE.stable_import_key(first) == MODULE.stable_import_key(moved)


def test_legacy_key_is_recognized_and_planned_for_upgrade():
    consultation = _consultation_for_key("DOC-OLD-C002")
    legacy = MODULE.legacy_import_key(consultation)
    stable = MODULE.stable_import_key(consultation)
    present, upgrades = MODULE.classify_existing_import_keys(
        [consultation], {legacy: 17}
    )
    assert present == {stable}
    assert upgrades == {legacy: stable}


def test_stable_key_is_recognized_without_upgrade():
    consultation = _consultation_for_key("DOC-C002")
    stable = MODULE.stable_import_key(consultation)
    present, upgrades = MODULE.classify_existing_import_keys(
        [consultation], {stable: 17}
    )
    assert present == {stable}
    assert upgrades == {}


def test_conflicting_legacy_and_stable_keys_stop_import():
    consultation = _consultation_for_key("DOC-C002")
    with pytest.raises(MODULE.ImportValidationError, match="конфликтующие ключи"):
        MODULE.classify_existing_import_keys(
            [consultation],
            {
                MODULE.legacy_import_key(consultation): 17,
                MODULE.stable_import_key(consultation): 18,
            },
        )


def test_source_directory_is_resolved_to_sqlite(tmp_path: Path):
    assert MODULE.resolve_source_path(tmp_path) == (tmp_path / "приемы.sqlite").resolve()


def test_source_relative_path_rejects_escape():
    assert MODULE.normalize_source_relative_path(r"folder\patient.doc") == "folder/patient.doc"
    with pytest.raises(MODULE.ImportValidationError):
        MODULE.normalize_source_relative_path(r"..\secret.doc")
    with pytest.raises(MODULE.ImportValidationError):
        MODULE.normalize_source_relative_path(r"D:\secret.doc")



def _lab_consultation(lab):
    return MODULE.SourceConsultation(
        consultation_id="C-LAB",
        source_sha256="d" * 64,
        source_ordinal=1,
        source_relative_path="patient.doc",
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
        laboratory=[lab],
    )


def test_creatinine_alias_without_unit_uses_mis_standard_unit():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 1, 1),
        date_precision="точная",
        day_is_artificial=False,
        study_type="Биохимия",
        indicator_raw="креат",
        indicator_normalized="креат",
        numeric_value="146.38",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="креат 146,38",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 1
    assert payloads["biochemistry_results"][0]["creatinine"] == MODULE.Decimal("146.38")
    assert residual == []
    assert stats.inferred_units == 1


def test_biochemistry_skf_without_unit_goes_to_ckd_epi_column():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 1, 1),
        date_precision="точная",
        day_is_artificial=False,
        study_type="Биохимия",
        indicator_raw="СКФ",
        indicator_normalized="скф",
        numeric_value="43",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="СКФ 43",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 1
    assert payloads["calculated_metrics"][0]["egfr_ckdepi"] == MODULE.Decimal("43")
    assert residual == []
    assert stats.egfr_mapped == 1
    assert stats.inferred_units == 1


def test_ckd_epi_year_is_not_imported_as_egfr_value():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 1, 1),
        date_precision="точная",
        day_is_artificial=False,
        study_type="Расчет",
        indicator_raw="СКФ CKD-EPI 2021",
        indicator_normalized="рСКФ CKD-EPI",
        numeric_value="2021",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="СКФ CKD-EPI 2021",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 0
    assert payloads == {}
    assert residual == []
    assert stats.ignored_as_artifact == 1


def test_month_year_is_ignored_instead_of_becoming_ptg():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 11, 15),
        date_precision="месяц",
        day_is_artificial=True,
        study_type="ПТГ",
        indicator_raw="ПТГ",
        indicator_normalized="Паратгормон",
        numeric_value="11.2024",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="ПТГ 11.2024",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 0
    assert payloads == {}
    assert residual == []
    assert stats.ignored_as_artifact == 1


def test_biochemistry_heading_with_date_is_ignored():
    lab = MODULE.LaboratoryFinding(
        analysis_date=None,
        date_precision="нет",
        day_is_artificial=False,
        study_type="Биохимия",
        indicator_raw="Биохимия",
        indicator_normalized="Биохимия",
        numeric_value="03.2025",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="Биохимия 03.2025",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 0
    assert payloads == {}
    assert residual == []
    assert stats.ignored_as_artifact == 1


def test_acr_without_unit_uses_mg_per_mmol():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 1, 1),
        date_precision="точная",
        day_is_artificial=False,
        study_type="МАУ",
        indicator_raw="ACR",
        indicator_normalized="Альбумин-креатининовое соотношение",
        numeric_value="20",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="ACR 20",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 1
    assert payloads["albuminuria_results"][0]["albumin_creatinine_ratio"] == MODULE.Decimal("20")
    assert residual == []
    assert stats.inferred_units == 1


def test_unsupported_ionized_calcium_keeps_value_with_approved_unit_in_other():
    lab = MODULE.LaboratoryFinding(
        analysis_date=date(2024, 1, 1),
        date_precision="точная",
        day_is_artificial=False,
        study_type="Биохимия",
        indicator_raw="Са ион",
        indicator_normalized="Кальций ионизированный",
        numeric_value="1.19",
        text_value=None,
        unit=None,
        source_order=1,
        note=None,
        source_text="Са ион 1,19",
    )
    stats = MODULE.LabBuildStats()
    payloads, residual, mapped = MODULE.build_lab_payloads(
        _lab_consultation(lab), age=44, weight=None, stats=stats
    )
    assert mapped == 0
    assert payloads == {}
    assert residual == ["01.01.2024, Биохимия: Кальций ионизированный: 1.19 ммоль/л"]
    assert stats.inferred_units == 1


def test_repair_labs_rebuilds_only_laboratory_rows(monkeypatch):
    consultation = _consultation_for_key("C-REPAIR", sha256="e" * 64, ordinal=1)

    class Cursor:
        def __init__(self):
            self.rowcount = 0
            self._rows = []
            self.executed = []

        def execute(self, query, params=None):
            text = str(query)
            self.executed.append((text, params))
            if "SELECT appointment_id, weight FROM examinations" in text:
                self._rows = [(42, MODULE.Decimal("70"))]
                self.rowcount = 1
            elif "UPDATE appointment_additional_studies" in text:
                self._rows = []
                self.rowcount = 1
            else:
                self._rows = []
                self.rowcount = 0

        def fetchall(self):
            return list(self._rows)

        def close(self):
            pass

    class Connection:
        def __init__(self):
            self.cursor_obj = Cursor()
            self.committed = False
            self.rolled_back = False

        def cursor(self):
            return self.cursor_obj

        def commit(self):
            self.committed = True

        def rollback(self):
            self.rolled_back = True

    inserted = []
    monkeypatch.setattr(MODULE, "validate_target_schema", lambda cursor: "0018")
    monkeypatch.setattr(MODULE, "target_numeric_specs", lambda cursor: {})
    monkeypatch.setattr(
        MODULE,
        "source_appointment_ids",
        lambda cursor, consultations: {MODULE.stable_import_key(consultation): 42},
    )
    monkeypatch.setattr(MODULE, "_count_lab_rows", lambda cursor, ids: 3)
    monkeypatch.setattr(MODULE, "_delete_lab_rows", lambda cursor, ids: 3)
    monkeypatch.setattr(
        MODULE,
        "build_lab_payloads",
        lambda *args, **kwargs: (
            {"calculated_metrics": [{"investigation_date": None, "egfr_ckdepi": MODULE.Decimal("55")}]},
            [],
            1,
        ),
    )
    monkeypatch.setattr(
        MODULE,
        "_insert_row",
        lambda cursor, table, values: inserted.append((table, values)),
    )

    connection = Connection()
    report = MODULE.ImportReport(mode="test", source_database="source.sqlite")
    MODULE.run_laboratory_repair(connection, [consultation], report, apply=True)

    assert connection.committed is True
    assert connection.rolled_back is False
    assert report.laboratory_appointments_repaired == 1
    assert report.laboratory_rows_deleted == 3
    assert inserted == [
        (
            "calculated_metrics",
            {
                "appointment_id": 42,
                "investigation_date": None,
                "egfr_ckdepi": MODULE.Decimal("55"),
            },
        )
    ]


def test_oam_blood_cell_aliases_without_units_go_to_standard_columns():
    consultation = _lab_consultation(
        MODULE.LaboratoryFinding(
            analysis_date=date(2024, 5, 15),
            date_precision="месяц",
            day_is_artificial=True,
            study_type="ОАМ",
            indicator_raw="Er",
            indicator_normalized="Эритроциты неизмененные",
            numeric_value="6",
            text_value=None,
            unit=None,
            source_order=1,
            note=None,
            source_text="Er 6",
        )
    )
    consultation.laboratory.append(
        MODULE.LaboratoryFinding(
            analysis_date=date(2024, 5, 15),
            date_precision="месяц",
            day_is_artificial=True,
            study_type="ОАМ",
            indicator_raw="Le",
            indicator_normalized="лейк",
            numeric_value="5",
            text_value=None,
            unit=None,
            source_order=2,
            note=None,
            source_text="Le 5",
        )
    )

    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation, age=44, weight=None
    )

    assert mapped == 2
    row = payloads["urinalysis_results"][0]
    assert row["erythrocytes"] == MODULE.Decimal("6")
    assert row["leukocytes"] == MODULE.Decimal("5")
    assert residual == []


def test_other_laboratory_contains_only_unsupported_grouped_parameters():
    consultation = _lab_consultation(
        MODULE.LaboratoryFinding(
            analysis_date=date(2024, 5, 15),
            date_precision="месяц",
            day_is_artificial=True,
            study_type="Биохимия",
            indicator_raw="холестерин",
            indicator_normalized="Общий холестерин",
            numeric_value="4.63",
            text_value=None,
            unit="ммоль/л",
            source_order=1,
            note=None,
            source_text="Холестерин 4,63",
        )
    )
    consultation.laboratory.extend(
        [
            MODULE.LaboratoryFinding(
                analysis_date=date(2024, 5, 15),
                date_precision="месяц",
                day_is_artificial=True,
                study_type="Биохимия",
                indicator_raw="триглицериды",
                indicator_normalized="Триглицериды",
                numeric_value="4",
                text_value=None,
                unit=None,
                source_order=2,
                note="Значение указано со знаком >",
                source_text="ТГ >4",
            ),
            MODULE.LaboratoryFinding(
                analysis_date=date(2024, 5, 15),
                date_precision="месяц",
                day_is_artificial=True,
                study_type="ОАМ",
                indicator_raw="уд.вес",
                indicator_normalized="Относительная плотность",
                numeric_value="1025",
                text_value=None,
                unit=None,
                source_order=3,
                note=None,
                source_text="уд.вес 1025",
            ),
        ]
    )

    payloads, residual, mapped = MODULE.build_lab_payloads(
        consultation, age=44, weight=None
    )

    assert mapped == 1
    assert payloads["urinalysis_results"][0]["specific_gravity"] == MODULE.Decimal("1.025")
    assert residual == [
        "05.2024, Биохимия: Общий холестерин: 4.63 ммоль/л; Триглицериды: >4"
    ]
    assert "искусственно" not in residual[0]
    assert "загружено как" not in residual[0]


def test_instrumental_text_removes_only_technical_notes_and_formats_date():
    consultation = _consultation_for_key("C-INSTR")
    consultation.instrumental = [
        MODULE.InstrumentalFinding(
            study_date=date(2024, 5, 15),
            date_precision="месяц",
            day_is_artificial=True,
            study_type="УЗИ почек",
            result_text="ЧЛС не расширена (15-е число установлено искусственно)",
            source_order=1,
            note="день 15 установлен искусственно",
        ),
        MODULE.InstrumentalFinding(
            study_date=date(2024, 6, 3),
            date_precision="точная",
            day_is_artificial=False,
            study_type="ЭКГ",
            result_text="Синусовый ритм",
            source_order=2,
            note="ЧСС 70",
        ),
    ]

    text = MODULE.build_instrumental_text(consultation)

    assert text == (
        "05.2024, УЗИ почек: ЧЛС не расширена\n"
        "03.06.2024, ЭКГ: Синусовый ритм; ЧСС 70"
    )
    assert "искусственно" not in text
