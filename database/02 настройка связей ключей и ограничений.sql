SET client_encoding = 'UTF8';

-- Внешние ключи
ALTER TABLE branches ADD CONSTRAINT fk_branches_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT;
ALTER TABLE locations ADD CONSTRAINT fk_locations_branch FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE RESTRICT;
ALTER TABLE locations ADD CONSTRAINT fk_locations_company FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE RESTRICT;
ALTER TABLE doctor_locations ADD CONSTRAINT fk_doctor_locations_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE CASCADE;
ALTER TABLE doctor_locations ADD CONSTRAINT fk_doctor_locations_location FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE;
ALTER TABLE users ADD CONSTRAINT fk_users_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;
ALTER TABLE users ADD CONSTRAINT fk_users_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
ALTER TABLE appointments ADD CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE;
ALTER TABLE appointments ADD CONSTRAINT fk_appointments_doctor FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;
ALTER TABLE appointments ADD CONSTRAINT fk_appointments_location FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT;
ALTER TABLE surveys ADD CONSTRAINT fk_surveys_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE examinations ADD CONSTRAINT fk_examinations_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE cbc_results ADD CONSTRAINT fk_cbc_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE biochemistry_results ADD CONSTRAINT fk_biochemistry_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE urinalysis_results ADD CONSTRAINT fk_urinalysis_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE albuminuria_results ADD CONSTRAINT fk_albuminuria_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE ultrasound_results ADD CONSTRAINT fk_ultrasound_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE calculated_metrics ADD CONSTRAINT fk_calculated_metrics_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT fk_ckd_prognosis_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT fk_ckd_prognosis_gfr_metric FOREIGN KEY (gfr_metric_id) REFERENCES calculated_metrics(id) ON DELETE SET NULL;
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT fk_ckd_prognosis_albuminuria_result FOREIGN KEY (albuminuria_result_id) REFERENCES albuminuria_results(id) ON DELETE SET NULL;
ALTER TABLE appointment_diets ADD CONSTRAINT fk_appointment_diets_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE prescriptions ADD CONSTRAINT fk_prescriptions_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE appointment_icd10_diagnoses ADD CONSTRAINT fk_appointment_icd10_diagnoses_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE appointment_icd10_diagnoses ADD CONSTRAINT fk_appointment_icd10_diagnoses_icd10 FOREIGN KEY (icd10_diagnosis_id) REFERENCES icd10_diagnoses(id) ON DELETE RESTRICT;
ALTER TABLE appointment_additional_studies ADD CONSTRAINT fk_appointment_additional_studies_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE CASCADE;
ALTER TABLE audit_events ADD CONSTRAINT fk_audit_events_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE audit_events ADD CONSTRAINT fk_audit_events_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL;
ALTER TABLE audit_events ADD CONSTRAINT fk_audit_events_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL;
ALTER TABLE audit_event_changes ADD CONSTRAINT fk_audit_event_changes_event FOREIGN KEY (audit_event_id) REFERENCES audit_events(id) ON DELETE CASCADE;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_scheduled_doctor FOREIGN KEY (scheduled_doctor_id) REFERENCES doctors(id) ON DELETE RESTRICT;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_location FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE RESTRICT;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_actual_doctor FOREIGN KEY (actual_doctor_id) REFERENCES doctors(id) ON DELETE SET NULL;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_appointment FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE schedule_entries ADD CONSTRAINT fk_schedule_entries_cancelled_by FOREIGN KEY (cancelled_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE ckd_registry_entries ADD CONSTRAINT fk_ckd_registry_entries_patient FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE RESTRICT;
ALTER TABLE ckd_registry_entries ADD CONSTRAINT fk_ckd_registry_entries_included_by FOREIGN KEY (included_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE ckd_registry_entries ADD CONSTRAINT fk_ckd_registry_entries_closed_by FOREIGN KEY (closed_by_user_id) REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE ckd_registry_outcomes ADD CONSTRAINT fk_ckd_registry_outcomes_entry FOREIGN KEY (registry_entry_id) REFERENCES ckd_registry_entries(id) ON DELETE CASCADE;
ALTER TABLE ckd_registry_outcomes ADD CONSTRAINT fk_ckd_registry_outcomes_created_by FOREIGN KEY (created_by_user_id) REFERENCES users(id) ON DELETE SET NULL;

-- Уникальность
ALTER TABLE users ADD CONSTRAINT uq_users_login UNIQUE (login);
ALTER TABLE doctor_locations ADD CONSTRAINT uq_doctor_locations_pair UNIQUE (doctor_id, location_id);
ALTER TABLE surveys ADD CONSTRAINT uq_surveys_appointment UNIQUE (appointment_id);
ALTER TABLE examinations ADD CONSTRAINT uq_examinations_appointment UNIQUE (appointment_id);
ALTER TABLE appointment_diets ADD CONSTRAINT uq_appointment_diets_appointment UNIQUE (appointment_id);
ALTER TABLE icd10_diagnoses ADD CONSTRAINT uq_icd10_diagnoses_diagnosis UNIQUE (diagnosis);
ALTER TABLE appointment_icd10_diagnoses ADD CONSTRAINT uq_appointment_icd10_diagnoses_position UNIQUE (appointment_id, diagnosis_type, sort_order);
ALTER TABLE medications ADD CONSTRAINT uq_medications_display_name UNIQUE (display_name);
ALTER TABLE ckd_registry_entries ADD CONSTRAINT uq_ckd_registry_entries_patient UNIQUE (patient_id);

-- Проверки
ALTER TABLE patients ADD CONSTRAINT chk_patients_birth_date_reasonable CHECK (birth_date >= DATE '1900-01-01' AND birth_date <= CURRENT_DATE);
ALTER TABLE users ADD CONSTRAINT chk_users_role_model CHECK (
    role IN ('admin', 'doctor', 'chief_physician', 'department_head', 'registrar')
    AND (
        (role IN ('admin', 'registrar') AND doctor_id IS NULL AND patient_id IS NULL)
        OR (role IN ('doctor', 'chief_physician', 'department_head') AND doctor_id IS NOT NULL AND patient_id IS NULL)
    )
);
COMMENT ON COLUMN users.role IS 'admin — Системный администратор; doctor — Врач-нефролог; department_head — Заведующий отделением; chief_physician — Главный врач; registrar — Регистратор';
ALTER TABLE appointments ADD CONSTRAINT chk_appointments_not_future CHECK (appointment_date <= CURRENT_TIMESTAMP);
ALTER TABLE appointments ADD CONSTRAINT chk_appointments_age_at_appointment CHECK (age_at_appointment BETWEEN 0 AND 130);
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_bp CHECK ((systolic_pressure IS NULL OR systolic_pressure BETWEEN 40 AND 280) AND (diastolic_pressure IS NULL OR diastolic_pressure BETWEEN 20 AND 200) AND (systolic_pressure IS NULL OR diastolic_pressure IS NULL OR systolic_pressure > diastolic_pressure));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_heart_rate CHECK (heart_rate IS NULL OR heart_rate BETWEEN 30 AND 220);
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_anthropometry CHECK ((height IS NULL OR height BETWEEN 50 AND 250) AND (weight IS NULL OR weight BETWEEN 20 AND 300) AND (bmi IS NULL OR bmi BETWEEN 5 AND 100));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_general_condition CHECK (general_condition IS NULL OR general_condition IN ('satisfactory', 'moderate', 'severe'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_consciousness CHECK (consciousness IS NULL OR consciousness IN ('clear', 'confused', 'sopor', 'coma'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_bed_position CHECK (bed_position IS NULL OR bed_position IN ('active', 'passive', 'forced'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_bed_position_details CHECK ((bed_position = 'forced' AND NULLIF(BTRIM(bed_position_details), '') IS NOT NULL) OR (bed_position IS DISTINCT FROM 'forced' AND bed_position_details IS NULL));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_constitution_type CHECK (constitution_type IS NULL OR constitution_type IN ('normosthenic', 'asthenic', 'hypersthenic'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_body_temperature CHECK (body_temperature IS NULL OR body_temperature BETWEEN 25.0 AND 45.0);
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_kidney_palpation CHECK (kidney_palpation IS NULL OR kidney_palpation IN ('palpable', 'not_palpable'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_kidney_palpation_details CHECK (kidney_palpation <> 'palpable' OR NULLIF(BTRIM(kidney_palpation_details), '') IS NOT NULL);
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_pasternatsky_result CHECK (pasternatsky_result IS NULL OR pasternatsky_result IN ('positive', 'negative'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_pasternatsky_side CHECK (pasternatsky_side IS NULL OR pasternatsky_side IN ('right', 'left', 'bilateral'));
ALTER TABLE examinations ADD CONSTRAINT chk_examinations_pasternatsky_pair CHECK ((pasternatsky_result IS NULL AND pasternatsky_side IS NULL) OR (pasternatsky_result IS NOT NULL AND pasternatsky_side IS NOT NULL));
ALTER TABLE cbc_results ADD CONSTRAINT chk_cbc_non_negative CHECK ((hemoglobin IS NULL OR hemoglobin >= 0) AND (erythrocytes IS NULL OR erythrocytes >= 0) AND (leukocytes IS NULL OR leukocytes >= 0) AND (platelets IS NULL OR platelets >= 0) AND (esr IS NULL OR esr >= 0) AND (mcv IS NULL OR mcv >= 0) AND (hematocrit IS NULL OR hematocrit >= 0));
ALTER TABLE biochemistry_results ADD CONSTRAINT chk_biochemistry_non_negative CHECK ((creatinine IS NULL OR creatinine > 0) AND (urea IS NULL OR urea >= 0) AND (uric_acid IS NULL OR uric_acid >= 0) AND (glucose IS NULL OR glucose >= 0) AND (total_protein IS NULL OR total_protein >= 0) AND (albumin IS NULL OR albumin >= 0) AND (potassium IS NULL OR potassium >= 0) AND (calcium IS NULL OR calcium >= 0) AND (phosphorus IS NULL OR phosphorus >= 0) AND (ferritin IS NULL OR ferritin >= 0) AND (ptg IS NULL OR ptg >= 0));
ALTER TABLE urinalysis_results ADD CONSTRAINT chk_urinalysis_non_negative CHECK ((specific_gravity IS NULL OR specific_gravity >= 0) AND (protein IS NULL OR protein >= 0) AND (leukocytes IS NULL OR leukocytes >= 0) AND (erythrocytes IS NULL OR erythrocytes >= 0));
ALTER TABLE albuminuria_results ADD CONSTRAINT chk_albuminuria_units CHECK (urine_albumin_unit IN ('mg_l', 'g_l') AND urine_creatinine_unit IN ('mmol_l', 'umol_l'));
ALTER TABLE albuminuria_results ADD CONSTRAINT chk_albuminuria_values CHECK ((urine_albumin IS NULL OR urine_albumin >= 0) AND (urine_creatinine IS NULL OR urine_creatinine > 0) AND (albumin_creatinine_ratio IS NULL OR albumin_creatinine_ratio >= 0));
ALTER TABLE albuminuria_results ADD CONSTRAINT chk_albuminuria_category CHECK (albuminuria_category IS NULL OR albuminuria_category IN ('A1', 'A2', 'A3'));
ALTER TABLE albuminuria_results ADD CONSTRAINT ck_albuminuria_daily_albumin_excretion_nonnegative CHECK (daily_albumin_excretion IS NULL OR daily_albumin_excretion >= 0);
ALTER TABLE ultrasound_results ADD CONSTRAINT chk_ultrasound_values CHECK ((left_parenchyma IS NULL OR left_parenchyma >= 0) AND (right_parenchyma IS NULL OR right_parenchyma >= 0));
ALTER TABLE calculated_metrics ADD CONSTRAINT chk_calculated_metrics_values CHECK ((creatinine IS NULL OR creatinine > 0) AND (age IS NULL OR age BETWEEN 0 AND 120) AND (weight_at_appointment IS NULL OR weight_at_appointment BETWEEN 20 AND 300) AND (egfr_ckdepi IS NULL OR egfr_ckdepi >= 0) AND (crcl_cockcroft_gault IS NULL OR crcl_cockcroft_gault >= 0));
ALTER TABLE calculated_metrics ADD CONSTRAINT chk_calculated_metrics_ckd_stage CHECK (ckd_stage IS NULL OR ckd_stage IN ('С1', 'С2', 'С3а', 'С3б', 'С4', 'С5'));
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT chk_ckd_prognosis_categories CHECK ((gfr_category IS NULL OR gfr_category IN ('С1','С2','С3а','С3б','С4','С5')) AND (albuminuria_category IS NULL OR albuminuria_category IN ('A1','A2','A3')) AND (prognosis_level IS NULL OR prognosis_level IN ('low','moderate','high','very_high')) AND (gfr_source_type IS NULL OR gfr_source_type IN ('current_appointment','previous_appointment','manual','legacy_unknown')) AND (albuminuria_source_type IS NULL OR albuminuria_source_type IN ('current_appointment','previous_appointment','manual','legacy_unknown')) AND calculation_status IN ('calculated','missing_gfr','missing_albuminuria','missing_both','stale_gfr','stale_albuminuria','stale_both','doctor_removed','legacy_incomplete'));
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT chk_ckd_prognosis_combined_category CHECK (combined_category IS NULL OR (gfr_category IS NOT NULL AND albuminuria_category IS NOT NULL AND combined_category = gfr_category || albuminuria_category));
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT chk_ckd_prognosis_source_interval CHECK (source_interval_days IS NULL OR source_interval_days >= 0);
ALTER TABLE ckd_prognosis_results ADD CONSTRAINT chk_ckd_prognosis_calculated_sources CHECK (calculation_status <> 'calculated' OR (gfr_metric_id IS NOT NULL AND albuminuria_result_id IS NOT NULL AND gfr_investigation_date IS NOT NULL AND albuminuria_investigation_date IS NOT NULL AND gfr_category IS NOT NULL AND albuminuria_category IS NOT NULL AND combined_category IS NOT NULL AND prognosis_level IS NOT NULL AND prognosis_text IS NOT NULL));
ALTER TABLE appointment_icd10_diagnoses ADD CONSTRAINT chk_appointment_icd10_diagnoses_type CHECK (diagnosis_type IN ('main','complication','comorbidity'));
ALTER TABLE prescriptions ADD CONSTRAINT ck_prescriptions_therapy_group CHECK (therapy_group IS NULL OR therapy_group IN ('Коррекция АД, ЧСС','Нефропротекция','Коррекция гиперлипидемии','Коррекция анемии','Другие препараты'));
ALTER TABLE audit_events ADD CONSTRAINT ck_audit_events_result CHECK (result IN ('success','error','denied'));
ALTER TABLE schedule_entries ADD CONSTRAINT ck_schedule_entries_time CHECK (ends_at > starts_at);
ALTER TABLE schedule_entries ADD CONSTRAINT ck_schedule_entries_appointment_type CHECK (appointment_type IN ('primary','repeat'));
ALTER TABLE schedule_entries ADD CONSTRAINT ck_schedule_entries_status CHECK (status IN ('booked','arrived','no_show','cancelled'));
ALTER TABLE ckd_registry_entries ADD CONSTRAINT ck_ckd_registry_entries_egfr_non_negative CHECK (egfr_at_inclusion IS NULL OR egfr_at_inclusion >= 0);
ALTER TABLE ckd_registry_entries ADD CONSTRAINT ck_ckd_registry_entries_stage CHECK (ckd_stage_at_inclusion IS NULL OR ckd_stage_at_inclusion IN ('С1','С2','С3а','С3б','С4','С5'));
ALTER TABLE ckd_registry_entries ADD CONSTRAINT ck_ckd_registry_entries_closure CHECK ((is_active AND closed_at IS NULL) OR (NOT is_active AND closed_at IS NOT NULL AND close_reason IS NOT NULL));
ALTER TABLE ckd_registry_outcomes ADD CONSTRAINT ck_ckd_registry_outcomes_type CHECK (outcome_type IN ('rrt_hemodialysis','rrt_peritoneal_dialysis','rrt_kidney_transplant','death'));
ALTER TABLE ckd_registry_outcomes ADD CONSTRAINT ck_ckd_registry_outcomes_date_not_future CHECK (outcome_date <= CURRENT_DATE);

-- Индексы
CREATE INDEX idx_patients_fio ON patients (last_name, first_name, patronymic);
CREATE INDEX idx_appointments_patient_id ON appointments (patient_id);
CREATE INDEX idx_appointments_doctor_id ON appointments (doctor_id);
CREATE INDEX idx_appointments_location_id ON appointments (location_id);
CREATE INDEX idx_appointments_date ON appointments (appointment_date);
CREATE INDEX idx_appointments_patient_date ON appointments (patient_id, appointment_date DESC);
CREATE INDEX idx_doctor_locations_doctor_id ON doctor_locations (doctor_id);
CREATE INDEX idx_doctor_locations_location_id ON doctor_locations (location_id);
CREATE INDEX idx_locations_branch_id ON locations (branch_id);
CREATE INDEX idx_branches_company_id ON branches (company_id);
CREATE INDEX idx_cbc_appointment_id ON cbc_results (appointment_id);
CREATE INDEX idx_cbc_appointment_date ON cbc_results (appointment_id, investigation_date);
CREATE INDEX idx_biochemistry_appointment_id ON biochemistry_results (appointment_id);
CREATE INDEX idx_biochemistry_appointment_date ON biochemistry_results (appointment_id, investigation_date);
CREATE INDEX idx_urinalysis_appointment_id ON urinalysis_results (appointment_id);
CREATE INDEX idx_urinalysis_appointment_date ON urinalysis_results (appointment_id, investigation_date);
CREATE INDEX idx_albuminuria_appointment_id ON albuminuria_results (appointment_id);
CREATE INDEX idx_albuminuria_appointment_date ON albuminuria_results (appointment_id, investigation_date);
CREATE INDEX idx_ultrasound_appointment_id ON ultrasound_results (appointment_id);
CREATE INDEX idx_ultrasound_appointment_date ON ultrasound_results (appointment_id, investigation_date);
CREATE INDEX idx_calculated_metrics_appointment_id ON calculated_metrics (appointment_id);
CREATE INDEX idx_calculated_metrics_appointment_date ON calculated_metrics (appointment_id, investigation_date);
CREATE INDEX idx_ckd_prognosis_appointment_id ON ckd_prognosis_results (appointment_id);
CREATE INDEX idx_ckd_prognosis_assessment_date ON ckd_prognosis_results (assessment_date);
CREATE INDEX idx_ckd_prognosis_gfr_date ON ckd_prognosis_results (gfr_investigation_date);
CREATE INDEX idx_ckd_prognosis_albuminuria_date ON ckd_prognosis_results (albuminuria_investigation_date);
CREATE INDEX idx_ckd_prognosis_assessment_active ON ckd_prognosis_results (appointment_id,is_active,display_order,id);
CREATE INDEX idx_ckd_prognosis_matrix_lookup ON ckd_prognosis_results (appointment_id,gfr_investigation_date,albuminuria_investigation_date);
CREATE UNIQUE INDEX uq_ckd_prognosis_active_source_pair ON ckd_prognosis_results (appointment_id,gfr_metric_id,albuminuria_result_id) WHERE is_active = TRUE AND calculation_status = 'calculated';
CREATE INDEX idx_prescriptions_appointment_id ON prescriptions (appointment_id);
CREATE INDEX idx_prescriptions_therapy_group ON prescriptions (therapy_group);
CREATE INDEX idx_surveys_appointment_id ON surveys (appointment_id);
CREATE INDEX idx_examinations_appointment_id ON examinations (appointment_id);
CREATE INDEX idx_appointment_diets_appointment_id ON appointment_diets (appointment_id);
CREATE INDEX idx_icd10_diagnoses_sort_order ON icd10_diagnoses(sort_order);
CREATE INDEX idx_icd10_diagnoses_active ON icd10_diagnoses(is_active);
CREATE INDEX idx_icd10_diagnoses_text ON icd10_diagnoses USING gin (to_tsvector('russian', diagnosis));
CREATE INDEX idx_appointment_icd10_diagnoses_appointment_id ON appointment_icd10_diagnoses(appointment_id);
CREATE INDEX idx_appointment_icd10_diagnoses_icd10_id ON appointment_icd10_diagnoses(icd10_diagnosis_id);
CREATE INDEX idx_appointment_icd10_diagnoses_type ON appointment_icd10_diagnoses(diagnosis_type);
CREATE INDEX idx_medications_is_active ON medications(is_active);
CREATE INDEX idx_medications_sort_order ON medications(sort_order);
CREATE INDEX idx_medications_active_substance ON medications(active_substance);
CREATE INDEX ix_audit_events_created_at ON audit_events(created_at);
CREATE INDEX ix_audit_events_user_id ON audit_events(user_id);
CREATE INDEX ix_audit_events_action ON audit_events(action);
CREATE INDEX ix_audit_events_result ON audit_events(result);
CREATE INDEX ix_audit_events_patient_id ON audit_events(patient_id);
CREATE INDEX ix_audit_events_appointment_id ON audit_events(appointment_id);
CREATE INDEX ix_audit_event_changes_event_id ON audit_event_changes(audit_event_id);
CREATE INDEX ix_audit_event_changes_section ON audit_event_changes(section);
CREATE INDEX ix_audit_event_changes_type ON audit_event_changes(change_type);
CREATE INDEX ix_schedule_entries_doctor_period ON schedule_entries(scheduled_doctor_id,starts_at,ends_at);
CREATE INDEX ix_schedule_entries_location_period ON schedule_entries(location_id,starts_at,ends_at);
CREATE INDEX ix_schedule_entries_patient ON schedule_entries(patient_id);
CREATE INDEX ix_schedule_entries_status ON schedule_entries(status);
CREATE UNIQUE INDEX ux_schedule_entries_appointment ON schedule_entries(appointment_id) WHERE appointment_id IS NOT NULL;
CREATE INDEX ix_ckd_registry_entries_included_at ON ckd_registry_entries(included_at);
CREATE INDEX ix_ckd_registry_entries_is_active ON ckd_registry_entries(is_active);
CREATE INDEX ix_ckd_registry_outcomes_entry_date ON ckd_registry_outcomes(registry_entry_id,outcome_date);
CREATE INDEX ix_ckd_registry_outcomes_type ON ckd_registry_outcomes(outcome_type);

CREATE OR REPLACE VIEW appointment_icd10_diagnoses_view AS
SELECT aid.id, aid.appointment_id, aid.diagnosis_type, aid.icd10_diagnosis_id,
       i.diagnosis AS icd10_diagnosis, aid.doctor_note, aid.sort_order, aid.created_at, aid.updated_at
FROM appointment_icd10_diagnoses aid
JOIN icd10_diagnoses i ON i.id = aid.icd10_diagnosis_id;

CREATE OR REPLACE FUNCTION set_ckd_prognosis_source_fields() RETURNS trigger AS $$
DECLARE source_gfr RECORD; source_albuminuria RECORD;
BEGIN
    IF NEW.gfr_metric_id IS NULL AND NEW.gfr_category IS NOT NULL THEN
        SELECT cm.id, COALESCE(cm.investigation_date,a.appointment_date::date) investigation_date INTO source_gfr
        FROM calculated_metrics cm JOIN appointments a ON a.id=cm.appointment_id
        WHERE cm.appointment_id=NEW.appointment_id AND cm.ckd_stage=NEW.gfr_category
        ORDER BY cm.investigation_date DESC NULLS LAST,cm.id DESC LIMIT 1;
        IF FOUND THEN NEW.gfr_metric_id:=source_gfr.id; NEW.gfr_investigation_date:=source_gfr.investigation_date; NEW.gfr_source_type:=COALESCE(NEW.gfr_source_type,'current_appointment'); END IF;
    END IF;
    IF NEW.albuminuria_result_id IS NULL AND NEW.albuminuria_category IS NOT NULL THEN
        SELECT ar.id,ar.investigation_date INTO source_albuminuria FROM albuminuria_results ar
        WHERE ar.appointment_id=NEW.appointment_id AND ar.albuminuria_category=NEW.albuminuria_category
        ORDER BY ar.investigation_date DESC NULLS LAST,ar.id DESC LIMIT 1;
        IF FOUND THEN NEW.albuminuria_result_id:=source_albuminuria.id; NEW.albuminuria_investigation_date:=source_albuminuria.investigation_date; NEW.albuminuria_source_type:=COALESCE(NEW.albuminuria_source_type,'current_appointment'); END IF;
    END IF;
    IF NEW.gfr_investigation_date IS NOT NULL AND NEW.albuminuria_investigation_date IS NOT NULL THEN NEW.source_interval_days:=ABS(NEW.gfr_investigation_date-NEW.albuminuria_investigation_date); END IF;
    IF NEW.is_active=FALSE AND NEW.hidden_at IS NULL THEN NEW.hidden_at:=NOW(); END IF;
    NEW.updated_at:=NOW(); RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_set_ckd_prognosis_source_fields BEFORE INSERT OR UPDATE ON ckd_prognosis_results FOR EACH ROW EXECUTE FUNCTION set_ckd_prognosis_source_fields();

COMMENT ON COLUMN appointments.id IS 'Идентификатор медицинского приёма';
COMMENT ON COLUMN appointments.patient_id IS 'Пациент';
COMMENT ON COLUMN appointments.doctor_id IS 'Врач';
COMMENT ON COLUMN appointments.location_id IS 'Место проведения приёма';
COMMENT ON COLUMN appointments.appointment_date IS 'Дата и время приёма';
COMMENT ON COLUMN appointments.age_at_appointment IS 'Возраст пациента в полных годах на дату приёма';
COMMENT ON COLUMN surveys.id IS 'Идентификатор опроса';
COMMENT ON COLUMN surveys.appointment_id IS 'Медицинский приём';
COMMENT ON COLUMN surveys.complaints IS 'Жалобы';
COMMENT ON COLUMN surveys.education_and_professional_history IS 'Образование и профессиональный анамнез';
COMMENT ON COLUMN surveys.housing_conditions IS 'Жилищные условия';
COMMENT ON COLUMN surveys.past_diseases IS 'Перенесённые заболевания';
COMMENT ON COLUMN surveys.habitual_intoxications IS 'Привычные интоксикации';
COMMENT ON COLUMN surveys.gynecological_history IS 'Гинекологический анамнез';
COMMENT ON COLUMN surveys.heredity_description IS 'Наследственность: свободное текстовое описание врача';
COMMENT ON COLUMN surveys.family_life IS 'Семейная жизнь';
COMMENT ON COLUMN surveys.allergological_history IS 'Аллергологический анамнез';
COMMENT ON COLUMN surveys.epidemiological_history IS 'Эпидемиологический анамнез';
COMMENT ON COLUMN surveys.insurance_history IS 'Страховой анамнез';
COMMENT ON COLUMN surveys.disease_onset IS 'Начало заболевания';
COMMENT ON COLUMN surveys.disease_course IS 'Течение заболевания';
COMMENT ON COLUMN examinations.id IS 'Идентификатор объективного осмотра';
COMMENT ON COLUMN examinations.appointment_id IS 'Медицинский приём';
COMMENT ON COLUMN examinations.general_condition IS 'Общее состояние';
COMMENT ON COLUMN examinations.consciousness IS 'Сознание';
COMMENT ON COLUMN examinations.bed_position IS 'Положение в постели';
COMMENT ON COLUMN examinations.bed_position_details IS 'Особенности вынужденного положения в постели';
COMMENT ON COLUMN examinations.body_build IS 'Телосложение';
COMMENT ON COLUMN examinations.height IS 'Рост, см';
COMMENT ON COLUMN examinations.weight IS 'Вес, кг';
COMMENT ON COLUMN examinations.bmi IS 'Индекс массы тела, кг/м²';
COMMENT ON COLUMN examinations.constitution_type IS 'Тип конституции';
COMMENT ON COLUMN examinations.skin_and_mucous_membranes IS 'Кожа и слизистые оболочки';
COMMENT ON COLUMN examinations.edema_location IS 'Периферические отёки и серозиты; структура хранения не изменена';
COMMENT ON COLUMN examinations.lymph_nodes IS 'Лимфатические узлы';
COMMENT ON COLUMN examinations.thyroid_gland IS 'Щитовидная железа';
COMMENT ON COLUMN examinations.musculoskeletal_system IS 'Опорно-двигательный аппарат';
COMMENT ON COLUMN examinations.body_temperature IS 'Температура тела, °C';
COMMENT ON COLUMN examinations.systolic_pressure IS 'Систолическое артериальное давление, мм рт. ст.';
COMMENT ON COLUMN examinations.diastolic_pressure IS 'Диастолическое артериальное давление, мм рт. ст.';
COMMENT ON COLUMN examinations.bp_note IS 'Примечание к измерению артериального давления';
COMMENT ON COLUMN examinations.heart_rate IS 'Частота сердечных сокращений, уд/мин';
COMMENT ON COLUMN examinations.veins_condition IS 'Состояние вен';
COMMENT ON COLUMN examinations.lung_auscultation IS 'Аускультация лёгких';
COMMENT ON COLUMN examinations.abdomen IS 'Живот';
COMMENT ON COLUMN examinations.kidney_palpation IS 'Пальпация почек: пальпируются или не пальпируются';
COMMENT ON COLUMN examinations.kidney_palpation_details IS 'Уточнение результатов пальпации почек';
COMMENT ON COLUMN examinations.pasternatsky_result IS 'Результат симптома Пастернацкого';
COMMENT ON COLUMN examinations.pasternatsky_side IS 'Сторона симптома Пастернацкого';
COMMENT ON COLUMN albuminuria_results.daily_albumin_excretion IS 'Суточная экскреция альбумина, мг/сут';
COMMENT ON TABLE appointment_additional_studies IS 'Свободные описания дополнительных исследований конкретного приёма';
COMMENT ON COLUMN appointment_additional_studies.other_laboratory_studies IS 'Другие лабораторные исследования';
COMMENT ON COLUMN appointment_additional_studies.other_instrumental_studies IS 'Другие инструментальные исследования';
COMMENT ON COLUMN patients.gender IS 'Пол пациента; для архивного импорта может быть не указан';
COMMENT ON COLUMN appointments.location_id IS 'Место проведения приёма; для архивного импорта может быть не указано';
