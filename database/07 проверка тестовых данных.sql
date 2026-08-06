DO $$
BEGIN
 IF (SELECT count(*) FROM patients)<>7 THEN RAISE EXCEPTION 'Ожидалось 7 тестовых пациентов'; END IF;
 IF (SELECT count(*) FROM appointments)<>17 THEN RAISE EXCEPTION 'Ожидалось 17 тестовых приёмов'; END IF;
 IF (SELECT count(*) FROM surveys)<>17 THEN RAISE EXCEPTION 'Ожидалось 17 опросов'; END IF;
 IF (SELECT count(*) FROM examinations)<>17 THEN RAISE EXCEPTION 'Ожидалось 17 осмотров'; END IF;
 IF EXISTS (SELECT 1 FROM appointments WHERE age_at_appointment IS NULL OR age_at_appointment NOT BETWEEN 0 AND 130) THEN RAISE EXCEPTION 'Ошибка возраста на дату приёма'; END IF;
 IF EXISTS (SELECT 1 FROM appointments a LEFT JOIN patients p ON p.id=a.patient_id LEFT JOIN doctors d ON d.id=a.doctor_id WHERE p.id IS NULL OR d.id IS NULL) THEN RAISE EXCEPTION 'Нарушены связи тестовых приёмов'; END IF;
 IF (SELECT count(*) FROM calculated_metrics)<>17 THEN RAISE EXCEPTION 'Ожидалось 17 расчётов'; END IF;
 IF (SELECT count(*) FROM ckd_prognosis_results)<>17 THEN RAISE EXCEPTION 'Ожидалось 17 результатов KDIGO'; END IF;
 IF EXISTS (SELECT 1 FROM ckd_prognosis_results WHERE calculation_status='calculated' AND (gfr_metric_id IS NULL OR albuminuria_result_id IS NULL)) THEN RAISE EXCEPTION 'KDIGO не связан с источниками'; END IF;
 IF (SELECT count(*) FROM prescriptions)<>85 THEN RAISE EXCEPTION 'Ожидалось 85 назначений'; END IF;
 IF EXISTS (SELECT 1 FROM appointments a LEFT JOIN appointment_icd10_diagnoses d ON d.appointment_id=a.id AND d.diagnosis_type='main' WHERE d.id IS NULL) THEN RAISE EXCEPTION 'Не всем приёмам назначен основной диагноз МКБ'; END IF;
 IF EXISTS (SELECT 1 FROM calculated_metrics WHERE ckd_stage LIKE 'G%' OR ckd_stage LIKE 'C%') THEN RAISE EXCEPTION 'Найдены старые обозначения стадий'; END IF;
END $$;
SELECT 'demo_data_ok' AS result;
