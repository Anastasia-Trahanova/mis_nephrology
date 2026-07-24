"""Repository свободных описаний дополнительных исследований приёма.

Назначение файла
----------------
Сохраняет два необязательных текстовых поля из утверждённой схемы истории
болезни:
- другие лабораторные исследования;
- другие инструментальные исследования.

Что редактировать здесь
-----------------------
- SQL сохранения таблицы appointment_additional_studies;
- состав полей этой небольшой таблицы при последующем расширении схемы.

Что не редактировать здесь
--------------------------
- таблицы ОАК, ОАМ, биохимии, альбуминурии и УЗИ;
- расчёты СКФ, категории альбуминурии и KDIGO;
- лекарства и назначения;
- внешний вид формы и карточки пациента.
"""

from __future__ import annotations

from typing import Any


def upsert_appointment_additional_studies(
    cur: Any,
    appointment_id: int,
    data: dict[str, Any],
) -> None:
    """Сохраняет свободные исследования, если заполнено хотя бы одно поле."""
    other_laboratory_studies = data.get("other_laboratory_studies")
    other_instrumental_studies = data.get("other_instrumental_studies")

    if not (other_laboratory_studies or other_instrumental_studies):
        return

    cur.execute(
        """
        INSERT INTO appointment_additional_studies (
            appointment_id,
            other_laboratory_studies,
            other_instrumental_studies
        )
        VALUES (%s, %s, %s)
        ON CONFLICT (appointment_id) DO UPDATE SET
            other_laboratory_studies = EXCLUDED.other_laboratory_studies,
            other_instrumental_studies = EXCLUDED.other_instrumental_studies
        """,
        (
            appointment_id,
            other_laboratory_studies,
            other_instrumental_studies,
        ),
    )
