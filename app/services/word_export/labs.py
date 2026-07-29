"""Лабораторные и инструментальные разделы Word-заключения."""

from __future__ import annotations

from .formatting import add_field_inline, add_history_table, add_table_title, has_value


def _last_three(records):
    """Истории приходят по возрастанию даты; в Word остаются три последние записи."""
    return list(records or [])[-3:]


def _has_record_values(records, fields) -> bool:
    return any(
        has_value(record.get(key))
        for record in records or []
        for _, key in fields
    )


def add_lab_sections(doc, context):
    """Выводит только реально заполненные исследования в порядке ЭМК."""
    appointment = context["appointment"]
    labs = context["labs"]

    sections = [
        (
            "Общий анализ крови",
            _last_three(labs["cbc_history"]),
            [
                ("Гемоглобин, г/л", "hemoglobin"),
                ("Эритроциты, ×10¹²/л", "erythrocytes"),
                ("Лейкоциты, ×10⁹/л", "leukocytes"),
                ("Тромбоциты, ×10⁹/л", "platelets"),
                ("СОЭ, мм/ч", "esr"),
                ("MCV, фл", "mcv"),
                ("Гематокрит, %", "hematocrit"),
            ],
        ),
        (
            "Общий анализ мочи",
            _last_three(labs["urinalysis_history"]),
            [
                ("Удельный вес", "specific_gravity"),
                ("Белок, г/л", "protein"),
                ("Лейкоциты", "leukocytes"),
                ("Эритроциты", "erythrocytes"),
                ("Бактерии", "bacteria"),
            ],
        ),
        (
            "Биохимический анализ крови",
            _last_three(labs["biochemistry_history"]),
            [
                ("Креатинин, мкмоль/л", "creatinine"),
                ("Мочевина, ммоль/л", "urea"),
                ("Мочевая кислота, мкмоль/л", "uric_acid"),
                ("Глюкоза, ммоль/л", "glucose"),
                ("Общий белок, г/л", "total_protein"),
                ("Альбумин, г/л", "albumin"),
                ("Калий, ммоль/л", "potassium"),
                ("Кальций, ммоль/л", "calcium"),
                ("Фосфор, ммоль/л", "phosphorus"),
                ("Ферритин, нг/мл", "ferritin"),
                ("ПТГ, пг/мл", "ptg"),
            ],
        ),
        (
            "Расчётные показатели",
            _last_three(labs["metrics_history"]),
            [
                ("СКФ CKD-EPI, мл/мин/1,73 м²", "egfr_ckdepi"),
                ("СКФ Кокрофт–Голт, мл/мин", "crcl_cockcroft_gault"),
                ("Стадия ХБП по СКФ", "ckd_stage"),
            ],
        ),
        (
            "Альбуминурия по KDIGO",
            _last_three(labs["albuminuria_history"]),
            [
                ("Альбумин мочи", "urine_albumin_display"),
                ("Креатинин мочи", "urine_creatinine_display"),
                ("Экскреция альбумина суточная, мг/сут", "daily_albumin_excretion"),
                ("Альбумин/креатинин мочи, мг/ммоль", "albumin_creatinine_ratio"),
                ("Категория альбуминурии", "albuminuria_category"),
            ],
        ),
        (
            "УЗИ почек",
            _last_three(labs["ultrasound_history"]),
            [
                ("Правая почка, размер, мм", "right_kidney_size"),
                ("Паренхима справа, мм", "right_parenchyma"),
                ("Левая почка, размер, мм", "left_kidney_size"),
                ("Паренхима слева, мм", "left_parenchyma"),
                ("Дополнительно", "description"),
            ],
        ),
    ]

    has_any = any(_has_record_values(records, fields) for _, records, fields in sections)
    has_any = has_any or has_value(appointment.get("other_laboratory_studies"))
    has_any = has_any or has_value(appointment.get("other_instrumental_studies"))
    if not has_any:
        return

    add_table_title(doc, "Результаты проведённых ранее исследований")

    # Порядок соответствует карточке: ОАК, ОАМ, биохимия, расчёты,
    # альбуминурия, другие лабораторные данные, УЗИ, другие инструменты.
    for title, records, fields in sections[:5]:
        add_history_table(doc, title, records, fields)

    add_field_inline(
        doc,
        "Другие лабораторные исследования",
        appointment.get("other_laboratory_studies"),
        space_before=5,
    )

    title, records, fields = sections[5]
    add_history_table(doc, title, records, fields)

    add_field_inline(
        doc,
        "Другие инструментальные исследования",
        appointment.get("other_instrumental_studies"),
        space_before=5,
    )
