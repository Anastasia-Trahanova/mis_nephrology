"""Путь к исходному документу архивной консультации.

Revision ID: 0018_archive_source_path
Revises: 0017_archive_import_doctors
Create Date: 2026-08-06

Исходные Word/PDF-файлы не помещаются в PostgreSQL и не попадают в Git.
В приёме хранится только безопасный относительный путь внутри настроенной
папки архива. Сам файл остаётся в medical_archive.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0018_archive_source_path"
down_revision = "0017_archive_import_doctors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "appointments",
        sa.Column("archive_source_relative_path", sa.Text(), nullable=True),
    )
    op.execute(
        "COMMENT ON COLUMN appointments.archive_source_relative_path "
        "IS 'Относительный путь к исходному документу внутри папки архивных документов';"
    )


def downgrade() -> None:
    op.drop_column("appointments", "archive_source_relative_path")
