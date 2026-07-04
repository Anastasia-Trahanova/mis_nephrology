"""
Repository для таблицы surveys.

Отвечает только за сохранение раздела «Опрос» конкретного приёма.
Подготовка данных формы выполняется выше, в appointment_form_parser.py.
"""

from __future__ import annotations

from typing import Any


def insert_survey(cur: Any, appointment_id: int, survey_data: dict[str, Any]) -> None:
    """Сохраняет анамнез, жалобы, наследственность и сопутствующие заболевания."""
    cur.execute(
        """
        INSERT INTO surveys (
            appointment_id,
            life_anamnesis,
            disease_anamnesis,
            complaints,
            heredity,
            heredity_description,
            comorbidities
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            appointment_id,
            survey_data.get("life_anamnesis"),
            survey_data.get("disease_anamnesis"),
            survey_data.get("complaints"),
            survey_data.get("heredity"),
            survey_data.get("heredity_description"),
            survey_data.get("comorbidities"),
        ),
    )
