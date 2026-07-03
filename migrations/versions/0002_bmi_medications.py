"""add BMI and medications dictionary

Revision ID: 0002_bmi_medications
Revises: 0001_baseline_schema
Create Date: 2026-07-03
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_bmi_medications"
down_revision = "0001_baseline_schema"
branch_labels = None
depends_on = None


MEDICATIONS = [
    # display_name, trade_name, active_substance, drug_group, sort_order
    ("Форсига (дапаглифлозин)", "Форсига", "дапаглифлозин", "SGLT2-ингибитор", 10),
    ("Джардинс (эмпаглифлозин)", "Джардинс", "эмпаглифлозин", "SGLT2-ингибитор", 20),
    ("Керендиа (финеренон)", "Керендиа", "финеренон", "антагонист минералокортикоидных рецепторов", 30),

    ("Эналаприл", "Эналаприл", "эналаприл", "ингибитор АПФ", 100),
    ("Периндоприл", "Периндоприл", "периндоприл", "ингибитор АПФ", 110),
    ("Рамиприл", "Рамиприл", "рамиприл", "ингибитор АПФ", 120),
    ("Лизиноприл", "Лизиноприл", "лизиноприл", "ингибитор АПФ", 130),

    ("Лозап (лозартан)", "Лозап", "лозартан", "БРА / сартан", 200),
    ("Валсартан", "Валсартан", "валсартан", "БРА / сартан", 210),
    ("Телмисартан", "Телмисартан", "телмисартан", "БРА / сартан", 220),
    ("Кандесартан", "Кандесартан", "кандесартан", "БРА / сартан", 230),

    ("Амлодипин", "Амлодипин", "амлодипин", "блокатор кальциевых каналов", 300),
    ("Леркамен (лерканидипин)", "Леркамен", "лерканидипин", "блокатор кальциевых каналов", 310),
    ("Бисопролол", "Бисопролол", "бисопролол", "бета-блокатор", 400),
    ("Небиволол", "Небиволол", "небиволол", "бета-блокатор", 410),
    ("Моксонидин", "Моксонидин", "моксонидин", "антигипертензивный препарат центрального действия", 420),

    ("Фуросемид", "Фуросемид", "фуросемид", "петлевой диуретик", 500),
    ("Торасемид", "Торасемид", "торасемид", "петлевой диуретик", 510),
    ("Индапамид", "Индапамид", "индапамид", "тиазидоподобный диуретик", 520),
    ("Спиронолактон", "Спиронолактон", "спиронолактон", "антагонист минералокортикоидных рецепторов", 530),
    ("Эплеренон", "Эплеренон", "эплеренон", "антагонист минералокортикоидных рецепторов", 540),

    ("Аторвастатин", "Аторвастатин", "аторвастатин", "статин", 600),
    ("Розувастатин", "Розувастатин", "розувастатин", "статин", 610),
    ("Эзетимиб", "Эзетимиб", "эзетимиб", "гиполипидемический препарат", 620),

    ("Метформин", "Метформин", "метформин", "сахароснижающий препарат", 700),
    ("Семаглутид", "Семаглутид", "семаглутид", "агонист рецепторов ГПП-1", 710),

    ("Аллопуринол", "Аллопуринол", "аллопуринол", "противоподагрический препарат", 800),
    ("Фебуксостат", "Фебуксостат", "фебуксостат", "противоподагрический препарат", 810),

    ("Кетостерил", "Кетостерил", "кетоаналоги аминокислот", "нутритивная поддержка при ХБП", 900),
    ("Севеламер", "Севеламер", "севеламер", "фосфатсвязывающий препарат", 910),
]


def upgrade() -> None:
    # 1. ИМТ храним там же, где уже хранятся рост и вес на приеме.
    op.add_column(
        "examinations",
        sa.Column("bmi", sa.Numeric(5, 2), nullable=True),
    )

    # Заполняем ИМТ для уже существующих осмотров.
    # height хранится в сантиметрах, weight — в килограммах.
    op.execute(
        """
        UPDATE examinations
        SET bmi = ROUND((weight / POWER(height / 100.0, 2))::numeric, 2)
        WHERE height IS NOT NULL
          AND weight IS NOT NULL
          AND height > 0
          AND weight > 0;
        """
    )

    # Пересоздаем CHECK антропометрии с учетом BMI.
    op.execute("ALTER TABLE examinations DROP CONSTRAINT IF EXISTS chk_examinations_anthropometry;")
    op.execute(
        """
        ALTER TABLE examinations
            ADD CONSTRAINT chk_examinations_anthropometry
            CHECK (
                (height IS NULL OR height BETWEEN 50 AND 250)
                AND (weight IS NULL OR weight BETWEEN 20 AND 300)
                AND (bmi IS NULL OR bmi BETWEEN 5 AND 100)
            );
        """
    )

    # 2. Справочник лекарств.
    # Пока не меняем prescriptions: в назначение по-прежнему можно сохранять текст medication.
    # Форма сможет брать названия из medications.display_name.
    op.create_table(
        "medications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("trade_name", sa.String(length=255), nullable=True),
        sa.Column("active_substance", sa.String(length=255), nullable=True),
        sa.Column("drug_group", sa.String(length=255), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_unique_constraint(
        "uq_medications_display_name",
        "medications",
        ["display_name"],
    )

    op.create_index(
        "idx_medications_is_active",
        "medications",
        ["is_active"],
    )

    op.create_index(
        "idx_medications_sort_order",
        "medications",
        ["sort_order"],
    )

    op.create_index(
        "idx_medications_active_substance",
        "medications",
        ["active_substance"],
    )

    medications_table = sa.table(
        "medications",
        sa.column("display_name", sa.String),
        sa.column("trade_name", sa.String),
        sa.column("active_substance", sa.String),
        sa.column("drug_group", sa.String),
        sa.column("sort_order", sa.Integer),
    )

    op.bulk_insert(
        medications_table,
        [
            {
                "display_name": display_name,
                "trade_name": trade_name,
                "active_substance": active_substance,
                "drug_group": drug_group,
                "sort_order": sort_order,
            }
            for display_name, trade_name, active_substance, drug_group, sort_order in MEDICATIONS
        ],
    )


def downgrade() -> None:
    op.drop_index("idx_medications_active_substance", table_name="medications")
    op.drop_index("idx_medications_sort_order", table_name="medications")
    op.drop_index("idx_medications_is_active", table_name="medications")
    op.drop_constraint("uq_medications_display_name", "medications", type_="unique")
    op.drop_table("medications")

    op.execute("ALTER TABLE examinations DROP CONSTRAINT IF EXISTS chk_examinations_anthropometry;")
    op.drop_column("examinations", "bmi")
    op.execute(
        """
        ALTER TABLE examinations
            ADD CONSTRAINT chk_examinations_anthropometry
            CHECK (
                (height IS NULL OR height BETWEEN 50 AND 250)
                AND (weight IS NULL OR weight BETWEEN 20 AND 300)
            );
        """
    )
