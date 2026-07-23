"""
Назначение файла: подготовка подробностей медицинского аудита по HTML-формам.

Как работает:
- получает уже успешно сохранённую форму нового пациента или повторного приёма;
- не пишет ничего в БД самостоятельно;
- строит список изменений для audit_event_changes;
- фиксирует только итоговые сохранённые изменения, а не каждое нажатие клавиши;
- для лабораторных анализов фиксирует факт сохранения нового анализа;
- для предзаполненных полей фиксирует только заполнение, удаление или изменение;
- для лекарств сравнивает назначения прошлого приёма с назначениями нового приёма;
- для МКБ-10 фиксирует системный основной диагноз как принятый/изменённый врачом,
  если форма передала ожидаемый системный диагноз.

Что редактировать здесь:
- списки полей формы и их русские подписи;
- правила сравнения лекарств и текстовых предзаполненных полей;
- какие разделы писать в audit_event_changes.

Что не редактировать здесь:
- SQL записи audit_event_changes — он в app/repositories/audit_log.py;
- сохранение медицинских данных — оно в app/services/appointment_save_service.py;
- live-пересчёт СКФ/KDIGO в браузере.
"""

from __future__ import annotations

from typing import Any

from app.services.appointment_text_builder import build_edema_location


MAX_AUDIT_VALUE_LENGTH = 500

SECTION_LABELS = {
    "patient": "Пациент",
    "appointment": "Приём",
    "survey": "Жалобы и анамнез",
    "examination": "Осмотр",
    "cbc": "Общий анализ крови",
    "biochemistry": "Биохимия крови",
    "urinalysis": "Общий анализ мочи",
    "albuminuria": "Альбуминурия",
    "ultrasound": "УЗИ почек",
    "kdigo": "KDIGO",
    "icd10": "МКБ-10 диагнозы",
    "diet": "Диета и рекомендации",
    "medications": "Лекарства",
}

PATIENT_FIELDS = [
    ("last_name", "Фамилия"),
    ("first_name", "Имя"),
    ("patronymic", "Отчество"),
    ("birth_date", "Дата рождения"),
    ("gender", "Пол"),
    ("phone", "Номер телефона"),
]

APPOINTMENT_FIELDS = [
    ("appointment_date", "Дата приёма"),
    ("appointment_time", "Время приёма"),
    ("doctor_id", "Врач"),
    ("location_id", "Кабинет/место приёма"),
]

PREFILL_TEXT_FIELDS = [
    ("survey", "complaints", "Жалобы"),
    ("survey", "education_and_professional_history", "Образование и профессиональный анамнез"),
    ("survey", "housing_conditions", "Жилищные условия"),
    ("survey", "past_diseases", "Перенесённые заболевания"),
    ("survey", "habitual_intoxications", "Привычные интоксикации"),
    ("survey", "gynecological_history", "Гинекологический анамнез"),
    ("survey", "heredity_description", "Наследственность"),
    ("survey", "family_life", "Семейная жизнь"),
    ("survey", "allergological_history", "Аллергологический анамнез"),
    ("survey", "epidemiological_history", "Эпидемиологический анамнез"),
    ("survey", "insurance_history", "Страховой анамнез"),
    ("survey", "disease_onset", "Начало болезни"),
    ("survey", "disease_course", "Течение заболевания"),
    ("examination", "general_condition", "Общее состояние"),
    ("examination", "consciousness", "Сознание"),
    ("examination", "bed_position", "Положение в постели"),
    ("examination", "bed_position_details", "Особенности вынужденного положения"),
    ("examination", "body_build", "Телосложение"),
    ("examination", "constitution_type", "Тип конституции"),
    ("examination", "skin_and_mucous_membranes", "Кожа и слизистые оболочки"),
    ("examination", "lymph_nodes", "Лимфатические узлы"),
    ("examination", "thyroid_gland", "Щитовидная железа"),
    ("examination", "musculoskeletal_system", "Опорно-двигательный аппарат"),
    ("examination", "bp_note", "Примечание к АД"),
    ("examination", "veins_condition", "Состояние вен"),
    ("examination", "lung_auscultation", "Аускультация лёгких"),
    ("examination", "abdomen", "Живот"),
    ("examination", "kidney_palpation", "Пальпация почек"),
    ("examination", "kidney_palpation_details", "Уточнение пальпации почек"),
    ("examination", "pasternatsky_result", "Симптом Пастернацкого"),
    ("examination", "pasternatsky_side", "Сторона симптома Пастернацкого"),
    ("diet", "diet", "Диета"),
    ("diet", "recommendations", "Рекомендации"),
]

EXAMINATION_NUMERIC_FIELDS = [
    ("body_temperature", "Температура тела"),
    ("systolic_pressure", "Систолическое АД"),
    ("diastolic_pressure", "Диастолическое АД"),
    ("heart_rate", "ЧСС"),
    ("height", "Рост"),
    ("weight", "Вес"),
]

LAB_GROUPS = [
    {
        "section": "cbc",
        "date_field": "cbc_investigation_date",
        "field_prefix": "ОАК",
        "fields": [
            ("hemoglobin", "Гемоглобин"),
            ("erythrocytes", "Эритроциты"),
            ("leukocytes", "Лейкоциты"),
            ("platelets", "Тромбоциты"),
            ("esr", "СОЭ"),
            ("mcv", "MCV"),
            ("hematocrit", "Гематокрит"),
        ],
    },
    {
        "section": "biochemistry",
        "date_field": "biochemistry_investigation_date",
        "field_prefix": "Биохимия",
        "fields": [
            ("creatinine", "Креатинин"),
            ("urea", "Мочевина"),
            ("uric_acid", "Мочевая кислота"),
            ("glucose", "Глюкоза"),
            ("total_protein", "Общий белок"),
            ("albumin", "Альбумин"),
            ("potassium", "Калий"),
            ("calcium", "Кальций"),
            ("phosphorus", "Фосфор"),
            ("ferritin", "Ферритин"),
            ("ptg", "ПТГ"),
        ],
        "autocalculated_if": ["creatinine"],
        "autocalculated_details": "СКФ и категория ХБП рассчитываются системой по креатинину, полу, возрасту и другим исходным данным.",
    },
    {
        "section": "urinalysis",
        "date_field": "urinalysis_investigation_date",
        "field_prefix": "ОАМ",
        "fields": [
            ("specific_gravity", "Удельный вес"),
            ("urine_protein", "Белок"),
            ("urine_leukocytes", "Лейкоциты"),
            ("urine_erythrocytes", "Эритроциты"),
            ("bacteria", "Бактерии"),
        ],
    },
    {
        "section": "albuminuria",
        "date_field": "albuminuria_investigation_date",
        "field_prefix": "Альбуминурия",
        "fields": [
            ("urine_albumin", "Альбумин мочи"),
            ("urine_albumin_unit", "Единицы альбумина"),
            ("urine_creatinine", "Креатинин мочи"),
            ("urine_creatinine_unit", "Единицы креатинина мочи"),
        ],
        "autocalculated_if": ["urine_albumin", "urine_creatinine"],
        "autocalculated_details": "ACR и категория альбуминурии рассчитываются системой.",
    },
    {
        "section": "ultrasound",
        "date_field": "ultrasound_investigation_date",
        "field_prefix": "УЗИ",
        "fields": [
            ("left_kidney_size", "Размер левой почки"),
            ("right_kidney_size", "Размер правой почки"),
            ("left_parenchyma", "Паренхима слева"),
            ("right_parenchyma", "Паренхима справа"),
            ("ultrasound_desc", "Описание УЗИ"),
        ],
    },
]


def _form_get(form: Any, key: str, default: Any = None) -> Any:
    """Достаёт одно значение из FormData/dict."""
    try:
        return form.get(key, default)
    except AttributeError:
        return default


def _form_getlist(form: Any, key: str) -> list[Any]:
    """Достаёт список значений из FormData/dict."""
    if hasattr(form, "getlist"):
        return list(form.getlist(key))
    value = _form_get(form, key)
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _clean(value: Any) -> str | None:
    """Нормализует значение для сравнения и записи в audit."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return text


def _display(value: Any) -> str | None:
    """Обрезает значение для подробной страницы аудита."""
    text = _clean(value)
    if not text:
        return None
    if len(text) > MAX_AUDIT_VALUE_LENGTH:
        return text[: MAX_AUDIT_VALUE_LENGTH - 1] + "…"
    return text


def _same(left: Any, right: Any) -> bool:
    """Сравнивает значения формы и предыдущего приёма без учёта лишних пробелов."""
    return (_clean(left) or "") == (_clean(right) or "")


def _change(
    section: str,
    field_name: str | None,
    field_label: str | None,
    change_type: str,
    *,
    old_value: Any = None,
    new_value: Any = None,
    details: str | None = None,
    sort_order: int = 0,
) -> dict[str, Any]:
    """Создаёт одну строку audit_event_changes в независимом от БД формате."""
    return {
        "section": section,
        "section_label": SECTION_LABELS.get(section, section),
        "field_name": field_name,
        "field_label": field_label,
        "change_type": change_type,
        "old_value": _display(old_value),
        "new_value": _display(new_value),
        "details": details,
        "sort_order": sort_order,
    }


def _append_if_changed_from_previous(
    changes: list[dict[str, Any]],
    form: Any,
    previous: dict[str, Any] | None,
    section: str,
    field_name: str,
    field_label: str,
    *,
    sort_order: int,
) -> None:
    """Добавляет изменение предзаполненного поля только если врач реально поменял значение."""
    current_value = _form_get(form, field_name)
    # Условные уточнения сохраняются только вместе с выбранным основным значением.
    # Аудит должен сравнивать именно итог, который попадёт в БД, а не скрытый текст,
    # оставшийся в браузере после смены зависимого выпадающего списка.
    if field_name == "bed_position_details" and _form_get(form, "bed_position") != "forced":
        current_value = None
    elif field_name == "kidney_palpation_details" and _form_get(form, "kidney_palpation") != "palpable":
        current_value = None

    previous_value = previous.get(field_name) if previous else None

    current_clean = _clean(current_value)
    previous_clean = _clean(previous_value)

    if not previous_clean and current_clean:
        changes.append(
            _change(
                section,
                field_name,
                field_label,
                "filled_new",
                new_value=current_value,
                sort_order=sort_order,
            )
        )
    elif previous_clean and not current_clean:
        changes.append(
            _change(
                section,
                field_name,
                field_label,
                "cleared_from_prefill",
                old_value=previous_value,
                details="врач удалил значение, подставленное с прошлого приёма",
                sort_order=sort_order,
            )
        )
    elif previous_clean and current_clean and not _same(current_value, previous_value):
        changes.append(
            _change(
                section,
                field_name,
                field_label,
                "changed_from_prefill",
                old_value=previous_value,
                new_value=current_value,
                sort_order=sort_order,
            )
        )


def _append_field_created(
    changes: list[dict[str, Any]],
    form: Any,
    section: str,
    field_name: str,
    field_label: str,
    *,
    change_type: str,
    sort_order: int,
) -> None:
    """Добавляет новое заполненное поле для первого приёма/нового пациента."""
    value = _form_get(form, field_name)
    if _clean(value):
        changes.append(
            _change(
                section,
                field_name,
                field_label,
                change_type,
                new_value=value,
                sort_order=sort_order,
            )
        )


def _list_at(values: list[Any], index: int) -> Any:
    """Безопасно берёт значение списка по индексу."""
    return values[index] if 0 <= index < len(values) else None


def _row_has_any_value(form: Any, fields: list[tuple[str, str]], index: int) -> bool:
    """Проверяет, заполнена ли хотя бы одна медицинская ячейка строки анализа."""
    return any(_clean(_list_at(_form_getlist(form, field_name), index)) for field_name, _ in fields)


def _format_lab_details(group: dict[str, Any], form: Any, index: int) -> str:
    """Готовит краткое описание сохранённого анализа без лишних технических слов."""
    if group["section"] == "albuminuria":
        albumin = _display(_list_at(_form_getlist(form, "urine_albumin"), index))
        albumin_unit = _display(_list_at(_form_getlist(form, "urine_albumin_unit"), index))
        creatinine = _display(_list_at(_form_getlist(form, "urine_creatinine"), index))
        creatinine_unit = _display(_list_at(_form_getlist(form, "urine_creatinine_unit"), index))

        rows: list[str] = []
        if albumin:
            rows.append(f"Альбумин мочи: {albumin}" + (f"; {albumin_unit}" if albumin_unit else ""))
        if creatinine:
            rows.append(f"Креатинин мочи: {creatinine}" + (f"; {creatinine_unit}" if creatinine_unit else ""))
        return "\n".join(rows) if rows else "анализ сохранён"

    filled_parts = []
    for field_name, label in group["fields"]:
        value = _list_at(_form_getlist(form, field_name), index)
        if _clean(value):
            filled_parts.append(f"{label}: {_display(value)}")
    return "; ".join(filled_parts) if filled_parts else "анализ сохранён"


def _append_lab_changes(changes: list[dict[str, Any]], form: Any, *, sort_base: int) -> None:
    """Фиксирует только реально сохранённые новые лабораторные исследования."""
    sort_order = sort_base

    for group in LAB_GROUPS:
        date_values = _form_getlist(form, group["date_field"])
        value_lengths = [len(date_values)]
        for field_name, _ in group["fields"]:
            value_lengths.append(len(_form_getlist(form, field_name)))
        max_len = max(value_lengths or [0])

        for index in range(max_len):
            if not _row_has_any_value(form, group["fields"], index):
                continue

            date_value = _list_at(date_values, index) or _form_get(form, "appointment_date")
            date_text = date_value or "даты приёма"

            changes.append(
                _change(
                    group["section"],
                    group["date_field"],
                    "Анализ",
                    "lab_added",
                    new_value=f"Добавлен анализ {date_text}",
                    details=_format_lab_details(group, form, index),
                    sort_order=sort_order,
                )
            )
            sort_order += 1

            autocalculated_if = group.get("autocalculated_if") or []
            if autocalculated_if and any(
                _clean(_list_at(_form_getlist(form, field_name), index))
                for field_name in autocalculated_if
            ):
                changes.append(
                    _change(
                        group["section"],
                        None,
                        "Расчётные показатели",
                        "autocalculated",
                        details=group.get("autocalculated_details"),
                        sort_order=sort_order,
                    )
                )
                sort_order += 1


def _append_structured_examination_text_changes(
    changes: list[dict[str, Any]],
    form: Any,
    previous: dict[str, Any] | None,
    *,
    sort_base: int,
) -> int:
    """Фиксирует отёки, которые по-прежнему собираются из checkbox-полей формы.

    Кожа и слизистые оболочки теперь вводятся обычным текстом и поэтому обрабатываются
    общим списком PREFILL_TEXT_FIELDS. Отёки остаются в прежнем формате: сервер собирает
    отмеченные пункты и дополнительное описание в одну итоговую строку.
    """
    sort_order = sort_base
    current_value = build_edema_location(form)
    previous_value = previous.get("edema_location") if previous else None
    current_clean = _clean(current_value)
    previous_clean = _clean(previous_value)

    if current_clean and not previous_clean:
        changes.append(
            _change(
                "examination",
                "edema_location",
                "Отёки",
                "filled_new",
                new_value=current_value,
                details="значение сформировано из отмеченных пунктов текущего приёма",
                sort_order=sort_order,
            )
        )
        sort_order += 1
    elif current_clean and previous_clean and not _same(current_value, previous_value):
        changes.append(
            _change(
                "examination",
                "edema_location",
                "Отёки",
                "changed_from_prefill",
                old_value=previous_value,
                new_value=current_value,
                details="значение сформировано из отмеченных пунктов текущего приёма",
                sort_order=sort_order,
            )
        )
        sort_order += 1
    # Если в текущем приёме врач ничего не отметил, это не считается удалением:
    # checkbox отёков не переносятся автоматически как активные элементы.

    return sort_order


def _normalize_medications_from_form(form: Any) -> list[dict[str, str | None]]:
    """Возвращает назначения из формы в виде списка строк."""
    medications = _form_getlist(form, "medication")
    dosages = _form_getlist(form, "dosage")
    schedules = _form_getlist(form, "schedule")
    max_len = max(len(medications), len(dosages), len(schedules), 0)

    rows: list[dict[str, str | None]] = []
    for index in range(max_len):
        row = {
            "medication": _clean(_list_at(medications, index)),
            "dosage": _clean(_list_at(dosages, index)),
            "schedule": _clean(_list_at(schedules, index)),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def _normalize_previous_medications(previous_medications: list[Any] | None) -> list[dict[str, str | None]]:
    """Возвращает лекарства прошлого приёма в том же формате, что и форма."""
    rows: list[dict[str, str | None]] = []
    for item in previous_medications or []:
        getter = item.get if hasattr(item, "get") else lambda key, default=None: getattr(item, key, default)
        row = {
            "medication": _clean(getter("medication")),
            "dosage": _clean(getter("dosage")),
            "schedule": _clean(getter("schedule")),
        }
        if any(row.values()):
            rows.append(row)
    return rows


def _med_key(row: dict[str, Any]) -> str:
    """Ключ препарата для сопоставления строк назначений."""
    return (_clean(row.get("medication")) or "").lower()


def _med_display(row: dict[str, Any]) -> str:
    """Человекочитаемая строка лекарства."""
    parts = [row.get("medication"), row.get("dosage"), row.get("schedule")]
    return " — ".join(str(part).strip() for part in parts if _clean(part))


def _append_medication_changes(
    changes: list[dict[str, Any]],
    form: Any,
    previous_medications: list[Any] | None,
    *,
    sort_base: int,
) -> None:
    """Сравнивает лекарства прошлого и нового приёма."""
    current_rows = _normalize_medications_from_form(form)
    previous_rows = _normalize_previous_medications(previous_medications)

    previous_by_name = {_med_key(row): row for row in previous_rows if _med_key(row)}
    current_names = {_med_key(row) for row in current_rows if _med_key(row)}
    sort_order = sort_base

    for row in current_rows:
        key = _med_key(row)
        previous = previous_by_name.get(key)

        if not previous:
            changes.append(
                _change(
                    "medications",
                    "medication",
                    row.get("medication") or "Лекарство",
                    "medication_added",
                    new_value=_med_display(row),
                    sort_order=sort_order,
                )
            )
            sort_order += 1
            continue

        if _same(row.get("dosage"), previous.get("dosage")) and _same(
            row.get("schedule"), previous.get("schedule")
        ):
            changes.append(
                _change(
                    "medications",
                    "medication",
                    row.get("medication") or "Лекарство",
                    "medication_continued",
                    new_value=_med_display(row),
                    sort_order=sort_order,
                )
            )
            sort_order += 1
            continue

        if not _same(row.get("dosage"), previous.get("dosage")):
            changes.append(
                _change(
                    "medications",
                    "dosage",
                    row.get("medication") or "Дозировка",
                    "dosage_changed",
                    old_value=previous.get("dosage"),
                    new_value=row.get("dosage"),
                    sort_order=sort_order,
                )
            )
            sort_order += 1

        if not _same(row.get("schedule"), previous.get("schedule")):
            changes.append(
                _change(
                    "medications",
                    "schedule",
                    row.get("medication") or "Режим приёма",
                    "schedule_changed",
                    old_value=previous.get("schedule"),
                    new_value=row.get("schedule"),
                    sort_order=sort_order,
                )
            )
            sort_order += 1

    for previous in previous_rows:
        key = _med_key(previous)
        if key and key not in current_names:
            changes.append(
                _change(
                    "medications",
                    "medication",
                    previous.get("medication") or "Лекарство",
                    "medication_removed",
                    old_value=_med_display(previous),
                    details="препарат удалён из текущего назначения",
                    sort_order=sort_order,
                )
            )
            sort_order += 1



def _diagnosis_display(diagnosis: Any, note: Any = None) -> str | None:
    """Возвращает диагноз МКБ-10 в человекочитаемом виде для аудита."""
    diagnosis_text = _clean(diagnosis)
    note_text = _clean(note)
    if not diagnosis_text:
        return None
    if note_text:
        return f"{diagnosis_text} ({note_text})"
    return diagnosis_text


def _diagnosis_key(diagnosis_type: str, diagnosis: Any) -> str:
    """Стабильный ключ диагноза для сравнения до/после сохранения."""
    text = (_clean(diagnosis) or "").lower().replace("ё", "е")
    text = " ".join(text.split())
    return f"{diagnosis_type}:{text}"


def _normalize_previous_icd10_diagnoses(previous_icd10_diagnoses: list[Any] | None) -> list[dict[str, str | None]]:
    """Приводит диагнозы прошлого приёма из БД к формату сравнения."""
    rows: list[dict[str, str | None]] = []
    for item in previous_icd10_diagnoses or []:
        getter = item.get if hasattr(item, "get") else lambda key, default=None: getattr(item, key, default)
        diagnosis_type = _clean(getter("diagnosis_type"))
        diagnosis = _clean(getter("icd10_diagnosis"))
        if not diagnosis_type or not diagnosis:
            continue
        rows.append({"diagnosis_type": diagnosis_type, "diagnosis": diagnosis, "doctor_note": _clean(getter("doctor_note"))})
    return rows


def _normalize_form_icd10_diagnoses(form: Any) -> list[dict[str, str | None]]:
    """Приводит диагнозы из формы к формату сравнения."""
    rows: list[dict[str, str | None]] = []
    main_diagnosis = _clean(_form_get(form, "icd10_main_diagnosis"))
    if main_diagnosis:
        rows.append({"diagnosis_type": "main", "diagnosis": main_diagnosis, "doctor_note": _clean(_form_get(form, "icd10_main_note"))})
    for diagnosis_type, diagnosis_field, note_field in [
        ("complication", "icd10_complication_diagnosis", "icd10_complication_note"),
        ("comorbidity", "icd10_comorbidity_diagnosis", "icd10_comorbidity_note"),
    ]:
        diagnoses = _form_getlist(form, diagnosis_field)
        notes = _form_getlist(form, note_field)
        for index, diagnosis in enumerate(diagnoses):
            diagnosis_text = _clean(diagnosis)
            if not diagnosis_text:
                continue
            rows.append({"diagnosis_type": diagnosis_type, "diagnosis": diagnosis_text, "doctor_note": _clean(_list_at(notes, index))})
    return rows


def _diagnosis_type_label(diagnosis_type: str) -> str:
    """Русская подпись типа диагноза."""
    return {"main": "Основной диагноз", "complication": "Осложнение", "comorbidity": "Сопутствующий диагноз"}.get(diagnosis_type, "Диагноз")


def _append_icd10_changes(
    changes: list[dict[str, Any]],
    form: Any,
    previous_icd10_diagnoses: list[Any] | None = None,
    *,
    sort_base: int,
) -> None:
    """Фиксирует реальные изменения МКБ-10 диагнозов через сравнение прошлого и текущего приёма."""
    sort_order = sort_base
    current_rows = _normalize_form_icd10_diagnoses(form)
    previous_rows = _normalize_previous_icd10_diagnoses(previous_icd10_diagnoses)
    previous_by_key = {_diagnosis_key(row["diagnosis_type"] or "", row["diagnosis"]): row for row in previous_rows}
    current_by_key = {_diagnosis_key(row["diagnosis_type"] or "", row["diagnosis"]): row for row in current_rows}
    suggested_main = (
        _form_get(form, "icd10_main_diagnosis_autofilled_value")
        or _form_get(form, "icd10_main_diagnosis_suggested")
        or _form_get(form, "icd10_system_main_diagnosis")
        or _form_get(form, "icd10_autofill_main_diagnosis")
    )
    main_user_edited = str(_form_get(form, "icd10_main_diagnosis_user_edited") or "").lower() == "true"
    for row in current_rows:
        diagnosis_type = row["diagnosis_type"] or ""
        key = _diagnosis_key(diagnosis_type, row["diagnosis"])
        previous = previous_by_key.get(key)
        field_label = _diagnosis_type_label(diagnosis_type)
        current_display = _diagnosis_display(row["diagnosis"], row.get("doctor_note"))
        if previous:
            previous_display = _diagnosis_display(previous["diagnosis"], previous.get("doctor_note"))
            if _same(previous.get("doctor_note"), row.get("doctor_note")):
                changes.append(_change("icd10", "icd10_diagnosis", field_label, "diagnosis_continued", new_value=current_display, details="диагноз перенесён в текущий приём без изменений", sort_order=sort_order))
            else:
                changes.append(_change("icd10", "icd10_doctor_note", f"Комментарий: {field_label.lower()}", "diagnosis_note_changed", old_value=previous_display, new_value=current_display, details="код диагноза оставлен, изменён комментарий врача", sort_order=sort_order))
            sort_order += 1
            continue
        if diagnosis_type == "main":
            if _clean(suggested_main):
                if _same(row["diagnosis"], suggested_main) and not main_user_edited:
                    change_type = "accepted_system_main"
                    details = "основной диагноз добавлен автоматически по категории СКФ"
                    old_value = None
                else:
                    change_type = "overridden_system_main"
                    details = "врач изменил основной диагноз, предложенный системой"
                    old_value = suggested_main
            else:
                change_type = "accepted_system_main"
                details = "основной диагноз добавлен автоматически; если врач менял поле вручную, это начнёт фиксироваться после обновления формы МКБ-10"
                old_value = None
        else:
            change_type = "diagnosis_added"
            details = "диагноз добавлен в текущий приём"
            old_value = None
        changes.append(_change("icd10", "icd10_diagnosis", field_label, change_type, old_value=old_value, new_value=current_display, details=details, sort_order=sort_order))
        sort_order += 1
    for previous in previous_rows:
        key = _diagnosis_key(previous["diagnosis_type"] or "", previous["diagnosis"])
        if key in current_by_key:
            continue
        changes.append(_change("icd10", "icd10_diagnosis", _diagnosis_type_label(previous["diagnosis_type"] or ""), "diagnosis_removed", old_value=_diagnosis_display(previous["diagnosis"], previous.get("doctor_note")), details="диагноз был в прошлом приёме, но не перенесён/удалён в текущем сохранении", sort_order=sort_order))
        sort_order += 1



def _humanize_kdigo_option(option: Any) -> str | None:
    """Преобразует технический ключ KDIGO в человеческое описание."""
    option_text = _clean(option)
    if not option_text:
        return None
    parts = option_text.split("|")
    if len(parts) >= 5 and parts[0] == "row":
        gfr_date, gfr_category, albuminuria_date, albuminuria_category = parts[1:5]
        return f"СКФ от {gfr_date}, категория {gfr_category}; альбуминурия от {albuminuria_date}, категория {albuminuria_category}"
    return None


def _append_kdigo_changes(changes: list[dict[str, Any]], form: Any, *, sort_base: int) -> None:
    """Фиксирует сохранённое решение по KDIGO без технических ключей вида row|..."""
    conclusion_text = (_form_get(form, "kdigo_selected_conclusion_text") or _form_get(form, "kdigo_conclusion_text") or _form_get(form, "kdigoSelectedConclusionText"))
    selected_option = _form_get(form, "kdigo_selected_current_option")
    excluded_pairs = _form_getlist(form, "kdigo_excluded_pair")
    if _clean(conclusion_text):
        human_option = _humanize_kdigo_option(selected_option)
        change_type = "selected_by_doctor" if _clean(selected_option) else "accepted_system"
        if change_type == "selected_by_doctor":
            details = "врач выбрал этот прогноз из доступных вариантов"
            if human_option:
                details += f": {human_option}"
        else:
            details = "прогноз сохранён как рассчитанный системой"
        changes.append(_change("kdigo", "kdigo_selected_current_option", "Прогноз KDIGO", change_type, new_value=conclusion_text, details=details, sort_order=sort_base))
    elif excluded_pairs:
        changes.append(_change("kdigo", "kdigo_excluded_pair", "Исключённые варианты KDIGO", "selected_by_doctor", details=f"исключено вариантов: {len(excluded_pairs)}", sort_order=sort_base))


def _append_diet_and_control_changes(
    changes: list[dict[str, Any]],
    form: Any,
    previous: dict[str, Any] | None,
    *,
    sort_base: int,
) -> None:
    """Фиксирует изменения диеты, рекомендаций и даты следующего контроля.

    Дата следующего контроля не переносится автоматически из прошлого приёма, поэтому
    пустое значение в новом приёме не является удалением. В журнале показываем
    человеческий статус «поле не заполнено».
    """
    sort_order = sort_base
    for _, field_name, label in [item for item in PREFILL_TEXT_FIELDS if item[0] == "diet"]:
        _append_if_changed_from_previous(
            changes,
            form,
            previous,
            "diet",
            field_name,
            label,
            sort_order=sort_order,
        )
        sort_order += 1

    current = _form_get(form, "next_control_date")
    previous_value = previous.get("next_control_date") if previous else None

    if _clean(current):
        if _clean(previous_value) and not _same(previous_value, current):
            change_type = "date_changed"
            old_value = previous_value
            details = "дата следующего контроля изменена в текущем приёме"
        else:
            change_type = "date_set"
            old_value = None
            details = "дата следующего контроля заполнена в текущем приёме"
        changes.append(
            _change(
                "diet",
                "next_control_date",
                "Дата следующего контроля",
                change_type,
                old_value=old_value,
                new_value=current,
                details=details,
                sort_order=sort_order,
            )
        )
    else:
        changes.append(
            _change(
                "diet",
                "next_control_date",
                "Дата следующего контроля",
                "field_not_filled",
                details="в текущем приёме дата следующего контроля не заполнена",
                sort_order=sort_order,
            )
        )


def build_patient_creation_audit_changes(
    form: Any,
    *,
    patient_id: int,
    appointment_id: int,
) -> list[dict[str, Any]]:
    """Создаёт подробности аудита для создания нового пациента и первого приёма."""
    changes: list[dict[str, Any]] = [
        _change(
            "patient",
            "patient_id",
            "Пациент",
            "patient_created",
            new_value=patient_id,
            details="создана карточка пациента",
            sort_order=10,
        ),
        _change(
            "appointment",
            "appointment_id",
            "Первый приём",
            "appointment_created",
            new_value=appointment_id,
            details="создан первый приём пациента",
            sort_order=20,
        ),
    ]

    sort_order = 30
    for field_name, label in PATIENT_FIELDS:
        _append_field_created(
            changes,
            form,
            "patient",
            field_name,
            label,
            change_type="filled_new",
            sort_order=sort_order,
        )
        sort_order += 1

    for field_name, label in APPOINTMENT_FIELDS:
        _append_field_created(
            changes,
            form,
            "appointment",
            field_name,
            label,
            change_type="filled_new",
            sort_order=sort_order,
        )
        sort_order += 1

    changes.extend(
        build_appointment_medical_audit_changes(
            form,
            previous_appointment=None,
            previous_medications=None,
            previous_icd10_diagnoses=None,
            appointment_id=appointment_id,
            sort_base=100,
            include_appointment_created=False,
        )
    )
    return changes


def build_appointment_medical_audit_changes(
    form: Any,
    *,
    previous_appointment: dict[str, Any] | None,
    previous_medications: list[Any] | None,
    previous_icd10_diagnoses: list[Any] | None = None,
    appointment_id: int,
    sort_base: int = 10,
    include_appointment_created: bool = True,
) -> list[dict[str, Any]]:
    """Создаёт подробности аудита для сохранённого приёма."""
    changes: list[dict[str, Any]] = []
    if include_appointment_created:
        changes.append(
            _change(
                "appointment",
                "appointment_id",
                "Приём",
                "appointment_created",
                new_value=appointment_id,
                details="создан новый приём",
                sort_order=sort_base,
            )
        )

    sort_order = sort_base + 10
    for section, field_name, label in PREFILL_TEXT_FIELDS:
        if section == "diet":
            continue
        _append_if_changed_from_previous(
            changes,
            form,
            previous_appointment,
            section,
            field_name,
            label,
            sort_order=sort_order,
        )
        sort_order += 1

    sort_order = _append_structured_examination_text_changes(
        changes,
        form,
        previous_appointment,
        sort_base=sort_order,
    )

    for field_name, label in EXAMINATION_NUMERIC_FIELDS:
        _append_if_changed_from_previous(
            changes,
            form,
            previous_appointment,
            "examination",
            field_name,
            label,
            sort_order=sort_order,
        )
        sort_order += 1

    if _clean(_form_get(form, "height")) or _clean(_form_get(form, "weight")):
        changes.append(
            _change(
                "examination",
                "bmi",
                "ИМТ",
                "autocalculated",
                details="ИМТ рассчитывается системой по росту и весу после сохранения",
                sort_order=sort_order,
            )
        )
        sort_order += 1

    _append_lab_changes(changes, form, sort_base=300)
    _append_kdigo_changes(changes, form, sort_base=500)
    _append_icd10_changes(
        changes,
        form,
        previous_icd10_diagnoses=previous_icd10_diagnoses,
        sort_base=600,
    )
    _append_diet_and_control_changes(
        changes,
        form,
        previous_appointment,
        sort_base=700,
    )
    _append_medication_changes(
        changes,
        form,
        previous_medications,
        sort_base=800,
    )

    return changes
