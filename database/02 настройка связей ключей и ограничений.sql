-- ЛЕГЕНДА
-- Файл: 02 настройка связей ключей и ограничений.sql
-- Назначение: добавляет внешние ключи, ограничения целостности, UNIQUE и индексы.
-- Когда запускать: после 01_create_tables.sql и до заполнения тестовыми данными.
-- Важно: если в базе уже есть плохие данные, часть ALTER TABLE может упасть. Для чистой базы файл должен выполниться без ошибок.
-- Версия v3: DBeaver-safe, без явного BEGIN/COMMIT.

-- =====================================================
-- 1. ВНЕШНИЕ КЛЮЧИ
-- =====================================================

ALTER TABLE branches DROP CONSTRAINT IF EXISTS fk_branches_company;
ALTER TABLE branches
    ADD CONSTRAINT fk_branches_company
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT;

ALTER TABLE locations DROP CONSTRAINT IF EXISTS fk_locations_branch;
ALTER TABLE locations
    ADD CONSTRAINT fk_locations_branch
    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT;

ALTER TABLE locations DROP CONSTRAINT IF EXISTS fk_locations_company;
ALTER TABLE locations
    ADD CONSTRAINT fk_locations_company
    FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT;

ALTER TABLE doctor_locations DROP CONSTRAINT IF EXISTS fk_doctor_locations_doctor;
ALTER TABLE doctor_locations
    ADD CONSTRAINT fk_doctor_locations_doctor
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE;

ALTER TABLE doctor_locations DROP CONSTRAINT IF EXISTS fk_doctor_locations_location;
ALTER TABLE doctor_locations
    ADD CONSTRAINT fk_doctor_locations_location
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE;

ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_doctor;
ALTER TABLE users
    ADD CONSTRAINT fk_users_doctor
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;

ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_patient;
ALTER TABLE users
    ADD CONSTRAINT fk_users_patient
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS fk_appointments_patient;
ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_patient
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS fk_appointments_doctor;
ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_doctor
    FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS fk_appointments_location;
ALTER TABLE appointments
    ADD CONSTRAINT fk_appointments_location
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT;

ALTER TABLE surveys DROP CONSTRAINT IF EXISTS fk_surveys_appointment;
ALTER TABLE surveys
    ADD CONSTRAINT fk_surveys_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE examinations DROP CONSTRAINT IF EXISTS fk_examinations_appointment;
ALTER TABLE examinations
    ADD CONSTRAINT fk_examinations_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE cbc_results DROP CONSTRAINT IF EXISTS fk_cbc_appointment;
ALTER TABLE cbc_results
    ADD CONSTRAINT fk_cbc_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE biochemistry_results DROP CONSTRAINT IF EXISTS fk_biochemistry_appointment;
ALTER TABLE biochemistry_results
    ADD CONSTRAINT fk_biochemistry_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE urinalysis_results DROP CONSTRAINT IF EXISTS fk_urinalysis_appointment;
ALTER TABLE urinalysis_results
    ADD CONSTRAINT fk_urinalysis_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE albuminuria_results DROP CONSTRAINT IF EXISTS fk_albuminuria_appointment;
ALTER TABLE albuminuria_results
    ADD CONSTRAINT fk_albuminuria_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE ultrasound_results DROP CONSTRAINT IF EXISTS fk_ultrasound_appointment;
ALTER TABLE ultrasound_results
    ADD CONSTRAINT fk_ultrasound_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE calculated_metrics DROP CONSTRAINT IF EXISTS fk_calculated_metrics_appointment;
ALTER TABLE calculated_metrics
    ADD CONSTRAINT fk_calculated_metrics_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE ckd_prognosis_results DROP CONSTRAINT IF EXISTS fk_ckd_prognosis_appointment;
ALTER TABLE ckd_prognosis_results
    ADD CONSTRAINT fk_ckd_prognosis_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE diagnoses DROP CONSTRAINT IF EXISTS fk_diagnoses_appointment;
ALTER TABLE diagnoses
    ADD CONSTRAINT fk_diagnoses_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE appointment_diets DROP CONSTRAINT IF EXISTS fk_appointment_diets_appointment;
ALTER TABLE appointment_diets
    ADD CONSTRAINT fk_appointment_diets_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

ALTER TABLE prescriptions DROP CONSTRAINT IF EXISTS fk_prescriptions_appointment;
ALTER TABLE prescriptions
    ADD CONSTRAINT fk_prescriptions_appointment
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;

-- =====================================================
-- 2. UNIQUE-ОГРАНИЧЕНИЯ
-- =====================================================

ALTER TABLE users DROP CONSTRAINT IF EXISTS uq_users_login;
ALTER TABLE users ADD CONSTRAINT uq_users_login UNIQUE (login);

ALTER TABLE doctor_locations DROP CONSTRAINT IF EXISTS uq_doctor_locations_pair;
ALTER TABLE doctor_locations ADD CONSTRAINT uq_doctor_locations_pair UNIQUE (doctor_id, location_id);

ALTER TABLE surveys DROP CONSTRAINT IF EXISTS uq_surveys_appointment;
ALTER TABLE surveys ADD CONSTRAINT uq_surveys_appointment UNIQUE (appointment_id);

ALTER TABLE examinations DROP CONSTRAINT IF EXISTS uq_examinations_appointment;
ALTER TABLE examinations ADD CONSTRAINT uq_examinations_appointment UNIQUE (appointment_id);

ALTER TABLE diagnoses DROP CONSTRAINT IF EXISTS uq_diagnoses_appointment;
ALTER TABLE diagnoses ADD CONSTRAINT uq_diagnoses_appointment UNIQUE (appointment_id);

ALTER TABLE appointment_diets DROP CONSTRAINT IF EXISTS uq_appointment_diets_appointment;
ALTER TABLE appointment_diets ADD CONSTRAINT uq_appointment_diets_appointment UNIQUE (appointment_id);

ALTER TABLE ckd_prognosis_results DROP CONSTRAINT IF EXISTS uq_ckd_prognosis_appointment;
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT uq_ckd_prognosis_appointment UNIQUE (appointment_id);

-- =====================================================
-- 3. CHECK-ОГРАНИЧЕНИЯ
-- =====================================================

ALTER TABLE patients DROP CONSTRAINT IF EXISTS chk_patients_birth_date_reasonable;
ALTER TABLE patients
    ADD CONSTRAINT chk_patients_birth_date_reasonable
    CHECK (birth_date >= DATE '1900-01-01' AND birth_date <= CURRENT_DATE);

ALTER TABLE users DROP CONSTRAINT IF EXISTS chk_users_role_model;
ALTER TABLE users
    ADD CONSTRAINT chk_users_role_model
    CHECK (
        role IN ('admin', 'doctor', 'patient')
        AND (
            (role = 'admin'  AND doctor_id IS NULL     AND patient_id IS NULL)
            OR
            (role = 'doctor' AND doctor_id IS NOT NULL AND patient_id IS NULL)
            OR
            (role = 'patient' AND doctor_id IS NULL    AND patient_id IS NOT NULL)
        )
    );

ALTER TABLE appointments DROP CONSTRAINT IF EXISTS chk_appointments_not_future;
ALTER TABLE appointments
    ADD CONSTRAINT chk_appointments_not_future
    CHECK (appointment_date <= CURRENT_TIMESTAMP);

ALTER TABLE examinations DROP CONSTRAINT IF EXISTS chk_examinations_bp;
ALTER TABLE examinations
    ADD CONSTRAINT chk_examinations_bp
    CHECK (
        (systolic_pressure IS NULL OR systolic_pressure BETWEEN 40 AND 280)
        AND (diastolic_pressure IS NULL OR diastolic_pressure BETWEEN 20 AND 200)
        AND (
            systolic_pressure IS NULL
            OR diastolic_pressure IS NULL
            OR systolic_pressure > diastolic_pressure
        )
    );

ALTER TABLE examinations DROP CONSTRAINT IF EXISTS chk_examinations_heart_rate;
ALTER TABLE examinations
    ADD CONSTRAINT chk_examinations_heart_rate
    CHECK (heart_rate IS NULL OR heart_rate BETWEEN 30 AND 220);

ALTER TABLE examinations DROP CONSTRAINT IF EXISTS chk_examinations_anthropometry;
ALTER TABLE examinations
    ADD CONSTRAINT chk_examinations_anthropometry
    CHECK (
        (height IS NULL OR height BETWEEN 50 AND 250)
        AND (weight IS NULL OR weight BETWEEN 20 AND 300)
    );

ALTER TABLE cbc_results DROP CONSTRAINT IF EXISTS chk_cbc_non_negative;
ALTER TABLE cbc_results
    ADD CONSTRAINT chk_cbc_non_negative
    CHECK (
        (hemoglobin IS NULL OR hemoglobin >= 0)
        AND (erythrocytes IS NULL OR erythrocytes >= 0)
        AND (leukocytes IS NULL OR leukocytes >= 0)
        AND (platelets IS NULL OR platelets >= 0)
        AND (esr IS NULL OR esr >= 0)
        AND (mcv IS NULL OR mcv >= 0)
        AND (hematocrit IS NULL OR hematocrit >= 0)
    );

ALTER TABLE biochemistry_results DROP CONSTRAINT IF EXISTS chk_biochemistry_non_negative;
ALTER TABLE biochemistry_results
    ADD CONSTRAINT chk_biochemistry_non_negative
    CHECK (
        (creatinine IS NULL OR creatinine > 0)
        AND (urea IS NULL OR urea >= 0)
        AND (uric_acid IS NULL OR uric_acid >= 0)
        AND (glucose IS NULL OR glucose >= 0)
        AND (total_protein IS NULL OR total_protein >= 0)
        AND (albumin IS NULL OR albumin >= 0)
        AND (potassium IS NULL OR potassium >= 0)
        AND (calcium IS NULL OR calcium >= 0)
        AND (phosphorus IS NULL OR phosphorus >= 0)
        AND (ferritin IS NULL OR ferritin >= 0)
        AND (ptg IS NULL OR ptg >= 0)
    );

ALTER TABLE urinalysis_results DROP CONSTRAINT IF EXISTS chk_urinalysis_non_negative;
ALTER TABLE urinalysis_results
    ADD CONSTRAINT chk_urinalysis_non_negative
    CHECK (
        (specific_gravity IS NULL OR specific_gravity >= 0)
        AND (protein IS NULL OR protein >= 0)
        AND (leukocytes IS NULL OR leukocytes >= 0)
        AND (erythrocytes IS NULL OR erythrocytes >= 0)
    );

ALTER TABLE albuminuria_results DROP CONSTRAINT IF EXISTS chk_albuminuria_units;
ALTER TABLE albuminuria_results
    ADD CONSTRAINT chk_albuminuria_units
    CHECK (
        urine_albumin_unit IN ('mg_l', 'g_l')
        AND urine_creatinine_unit IN ('mmol_l', 'umol_l')
    );

ALTER TABLE albuminuria_results DROP CONSTRAINT IF EXISTS chk_albuminuria_values;
ALTER TABLE albuminuria_results
    ADD CONSTRAINT chk_albuminuria_values
    CHECK (
        (urine_albumin IS NULL OR urine_albumin >= 0)
        AND (urine_creatinine IS NULL OR urine_creatinine > 0)
        AND (albumin_creatinine_ratio IS NULL OR albumin_creatinine_ratio >= 0)
    );

ALTER TABLE albuminuria_results DROP CONSTRAINT IF EXISTS chk_albuminuria_category;
ALTER TABLE albuminuria_results
    ADD CONSTRAINT chk_albuminuria_category
    CHECK (albuminuria_category IS NULL OR albuminuria_category IN ('A1', 'A2', 'A3'));

ALTER TABLE ultrasound_results DROP CONSTRAINT IF EXISTS chk_ultrasound_values;
ALTER TABLE ultrasound_results
    ADD CONSTRAINT chk_ultrasound_values
    CHECK (
        (left_parenchyma IS NULL OR left_parenchyma >= 0)
        AND (right_parenchyma IS NULL OR right_parenchyma >= 0)
    );

ALTER TABLE calculated_metrics DROP CONSTRAINT IF EXISTS chk_calculated_metrics_values;
ALTER TABLE calculated_metrics
    ADD CONSTRAINT chk_calculated_metrics_values
    CHECK (
        (creatinine IS NULL OR creatinine > 0)
        AND (age IS NULL OR age BETWEEN 0 AND 120)
        AND (weight_at_appointment IS NULL OR weight_at_appointment BETWEEN 20 AND 300)
        AND (egfr_ckdepi IS NULL OR egfr_ckdepi >= 0)
        AND (crcl_cockcroft_gault IS NULL OR crcl_cockcroft_gault >= 0)
    );

ALTER TABLE calculated_metrics DROP CONSTRAINT IF EXISTS chk_calculated_metrics_ckd_stage;
ALTER TABLE calculated_metrics
    ADD CONSTRAINT chk_calculated_metrics_ckd_stage
    CHECK (ckd_stage IS NULL OR ckd_stage IN ('С1', 'С2', 'С3а', 'С3б', 'С4', 'С5'));

ALTER TABLE ckd_prognosis_results DROP CONSTRAINT IF EXISTS chk_ckd_prognosis_categories;
ALTER TABLE ckd_prognosis_results
    ADD CONSTRAINT chk_ckd_prognosis_categories
    CHECK (
        (gfr_category IS NULL OR gfr_category IN ('С1', 'С2', 'С3а', 'С3б', 'С4', 'С5'))
        AND (albuminuria_category IS NULL OR albuminuria_category IN ('A1', 'A2', 'A3'))
        AND (prognosis_level IS NULL OR prognosis_level IN ('low', 'moderate', 'high', 'very_high'))
    );

ALTER TABLE diagnoses DROP CONSTRAINT IF EXISTS chk_diagnoses_main_not_blank;
ALTER TABLE diagnoses
    ADD CONSTRAINT chk_diagnoses_main_not_blank
    CHECK (main_diagnosis IS NULL OR LENGTH(TRIM(main_diagnosis)) > 0);

-- =====================================================
-- 4. ИНДЕКСЫ ДЛЯ РАБОТЫ ПРИЛОЖЕНИЯ
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_patients_fio ON patients (last_name, first_name, patronymic);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_id ON appointments (patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor_id ON appointments (doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_location_id ON appointments (location_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments (appointment_date);
CREATE INDEX IF NOT EXISTS idx_appointments_patient_date ON appointments (patient_id, appointment_date DESC);
CREATE INDEX IF NOT EXISTS idx_doctor_locations_doctor_id ON doctor_locations (doctor_id);
CREATE INDEX IF NOT EXISTS idx_doctor_locations_location_id ON doctor_locations (location_id);
CREATE INDEX IF NOT EXISTS idx_locations_branch_id ON locations (branch_id);
CREATE INDEX IF NOT EXISTS idx_branches_company_id ON branches (company_id);

CREATE INDEX IF NOT EXISTS idx_cbc_appointment_id ON cbc_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_cbc_appointment_date ON cbc_results (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_biochemistry_appointment_id ON biochemistry_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_biochemistry_appointment_date ON biochemistry_results (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_urinalysis_appointment_id ON urinalysis_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_urinalysis_appointment_date ON urinalysis_results (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_albuminuria_appointment_id ON albuminuria_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_albuminuria_appointment_date ON albuminuria_results (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_ultrasound_appointment_id ON ultrasound_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_ultrasound_appointment_date ON ultrasound_results (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_calculated_metrics_appointment_id ON calculated_metrics (appointment_id);
CREATE INDEX IF NOT EXISTS idx_calculated_metrics_appointment_date ON calculated_metrics (appointment_id, investigation_date);
CREATE INDEX IF NOT EXISTS idx_ckd_prognosis_appointment_id ON ckd_prognosis_results (appointment_id);
CREATE INDEX IF NOT EXISTS idx_ckd_prognosis_assessment_date ON ckd_prognosis_results (assessment_date);
CREATE INDEX IF NOT EXISTS idx_prescriptions_appointment_id ON prescriptions (appointment_id);
CREATE INDEX IF NOT EXISTS idx_surveys_appointment_id ON surveys (appointment_id);
CREATE INDEX IF NOT EXISTS idx_examinations_appointment_id ON examinations (appointment_id);
CREATE INDEX IF NOT EXISTS idx_diagnoses_appointment_id ON diagnoses (appointment_id);
CREATE INDEX IF NOT EXISTS idx_appointment_diets_appointment_id ON appointment_diets (appointment_id);
