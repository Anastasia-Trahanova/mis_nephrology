-- ============================================================================
-- Файл: 09_stage1_form_integrity_checks.sql
-- Назначение: автоматические проверки первого этапа исключительно внутри БД.
--
-- Успешный результат: файл завершается без EXCEPTION и выводит итоговые
-- диагностические таблицы. Любая критическая ошибка останавливает выполнение.
--
-- Предусловия:
--   1) применена миграция 0009_previsit_form_schema;
--   2) выполнен 08_stage1_form_test_data.sql.
-- ============================================================================

-- --------------------------------------------------------------------------
-- 1. СТРУКТУРА СХЕМЫ.
-- --------------------------------------------------------------------------
DO $$
DECLARE
    missing_columns text;
    forbidden_columns text;
BEGIN
    SELECT string_agg(required.column_name, ', ' ORDER BY required.column_name)
    INTO missing_columns
    FROM (
        VALUES
            ('appointments', 'age_at_appointment'),
            ('surveys', 'complaints'),
            ('surveys', 'education_and_professional_history'),
            ('surveys', 'housing_conditions'),
            ('surveys', 'past_diseases'),
            ('surveys', 'habitual_intoxications'),
            ('surveys', 'gynecological_history'),
            ('surveys', 'heredity'),
            ('surveys', 'heredity_description'),
            ('surveys', 'family_life'),
            ('surveys', 'allergological_history'),
            ('surveys', 'epidemiological_history'),
            ('surveys', 'insurance_history'),
            ('surveys', 'disease_onset'),
            ('surveys', 'disease_course'),
            ('examinations', 'general_condition'),
            ('examinations', 'consciousness'),
            ('examinations', 'bed_position'),
            ('examinations', 'bed_position_details'),
            ('examinations', 'body_build'),
            ('examinations', 'height'),
            ('examinations', 'weight'),
            ('examinations', 'bmi'),
            ('examinations', 'constitution_type'),
            ('examinations', 'skin_and_mucous_membranes'),
            ('examinations', 'edema_location'),
            ('examinations', 'lymph_nodes'),
            ('examinations', 'thyroid_gland'),
            ('examinations', 'musculoskeletal_system'),
            ('examinations', 'body_temperature'),
            ('examinations', 'systolic_pressure'),
            ('examinations', 'diastolic_pressure'),
            ('examinations', 'bp_note'),
            ('examinations', 'heart_rate'),
            ('examinations', 'veins_condition'),
            ('examinations', 'lung_auscultation'),
            ('examinations', 'abdomen'),
            ('examinations', 'kidney_palpation'),
            ('examinations', 'kidney_palpation_details'),
            ('examinations', 'pasternatsky_result'),
            ('examinations', 'pasternatsky_side')
    ) AS required(table_name, column_name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns AS c
        WHERE c.table_schema = current_schema()
          AND c.table_name = required.table_name
          AND c.column_name = required.column_name
    );

    IF missing_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Не найдены обязательные столбцы: %', missing_columns;
    END IF;

    SELECT string_agg(legacy.table_name || '.' || legacy.column_name, ', ')
    INTO forbidden_columns
    FROM (
        VALUES
            ('surveys', 'life_anamnesis'),
            ('surveys', 'disease_anamnesis'),
            ('surveys', 'comorbidities'),
            ('examinations', 'skin_condition')
    ) AS legacy(table_name, column_name)
    WHERE EXISTS (
        SELECT 1
        FROM information_schema.columns AS c
        WHERE c.table_schema = current_schema()
          AND c.table_name = legacy.table_name
          AND c.column_name = legacy.column_name
    );

    IF forbidden_columns IS NOT NULL THEN
        RAISE EXCEPTION 'Legacy-столбцы не удалены: %', forbidden_columns;
    END IF;
END
$$;

-- Проверяем наличие ключевых CHECK-ограничений.
DO $$
DECLARE
    missing_constraints text;
BEGIN
    SELECT string_agg(expected.name, ', ' ORDER BY expected.name)
    INTO missing_constraints
    FROM (
        VALUES
            ('chk_appointments_age_at_appointment'),
            ('chk_surveys_heredity_description'),
            ('chk_examinations_general_condition'),
            ('chk_examinations_consciousness'),
            ('chk_examinations_bed_position'),
            ('chk_examinations_bed_position_details'),
            ('chk_examinations_constitution_type'),
            ('chk_examinations_body_temperature'),
            ('chk_examinations_kidney_palpation'),
            ('chk_examinations_kidney_palpation_details'),
            ('chk_examinations_pasternatsky_result'),
            ('chk_examinations_pasternatsky_side'),
            ('chk_examinations_pasternatsky_pair')
    ) AS expected(name)
    WHERE NOT EXISTS (
        SELECT 1
        FROM pg_constraint AS pc
        WHERE pc.conname = expected.name
    );

    IF missing_constraints IS NOT NULL THEN
        RAISE EXCEPTION 'Не найдены CHECK-ограничения: %', missing_constraints;
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 2. СВЯЗИ И КОЛИЧЕСТВО ТЕСТОВЫХ СТРОК.
-- --------------------------------------------------------------------------
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM appointments WHERE id BETWEEN 1 AND 17) <> 17 THEN
        RAISE EXCEPTION 'Ожидалось 17 тестовых приёмов с id 1–17';
    END IF;

    IF (SELECT COUNT(*) FROM surveys WHERE appointment_id BETWEEN 1 AND 17) <> 17 THEN
        RAISE EXCEPTION 'Не для всех 17 тестовых приёмов создан surveys';
    END IF;

    IF (SELECT COUNT(*) FROM examinations WHERE appointment_id BETWEEN 1 AND 17) <> 17 THEN
        RAISE EXCEPTION 'Не для всех 17 тестовых приёмов создан examinations';
    END IF;

    IF EXISTS (
        SELECT appointment_id
        FROM surveys
        GROUP BY appointment_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Обнаружены дубли surveys для одного приёма';
    END IF;

    IF EXISTS (
        SELECT appointment_id
        FROM examinations
        GROUP BY appointment_id
        HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'Обнаружены дубли examinations для одного приёма';
    END IF;

    IF EXISTS (
        SELECT 1 FROM surveys s
        LEFT JOIN appointments a ON a.id = s.appointment_id
        WHERE a.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Обнаружен surveys без существующего appointments';
    END IF;

    IF EXISTS (
        SELECT 1 FROM examinations e
        LEFT JOIN appointments a ON a.id = e.appointment_id
        WHERE a.id IS NULL
    ) THEN
        RAISE EXCEPTION 'Обнаружен examinations без существующего appointments';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 3. ВОЗРАСТ НА ДАТУ ПРИЁМА.
-- --------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE a.id BETWEEN 1 AND 17
          AND a.age_at_appointment IS DISTINCT FROM
              EXTRACT(YEAR FROM age(a.appointment_date::date, p.birth_date))::smallint
    ) THEN
        RAISE EXCEPTION 'Возраст на дату приёма рассчитан неверно';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 4. АНАМНЕЗ.
-- --------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM surveys s
        WHERE s.appointment_id BETWEEN 1 AND 17
          AND (
              NULLIF(BTRIM(s.complaints), '') IS NULL
              OR NULLIF(BTRIM(s.education_and_professional_history), '') IS NULL
              OR NULLIF(BTRIM(s.housing_conditions), '') IS NULL
              OR NULLIF(BTRIM(s.past_diseases), '') IS NULL
              OR NULLIF(BTRIM(s.habitual_intoxications), '') IS NULL
              OR NULLIF(BTRIM(s.family_life), '') IS NULL
              OR NULLIF(BTRIM(s.allergological_history), '') IS NULL
              OR NULLIF(BTRIM(s.epidemiological_history), '') IS NULL
              OR NULLIF(BTRIM(s.insurance_history), '') IS NULL
              OR NULLIF(BTRIM(s.disease_onset), '') IS NULL
              OR NULLIF(BTRIM(s.disease_course), '') IS NULL
          )
    ) THEN
        RAISE EXCEPTION 'В обязательном тестовом анамнезе есть пустые значения';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM surveys
        WHERE heredity = TRUE
          AND NULLIF(BTRIM(heredity_description), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'Отягощённая наследственность не имеет описания';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM surveys
        WHERE heredity = FALSE
          AND heredity_description IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'При отрицательной наследственности осталось описание';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM surveys s
        JOIN appointments a ON a.id = s.appointment_id
        JOIN patients p ON p.id = a.patient_id
        WHERE s.appointment_id BETWEEN 1 AND 17
          AND p.gender = TRUE
          AND s.gynecological_history IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'У пациента мужского пола заполнен гинекологический анамнез';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM surveys s
        JOIN appointments a ON a.id = s.appointment_id
        JOIN patients p ON p.id = a.patient_id
        WHERE s.appointment_id BETWEEN 1 AND 17
          AND p.gender = FALSE
          AND NULLIF(BTRIM(s.gynecological_history), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'У тестовой пациентки не заполнен гинекологический анамнез';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 5. ОБЪЕКТИВНЫЙ ОСМОТР.
-- --------------------------------------------------------------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM examinations e
        WHERE e.appointment_id BETWEEN 1 AND 17
          AND (
              NULLIF(BTRIM(e.body_build), '') IS NULL
              OR NULLIF(BTRIM(e.skin_and_mucous_membranes), '') IS NULL
              OR NULLIF(BTRIM(e.edema_location), '') IS NULL
              OR NULLIF(BTRIM(e.lymph_nodes), '') IS NULL
              OR NULLIF(BTRIM(e.thyroid_gland), '') IS NULL
              OR NULLIF(BTRIM(e.musculoskeletal_system), '') IS NULL
              OR NULLIF(BTRIM(e.veins_condition), '') IS NULL
              OR NULLIF(BTRIM(e.lung_auscultation), '') IS NULL
              OR NULLIF(BTRIM(e.abdomen), '') IS NULL
          )
    ) THEN
        RAISE EXCEPTION 'В обязательном тестовом объективном осмотре есть пустые тексты';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND bed_position = 'forced'
          AND NULLIF(BTRIM(bed_position_details), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'Вынужденное положение не имеет уточнения';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND bed_position <> 'forced'
          AND bed_position_details IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'Уточнение положения заполнено не для вынужденного положения';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND kidney_palpation = 'palpable'
          AND NULLIF(BTRIM(kidney_palpation_details), '') IS NULL
    ) THEN
        RAISE EXCEPTION 'Пальпируемые почки не имеют текстового уточнения';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND ((pasternatsky_result IS NULL) <> (pasternatsky_side IS NULL))
    ) THEN
        RAISE EXCEPTION 'Результат и сторона симптома Пастернацкого заполнены несогласованно';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND (
              systolic_pressure <= diastolic_pressure
              OR body_temperature NOT BETWEEN 25.0 AND 45.0
              OR height NOT BETWEEN 50 AND 250
              OR weight NOT BETWEEN 20 AND 300
              OR heart_rate NOT BETWEEN 30 AND 220
          )
    ) THEN
        RAISE EXCEPTION 'Обнаружены технически недопустимые показатели осмотра';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM examinations
        WHERE appointment_id BETWEEN 1 AND 17
          AND ABS(
              bmi - ROUND((weight / POWER(height / 100.0, 2))::numeric, 2)
          ) > 0.01
    ) THEN
        RAISE EXCEPTION 'ИМТ не соответствует росту и весу';
    END IF;
END
$$;

-- Проверяем, что набор тестовых данных покрывает основные варианты формы.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND general_condition = 'satisfactory')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND general_condition = 'moderate')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND general_condition = 'severe') THEN
        RAISE EXCEPTION 'Тестовые данные не покрывают все варианты общего состояния';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND bed_position = 'active')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND bed_position = 'passive')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND bed_position = 'forced') THEN
        RAISE EXCEPTION 'Тестовые данные не покрывают все варианты положения в постели';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND constitution_type = 'normosthenic')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND constitution_type = 'asthenic')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND constitution_type = 'hypersthenic') THEN
        RAISE EXCEPTION 'Тестовые данные не покрывают все типы конституции';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND pasternatsky_result = 'positive' AND pasternatsky_side = 'right')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND pasternatsky_result = 'positive' AND pasternatsky_side = 'left')
       OR NOT EXISTS (SELECT 1 FROM examinations WHERE appointment_id BETWEEN 1 AND 17 AND pasternatsky_result = 'positive' AND pasternatsky_side = 'bilateral') THEN
        RAISE EXCEPTION 'Тестовые данные не покрывают правый, левый и двусторонний положительный симптом Пастернацкого';
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 6. СОХРАННОСТЬ СВЯЗЕЙ НИЖНЕЙ ЧАСТИ ФОРМЫ.
-- Содержимое исследований не проверяется и не изменяется на первом этапе.
-- --------------------------------------------------------------------------
DO $$
DECLARE
    orphan_count integer;
BEGIN
    SELECT COUNT(*) INTO orphan_count
    FROM (
        SELECT appointment_id FROM cbc_results
        UNION ALL SELECT appointment_id FROM biochemistry_results
        UNION ALL SELECT appointment_id FROM urinalysis_results
        UNION ALL SELECT appointment_id FROM albuminuria_results
        UNION ALL SELECT appointment_id FROM ultrasound_results
        UNION ALL SELECT appointment_id FROM calculated_metrics
        UNION ALL SELECT appointment_id FROM ckd_prognosis_results
        UNION ALL SELECT appointment_id FROM appointment_diets
        UNION ALL SELECT appointment_id FROM prescriptions
        UNION ALL SELECT appointment_id FROM appointment_icd10_diagnoses
    ) AS child
    LEFT JOIN appointments a ON a.id = child.appointment_id
    WHERE a.id IS NULL;

    IF orphan_count > 0 THEN
        RAISE EXCEPTION 'Найдены дочерние данные без существующего приёма: %', orphan_count;
    END IF;
END
$$;

-- --------------------------------------------------------------------------
-- 7. ИТОГОВЫЕ ДИАГНОСТИЧЕСКИЕ ВЫБОРКИ.
-- --------------------------------------------------------------------------
SELECT
    a.id AS appointment_id,
    p.last_name || ' ' || p.first_name AS patient,
    a.appointment_date,
    a.age_at_appointment,
    e.general_condition
FROM appointments a
JOIN patients p ON p.id = a.patient_id
LEFT JOIN examinations e ON e.appointment_id = a.id
WHERE a.id BETWEEN 1 AND 17
ORDER BY a.id;

SELECT
    general_condition,
    COUNT(*) AS rows_count
FROM examinations
WHERE appointment_id BETWEEN 1 AND 17
GROUP BY general_condition
ORDER BY general_condition;

SELECT
    bed_position,
    COUNT(*) AS rows_count
FROM examinations
WHERE appointment_id BETWEEN 1 AND 17
GROUP BY bed_position
ORDER BY bed_position;

SELECT
    pasternatsky_result,
    pasternatsky_side,
    COUNT(*) AS rows_count
FROM examinations
WHERE appointment_id BETWEEN 1 AND 17
GROUP BY pasternatsky_result, pasternatsky_side
ORDER BY pasternatsky_result, pasternatsky_side;

-- Информационная, не блокирующая проверка legacy calculated_metrics.age.
-- Эти расчётные данные относятся к третьему этапу и здесь не исправляются.
SELECT
    a.id AS appointment_id,
    a.age_at_appointment,
    cm.age AS legacy_calculated_metrics_age
FROM appointments a
JOIN calculated_metrics cm ON cm.appointment_id = a.id
WHERE a.id BETWEEN 1 AND 17
  AND cm.age IS DISTINCT FROM a.age_at_appointment
ORDER BY a.id;
