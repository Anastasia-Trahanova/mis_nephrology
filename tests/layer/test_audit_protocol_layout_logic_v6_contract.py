"""
Назначение файла: тесты человекочитаемого протокола аудита v6.

Как работает:
- проверяет формирование детальных изменений без подключения к БД;
- фиксирует договорённости по текстам статусов для страницы /admin/audit/{event_id};
- проверяет, что кожные покровы и отёки логируются как сохранённые значения текущего приёма,
  а не как удалённые автоподстановки;
- проверяет, что альбуминурия выводится без лишних слов про единицы;
- проверяет, что пустая дата контроля не считается удалением.

Что редактировать здесь:
- ожидаемые статусы аудита при изменении правил отображения протокола.

Что не редактировать здесь:
- SQL и реальные данные пациентов.
"""

from __future__ import annotations

from app.repositories.audit_log import CHANGE_TYPE_LABELS
from app.services.audit_details import build_appointment_medical_audit_changes


class FakeForm(dict):
    """Минимальный аналог FormData для unit-тестов audit_details."""

    def getlist(self, key):
        value = self.get(key)
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


def changes_by_field(changes, field_name):
    return [item for item in changes if item.get("field_name") == field_name]


def test_albuminuria_details_are_human_readable_without_unit_words():
    form = FakeForm(
        {
            "appointment_date": "2026-07-09",
            "albuminuria_investigation_date": ["2026-07-09"],
            "urine_albumin": ["234"],
            "urine_albumin_unit": ["mg_l"],
            "urine_creatinine": ["9"],
            "urine_creatinine_unit": ["mmol_l"],
        }
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={},
        previous_medications=[],
        previous_icd10_diagnoses=[],
        appointment_id=30,
    )

    lab = [
        item
        for item in changes
        if item["section"] == "albuminuria" and item["change_type"] == "lab_added"
    ][0]

    assert lab["new_value"] == "Добавлен анализ 2026-07-09"
    assert "Альбумин мочи: 234; mg_l" in lab["details"]
    assert "Креатинин мочи: 9; mmol_l" in lab["details"]
    assert "Единицы альбумина" not in lab["details"]
    assert "Единицы креатинина" not in lab["details"]


def test_skin_and_edema_are_logged_as_current_saved_values_not_deleted_prefill():
    form = FakeForm(
        {
            "skin_color": ["Цианотичные", "мраморный"],
            "edema_peripheral": ["Голени", "стопы"],
        }
    )

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={
            "skin_condition": "Высыпания: нет",
            "edema_location": "Периферические отёки: нет",
        },
        previous_medications=[],
        previous_icd10_diagnoses=[],
        appointment_id=30,
    )

    skin = changes_by_field(changes, "skin_condition")[0]
    edema = changes_by_field(changes, "edema_location")[0]

    assert skin["change_type"] == "changed_from_prefill"
    assert "Окраска: Цианотичные, мраморный" in skin["new_value"]
    assert skin["old_value"] == "Высыпания: нет"

    assert edema["change_type"] == "changed_from_prefill"
    assert "Периферические отёки: Голени, стопы" in edema["new_value"]
    assert edema["old_value"] == "Периферические отёки: нет"


def test_empty_next_control_date_is_not_marked_as_deleted():
    form = FakeForm({"next_control_date": ""})

    changes = build_appointment_medical_audit_changes(
        form,
        previous_appointment={"next_control_date": "2026-09-01"},
        previous_medications=[],
        previous_icd10_diagnoses=[],
        appointment_id=30,
    )

    date_change = changes_by_field(changes, "next_control_date")[0]

    assert date_change["change_type"] == "field_not_filled"
    assert date_change["old_value"] is None
    assert date_change["new_value"] is None
    assert "не заполнена" in date_change["details"]


def test_removed_medication_label_is_removed_not_not_carried():
    assert CHANGE_TYPE_LABELS["medication_removed"] == "Препарат удалён"


def test_main_diagnosis_status_distinguishes_system_and_manual():
    automatic_form = FakeForm(
        {
            "icd10_main_diagnosis": "N18.3 — Хроническая болезнь почек, стадия 3",
            "icd10_main_diagnosis_autofilled_value": "N18.3 — Хроническая болезнь почек, стадия 3",
            "icd10_main_diagnosis_user_edited": "false",
        }
    )
    manual_form = FakeForm(
        {
            "icd10_main_diagnosis": "N18.4 — Хроническая болезнь почек, стадия 4",
            "icd10_main_diagnosis_autofilled_value": "N18.3 — Хроническая болезнь почек, стадия 3",
            "icd10_main_diagnosis_user_edited": "true",
        }
    )

    automatic = build_appointment_medical_audit_changes(
        automatic_form,
        previous_appointment={},
        previous_medications=[],
        previous_icd10_diagnoses=[],
        appointment_id=30,
    )
    manual = build_appointment_medical_audit_changes(
        manual_form,
        previous_appointment={},
        previous_medications=[],
        previous_icd10_diagnoses=[],
        appointment_id=31,
    )

    automatic_main = [
        item for item in automatic if item["section"] == "icd10" and item["field_label"] == "Основной диагноз"
    ][0]
    manual_main = [
        item for item in manual if item["section"] == "icd10" and item["field_label"] == "Основной диагноз"
    ][0]

    assert automatic_main["change_type"] == "accepted_system_main"
    assert "автоматически" in automatic_main["details"]

    assert manual_main["change_type"] == "overridden_system_main"
    assert manual_main["old_value"] == "N18.3 — Хроническая болезнь почек, стадия 3"
    assert "врач изменил" in manual_main["details"]
