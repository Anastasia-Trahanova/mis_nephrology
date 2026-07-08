"""Лабораторные и инструментальные разделы Word-заключения."""

from __future__ import annotations

from .formatting import add_history_table


def add_lab_sections(doc, context):
    labs = context["labs"]

    add_history_table(
        doc,
        "Общий анализ крови",
        labs["cbc_history"],
        [
            ("Гемоглобин", "hemoglobin"),
            ("Эритроциты", "erythrocytes"),
            ("Лейкоциты", "leukocytes"),
            ("Тромбоциты", "platelets"),
            ("СОЭ", "esr"),
            ("MCV", "mcv"),
            ("Гематокрит", "hematocrit"),
        ],
    )
    add_history_table(
        doc,
        "Биохимический анализ крови",
        labs["biochemistry_history"],
        [
            ("Креатинин", "creatinine"),
            ("Мочевина", "urea"),
            ("Мочевая кислота", "uric_acid"),
            ("Глюкоза", "glucose"),
            ("Общий белок", "total_protein"),
            ("Альбумин", "albumin"),
            ("Калий", "potassium"),
            ("Кальций", "calcium"),
            ("Фосфор", "phosphorus"),
            ("Ферритин", "ferritin"),
            ("ПТГ", "ptg"),
        ],
    )
    add_history_table(
        doc,
        "Общий анализ мочи",
        labs["urinalysis_history"],
        [
            ("Удельный вес", "specific_gravity"),
            ("Белок", "protein"),
            ("Лейкоциты", "leukocytes"),
            ("Эритроциты", "erythrocytes"),
            ("Бактерии", "bacteria"),
        ],
    )
    add_history_table(
        doc,
        "Скорость клубочковой фильтрации",
        labs["metrics_history"],
        [
            ("Креатинин крови, мкмоль/л", "creatinine"),
            ("СКФ CKD-EPI, мл/мин/1.73 м²", "egfr_ckdepi"),
            ("СКФ Кокрофт-Голт, мл/мин", "crcl_cockcroft_gault"),
            ("Категория СКФ", "ckd_stage"),
        ],
    )
    add_history_table(
        doc,
        "Альбуминурия по KDIGO",
        labs["albuminuria_history"],
        [
            ("Альбумин мочи", "urine_albumin_display"),
            ("Креатинин мочи", "urine_creatinine_display"),
            ("ACR, мг/ммоль", "albumin_creatinine_ratio"),
            ("Категория альбуминурии", "albuminuria_category"),
        ],
    )
    add_history_table(
        doc,
        "УЗИ почек",
        labs["ultrasound_history"],
        [
            ("Размер левой почки", "left_kidney_size"),
            ("Размер правой почки", "right_kidney_size"),
            ("Паренхима слева", "left_parenchyma"),
            ("Паренхима справа", "right_parenchyma"),
            ("Описание", "description"),
        ],
    )
