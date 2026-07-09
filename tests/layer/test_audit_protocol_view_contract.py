"""Contract-тесты протокола подробного аудита."""
from __future__ import annotations
import os
os.environ.setdefault("DB_NAME","test_db"); os.environ.setdefault("DB_USER","test_user"); os.environ.setdefault("DB_PASSWORD","test_password"); os.environ.setdefault("SESSION_SECRET_KEY","test-session-secret")
from app.repositories.audit_log import build_audit_protocol_summary
from app.services.audit_details import build_appointment_medical_audit_changes

def _by_type(changes, t): return [x for x in changes if x["change_type"]==t]

def test_icd10_removed_diagnoses_are_logged_as_removed_not_added():
    form={"icd10_main_diagnosis":"N18.3 — Хроническая болезнь почек, стадия 3","icd10_main_note":"","icd10_complication_diagnosis":[],"icd10_comorbidity_diagnosis":[],"kdigo_selected_conclusion_text":"По KDIGO: C3aA2 — высокий риск прогрессирования ХБП и развития ХПН.","kdigo_selected_current_option":"row|2026-07-09|C3a|2026-07-09|A2"}
    previous=[{"diagnosis_type":"main","icd10_diagnosis":"N18.3 — Хроническая болезнь почек, стадия 3","doctor_note":None},{"diagnosis_type":"complication","icd10_diagnosis":"R80 — Изолированная протеинурия","doctor_note":None},{"diagnosis_type":"comorbidity","icd10_diagnosis":"I12.9 — Гипертензивная болезнь с поражением почек без почечной недостаточности","doctor_note":None}]
    changes=build_appointment_medical_audit_changes(form,previous_appointment={},previous_medications=[],previous_icd10_diagnoses=previous,appointment_id=29)
    assert len(_by_type(changes,"diagnosis_removed"))==2
    assert not _by_type(changes,"diagnosis_added")
    assert _by_type(changes,"diagnosis_continued")

def test_kdigo_details_are_human_readable_without_raw_row_key():
    form={"kdigo_selected_conclusion_text":"По KDIGO: C3aA2 — высокий риск прогрессирования ХБП и развития ХПН.","kdigo_selected_current_option":"row|2026-07-09|C3a|2026-07-09|A2"}
    changes=build_appointment_medical_audit_changes(form,previous_appointment={},previous_medications=[],previous_icd10_diagnoses=[],appointment_id=29)
    kdigo=[x for x in changes if x["section"]=="kdigo"][0]
    assert "row|" not in (kdigo["details"] or "")
    assert "СКФ от 2026-07-09, категория C3a" in kdigo["details"]

def test_protocol_summary_groups_removed_changed_system_and_unchanged():
    changes=[{"change_type":"diagnosis_removed","field_label":"Осложнение","old_value":"R80 — Изолированная протеинурия"},{"change_type":"changed_from_prefill","field_label":"ЧСС","old_value":"82","new_value":"86"},{"change_type":"autocalculated","field_label":"ИМТ","details":"ИМТ рассчитан системой"},{"change_type":"medication_continued","field_label":"Эналаприл","new_value":"Эналаприл — 10 мг"}]
    by_key={x["key"]:x for x in build_audit_protocol_summary(changes)}
    assert {"removed","changed","system","unchanged"}.issubset(by_key)
    assert any("R80" in x for x in by_key["removed"]["items"])
