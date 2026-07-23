"""Расширение структуры верхней части формы приёма до раздела исследований.

Revision ID: 0009_previsit_form_schema
Revises: 0008_schedule_admin_mvp
Create Date: 2026-07-22

Назначение миграции
-------------------
1. Закрепляет возраст пациента за конкретным медицинским приёмом.
2. Заменяет два общих текстовых поля анамнеза структурированными полями
   в таблице surveys.
3. Удаляет surveys.comorbidities, потому что после миграции 0004 источником
   истины по диагнозам является связка appointment_icd10_diagnoses.
4. Заменяет examinations.skin_condition на свободное текстовое описание
   кожи и слизистых оболочек.
5. Расширяет объективный осмотр полями из утверждённой схемы формы.
6. Добавляет CHECK-ограничения и русские комментарии к столбцам.

Важно
-----
- Миграция намеренно не меняет код приложения, лабораторные таблицы,
  расписание, назначения и прогноз KDIGO.
- Старые life_anamnesis, disease_anamnesis, comorbidities и skin_condition
  считаются искусственными тестовыми данными и удаляются.
- Новые клинические поля остаются nullable: обязательность будет задаваться
  серверной логикой на втором этапе.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_previsit_form_schema"
down_revision = "0008_schedule_admin_mvp"
branch_labels = None
depends_on = None


def _comment(table_name: str, column_name: str, russian_name: str) -> None:
    """Записывает понятное русское описание столбца в каталог PostgreSQL."""
    escaped = russian_name.replace("'", "''")
    op.execute(
        f"COMMENT ON COLUMN {table_name}.{column_name} IS '{escaped}';"
    )


def upgrade() -> None:
    """Применяет структуру первого этапа формы приёма."""

    # ------------------------------------------------------------------
    # 1. ПРИЁМ: возраст хранится на дату конкретного посещения.
    # ------------------------------------------------------------------
    op.add_column(
        "appointments",
        sa.Column("age_at_appointment", sa.SmallInteger(), nullable=True),
    )

    # Возраст рассчитывается в полных годах по дате приёма и дате рождения.
    op.execute(
        """
        UPDATE appointments AS a
        SET age_at_appointment = EXTRACT(
            YEAR FROM age(a.appointment_date::date, p.birth_date)
        )::smallint
        FROM patients AS p
        WHERE p.id = a.patient_id;
        """
    )

    # Если исторические данные нарушены, останавливаем миграцию понятной
    # ошибкой до установки NOT NULL и CHECK.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM appointments
                WHERE age_at_appointment IS NULL
                   OR age_at_appointment < 0
                   OR age_at_appointment > 130
            ) THEN
                RAISE EXCEPTION
                    'Невозможно заполнить appointments.age_at_appointment: '
                    'проверьте дату рождения пациента и дату приёма';
            END IF;
        END
        $$;
        """
    )

    op.alter_column(
        "appointments",
        "age_at_appointment",
        existing_type=sa.SmallInteger(),
        nullable=False,
    )
    op.create_check_constraint(
        "chk_appointments_age_at_appointment",
        "appointments",
        "age_at_appointment BETWEEN 0 AND 130",
    )

    # ------------------------------------------------------------------
    # 2. ОПРОС И АНАМНЕЗ.
    # Каждый пункт утверждённой формы получает отдельный столбец.
    # ------------------------------------------------------------------
    op.add_column("surveys", sa.Column("education_and_professional_history", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("housing_conditions", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("past_diseases", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("habitual_intoxications", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("gynecological_history", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("family_life", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("allergological_history", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("epidemiological_history", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("insurance_history", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("disease_onset", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("disease_course", sa.Text(), nullable=True))

    # Нормализуем старое тестовое поле наследственности перед ограничением:
    # FALSE означает отсутствие описания; NULL трактуем как FALSE.
    op.execute("UPDATE surveys SET heredity = FALSE WHERE heredity IS NULL;")
    op.execute(
        "UPDATE surveys SET heredity_description = NULL WHERE heredity = FALSE;"
    )
    op.execute(
        """
        UPDATE surveys
        SET heredity = FALSE,
            heredity_description = NULL
        WHERE heredity = TRUE
          AND NULLIF(BTRIM(heredity_description), '') IS NULL;
        """
    )
    op.alter_column(
        "surveys",
        "heredity",
        existing_type=sa.Boolean(),
        nullable=False,
        server_default=sa.text("false"),
    )
    op.create_check_constraint(
        "chk_surveys_heredity_description",
        "surveys",
        """
        (heredity = TRUE AND NULLIF(BTRIM(heredity_description), '') IS NOT NULL)
        OR
        (heredity = FALSE AND heredity_description IS NULL)
        """,
    )

    # Старые сводные поля намеренно удаляются: данные в них тестовые,
    # а их смысл полностью заменён структурированными полями выше.
    op.drop_column("surveys", "life_anamnesis")
    op.drop_column("surveys", "disease_anamnesis")
    op.drop_column("surveys", "comorbidities")

    # ------------------------------------------------------------------
    # 3. ОБЪЕКТИВНЫЙ ОСМОТР.
    # Рост, вес, ИМТ, АД, ЧСС и отёки сохраняются в прежних столбцах.
    # ------------------------------------------------------------------
    op.add_column("examinations", sa.Column("general_condition", sa.String(length=30), nullable=True))
    op.add_column("examinations", sa.Column("consciousness", sa.String(length=30), nullable=True))
    op.add_column("examinations", sa.Column("bed_position", sa.String(length=30), nullable=True))
    op.add_column("examinations", sa.Column("bed_position_details", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("body_build", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("constitution_type", sa.String(length=30), nullable=True))
    op.add_column("examinations", sa.Column("skin_and_mucous_membranes", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("lymph_nodes", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("thyroid_gland", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("musculoskeletal_system", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("body_temperature", sa.Numeric(4, 1), nullable=True))
    op.add_column("examinations", sa.Column("veins_condition", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("lung_auscultation", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("abdomen", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("kidney_palpation", sa.String(length=30), nullable=True))
    op.add_column("examinations", sa.Column("kidney_palpation_details", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("pasternatsky_result", sa.String(length=20), nullable=True))
    op.add_column("examinations", sa.Column("pasternatsky_side", sa.String(length=20), nullable=True))

    # Старая кожа из checkbox-значений удаляется и не переносится.
    op.drop_column("examinations", "skin_condition")

    # Разрешённые значения выпадающих списков.
    op.create_check_constraint(
        "chk_examinations_general_condition",
        "examinations",
        "general_condition IS NULL OR general_condition IN ('satisfactory', 'moderate', 'severe')",
    )
    op.create_check_constraint(
        "chk_examinations_consciousness",
        "examinations",
        "consciousness IS NULL OR consciousness IN ('clear', 'confused', 'sopor', 'coma')",
    )
    op.create_check_constraint(
        "chk_examinations_bed_position",
        "examinations",
        "bed_position IS NULL OR bed_position IN ('active', 'passive', 'forced')",
    )
    op.create_check_constraint(
        "chk_examinations_bed_position_details",
        "examinations",
        """
        (bed_position = 'forced' AND NULLIF(BTRIM(bed_position_details), '') IS NOT NULL)
        OR
        (bed_position IS DISTINCT FROM 'forced' AND bed_position_details IS NULL)
        """,
    )
    op.create_check_constraint(
        "chk_examinations_constitution_type",
        "examinations",
        "constitution_type IS NULL OR constitution_type IN ('normosthenic', 'asthenic', 'hypersthenic')",
    )
    op.create_check_constraint(
        "chk_examinations_body_temperature",
        "examinations",
        "body_temperature IS NULL OR body_temperature BETWEEN 25.0 AND 45.0",
    )
    op.create_check_constraint(
        "chk_examinations_kidney_palpation",
        "examinations",
        "kidney_palpation IS NULL OR kidney_palpation IN ('palpable', 'not_palpable')",
    )
    op.create_check_constraint(
        "chk_examinations_kidney_palpation_details",
        "examinations",
        "kidney_palpation <> 'palpable' OR NULLIF(BTRIM(kidney_palpation_details), '') IS NOT NULL",
    )
    op.create_check_constraint(
        "chk_examinations_pasternatsky_result",
        "examinations",
        "pasternatsky_result IS NULL OR pasternatsky_result IN ('positive', 'negative')",
    )
    op.create_check_constraint(
        "chk_examinations_pasternatsky_side",
        "examinations",
        "pasternatsky_side IS NULL OR pasternatsky_side IN ('right', 'left', 'bilateral')",
    )
    op.create_check_constraint(
        "chk_examinations_pasternatsky_pair",
        "examinations",
        """
        (pasternatsky_result IS NULL AND pasternatsky_side IS NULL)
        OR
        (pasternatsky_result IS NOT NULL AND pasternatsky_side IS NOT NULL)
        """,
    )

    # ------------------------------------------------------------------
    # 4. РУССКИЕ КОММЕНТАРИИ В СХЕМЕ POSTGRESQL.
    # Они видны в DBeaver/pgAdmin и помогают понимать назначение полей.
    # ------------------------------------------------------------------
    _comment("appointments", "id", "Идентификатор медицинского приёма")
    _comment("appointments", "patient_id", "Пациент")
    _comment("appointments", "doctor_id", "Врач")
    _comment("appointments", "location_id", "Место проведения приёма")
    _comment("appointments", "appointment_date", "Дата и время приёма")
    _comment("appointments", "age_at_appointment", "Возраст пациента в полных годах на дату приёма")

    survey_comments = {
        "id": "Идентификатор опроса",
        "appointment_id": "Медицинский приём",
        "complaints": "Жалобы",
        "education_and_professional_history": "Образование и профессиональный анамнез",
        "housing_conditions": "Жилищные условия",
        "past_diseases": "Перенесённые заболевания",
        "habitual_intoxications": "Привычные интоксикации",
        "gynecological_history": "Гинекологический анамнез",
        "heredity": "Признак отягощённой наследственности",
        "heredity_description": "Описание наследственности",
        "family_life": "Семейная жизнь",
        "allergological_history": "Аллергологический анамнез",
        "epidemiological_history": "Эпидемиологический анамнез",
        "insurance_history": "Страховой анамнез",
        "disease_onset": "Начало заболевания",
        "disease_course": "Течение заболевания",
    }
    for column_name, russian_name in survey_comments.items():
        _comment("surveys", column_name, russian_name)

    examination_comments = {
        "id": "Идентификатор объективного осмотра",
        "appointment_id": "Медицинский приём",
        "general_condition": "Общее состояние",
        "consciousness": "Сознание",
        "bed_position": "Положение в постели",
        "bed_position_details": "Особенности вынужденного положения в постели",
        "body_build": "Телосложение",
        "height": "Рост, см",
        "weight": "Вес, кг",
        "bmi": "Индекс массы тела, кг/м²",
        "constitution_type": "Тип конституции",
        "skin_and_mucous_membranes": "Кожа и слизистые оболочки",
        "edema_location": "Периферические отёки и серозиты; структура хранения не изменена",
        "lymph_nodes": "Лимфатические узлы",
        "thyroid_gland": "Щитовидная железа",
        "musculoskeletal_system": "Опорно-двигательный аппарат",
        "body_temperature": "Температура тела, °C",
        "systolic_pressure": "Систолическое артериальное давление, мм рт. ст.",
        "diastolic_pressure": "Диастолическое артериальное давление, мм рт. ст.",
        "bp_note": "Примечание к измерению артериального давления",
        "heart_rate": "Частота сердечных сокращений, уд/мин",
        "veins_condition": "Состояние вен",
        "lung_auscultation": "Аускультация лёгких",
        "abdomen": "Живот",
        "kidney_palpation": "Пальпация почек: пальпируются или не пальпируются",
        "kidney_palpation_details": "Уточнение результатов пальпации почек",
        "pasternatsky_result": "Результат симптома Пастернацкого",
        "pasternatsky_side": "Сторона симптома Пастернацкого",
    }
    for column_name, russian_name in examination_comments.items():
        _comment("examinations", column_name, russian_name)


def downgrade() -> None:
    """Возвращает структуру к состоянию 0008.

    Полный исходный искусственный текст восстановить невозможно. Для более
    безопасного отката часть новых данных собирается обратно в старые поля.
    """

    # Удаляем ограничения, зависящие от новых столбцов.
    for constraint_name in (
        "chk_examinations_pasternatsky_pair",
        "chk_examinations_pasternatsky_side",
        "chk_examinations_pasternatsky_result",
        "chk_examinations_kidney_palpation_details",
        "chk_examinations_kidney_palpation",
        "chk_examinations_body_temperature",
        "chk_examinations_constitution_type",
        "chk_examinations_bed_position_details",
        "chk_examinations_bed_position",
        "chk_examinations_consciousness",
        "chk_examinations_general_condition",
    ):
        op.drop_constraint(constraint_name, "examinations", type_="check")

    op.drop_constraint("chk_surveys_heredity_description", "surveys", type_="check")
    op.drop_constraint("chk_appointments_age_at_appointment", "appointments", type_="check")

    # Возвращаем старые столбцы, необходимые версии приложения до этапа 2.
    op.add_column("surveys", sa.Column("life_anamnesis", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("disease_anamnesis", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("comorbidities", sa.Text(), nullable=True))
    op.add_column("examinations", sa.Column("skin_condition", sa.Text(), nullable=True))

    # Собираем структурированные тексты в читаемый legacy-формат.
    op.execute(
        """
        UPDATE surveys
        SET life_anamnesis = concat_ws(E'\n',
                CASE WHEN NULLIF(BTRIM(education_and_professional_history), '') IS NOT NULL
                     THEN 'Образование и профессиональный анамнез: ' || education_and_professional_history END,
                CASE WHEN NULLIF(BTRIM(housing_conditions), '') IS NOT NULL
                     THEN 'Жилищные условия: ' || housing_conditions END,
                CASE WHEN NULLIF(BTRIM(past_diseases), '') IS NOT NULL
                     THEN 'Перенесённые заболевания: ' || past_diseases END,
                CASE WHEN NULLIF(BTRIM(habitual_intoxications), '') IS NOT NULL
                     THEN 'Привычные интоксикации: ' || habitual_intoxications END,
                CASE WHEN NULLIF(BTRIM(gynecological_history), '') IS NOT NULL
                     THEN 'Гинекологический анамнез: ' || gynecological_history END,
                CASE WHEN NULLIF(BTRIM(family_life), '') IS NOT NULL
                     THEN 'Семейная жизнь: ' || family_life END,
                CASE WHEN NULLIF(BTRIM(allergological_history), '') IS NOT NULL
                     THEN 'Аллергологический анамнез: ' || allergological_history END,
                CASE WHEN NULLIF(BTRIM(epidemiological_history), '') IS NOT NULL
                     THEN 'Эпидемиологический анамнез: ' || epidemiological_history END,
                CASE WHEN NULLIF(BTRIM(insurance_history), '') IS NOT NULL
                     THEN 'Страховой анамнез: ' || insurance_history END
            ),
            disease_anamnesis = concat_ws(E'\n',
                CASE WHEN NULLIF(BTRIM(disease_onset), '') IS NOT NULL
                     THEN 'Начало болезни: ' || disease_onset END,
                CASE WHEN NULLIF(BTRIM(disease_course), '') IS NOT NULL
                     THEN 'Течение заболевания: ' || disease_course END
            ),
            comorbidities = NULL;
        """
    )
    op.execute(
        "UPDATE examinations SET skin_condition = skin_and_mucous_membranes;"
    )

    # Удаляем новые поля осмотра в обратном порядке.
    for column_name in (
        "pasternatsky_side",
        "pasternatsky_result",
        "kidney_palpation_details",
        "kidney_palpation",
        "abdomen",
        "lung_auscultation",
        "veins_condition",
        "body_temperature",
        "musculoskeletal_system",
        "thyroid_gland",
        "lymph_nodes",
        "skin_and_mucous_membranes",
        "constitution_type",
        "body_build",
        "bed_position_details",
        "bed_position",
        "consciousness",
        "general_condition",
    ):
        op.drop_column("examinations", column_name)

    # Удаляем новые поля опроса.
    for column_name in (
        "disease_course",
        "disease_onset",
        "insurance_history",
        "epidemiological_history",
        "allergological_history",
        "family_life",
        "gynecological_history",
        "habitual_intoxications",
        "past_diseases",
        "housing_conditions",
        "education_and_professional_history",
    ):
        op.drop_column("surveys", column_name)

    # В старой схеме heredity допускал NULL и имел DEFAULT FALSE.
    op.alter_column(
        "surveys",
        "heredity",
        existing_type=sa.Boolean(),
        nullable=True,
        server_default=sa.text("false"),
    )

    op.drop_column("appointments", "age_at_appointment")

    _comment("surveys", "life_anamnesis", "Анамнез жизни в старом сводном формате")
    _comment("surveys", "disease_anamnesis", "Анамнез заболевания в старом сводном формате")
    _comment("surveys", "comorbidities", "Старое свободное текстовое поле сопутствующих заболеваний")
    _comment("examinations", "skin_condition", "Старое описание состояния кожи")
