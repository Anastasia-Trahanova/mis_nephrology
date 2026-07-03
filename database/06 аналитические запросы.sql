-- ЛЕГЕНДА
-- Файл: 06 аналитические запросы.sql
-- Назначение: набор аналитических выборок для проверки наполнения базы и клинических категорий.
-- Запускать после seed-файла и integrity checks.
-- Этот файл не меняет данные, только показывает выборки.

-- =====================================================
-- A. ПЕРСОНАЛЬНАЯ ДИНАМИКА ПАЦИЕНТА
-- =====================================================

-- A01. Хронология приёмов пациента с категориями G/A и прогнозом ХБП
SELECT
    a.id AS appointment_id,
    a.appointment_date,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio,
    l.name AS location_name,
    cm.egfr_ckdepi,
    cm.ckd_stage AS gfr_category,
    ar.albumin_creatinine_ratio AS acr_mg_mmol,
    ar.albuminuria_category,
    cpr.combined_category,
    cpr.prognosis_text AS ckd_prognosis
FROM appointments a
JOIN doctors d ON d.id = a.doctor_id
JOIN locations l ON l.id = a.location_id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = a.id
LEFT JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY a.appointment_date, cm.investigation_date, ar.investigation_date;

-- A02. Динамика СКФ CKD-EPI и клиренса Cockcroft-Gault
SELECT
    COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
    cm.creatinine,
    cm.egfr_ckdepi,
    cm.crcl_cockcroft_gault,
    cm.ckd_stage
FROM calculated_metrics cm
JOIN appointments a ON a.id = cm.appointment_id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date), cm.id;

-- A03. Динамика альбуминурии / ACR
SELECT
    ar.investigation_date,
    ar.urine_albumin,
    ar.urine_albumin_unit,
    ar.urine_creatinine,
    ar.urine_creatinine_unit,
    ar.albumin_creatinine_ratio AS acr_mg_mmol,
    ar.albuminuria_category
FROM albuminuria_results ar
JOIN appointments a ON a.id = ar.appointment_id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY ar.investigation_date, ar.id;

-- A04. Динамика АД, веса и ЧСС
SELECT
    a.appointment_date,
    e.systolic_pressure,
    e.diastolic_pressure,
    e.bp_note,
    e.heart_rate,
    e.height,
    e.weight
FROM examinations e
JOIN appointments a ON a.id = e.appointment_id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY a.appointment_date;

-- A05. Лабораторная сводка пациента по датам
SELECT
    a.appointment_date::date AS appointment_date,
    b.investigation_date AS biochemistry_date,
    b.creatinine,
    b.urea,
    b.potassium,
    b.calcium,
    b.phosphorus,
    b.albumin,
    c.investigation_date AS cbc_date,
    c.hemoglobin,
    u.investigation_date AS urinalysis_date,
    u.protein,
    ar.albumin_creatinine_ratio AS acr_mg_mmol
FROM appointments a
LEFT JOIN biochemistry_results b ON b.appointment_id = a.id
LEFT JOIN cbc_results c ON c.appointment_id = a.id
LEFT JOIN urinalysis_results u ON u.appointment_id = a.id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = a.id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY a.appointment_date;

-- A06. История назначений пациента
SELECT
    a.appointment_date,
    pr.medication,
    pr.dosage,
    pr.schedule,
    ad.diet,
    ad.next_control_date
FROM appointments a
LEFT JOIN prescriptions pr ON pr.appointment_id = a.id
LEFT JOIN appointment_diets ad ON ad.appointment_id = a.id
WHERE a.patient_id = 101 -- замените на нужный id пациента
ORDER BY a.appointment_date, pr.id;

-- =====================================================
-- B. КЛИНИЧЕСКИЕ СПИСКИ ВНИМАНИЯ
-- =====================================================

-- B01. Пациенты с очень высоким прогнозом ХБП по KDIGO
SELECT DISTINCT ON (p.id)
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.appointment_date,
    cpr.combined_category,
    cpr.prognosis_text,
    cm.egfr_ckdepi,
    ar.albumin_creatinine_ratio AS acr_mg_mmol
FROM patients p
JOIN appointments a ON a.patient_id = p.id
JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = a.id
WHERE cpr.prognosis_level = 'very_high'
ORDER BY p.id, a.appointment_date DESC;

-- B02. Пациенты с eGFR < 45 мл/мин/1,73 м²: потенциально нужен пересмотр доз лекарств
SELECT DISTINCT ON (p.id)
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.appointment_date,
    cm.egfr_ckdepi,
    cm.ckd_stage
FROM patients p
JOIN appointments a ON a.patient_id = p.id
JOIN calculated_metrics cm ON cm.appointment_id = a.id
WHERE cm.egfr_ckdepi < 45
ORDER BY p.id, a.appointment_date DESC, cm.id DESC;

-- B03. Гиперкалиемия: калий > 5.5 ммоль/л
SELECT
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.appointment_date,
    b.investigation_date,
    b.potassium,
    cm.ckd_stage
FROM biochemistry_results b
JOIN appointments a ON a.id = b.appointment_id
JOIN patients p ON p.id = a.patient_id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
WHERE b.potassium > 5.5
ORDER BY b.potassium DESC, b.investigation_date DESC;

-- B04. Анемия: гемоглобин < 110 г/л
SELECT
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.appointment_date,
    c.investigation_date,
    c.hemoglobin,
    cm.ckd_stage
FROM cbc_results c
JOIN appointments a ON a.id = c.appointment_id
JOIN patients p ON p.id = a.patient_id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
WHERE c.hemoglobin < 110
ORDER BY c.hemoglobin ASC, c.investigation_date DESC;

-- B05. Выраженная альбуминурия A3 или ACR > 30 мг/ммоль
SELECT
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.appointment_date,
    ar.investigation_date,
    ar.albumin_creatinine_ratio AS acr_mg_mmol,
    ar.albuminuria_category
FROM albuminuria_results ar
JOIN appointments a ON a.id = ar.appointment_id
JOIN patients p ON p.id = a.patient_id
WHERE ar.albuminuria_category = 'A3'
   OR ar.albumin_creatinine_ratio > 30
ORDER BY ar.albumin_creatinine_ratio DESC;

-- B06. Пациенты без визита более 6 месяцев
SELECT
    p.id AS patient_id,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    MAX(a.appointment_date)::date AS last_appointment_date,
    CURRENT_DATE - MAX(a.appointment_date)::date AS days_since_last_appointment
FROM patients p
JOIN appointments a ON a.patient_id = p.id
GROUP BY p.id, p.last_name, p.first_name, p.patronymic
HAVING MAX(a.appointment_date) < CURRENT_DATE - INTERVAL '6 months'
ORDER BY last_appointment_date;

-- =====================================================
-- C. ОТЧЁТЫ ПО ОТДЕЛЕНИЮ / ВРАЧАМ
-- =====================================================

-- C01. Количество приёмов по врачам за последние 12 месяцев
SELECT
    d.id AS doctor_id,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio,
    COUNT(a.id) AS appointments_count,
    COUNT(DISTINCT a.patient_id) AS unique_patients_count
FROM doctors d
LEFT JOIN appointments a ON a.doctor_id = d.id
    AND a.appointment_date >= CURRENT_DATE - INTERVAL '12 months'
GROUP BY d.id, d.last_name, d.first_name, d.patronymic
ORDER BY appointments_count DESC, doctor_fio;

-- C02. Количество приёмов по филиалам и отделениям
SELECT
    b.name AS branch_name,
    l.name AS location_name,
    COUNT(a.id) AS appointments_count,
    COUNT(DISTINCT a.patient_id) AS unique_patients_count
FROM locations l
JOIN branches b ON b.id = l.branch_id
LEFT JOIN appointments a ON a.location_id = l.id
GROUP BY b.id, b.name, l.id, l.name
ORDER BY appointments_count DESC, branch_name, location_name;

-- C03. Распределение последних известных стадий СКФ по пациентам
WITH latest_metric AS (
    SELECT DISTINCT ON (a.patient_id)
        a.patient_id,
        cm.ckd_stage,
        cm.egfr_ckdepi,
        COALESCE(cm.investigation_date, a.appointment_date::date) AS metric_date
    FROM appointments a
    JOIN calculated_metrics cm ON cm.appointment_id = a.id
    WHERE cm.ckd_stage IS NOT NULL
    ORDER BY a.patient_id, COALESCE(cm.investigation_date, a.appointment_date::date) DESC, cm.id DESC
)
SELECT
    ckd_stage,
    COUNT(*) AS patients_count,
    ROUND(AVG(egfr_ckdepi), 1) AS avg_egfr
FROM latest_metric
GROUP BY ckd_stage
ORDER BY CASE ckd_stage
    WHEN 'С1' THEN 1 WHEN 'С2' THEN 2 WHEN 'С3а' THEN 3
    WHEN 'С3б' THEN 4 WHEN 'С4' THEN 5 WHEN 'С5' THEN 6 ELSE 99 END;

-- C04. Матрица KDIGO: количество пациентов по последней категории G/A
WITH latest_prognosis AS (
    SELECT DISTINCT ON (a.patient_id)
        a.patient_id,
        cpr.gfr_category,
        cpr.albuminuria_category,
        cpr.prognosis_level,
        cpr.prognosis_text,
        cpr.assessment_date
    FROM appointments a
    JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
    ORDER BY a.patient_id, cpr.assessment_date DESC, cpr.id DESC
)
SELECT
    gfr_category,
    albuminuria_category,
    prognosis_text,
    COUNT(*) AS patients_count
FROM latest_prognosis
GROUP BY gfr_category, albuminuria_category, prognosis_text
ORDER BY CASE gfr_category
    WHEN 'С1' THEN 1 WHEN 'С2' THEN 2 WHEN 'С3а' THEN 3
    WHEN 'С3б' THEN 4 WHEN 'С4' THEN 5 WHEN 'С5' THEN 6 ELSE 99 END,
    albuminuria_category;

-- C05. Топ назначаемых препаратов
SELECT
    medication,
    COUNT(*) AS prescriptions_count,
    COUNT(DISTINCT appointment_id) AS appointments_count
FROM prescriptions
WHERE medication IS NOT NULL
  AND LENGTH(TRIM(medication)) > 0
GROUP BY medication
ORDER BY prescriptions_count DESC, medication
LIMIT 20;

-- C06. Средние показатели по категориям прогноза ХБП
SELECT
    cpr.prognosis_text,
    COUNT(DISTINCT a.patient_id) AS patients_count,
    ROUND(AVG(cm.egfr_ckdepi), 1) AS avg_egfr,
    ROUND(AVG(ar.albumin_creatinine_ratio), 1) AS avg_acr_mg_mmol,
    ROUND(AVG(b.potassium), 2) AS avg_potassium,
    ROUND(AVG(c.hemoglobin), 1) AS avg_hemoglobin
FROM ckd_prognosis_results cpr
JOIN appointments a ON a.id = cpr.appointment_id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = a.id
LEFT JOIN biochemistry_results b ON b.appointment_id = a.id
LEFT JOIN cbc_results c ON c.appointment_id = a.id
GROUP BY cpr.prognosis_level, cpr.prognosis_text
ORDER BY CASE cpr.prognosis_level
    WHEN 'low' THEN 1 WHEN 'moderate' THEN 2 WHEN 'high' THEN 3 WHEN 'very_high' THEN 4 ELSE 99 END;

-- C07. Динамика средней СКФ по месяцам
SELECT
    DATE_TRUNC('month', COALESCE(cm.investigation_date, a.appointment_date::date))::date AS month,
    COUNT(*) AS measurements_count,
    ROUND(AVG(cm.egfr_ckdepi), 1) AS avg_egfr
FROM calculated_metrics cm
JOIN appointments a ON a.id = cm.appointment_id
WHERE cm.egfr_ckdepi IS NOT NULL
GROUP BY DATE_TRUNC('month', COALESCE(cm.investigation_date, a.appointment_date::date))
ORDER BY month;

-- =====================================================
-- D. КОНТРОЛЬ ЗАПОЛНЕНИЯ И КАЧЕСТВА ДАННЫХ
-- =====================================================

-- D01. Полнота заполнения блоков по каждому приёму
SELECT
    a.id AS appointment_id,
    a.appointment_date,
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    CASE WHEN s.id IS NOT NULL THEN 'да' ELSE 'нет' END AS has_survey,
    CASE WHEN e.id IS NOT NULL THEN 'да' ELSE 'нет' END AS has_examination,
    CASE WHEN EXISTS (SELECT 1 FROM cbc_results c WHERE c.appointment_id = a.id) THEN 'да' ELSE 'нет' END AS has_cbc,
    CASE WHEN EXISTS (SELECT 1 FROM biochemistry_results b WHERE b.appointment_id = a.id) THEN 'да' ELSE 'нет' END AS has_biochemistry,
    CASE WHEN EXISTS (SELECT 1 FROM urinalysis_results u WHERE u.appointment_id = a.id) THEN 'да' ELSE 'нет' END AS has_urinalysis,
    CASE WHEN EXISTS (SELECT 1 FROM albuminuria_results ar WHERE ar.appointment_id = a.id) THEN 'да' ELSE 'нет' END AS has_albuminuria,
    CASE WHEN EXISTS (SELECT 1 FROM ultrasound_results us WHERE us.appointment_id = a.id) THEN 'да' ELSE 'нет' END AS has_ultrasound,
    CASE WHEN d.id IS NOT NULL THEN 'да' ELSE 'нет' END AS has_diagnosis,
    CASE WHEN cpr.id IS NOT NULL THEN 'да' ELSE 'нет' END AS has_ckd_prognosis
FROM appointments a
JOIN patients p ON p.id = a.patient_id
LEFT JOIN surveys s ON s.appointment_id = a.id
LEFT JOIN examinations e ON e.appointment_id = a.id
LEFT JOIN diagnoses d ON d.appointment_id = a.id
LEFT JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
ORDER BY a.appointment_date DESC;

-- D02. Пациенты с несколькими строками calculated_metrics на один приём
-- Это не всегда ошибка: приложение поддерживает несколько анализов в рамках одного приёма.
SELECT
    appointment_id,
    COUNT(*) AS metrics_count,
    MIN(investigation_date) AS first_metric_date,
    MAX(investigation_date) AS last_metric_date
FROM calculated_metrics
GROUP BY appointment_id
HAVING COUNT(*) > 1
ORDER BY metrics_count DESC;

-- D03. Последний статус каждого пациента для быстрой сводки
WITH latest_appointment AS (
    SELECT DISTINCT ON (p.id)
        p.id AS patient_id,
        p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
        a.id AS appointment_id,
        a.appointment_date
    FROM patients p
    JOIN appointments a ON a.patient_id = p.id
    ORDER BY p.id, a.appointment_date DESC
)
SELECT
    la.patient_id,
    la.patient_fio,
    la.appointment_date AS last_appointment_date,
    cm.egfr_ckdepi,
    cm.ckd_stage,
    ar.albumin_creatinine_ratio AS acr_mg_mmol,
    ar.albuminuria_category,
    cpr.combined_category,
    cpr.prognosis_text
FROM latest_appointment la
LEFT JOIN calculated_metrics cm ON cm.appointment_id = la.appointment_id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = la.appointment_id
LEFT JOIN ckd_prognosis_results cpr ON cpr.appointment_id = la.appointment_id
ORDER BY la.patient_fio;
