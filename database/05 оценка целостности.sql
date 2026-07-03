-- ЛЕГЕНДА
-- Файл: 05 оценка целостности.sql
-- Назначение: проверяет целостность данных после создания структуры и заполнения тестовыми данными.
-- Хороший результат: запросы на проблемные записи возвращают 0 строк или ожидаемые диагностические сводки.
-- Запускать после seed-файла.

-- =====================================================
-- A. ЖЁСТКИЕ ПРОВЕРКИ: ожидаемый результат — 0 строк
-- =====================================================

-- A01. Филиалы без существующей компании
SELECT 'A01 branches_without_company' AS check_name, b.*
FROM branches b
LEFT JOIN companies c ON c.id = b.company_id
WHERE c.id IS NULL;

-- A02. Отделения без существующего филиала
SELECT 'A02 locations_without_branch' AS check_name, l.*
FROM locations l
LEFT JOIN branches b ON b.id = l.branch_id
WHERE b.id IS NULL;

-- A03. Отделения с company_id, который не совпадает с company_id филиала
SELECT 'A03 locations_company_mismatch' AS check_name,
       l.id AS location_id, l.name AS location_name,
       l.company_id AS location_company_id,
       b.company_id AS branch_company_id
FROM locations l
JOIN branches b ON b.id = l.branch_id
WHERE l.company_id IS NOT NULL
  AND l.company_id <> b.company_id;

-- A04. Дубли связей врач-отделение
SELECT 'A04 duplicate_doctor_locations' AS check_name,
       doctor_id, location_id, COUNT(*) AS duplicate_count
FROM doctor_locations
GROUP BY doctor_id, location_id
HAVING COUNT(*) > 1;

-- A05. Некорректная ролевая модель пользователей
SELECT 'A05 invalid_user_role_model' AS check_name,
       id, login, role, doctor_id, patient_id
FROM users
WHERE role NOT IN ('admin', 'doctor', 'patient')
   OR (role = 'admin'  AND (doctor_id IS NOT NULL OR patient_id IS NOT NULL))
   OR (role = 'doctor' AND (doctor_id IS NULL OR patient_id IS NOT NULL))
   OR (role = 'patient' AND (patient_id IS NULL OR doctor_id IS NOT NULL));

-- A06. Дубли логинов
SELECT 'A06 duplicate_user_logins' AS check_name,
       login, COUNT(*) AS duplicate_count
FROM users
GROUP BY login
HAVING COUNT(*) > 1;

-- A07. Пациенты с некорректной датой рождения
SELECT 'A07 invalid_patient_birth_date' AS check_name,
       id, last_name, first_name, patronymic, birth_date
FROM patients
WHERE birth_date IS NULL
   OR birth_date < DATE '1900-01-01'
   OR birth_date > CURRENT_DATE;

-- A08. Приёмы без пациента/врача/отделения или с будущей датой
SELECT 'A08 invalid_appointments' AS check_name,
       a.id, a.patient_id, a.doctor_id, a.location_id, a.appointment_date
FROM appointments a
LEFT JOIN patients p ON p.id = a.patient_id
LEFT JOIN doctors d ON d.id = a.doctor_id
LEFT JOIN locations l ON l.id = a.location_id
WHERE p.id IS NULL
   OR d.id IS NULL
   OR l.id IS NULL
   OR a.appointment_date IS NULL
   OR a.appointment_date > CURRENT_TIMESTAMP;

-- A09. Систолическое АД меньше/равно диастолическому или вне диапазонов
SELECT 'A09 invalid_blood_pressure' AS check_name,
       id, appointment_id, systolic_pressure, diastolic_pressure
FROM examinations
WHERE (systolic_pressure IS NOT NULL AND (systolic_pressure < 40 OR systolic_pressure > 280))
   OR (diastolic_pressure IS NOT NULL AND (diastolic_pressure < 20 OR diastolic_pressure > 200))
   OR (systolic_pressure IS NOT NULL AND diastolic_pressure IS NOT NULL AND systolic_pressure <= diastolic_pressure);

-- A10. Нереалистичные рост/вес/ЧСС
SELECT 'A10 invalid_examination_values' AS check_name,
       id, appointment_id, heart_rate, height, weight
FROM examinations
WHERE (heart_rate IS NOT NULL AND (heart_rate < 30 OR heart_rate > 220))
   OR (height IS NOT NULL AND (height < 50 OR height > 250))
   OR (weight IS NOT NULL AND (weight < 20 OR weight > 300));

-- A11. Отрицательные или нулевые значения в биохимии, где они невозможны
SELECT 'A11 invalid_biochemistry_values' AS check_name, *
FROM biochemistry_results
WHERE (creatinine IS NOT NULL AND creatinine <= 0)
   OR (urea IS NOT NULL AND urea < 0)
   OR (uric_acid IS NOT NULL AND uric_acid < 0)
   OR (glucose IS NOT NULL AND glucose < 0)
   OR (total_protein IS NOT NULL AND total_protein < 0)
   OR (albumin IS NOT NULL AND albumin < 0)
   OR (potassium IS NOT NULL AND potassium < 0)
   OR (calcium IS NOT NULL AND calcium < 0)
   OR (phosphorus IS NOT NULL AND phosphorus < 0)
   OR (ferritin IS NOT NULL AND ferritin < 0)
   OR (ptg IS NOT NULL AND ptg < 0);

-- A12. Отрицательные значения в ОАК
SELECT 'A12 invalid_cbc_values' AS check_name, *
FROM cbc_results
WHERE (hemoglobin IS NOT NULL AND hemoglobin < 0)
   OR (erythrocytes IS NOT NULL AND erythrocytes < 0)
   OR (leukocytes IS NOT NULL AND leukocytes < 0)
   OR (platelets IS NOT NULL AND platelets < 0)
   OR (esr IS NOT NULL AND esr < 0)
   OR (mcv IS NOT NULL AND mcv < 0)
   OR (hematocrit IS NOT NULL AND hematocrit < 0);

-- A13. Отрицательные значения в ОАМ
SELECT 'A13 invalid_urinalysis_values' AS check_name, *
FROM urinalysis_results
WHERE (specific_gravity IS NOT NULL AND specific_gravity < 0)
   OR (protein IS NOT NULL AND protein < 0)
   OR (leukocytes IS NOT NULL AND leukocytes < 0)
   OR (erythrocytes IS NOT NULL AND erythrocytes < 0);

-- A14. Некорректные значения альбуминурии или единицы измерения
SELECT 'A14 invalid_albuminuria_values' AS check_name, *
FROM albuminuria_results
WHERE urine_albumin_unit NOT IN ('mg_l', 'g_l')
   OR urine_creatinine_unit NOT IN ('mmol_l', 'umol_l')
   OR (urine_albumin IS NOT NULL AND urine_albumin < 0)
   OR (urine_creatinine IS NOT NULL AND urine_creatinine <= 0)
   OR (albumin_creatinine_ratio IS NOT NULL AND albumin_creatinine_ratio < 0)
   OR (albuminuria_category IS NOT NULL AND albuminuria_category NOT IN ('A1', 'A2', 'A3'));

-- A15. Категория альбуминурии не соответствует ACR в мг/ммоль
SELECT 'A15_albuminuria_category_mismatch' AS check_name,
       id, appointment_id, albumin_creatinine_ratio, albuminuria_category,
       CASE
           WHEN albumin_creatinine_ratio < 3 THEN 'A1'
           WHEN albumin_creatinine_ratio <= 30 THEN 'A2'
           WHEN albumin_creatinine_ratio > 30 THEN 'A3'
       END AS expected_category
FROM albuminuria_results
WHERE albumin_creatinine_ratio IS NOT NULL
  AND albuminuria_category IS NOT NULL
  AND albuminuria_category <> CASE
           WHEN albumin_creatinine_ratio < 3 THEN 'A1'
           WHEN albumin_creatinine_ratio <= 30 THEN 'A2'
           WHEN albumin_creatinine_ratio > 30 THEN 'A3'
       END;

-- A16. Категория СКФ не соответствует eGFR CKD-EPI
SELECT 'A16_ckd_stage_mismatch' AS check_name,
       id, appointment_id, egfr_ckdepi, ckd_stage,
       CASE
           WHEN egfr_ckdepi >= 90 THEN 'С1'
           WHEN egfr_ckdepi >= 60 THEN 'С2'
           WHEN egfr_ckdepi >= 45 THEN 'С3а'
           WHEN egfr_ckdepi >= 30 THEN 'С3б'
           WHEN egfr_ckdepi >= 15 THEN 'С4'
           WHEN egfr_ckdepi < 15 THEN 'С5'
       END AS expected_stage
FROM calculated_metrics
WHERE egfr_ckdepi IS NOT NULL
  AND ckd_stage IS NOT NULL
  AND ckd_stage <> CASE
           WHEN egfr_ckdepi >= 90 THEN 'С1'
           WHEN egfr_ckdepi >= 60 THEN 'С2'
           WHEN egfr_ckdepi >= 45 THEN 'С3а'
           WHEN egfr_ckdepi >= 30 THEN 'С3б'
           WHEN egfr_ckdepi >= 15 THEN 'С4'
           WHEN egfr_ckdepi < 15 THEN 'С5'
       END;

-- A17. Прогноз ХБП не соответствует матрице KDIGO G x A
WITH expected AS (
    SELECT
        id,
        appointment_id,
        gfr_category,
        albuminuria_category,
        prognosis_level,
        CASE
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A1' THEN 'low'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A2' THEN 'moderate'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A3' THEN 'high'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A1' THEN 'moderate'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A2' THEN 'high'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A3' THEN 'very_high'
            WHEN gfr_category = 'С3б' AND albuminuria_category = 'A1' THEN 'high'
            WHEN gfr_category = 'С3б' AND albuminuria_category IN ('A2', 'A3') THEN 'very_high'
            WHEN gfr_category IN ('С4', 'С5') THEN 'very_high'
        END AS expected_level
    FROM ckd_prognosis_results
)
SELECT 'A17_ckd_prognosis_mismatch' AS check_name, *
FROM expected
WHERE expected_level IS NOT NULL
  AND prognosis_level <> expected_level;

-- A18. Пустой основной диагноз: NULL допустим, пустая строка — нет
SELECT 'A18_blank_main_diagnosis' AS check_name, id, appointment_id, main_diagnosis
FROM diagnoses
WHERE main_diagnosis IS NOT NULL
  AND LENGTH(TRIM(main_diagnosis)) = 0;

-- =====================================================
-- B. МЯГКИЕ ПРОВЕРКИ: результат нужно просмотреть, но это не всегда ошибка
-- =====================================================

-- B01. Приёмы без опроса/осмотра/диагноза/диеты/прогноза
SELECT 'B01_incomplete_appointments' AS check_name,
       a.id AS appointment_id,
       p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
       a.appointment_date,
       CASE WHEN s.id IS NULL THEN 'нет опроса; ' ELSE '' END ||
       CASE WHEN e.id IS NULL THEN 'нет осмотра; ' ELSE '' END ||
       CASE WHEN d.id IS NULL THEN 'нет диагноза; ' ELSE '' END ||
       CASE WHEN ad.id IS NULL THEN 'нет диеты; ' ELSE '' END ||
       CASE WHEN cpr.id IS NULL THEN 'нет прогноза ХБП; ' ELSE '' END AS missing_blocks
FROM appointments a
JOIN patients p ON p.id = a.patient_id
LEFT JOIN surveys s ON s.appointment_id = a.id
LEFT JOIN examinations e ON e.appointment_id = a.id
LEFT JOIN diagnoses d ON d.appointment_id = a.id
LEFT JOIN appointment_diets ad ON ad.appointment_id = a.id
LEFT JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
WHERE s.id IS NULL OR e.id IS NULL OR d.id IS NULL OR ad.id IS NULL OR cpr.id IS NULL
ORDER BY a.appointment_date DESC;

-- B02. Приёмы без лабораторных данных
SELECT 'B02_appointments_without_labs' AS check_name,
       a.id AS appointment_id,
       p.last_name || ' ' || p.first_name AS patient_fio,
       a.appointment_date
FROM appointments a
JOIN patients p ON p.id = a.patient_id
WHERE NOT EXISTS (SELECT 1 FROM cbc_results c WHERE c.appointment_id = a.id)
   OR NOT EXISTS (SELECT 1 FROM biochemistry_results b WHERE b.appointment_id = a.id)
   OR NOT EXISTS (SELECT 1 FROM urinalysis_results u WHERE u.appointment_id = a.id)
ORDER BY a.appointment_date DESC;

-- B03. Анализы с датой позже даты приёма
SELECT 'B03_labs_after_appointment_date' AS check_name, source_table, appointment_id, appointment_date, investigation_date
FROM (
    SELECT 'cbc_results' AS source_table, a.id AS appointment_id, a.appointment_date::date AS appointment_date, c.investigation_date
    FROM cbc_results c JOIN appointments a ON a.id = c.appointment_id
    UNION ALL
    SELECT 'biochemistry_results', a.id, a.appointment_date::date, b.investigation_date
    FROM biochemistry_results b JOIN appointments a ON a.id = b.appointment_id
    UNION ALL
    SELECT 'urinalysis_results', a.id, a.appointment_date::date, u.investigation_date
    FROM urinalysis_results u JOIN appointments a ON a.id = u.appointment_id
    UNION ALL
    SELECT 'albuminuria_results', a.id, a.appointment_date::date, ar.investigation_date
    FROM albuminuria_results ar JOIN appointments a ON a.id = ar.appointment_id
    UNION ALL
    SELECT 'ultrasound_results', a.id, a.appointment_date::date, us.investigation_date
    FROM ultrasound_results us JOIN appointments a ON a.id = us.appointment_id
) x
WHERE investigation_date > appointment_date
ORDER BY appointment_id, source_table;

-- =====================================================
-- C. ИТОГОВАЯ СТАТИСТИКА ПО ТАБЛИЦАМ
-- =====================================================

SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'branches', COUNT(*) FROM branches
UNION ALL SELECT 'locations', COUNT(*) FROM locations
UNION ALL SELECT 'doctors', COUNT(*) FROM doctors
UNION ALL SELECT 'doctor_locations', COUNT(*) FROM doctor_locations
UNION ALL SELECT 'users', COUNT(*) FROM users
UNION ALL SELECT 'patients', COUNT(*) FROM patients
UNION ALL SELECT 'appointments', COUNT(*) FROM appointments
UNION ALL SELECT 'surveys', COUNT(*) FROM surveys
UNION ALL SELECT 'examinations', COUNT(*) FROM examinations
UNION ALL SELECT 'cbc_results', COUNT(*) FROM cbc_results
UNION ALL SELECT 'biochemistry_results', COUNT(*) FROM biochemistry_results
UNION ALL SELECT 'urinalysis_results', COUNT(*) FROM urinalysis_results
UNION ALL SELECT 'albuminuria_results', COUNT(*) FROM albuminuria_results
UNION ALL SELECT 'ultrasound_results', COUNT(*) FROM ultrasound_results
UNION ALL SELECT 'calculated_metrics', COUNT(*) FROM calculated_metrics
UNION ALL SELECT 'ckd_prognosis_results', COUNT(*) FROM ckd_prognosis_results
UNION ALL SELECT 'diagnoses', COUNT(*) FROM diagnoses
UNION ALL SELECT 'appointment_diets', COUNT(*) FROM appointment_diets
UNION ALL SELECT 'prescriptions', COUNT(*) FROM prescriptions
ORDER BY table_name;
