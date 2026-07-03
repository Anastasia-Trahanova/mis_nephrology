-- ЛЕГЕНДА
-- Файл: 01 создание таблиц.sql
-- Назначение: создаёт финальную структуру таблиц для программы нефролога.
-- Что внутри: справочники организации, пользователи, пациенты, приёмы, клинические блоки, анализы, расчёты и прогноз ХБП.
-- Важно: здесь создаются таблицы и первичные ключи. Внешние ключи, CHECK, UNIQUE и индексы вынесены в 02_constraints_indexes.sql.
-- Дополнение: поле appointment_diets.recommendations уже включено в структуру, отдельный файл 01b больше не нужен.
-- Версия v3: DBeaver-safe, без явного BEGIN/COMMIT.

CREATE TABLE IF NOT EXISTS companies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    legal_address TEXT,
    phone VARCHAR(50),
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS branches (
    id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    legal_address TEXT,
    phone VARCHAR(50),
    fax VARCHAR(50),
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER NOT NULL,
    company_id INTEGER,
    name VARCHAR(255) NOT NULL,
    factual_address TEXT,
    phone VARCHAR(50),
    email VARCHAR(255),
    fax VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS doctors (
    id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    patronymic VARCHAR(100),
    position VARCHAR(255),
    initial_education TEXT,
    retraining_institution TEXT,
    certificate TEXT,
    qualification TEXT,
    phone VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS doctor_locations (
    id SERIAL PRIMARY KEY,
    doctor_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    last_name VARCHAR(100) NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    patronymic VARCHAR(100),
    birth_date DATE NOT NULL,
    gender BOOLEAN NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    login VARCHAR(100) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL,
    doctor_id INTEGER,
    patient_id INTEGER
);

CREATE TABLE IF NOT EXISTS appointments (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    appointment_date TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    life_anamnesis TEXT,
    disease_anamnesis TEXT,
    complaints TEXT,
    heredity BOOLEAN DEFAULT FALSE,
    heredity_description TEXT,
    comorbidities TEXT
);

CREATE TABLE IF NOT EXISTS examinations (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    skin_condition TEXT,
    edema_location TEXT,
    systolic_pressure INTEGER,
    diastolic_pressure INTEGER,
    bp_note TEXT,
    heart_rate INTEGER,
    height NUMERIC(5,2),
    weight NUMERIC(5,2)
);

CREATE TABLE IF NOT EXISTS cbc_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE NOT NULL,
    hemoglobin NUMERIC(6,2),
    erythrocytes NUMERIC(6,2),
    leukocytes NUMERIC(6,2),
    platelets NUMERIC(7,2),
    esr NUMERIC(6,2),
    mcv NUMERIC(6,2),
    hematocrit NUMERIC(6,2)
);

CREATE TABLE IF NOT EXISTS biochemistry_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE NOT NULL,
    creatinine NUMERIC(8,2),
    urea NUMERIC(8,2),
    uric_acid NUMERIC(8,2),
    glucose NUMERIC(6,2),
    total_protein NUMERIC(6,2),
    albumin NUMERIC(6,2),
    potassium NUMERIC(5,2),
    calcium NUMERIC(5,2),
    phosphorus NUMERIC(5,2),
    ferritin NUMERIC(8,2),
    ptg NUMERIC(8,2)
);

CREATE TABLE IF NOT EXISTS urinalysis_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE NOT NULL,
    specific_gravity NUMERIC(5,3),
    protein NUMERIC(8,3),
    leukocytes NUMERIC(8,2),
    erythrocytes NUMERIC(8,2),
    bacteria VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS albuminuria_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE NOT NULL,
    urine_albumin NUMERIC(10,3),
    urine_albumin_unit VARCHAR(20) NOT NULL DEFAULT 'mg_l',
    urine_creatinine NUMERIC(10,3),
    urine_creatinine_unit VARCHAR(20) NOT NULL DEFAULT 'mmol_l',
    albumin_creatinine_ratio NUMERIC(10,2),
    albuminuria_category VARCHAR(2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ultrasound_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE NOT NULL,
    left_kidney_size VARCHAR(50),
    right_kidney_size VARCHAR(50),
    left_parenchyma NUMERIC(5,2),
    right_parenchyma NUMERIC(5,2),
    description TEXT
);

CREATE TABLE IF NOT EXISTS calculated_metrics (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    investigation_date DATE,
    creatinine NUMERIC(8,2),
    age INTEGER,
    gender BOOLEAN,
    weight_at_appointment NUMERIC(5,2),
    egfr_ckdepi NUMERIC(6,2),
    crcl_cockcroft_gault NUMERIC(6,2),
    ckd_stage VARCHAR(3),
    calculation_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ckd_prognosis_results (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    assessment_date DATE NOT NULL,
    gfr_category VARCHAR(3),
    albuminuria_category VARCHAR(2),
    combined_category VARCHAR(8),
    prognosis_level VARCHAR(20),
    prognosis_text VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS diagnoses (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    main_diagnosis TEXT,
    complications TEXT,
    comorbidities TEXT
);

CREATE TABLE IF NOT EXISTS appointment_diets (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    diet TEXT,
    next_control_date DATE,
    recommendations TEXT
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    medication VARCHAR(255),
    dosage VARCHAR(100),
    schedule VARCHAR(255)
);
