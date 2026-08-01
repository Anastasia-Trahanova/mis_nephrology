"""Справочник препаратов, группы назначений и тестовые назначения.

Revision ID: 0015_grouped_prescriptions
Revises: 0014_ckd_registry_roles
Create Date: 2026-08-01

Миграция предназначена для текущей тестовой базы:
- очищает старый справочник лекарств;
- заполняет его согласованными названиями;
- добавляет prescriptions.therapy_group;
- заменяет назначения тестовыми: по 5 групп на каждый существующий приём.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0015_grouped_prescriptions"
down_revision = "0014_ckd_registry_roles"
branch_labels = None
depends_on = None


THERAPY_GROUPS = (
    "Коррекция АД, ЧСС",
    "Нефропротекция",
    "Коррекция гиперлипидемии",
    "Коррекция анемии",
    "Другие препараты",
)


# display_name, active_substance, sort_order
MEDICATIONS = (
    ("Лозартан", "лозартан", 10),
    ("Бисопролол", "бисопролол", 20),
    ("Метопролол", "метопролол", 30),
    ("Карведилол", "карведилол", 40),
    ("Амлодипин", "амлодипин", 50),
    ("Лерканидипин", "лерканидипин", 60),
    ("Нифедипин", "нифедипин", 70),
    (
        "Нифедипин с модифицированным высвобождением",
        "нифедипин",
        80,
    ),
    ("Спиронолактон", "спиронолактон", 90),
    ("Индапамид", "индапамид", 100),
    ("Торасемид", "торасемид", 110),
    ("Фуросемид", "фуросемид", 120),
    ("Моксонидин", "моксонидин", 130),
    ("Дапаглифлозин", "дапаглифлозин", 140),
    ("Эмпаглифлозин", "эмпаглифлозин", 150),
    ("Финеренон", "финеренон", 160),
    ("Аторвастатин", "аторвастатин", 170),
    ("Розувастатин", "розувастатин", 180),
    ("Питавастатин", "питавастатин", 190),
    ("Эзетимиб", "эзетимиб", 200),
    (
        "Железа III гидроксид полимальтозат",
        "железа III гидроксид полимальтозат",
        210,
    ),
    (
        "Железа III гидроксид полисахарозный комплекс",
        "железа III гидроксид полисахарозный комплекс",
        220,
    ),
    ("Эпоэтин альфа", "эпоэтин альфа", 230),
    ("Эпоэтин бета", "эпоэтин бета", 240),
    (
        "Метоксиполиэтиленгликоль-эпоэтин бета",
        "метоксиполиэтиленгликоль-эпоэтин бета",
        250,
    ),
    ("Аллопуринол", "аллопуринол", 260),
    ("Фебуксостат", "фебуксостат", 270),
)


# Варианты нужны только для тестового наполнения текущих приёмов.
# На каждый приём будет выбрано по одному назначению из каждой группы.
PRESCRIPTION_VARIANTS = {
    "Коррекция АД, ЧСС": (
        ("Лозартан", "50 мг", "1 раз утром"),
        ("Бисопролол", "5 мг", "1 раз утром"),
        ("Амлодипин", "5 мг", "1 раз вечером"),
        ("Карведилол", "12,5 мг", "2 раза в день"),
        ("Торасемид", "10 мг", "1 раз утром"),
        ("Моксонидин", "0,2 мг", "1 раз вечером"),
    ),
    "Нефропротекция": (
        ("Дапаглифлозин", "10 мг", "1 раз утром"),
        ("Эмпаглифлозин", "10 мг", "1 раз утром"),
        ("Финеренон", "10 мг", "1 раз в день"),
        ("Лозартан", "50 мг", "1 раз вечером"),
    ),
    "Коррекция гиперлипидемии": (
        ("Аторвастатин", "20 мг", "1 раз вечером"),
        ("Розувастатин", "10 мг", "1 раз вечером"),
        ("Питавастатин", "2 мг", "1 раз вечером"),
        ("Эзетимиб", "10 мг", "1 раз в день"),
    ),
    "Коррекция анемии": (
        (
            "Железа III гидроксид полимальтозат",
            "100 мг",
            "1 раз в день после еды",
        ),
        (
            "Железа III гидроксид полисахарозный комплекс",
            "100 мг",
            "по индивидуальной схеме",
        ),
        ("Эпоэтин альфа", "4000 МЕ", "3 раза в неделю"),
        ("Эпоэтин бета", "4000 МЕ", "2 раза в неделю"),
        (
            "Метоксиполиэтиленгликоль-эпоэтин бета",
            "50 мкг",
            "1 раз в месяц",
        ),
    ),
    "Другие препараты": (
        ("Аллопуринол", "100 мг", "1 раз в день после еды"),
        ("Фебуксостат", "40 мг", "1 раз в день"),
    ),
}


def _therapy_group_check() -> str:
    allowed = ", ".join("'" + value.replace("'", "''") + "'" for value in THERAPY_GROUPS)
    return f"therapy_group IS NULL OR therapy_group IN ({allowed})"


def upgrade() -> None:
    # NULL временно разрешён: старый код формы ещё не передаёт therapy_group.
    # После обновления формы ограничение можно ужесточить отдельной миграцией.
    op.add_column(
        "prescriptions",
        sa.Column("therapy_group", sa.String(length=64), nullable=True),
    )
    op.create_check_constraint(
        "ck_prescriptions_therapy_group",
        "prescriptions",
        _therapy_group_check(),
    )
    op.create_index(
        "idx_prescriptions_therapy_group",
        "prescriptions",
        ["therapy_group"],
    )

    # Это тестовые данные: старые назначения заменяются полностью.
    op.execute("TRUNCATE TABLE prescriptions RESTART IDENTITY")

    # Оставляем в справочнике только согласованные названия для подсказок.
    op.execute("TRUNCATE TABLE medications RESTART IDENTITY")
    medications_table = sa.table(
        "medications",
        sa.column("display_name", sa.String),
        sa.column("trade_name", sa.String),
        sa.column("active_substance", sa.String),
        sa.column("drug_group", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        medications_table,
        [
            {
                "display_name": display_name,
                "trade_name": None,
                "active_substance": active_substance,
                "drug_group": None,
                "sort_order": sort_order,
                "is_active": True,
            }
            for display_name, active_substance, sort_order in MEDICATIONS
        ],
    )

    bind = op.get_bind()
    appointment_ids = [
        int(row[0])
        for row in bind.execute(sa.text("SELECT id FROM appointments ORDER BY id"))
    ]

    prescriptions_table = sa.table(
        "prescriptions",
        sa.column("appointment_id", sa.Integer),
        sa.column("therapy_group", sa.String),
        sa.column("medication", sa.String),
        sa.column("dosage", sa.String),
        sa.column("schedule", sa.String),
    )

    rows: list[dict[str, object]] = []
    for appointment_index, appointment_id in enumerate(appointment_ids):
        for group_index, therapy_group in enumerate(THERAPY_GROUPS):
            variants = PRESCRIPTION_VARIANTS[therapy_group]
            # Сдвиг по группе делает сочетания между приёмами разнообразнее.
            medication, dosage, schedule = variants[
                (appointment_index + group_index) % len(variants)
            ]
            rows.append(
                {
                    "appointment_id": appointment_id,
                    "therapy_group": therapy_group,
                    "medication": medication,
                    "dosage": dosage,
                    "schedule": schedule,
                }
            )

    if rows:
        op.bulk_insert(prescriptions_table, rows)


def downgrade() -> None:
    raise RuntimeError(
        "Миграция 0015 необратимо заменяет тестовые prescriptions и medications; "
        "автоматический downgrade намеренно запрещён."
    )
