"""store KDIGO risk assessment source data

Revision ID: 0003_kdigo_risk_sources
Revises: 0002_bmi_medications
Create Date: 2026-07-05

Назначение миграции
-------------------
Эта миграция подготавливает таблицу ckd_prognosis_results к новой логике
оценки риска по KDIGO.

До миграции в таблице могла храниться только одна строка на приём.
Это мешает сохранять несколько комбинаций, если врач в рамках одного приёма
добавил несколько расчётов СКФ и/или несколько исследований альбуминурии.

После миграции таблица хранит не только итоговую категорию риска, но и строгие
источники расчёта:
- id строки СКФ из calculated_metrics;
- дату исследования, по которому получена СКФ;
- id строки альбуминурии из albuminuria_results;
- дату исследования, по которому получена альбуминурия;
- итоговую категорию вида С3аA2;
- уровень риска по матрице KDIGO.

Важно
-----
Эта миграция НЕ меняет таблицы анализов и НЕ трогает инструкции по базе данных.
Она только расширяет ckd_prognosis_results и убирает старое ограничение
"один прогноз на один приём".
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003_kdigo_risk_sources"
down_revision = "0002_bmi_medications"
branch_labels = None
depends_on = None


GFR_CATEGORIES_SQL = "'С1', 'С2', 'С3а', 'С3б', 'С4', 'С5'"
ALBUMINURIA_CATEGORIES_SQL = "'A1', 'A2', 'A3'"
RISK_LEVELS_SQL = "'low', 'moderate', 'high', 'very_high'"
SOURCE_TYPES_SQL = "'current_appointment', 'previous_appointment', 'manual', 'legacy_unknown'"
STATUSES_SQL = (
    "'calculated', "
    "'missing_gfr', "
    "'missing_albuminuria', "
    "'missing_both', "
    "'stale_gfr', "
    "'stale_albuminuria', "
    "'stale_both', "
    "'doctor_removed', "
    "'legacy_incomplete'"
)


def upgrade() -> None:
    # Старое ограничение разрешало только одну строку KDIGO на приём.
    # Для новой матрицы это неправильно: один приём может содержать несколько
    # расчётов СКФ и несколько исследований альбуминурии.
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS uq_ckd_prognosis_appointment;"
    )

    op.add_column(
        "ckd_prognosis_results",
        sa.Column("gfr_metric_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("albuminuria_result_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("gfr_investigation_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("albuminuria_investigation_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("gfr_source_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("albuminuria_source_type", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("source_interval_days", sa.Integer(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column(
            "calculation_status",
            sa.String(length=30),
            nullable=False,
            server_default="calculated",
        ),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("hidden_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "ckd_prognosis_results",
        sa.Column("hidden_reason", sa.Text(), nullable=True),
    )

    # Источники расчёта могут быть удалены вместе со старым приёмом.
    # Поэтому FK ставим ON DELETE SET NULL, а сами даты/категории храним снимком.
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS fk_ckd_prognosis_gfr_metric;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "ADD CONSTRAINT fk_ckd_prognosis_gfr_metric "
        "FOREIGN KEY (gfr_metric_id) REFERENCES calculated_metrics(id) "
        "ON DELETE SET NULL;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS fk_ckd_prognosis_albuminuria_result;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "ADD CONSTRAINT fk_ckd_prognosis_albuminuria_result "
        "FOREIGN KEY (albuminuria_result_id) REFERENCES albuminuria_results(id) "
        "ON DELETE SET NULL;"
    )

    # Заполняем новые поля для уже существующих строк.
    # Старый код сохранял прогноз только по данным текущего приёма, поэтому
    # для legacy-строк ищем источники внутри appointment_id.
    op.execute(
        """
        UPDATE ckd_prognosis_results cpr
        SET
            gfr_metric_id = (
                SELECT cm.id
                FROM calculated_metrics cm
                WHERE cm.appointment_id = cpr.appointment_id
                  AND cm.ckd_stage = cpr.gfr_category
                ORDER BY cm.investigation_date DESC NULLS LAST, cm.id DESC
                LIMIT 1
            ),
            gfr_investigation_date = (
                SELECT COALESCE(cm.investigation_date, a.appointment_date::date)
                FROM calculated_metrics cm
                JOIN appointments a ON a.id = cm.appointment_id
                WHERE cm.appointment_id = cpr.appointment_id
                  AND cm.ckd_stage = cpr.gfr_category
                ORDER BY cm.investigation_date DESC NULLS LAST, cm.id DESC
                LIMIT 1
            ),
            gfr_source_type = 'current_appointment'
        WHERE cpr.gfr_metric_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE ckd_prognosis_results cpr
        SET
            albuminuria_result_id = (
                SELECT ar.id
                FROM albuminuria_results ar
                WHERE ar.appointment_id = cpr.appointment_id
                  AND ar.albuminuria_category = cpr.albuminuria_category
                ORDER BY ar.investigation_date DESC NULLS LAST, ar.id DESC
                LIMIT 1
            ),
            albuminuria_investigation_date = (
                SELECT ar.investigation_date
                FROM albuminuria_results ar
                WHERE ar.appointment_id = cpr.appointment_id
                  AND ar.albuminuria_category = cpr.albuminuria_category
                ORDER BY ar.investigation_date DESC NULLS LAST, ar.id DESC
                LIMIT 1
            ),
            albuminuria_source_type = 'current_appointment'
        WHERE cpr.albuminuria_result_id IS NULL;
        """
    )
    op.execute(
        """
        UPDATE ckd_prognosis_results
        SET source_interval_days = ABS(gfr_investigation_date - albuminuria_investigation_date)
        WHERE gfr_investigation_date IS NOT NULL
          AND albuminuria_investigation_date IS NOT NULL;
        """
    )
    op.execute(
        """
        UPDATE ckd_prognosis_results
        SET calculation_status = 'legacy_incomplete'
        WHERE calculation_status = 'calculated'
          AND (
              gfr_metric_id IS NULL
              OR albuminuria_result_id IS NULL
              OR gfr_investigation_date IS NULL
              OR albuminuria_investigation_date IS NULL
              OR gfr_category IS NULL
              OR albuminuria_category IS NULL
              OR combined_category IS NULL
              OR prognosis_level IS NULL
          );
        """
    )

    # Триггер нужен для обратной совместимости со старым кодом до следующего этапа.
    # Если старый repository вставит только категории и итоговый риск, БД сама
    # попытается заполнить source id/date по текущему приёму.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_ckd_prognosis_source_fields()
        RETURNS trigger AS $$
        DECLARE
            source_gfr RECORD;
            source_albuminuria RECORD;
        BEGIN
            IF NEW.gfr_metric_id IS NULL AND NEW.gfr_category IS NOT NULL THEN
                SELECT
                    cm.id,
                    COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date
                INTO source_gfr
                FROM calculated_metrics cm
                JOIN appointments a ON a.id = cm.appointment_id
                WHERE cm.appointment_id = NEW.appointment_id
                  AND cm.ckd_stage = NEW.gfr_category
                ORDER BY cm.investigation_date DESC NULLS LAST, cm.id DESC
                LIMIT 1;

                IF FOUND THEN
                    NEW.gfr_metric_id := source_gfr.id;
                    NEW.gfr_investigation_date := source_gfr.investigation_date;
                    NEW.gfr_source_type := COALESCE(NEW.gfr_source_type, 'current_appointment');
                END IF;
            END IF;

            IF NEW.albuminuria_result_id IS NULL AND NEW.albuminuria_category IS NOT NULL THEN
                SELECT ar.id, ar.investigation_date
                INTO source_albuminuria
                FROM albuminuria_results ar
                WHERE ar.appointment_id = NEW.appointment_id
                  AND ar.albuminuria_category = NEW.albuminuria_category
                ORDER BY ar.investigation_date DESC NULLS LAST, ar.id DESC
                LIMIT 1;

                IF FOUND THEN
                    NEW.albuminuria_result_id := source_albuminuria.id;
                    NEW.albuminuria_investigation_date := source_albuminuria.investigation_date;
                    NEW.albuminuria_source_type := COALESCE(NEW.albuminuria_source_type, 'current_appointment');
                END IF;
            END IF;

            IF NEW.gfr_investigation_date IS NOT NULL
               AND NEW.albuminuria_investigation_date IS NOT NULL THEN
                NEW.source_interval_days := ABS(NEW.gfr_investigation_date - NEW.albuminuria_investigation_date);
            END IF;

            IF NEW.is_active = FALSE AND NEW.hidden_at IS NULL THEN
                NEW.hidden_at := NOW();
            END IF;

            NEW.updated_at := NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_set_ckd_prognosis_source_fields
        ON ckd_prognosis_results;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_set_ckd_prognosis_source_fields
        BEFORE INSERT OR UPDATE ON ckd_prognosis_results
        FOR EACH ROW
        EXECUTE FUNCTION set_ckd_prognosis_source_fields();
        """
    )

    # Обновляем CHECK-ограничение с учетом новых статусов и источников.
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_categories;"
    )
    op.execute(
        f"""
        ALTER TABLE ckd_prognosis_results
        ADD CONSTRAINT chk_ckd_prognosis_categories CHECK (
            (gfr_category IS NULL OR gfr_category IN ({GFR_CATEGORIES_SQL}))
            AND (albuminuria_category IS NULL OR albuminuria_category IN ({ALBUMINURIA_CATEGORIES_SQL}))
            AND (prognosis_level IS NULL OR prognosis_level IN ({RISK_LEVELS_SQL}))
            AND (gfr_source_type IS NULL OR gfr_source_type IN ({SOURCE_TYPES_SQL}))
            AND (albuminuria_source_type IS NULL OR albuminuria_source_type IN ({SOURCE_TYPES_SQL}))
            AND calculation_status IN ({STATUSES_SQL})
        );
        """
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_combined_category;"
    )
    op.execute(
        """
        ALTER TABLE ckd_prognosis_results
        ADD CONSTRAINT chk_ckd_prognosis_combined_category CHECK (
            combined_category IS NULL
            OR (
                gfr_category IS NOT NULL
                AND albuminuria_category IS NOT NULL
                AND combined_category = gfr_category || albuminuria_category
            )
        );
        """
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_source_interval;"
    )
    op.execute(
        """
        ALTER TABLE ckd_prognosis_results
        ADD CONSTRAINT chk_ckd_prognosis_source_interval CHECK (
            source_interval_days IS NULL OR source_interval_days >= 0
        );
        """
    )

    # Для рассчитанного риска требуем строгие источники. Legacy-строки, которые
    # не удалось восстановить, выше переведены в legacy_incomplete.
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_calculated_sources;"
    )
    op.execute(
        """
        ALTER TABLE ckd_prognosis_results
        ADD CONSTRAINT chk_ckd_prognosis_calculated_sources CHECK (
            calculation_status <> 'calculated'
            OR (
                gfr_metric_id IS NOT NULL
                AND albuminuria_result_id IS NOT NULL
                AND gfr_investigation_date IS NOT NULL
                AND albuminuria_investigation_date IS NOT NULL
                AND gfr_category IS NOT NULL
                AND albuminuria_category IS NOT NULL
                AND combined_category IS NOT NULL
                AND prognosis_level IS NOT NULL
                AND prognosis_text IS NOT NULL
            )
        );
        """
    )

    op.create_index(
        "idx_ckd_prognosis_gfr_date",
        "ckd_prognosis_results",
        ["gfr_investigation_date"],
    )
    op.create_index(
        "idx_ckd_prognosis_albuminuria_date",
        "ckd_prognosis_results",
        ["albuminuria_investigation_date"],
    )
    op.create_index(
        "idx_ckd_prognosis_assessment_active",
        "ckd_prognosis_results",
        ["appointment_id", "is_active", "display_order", "id"],
    )
    op.create_index(
        "idx_ckd_prognosis_matrix_lookup",
        "ckd_prognosis_results",
        [
            "appointment_id",
            "gfr_investigation_date",
            "albuminuria_investigation_date",
        ],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ckd_prognosis_active_source_pair
        ON ckd_prognosis_results (appointment_id, gfr_metric_id, albuminuria_result_id)
        WHERE is_active = true AND calculation_status = 'calculated';
        """
    )


def downgrade() -> None:
    # Downgrade возвращает старую модель "один прогноз на один приём".
    # Если после миграции появились несколько строк на один appointment_id,
    # оставляем первую активную строку, иначе старое UNIQUE не создастся.
    op.execute(
        """
        DELETE FROM ckd_prognosis_results cpr
        USING ckd_prognosis_results newer
        WHERE cpr.appointment_id = newer.appointment_id
          AND cpr.id > newer.id;
        """
    )

    op.execute("DROP INDEX IF EXISTS uq_ckd_prognosis_active_source_pair;")
    op.drop_index("idx_ckd_prognosis_matrix_lookup", table_name="ckd_prognosis_results")
    op.drop_index("idx_ckd_prognosis_assessment_active", table_name="ckd_prognosis_results")
    op.drop_index("idx_ckd_prognosis_albuminuria_date", table_name="ckd_prognosis_results")
    op.drop_index("idx_ckd_prognosis_gfr_date", table_name="ckd_prognosis_results")

    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_calculated_sources;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_source_interval;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_combined_category;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_categories;"
    )
    op.execute(
        f"""
        ALTER TABLE ckd_prognosis_results
        ADD CONSTRAINT chk_ckd_prognosis_categories CHECK (
            (gfr_category IS NULL OR gfr_category IN ({GFR_CATEGORIES_SQL}))
            AND (albuminuria_category IS NULL OR albuminuria_category IN ({ALBUMINURIA_CATEGORIES_SQL}))
            AND (prognosis_level IS NULL OR prognosis_level IN ({RISK_LEVELS_SQL}))
        );
        """
    )

    op.execute(
        "DROP TRIGGER IF EXISTS trg_set_ckd_prognosis_source_fields "
        "ON ckd_prognosis_results;"
    )
    op.execute("DROP FUNCTION IF EXISTS set_ckd_prognosis_source_fields();")

    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS fk_ckd_prognosis_albuminuria_result;"
    )
    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "DROP CONSTRAINT IF EXISTS fk_ckd_prognosis_gfr_metric;"
    )

    op.drop_column("ckd_prognosis_results", "hidden_reason")
    op.drop_column("ckd_prognosis_results", "hidden_at")
    op.drop_column("ckd_prognosis_results", "is_active")
    op.drop_column("ckd_prognosis_results", "display_order")
    op.drop_column("ckd_prognosis_results", "calculation_status")
    op.drop_column("ckd_prognosis_results", "source_interval_days")
    op.drop_column("ckd_prognosis_results", "albuminuria_source_type")
    op.drop_column("ckd_prognosis_results", "gfr_source_type")
    op.drop_column("ckd_prognosis_results", "albuminuria_investigation_date")
    op.drop_column("ckd_prognosis_results", "gfr_investigation_date")
    op.drop_column("ckd_prognosis_results", "albuminuria_result_id")
    op.drop_column("ckd_prognosis_results", "gfr_metric_id")

    op.execute(
        "ALTER TABLE ckd_prognosis_results "
        "ADD CONSTRAINT uq_ckd_prognosis_appointment UNIQUE (appointment_id);"
    )
