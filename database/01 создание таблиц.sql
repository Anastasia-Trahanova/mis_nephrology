SET client_encoding = 'UTF8';

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
    gender BOOLEAN NULL,
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
    location_id INTEGER NULL,
    appointment_date TIMESTAMP NOT NULL,
    age_at_appointment SMALLINT NOT NULL
);

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    complaints TEXT,
    education_and_professional_history TEXT,
    housing_conditions TEXT,
    past_diseases TEXT,
    habitual_intoxications TEXT,
    gynecological_history TEXT,
    heredity_description TEXT,
    family_life TEXT,
    allergological_history TEXT,
    epidemiological_history TEXT,
    insurance_history TEXT,
    disease_onset TEXT,
    disease_course TEXT
);

CREATE TABLE IF NOT EXISTS examinations (
    id SERIAL PRIMARY KEY,
    appointment_id INTEGER NOT NULL,
    general_condition VARCHAR(30),
    consciousness VARCHAR(30),
    bed_position VARCHAR(30),
    bed_position_details TEXT,
    body_build TEXT,
    height NUMERIC(5,2),
    weight NUMERIC(5,2),
    bmi NUMERIC(5,2),
    constitution_type VARCHAR(30),
    skin_and_mucous_membranes TEXT,
    edema_location TEXT,
    lymph_nodes TEXT,
    thyroid_gland TEXT,
    musculoskeletal_system TEXT,
    body_temperature NUMERIC(4,1),
    systolic_pressure INTEGER,
    diastolic_pressure INTEGER,
    bp_note TEXT,
    heart_rate INTEGER,
    veins_condition TEXT,
    lung_auscultation TEXT,
    abdomen TEXT,
    kidney_palpation VARCHAR(30),
    kidney_palpation_details TEXT,
    pasternatsky_result VARCHAR(20),
    pasternatsky_side VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS cbc_results (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, investigation_date DATE NOT NULL,
    hemoglobin NUMERIC(6,2), erythrocytes NUMERIC(6,2), leukocytes NUMERIC(6,2),
    platelets NUMERIC(7,2), esr NUMERIC(6,2), mcv NUMERIC(6,2), hematocrit NUMERIC(6,2)
);

CREATE TABLE IF NOT EXISTS biochemistry_results (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, investigation_date DATE NOT NULL,
    creatinine NUMERIC(8,2), urea NUMERIC(8,2), uric_acid NUMERIC(8,2), glucose NUMERIC(6,2),
    total_protein NUMERIC(6,2), albumin NUMERIC(6,2), potassium NUMERIC(5,2), calcium NUMERIC(5,2),
    phosphorus NUMERIC(5,2), ferritin NUMERIC(8,2), ptg NUMERIC(8,2)
);

CREATE TABLE IF NOT EXISTS urinalysis_results (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, investigation_date DATE NOT NULL,
    specific_gravity NUMERIC(5,3), protein NUMERIC(8,3), leukocytes NUMERIC(8,2),
    erythrocytes NUMERIC(8,2), bacteria VARCHAR(100)
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
    daily_albumin_excretion NUMERIC(12,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ultrasound_results (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, investigation_date DATE NOT NULL,
    left_kidney_size VARCHAR(50), right_kidney_size VARCHAR(50),
    left_parenchyma NUMERIC(5,2), right_parenchyma NUMERIC(5,2), description TEXT
);

CREATE TABLE IF NOT EXISTS calculated_metrics (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, investigation_date DATE,
    creatinine NUMERIC(8,2), age INTEGER, gender BOOLEAN, weight_at_appointment NUMERIC(5,2),
    egfr_ckdepi NUMERIC(6,2), crcl_cockcroft_gault NUMERIC(6,2), ckd_stage VARCHAR(3),
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
    gfr_metric_id INTEGER,
    albuminuria_result_id INTEGER,
    gfr_investigation_date DATE,
    albuminuria_investigation_date DATE,
    gfr_source_type VARCHAR(30),
    albuminuria_source_type VARCHAR(30),
    source_interval_days INTEGER,
    calculation_status VARCHAR(30) NOT NULL DEFAULT 'calculated',
    display_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    hidden_at TIMESTAMP,
    hidden_reason TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointment_diets (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, diet TEXT,
    next_control_date DATE, recommendations TEXT
);

CREATE TABLE IF NOT EXISTS prescriptions (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL,
    medication VARCHAR(255), dosage VARCHAR(100), schedule VARCHAR(255), therapy_group VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS icd10_diagnoses (
    id SERIAL PRIMARY KEY, diagnosis TEXT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointment_icd10_diagnoses (
    id SERIAL PRIMARY KEY, appointment_id INTEGER NOT NULL, diagnosis_type VARCHAR(20) NOT NULL,
    icd10_diagnosis_id INTEGER NOT NULL, doctor_note TEXT, sort_order INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS medications (
    id SERIAL PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    trade_name VARCHAR(255),
    active_substance VARCHAR(255),
    drug_group VARCHAR(255),
    sort_order INTEGER NOT NULL DEFAULT 1000,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS appointment_additional_studies (
    appointment_id INTEGER PRIMARY KEY,
    other_laboratory_studies TEXT,
    other_instrumental_studies TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id INTEGER,
    user_login TEXT,
    user_role VARCHAR(50),
    action VARCHAR(100) NOT NULL,
    result VARCHAR(30) NOT NULL DEFAULT 'success',
    patient_id INTEGER,
    appointment_id INTEGER,
    entity_type VARCHAR(100),
    entity_id INTEGER,
    ip_address INET,
    path TEXT,
    method VARCHAR(10),
    status_code INTEGER,
    details TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS audit_event_changes (
    id SERIAL PRIMARY KEY,
    audit_event_id INTEGER NOT NULL,
    section VARCHAR(100) NOT NULL,
    section_label VARCHAR(255) NOT NULL,
    field_name VARCHAR(100),
    field_label VARCHAR(255),
    change_type VARCHAR(60) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    details TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS schedule_entries (
    id SERIAL PRIMARY KEY,
    scheduled_doctor_id INTEGER NOT NULL,
    location_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    starts_at TIMESTAMP NOT NULL,
    ends_at TIMESTAMP NOT NULL,
    appointment_type VARCHAR(20) NOT NULL DEFAULT 'primary',
    status VARCHAR(20) NOT NULL DEFAULT 'booked',
    actual_doctor_id INTEGER,
    appointment_id INTEGER,
    note TEXT,
    created_by_user_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP,
    cancelled_by_user_id INTEGER,
    cancel_reason TEXT
);

CREATE TABLE IF NOT EXISTS ckd_registry_entries (
    id BIGSERIAL PRIMARY KEY,
    patient_id INTEGER NOT NULL,
    included_at DATE NOT NULL,
    included_by_user_id INTEGER,
    diagnosis_at_inclusion TEXT NOT NULL,
    egfr_at_inclusion NUMERIC(6,2),
    ckd_stage_at_inclusion VARCHAR(3),
    comment_at_inclusion TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    closed_at DATE,
    closed_by_user_id INTEGER,
    close_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ckd_registry_outcomes (
    id BIGSERIAL PRIMARY KEY,
    registry_entry_id BIGINT NOT NULL,
    outcome_type VARCHAR(40) NOT NULL,
    outcome_date DATE NOT NULL,
    comment TEXT,
    created_by_user_id INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
