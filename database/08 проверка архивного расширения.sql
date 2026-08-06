DO $$
BEGIN
 IF NOT EXISTS (SELECT 1 FROM alembic_version WHERE version_num='0018_archive_source_path') THEN RAISE EXCEPTION 'Неверная Alembic-ревизия'; END IF;
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='surveys' AND column_name='disease_anamnesis_text') THEN RAISE EXCEPTION 'Нет surveys.disease_anamnesis_text'; END IF;
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='surveys' AND column_name='life_anamnesis_text') THEN RAISE EXCEPTION 'Нет surveys.life_anamnesis_text'; END IF;
 IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='appointments' AND column_name='archive_source_relative_path') THEN RAISE EXCEPTION 'Нет пути исходного документа'; END IF;
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_appointments_archive_import_key') THEN RAISE EXCEPTION 'Нет уникальности archive_import_key'; END IF;
 IF EXISTS (SELECT archive_import_key FROM appointments WHERE archive_import_key IS NOT NULL GROUP BY archive_import_key HAVING count(*)>1) THEN RAISE EXCEPTION 'Есть дубли archive_import_key'; END IF;
END $$;
SELECT 'archive_extension_ok' AS result;
