"""Repository для структурированного анамнеза и жалоб приёма."""

from __future__ import annotations

from typing import Any


def insert_survey(cur: Any, appointment_id: int, survey_data: dict[str, Any]) -> None:
    """Сохраняет верхнюю часть истории болезни в структуру миграции 0009."""
    cur.execute(
        """
        INSERT INTO surveys (
            appointment_id,
            complaints,
            education_and_professional_history,
            housing_conditions,
            past_diseases,
            habitual_intoxications,
            gynecological_history,
            heredity,
            heredity_description,
            family_life,
            allergological_history,
            epidemiological_history,
            insurance_history,
            disease_onset,
            disease_course
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
        """,
        (
            appointment_id,
            survey_data.get("complaints"),
            survey_data.get("education_and_professional_history"),
            survey_data.get("housing_conditions"),
            survey_data.get("past_diseases"),
            survey_data.get("habitual_intoxications"),
            survey_data.get("gynecological_history"),
            survey_data.get("heredity", False),
            survey_data.get("heredity_description"),
            survey_data.get("family_life"),
            survey_data.get("allergological_history"),
            survey_data.get("epidemiological_history"),
            survey_data.get("insurance_history"),
            survey_data.get("disease_onset"),
            survey_data.get("disease_course"),
        ),
    )
