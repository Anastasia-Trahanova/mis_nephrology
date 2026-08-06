"""Единое расширение базы 2.0 для импорта архивных консультаций."""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "0018_archive_source_path"
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("surveys", sa.Column("disease_anamnesis_text", sa.Text(), nullable=True))
    op.add_column("surveys", sa.Column("life_anamnesis_text", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("diagnosis_text", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("diagnosis_comment_text", sa.Text(), nullable=True))
    op.add_column("appointments", sa.Column("is_archive_import", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("appointments", sa.Column("archive_import_key", sa.String(length=255), nullable=True))
    op.add_column("appointments", sa.Column("archive_source_relative_path", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_appointments_archive_import_key", "appointments", ["archive_import_key"])
    op.execute("COMMENT ON COLUMN surveys.disease_anamnesis_text IS 'Анамнез заболевания: свободный текст из архивной консультации'")
    op.execute("COMMENT ON COLUMN surveys.life_anamnesis_text IS 'Анамнез жизни: свободный текст из архивной консультации'")
    op.execute("COMMENT ON COLUMN appointments.diagnosis_text IS 'Диагноз в исходной формулировке врача без автоматического кодирования МКБ-10'")
    op.execute("COMMENT ON COLUMN appointments.diagnosis_comment_text IS 'Пояснения и комментарии врача к диагнозу'")
    op.execute("COMMENT ON COLUMN appointments.is_archive_import IS 'Приём импортирован из архива консультаций'")
    op.execute("COMMENT ON COLUMN appointments.archive_import_key IS 'Уникальный технический ключ архивного приёма для защиты от повторного импорта'")
    op.execute("COMMENT ON COLUMN appointments.archive_source_relative_path IS 'Относительный путь к исходному документу внутри папки архивных документов'")

def downgrade() -> None:
    op.drop_constraint("uq_appointments_archive_import_key", "appointments", type_="unique")
    op.drop_column("appointments", "archive_source_relative_path")
    op.drop_column("appointments", "archive_import_key")
    op.drop_column("appointments", "is_archive_import")
    op.drop_column("appointments", "diagnosis_comment_text")
    op.drop_column("appointments", "diagnosis_text")
    op.drop_column("surveys", "life_anamnesis_text")
    op.drop_column("surveys", "disease_anamnesis_text")
