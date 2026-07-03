"""
ЛЕГЕНДА
Файл: app/registry_queries.py
Назначение: серверные запросы для административного регистра ХБП.
Что делает: за один SQL-запрос собирает сводку, клинические очереди и управленческие списки.
Почему отдельный файл: не раздувает основной database.py и не ломает существующие функции приложения.
"""

from typing import Any, Dict

from .database import get_db_connection


CKD_REGISTRY_SQL = """
WITH
latest_appointment AS (
    SELECT DISTINCT ON (a.patient_id)
        a.patient_id,
        a.id AS appointment_id,
        a.appointment_date,
        a.doctor_id,
        a.location_id,
        d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
        l.name AS location_name,
        b.name AS branch_name
    FROM appointments a
    JOIN doctors d ON d.id = a.doctor_id
    JOIN locations l ON l.id = a.location_id
    JOIN branches b ON b.id = l.branch_id
    ORDER BY a.patient_id, a.appointment_date DESC, a.id DESC
),
metric_ranked AS (
    SELECT
        a.patient_id,
        cm.appointment_id,
        COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
        cm.creatinine,
        cm.egfr_ckdepi,
        cm.ckd_stage,
        ROW_NUMBER() OVER (
            PARTITION BY a.patient_id
            ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) DESC, a.appointment_date DESC, cm.id DESC
        ) AS rn
    FROM calculated_metrics cm
    JOIN appointments a ON a.id = cm.appointment_id
    WHERE cm.creatinine IS NOT NULL OR cm.egfr_ckdepi IS NOT NULL OR cm.ckd_stage IS NOT NULL
),
latest_metric AS (
    SELECT * FROM metric_ranked WHERE rn = 1
),
previous_metric AS (
    SELECT * FROM metric_ranked WHERE rn = 2
),
albuminuria_ranked AS (
    SELECT
        a.patient_id,
        ar.appointment_id,
        ar.investigation_date,
        ar.urine_albumin,
        ar.urine_albumin_unit,
        ar.urine_creatinine,
        ar.urine_creatinine_unit,
        ar.albumin_creatinine_ratio,
        ar.albuminuria_category,
        ROW_NUMBER() OVER (
            PARTITION BY a.patient_id
            ORDER BY ar.investigation_date DESC, a.appointment_date DESC, ar.id DESC
        ) AS rn
    FROM albuminuria_results ar
    JOIN appointments a ON a.id = ar.appointment_id
),
latest_albuminuria AS (
    SELECT * FROM albuminuria_ranked WHERE rn = 1
),
prognosis_ranked AS (
    SELECT
        a.patient_id,
        cpr.appointment_id,
        cpr.assessment_date,
        cpr.gfr_category,
        cpr.albuminuria_category,
        cpr.combined_category,
        cpr.prognosis_level,
        cpr.prognosis_text,
        ROW_NUMBER() OVER (
            PARTITION BY a.patient_id
            ORDER BY cpr.assessment_date DESC, a.appointment_date DESC, cpr.id DESC
        ) AS rn
    FROM ckd_prognosis_results cpr
    JOIN appointments a ON a.id = cpr.appointment_id
),
latest_prognosis AS (
    SELECT * FROM prognosis_ranked WHERE rn = 1
),
diet_ranked AS (
    SELECT
        a.patient_id,
        ad.appointment_id,
        a.appointment_date,
        ad.next_control_date,
        ad.diet,
        ad.recommendations,
        ROW_NUMBER() OVER (
            PARTITION BY a.patient_id
            ORDER BY a.appointment_date DESC, ad.id DESC
        ) AS rn
    FROM appointment_diets ad
    JOIN appointments a ON a.id = ad.appointment_id
),
latest_diet AS (
    SELECT * FROM diet_ranked WHERE rn = 1
),
patient_snapshot AS (
    SELECT
        p.id AS patient_id,
        p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
        p.birth_date,
        EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date))::int AS age,
        CASE WHEN p.gender THEN 'Мужской' ELSE 'Женский' END AS gender_str,

        la.appointment_id AS last_appointment_id,
        la.appointment_date AS last_appointment_date,
        la.doctor_id AS last_doctor_id,
        la.doctor_name AS last_doctor_name,
        la.location_id AS last_location_id,
        la.location_name AS last_location_name,
        la.branch_name AS last_branch_name,

        lm.appointment_id AS metric_appointment_id,
        lm.investigation_date AS metric_date,
        lm.creatinine AS latest_creatinine,
        lm.egfr_ckdepi AS latest_egfr,
        lm.ckd_stage AS latest_gfr_category,

        pm.investigation_date AS previous_metric_date,
        pm.egfr_ckdepi AS previous_egfr,
        CASE
            WHEN pm.egfr_ckdepi IS NOT NULL AND lm.egfr_ckdepi IS NOT NULL THEN ROUND((pm.egfr_ckdepi - lm.egfr_ckdepi)::numeric, 2)
            ELSE NULL
        END AS egfr_decline_abs,
        CASE
            WHEN pm.egfr_ckdepi IS NOT NULL AND pm.egfr_ckdepi > 0 AND lm.egfr_ckdepi IS NOT NULL THEN
                ROUND(((pm.egfr_ckdepi - lm.egfr_ckdepi) / pm.egfr_ckdepi * 100)::numeric, 1)
            ELSE NULL
        END AS egfr_decline_percent,

        lar.investigation_date AS albuminuria_date,
        lar.albumin_creatinine_ratio AS latest_acr,
        lar.albuminuria_category AS latest_albuminuria_category,

        lp.assessment_date AS prognosis_date,
        lp.gfr_category AS prognosis_gfr_category,
        lp.albuminuria_category AS prognosis_albuminuria_category,
        lp.combined_category,
        lp.prognosis_level,
        lp.prognosis_text,

        ld.next_control_date,
        ld.diet,
        ld.recommendations,

        EXISTS (
            SELECT 1
            FROM diagnoses d
            JOIN appointments adx ON adx.id = d.appointment_id
            WHERE adx.patient_id = p.id
              AND (
                    d.main_diagnosis ILIKE '%ХБП%'
                    OR d.main_diagnosis ILIKE '%хроническ%поч%'
                  )
        ) AS has_ckd_diagnosis,

        (
            lm.ckd_stage IS NOT NULL
            OR lar.albuminuria_category IS NOT NULL
            OR lp.prognosis_level IS NOT NULL
            OR EXISTS (
                SELECT 1
                FROM diagnoses d
                JOIN appointments adx ON adx.id = d.appointment_id
                WHERE adx.patient_id = p.id
                  AND (
                        d.main_diagnosis ILIKE '%ХБП%'
                        OR d.main_diagnosis ILIKE '%хроническ%поч%'
                      )
            )
        ) AS is_ckd_observed,

        (lp.prognosis_level IS NULL) AS flag_no_prognosis,
        (lar.albuminuria_category = 'A3') AS flag_a3,
        (lm.ckd_stage IN ('G4', 'G5')) AS flag_g4_g5,
        (lp.prognosis_level = 'very_high') AS flag_very_high,
        (ld.next_control_date IS NOT NULL AND ld.next_control_date < CURRENT_DATE) AS flag_overdue_control,
        (lar.albuminuria_category IS NULL) AS flag_no_albuminuria,
        (lm.investigation_date IS NULL OR lm.investigation_date < CURRENT_DATE - INTERVAL '180 days') AS flag_no_fresh_creatinine,
        (
            la.appointment_id IS NOT NULL
            AND (
                lm.ckd_stage IS NULL
                OR lar.albuminuria_category IS NULL
                OR lp.prognosis_level IS NULL
            )
        ) AS flag_incomplete_labs,
        (
            pm.egfr_ckdepi IS NOT NULL
            AND lm.egfr_ckdepi IS NOT NULL
            AND pm.egfr_ckdepi > lm.egfr_ckdepi
            AND (
                (pm.egfr_ckdepi - lm.egfr_ckdepi) >= 5
                OR ((pm.egfr_ckdepi - lm.egfr_ckdepi) / NULLIF(pm.egfr_ckdepi, 0)) >= 0.10
            )
        ) AS flag_rapid_egfr_decline
    FROM patients p
    LEFT JOIN latest_appointment la ON la.patient_id = p.id
    LEFT JOIN latest_metric lm ON lm.patient_id = p.id
    LEFT JOIN previous_metric pm ON pm.patient_id = p.id
    LEFT JOIN latest_albuminuria lar ON lar.patient_id = p.id
    LEFT JOIN latest_prognosis lp ON lp.patient_id = p.id
    LEFT JOIN latest_diet ld ON ld.patient_id = p.id
),
appointment_quality AS (
    SELECT
        a.id AS appointment_id,
        a.patient_id,
        a.doctor_id,
        a.location_id,
        a.appointment_date,
        NOT EXISTS (SELECT 1 FROM surveys s WHERE s.appointment_id = a.id) AS missing_survey,
        NOT EXISTS (SELECT 1 FROM examinations e WHERE e.appointment_id = a.id) AS missing_examination,
        NOT EXISTS (SELECT 1 FROM biochemistry_results bch WHERE bch.appointment_id = a.id AND bch.creatinine IS NOT NULL) AS missing_creatinine,
        NOT EXISTS (SELECT 1 FROM albuminuria_results ar WHERE ar.appointment_id = a.id AND ar.albuminuria_category IS NOT NULL) AS missing_albuminuria,
        NOT EXISTS (SELECT 1 FROM ckd_prognosis_results cpr WHERE cpr.appointment_id = a.id AND cpr.prognosis_level IS NOT NULL) AS missing_prognosis,
        NOT EXISTS (SELECT 1 FROM diagnoses d WHERE d.appointment_id = a.id AND d.main_diagnosis IS NOT NULL) AS missing_diagnosis
    FROM appointments a
),
appointment_quality_marked AS (
    SELECT
        aq.*,
        (
            missing_survey
            OR missing_examination
            OR missing_creatinine
            OR missing_albuminuria
            OR missing_prognosis
            OR missing_diagnosis
        ) AS is_incomplete
    FROM appointment_quality aq
),
patient_json AS (
    SELECT
        patient_id,
        jsonb_build_object(
            'patient_id', patient_id,
            'patient_fio', patient_fio,
            'age', age,
            'gender', gender_str,
            'last_appointment_id', last_appointment_id,
            'last_appointment_date', last_appointment_date,
            'last_doctor_name', last_doctor_name,
            'last_location_name', last_location_name,
            'metric_date', metric_date,
            'latest_creatinine', latest_creatinine,
            'latest_egfr', latest_egfr,
            'latest_gfr_category', latest_gfr_category,
            'albuminuria_date', albuminuria_date,
            'latest_acr', latest_acr,
            'latest_albuminuria_category', latest_albuminuria_category,
            'combined_category', combined_category,
            'prognosis_level', prognosis_level,
            'prognosis_text', prognosis_text,
            'next_control_date', next_control_date,
            'previous_metric_date', previous_metric_date,
            'previous_egfr', previous_egfr,
            'egfr_decline_abs', egfr_decline_abs,
            'egfr_decline_percent', egfr_decline_percent
        ) AS item
    FROM patient_snapshot
)
SELECT jsonb_build_object(
    'generated_at', NOW(),
    'summary', (
        SELECT jsonb_build_object(
            'patients_total', COUNT(*),
            'patients_with_appointments', COUNT(*) FILTER (WHERE last_appointment_id IS NOT NULL),
            'ckd_patients_total', COUNT(*) FILTER (WHERE is_ckd_observed),
            'high_risk_ckd_patients', COUNT(*) FILTER (WHERE is_ckd_observed AND prognosis_level IN ('high', 'very_high')),
            'very_high_ckd_patients', COUNT(*) FILTER (WHERE is_ckd_observed AND prognosis_level = 'very_high'),
            'without_albuminuria', COUNT(*) FILTER (WHERE is_ckd_observed AND flag_no_albuminuria),
            'without_fresh_creatinine', COUNT(*) FILTER (WHERE is_ckd_observed AND flag_no_fresh_creatinine),
            'without_prognosis', COUNT(*) FILTER (WHERE is_ckd_observed AND flag_no_prognosis),
            'g4_g5_without_control_date', COUNT(*) FILTER (WHERE is_ckd_observed AND flag_g4_g5 AND next_control_date IS NULL),
            'a3_patients', COUNT(*) FILTER (WHERE flag_a3),
            'g4_g5_patients', COUNT(*) FILTER (WHERE flag_g4_g5),
            'very_high_patients', COUNT(*) FILTER (WHERE flag_very_high),
            'overdue_control_patients', COUNT(*) FILTER (WHERE flag_overdue_control),
            'incomplete_lab_patients', COUNT(*) FILTER (WHERE flag_incomplete_labs),
            'rapid_egfr_decline_patients', COUNT(*) FILTER (WHERE flag_rapid_egfr_decline),
            'incomplete_appointments_total', (SELECT COUNT(*) FROM appointment_quality_marked WHERE is_incomplete)
        )
        FROM patient_snapshot
    ),
    'queues', jsonb_build_object(
        'without_prognosis', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY (pj.item->>'last_appointment_date') DESC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.is_ckd_observed AND ps.flag_no_prognosis
        ), '[]'::jsonb),
        'a3', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY (pj.item->>'latest_acr')::numeric DESC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_a3
        ), '[]'::jsonb),
        'g4_g5', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY ps.latest_egfr ASC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_g4_g5
        ), '[]'::jsonb),
        'very_high', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY (pj.item->>'last_appointment_date') DESC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_very_high
        ), '[]'::jsonb),
        'overdue_control', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY ps.next_control_date ASC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_overdue_control
        ), '[]'::jsonb),
        'incomplete_labs', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY (pj.item->>'last_appointment_date') DESC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_incomplete_labs
        ), '[]'::jsonb),
        'rapid_egfr_decline', COALESCE((
            SELECT jsonb_agg(pj.item ORDER BY ps.egfr_decline_abs DESC NULLS LAST)
            FROM patient_snapshot ps
            JOIN patient_json pj ON pj.patient_id = ps.patient_id
            WHERE ps.flag_rapid_egfr_decline
        ), '[]'::jsonb)
    ),
    'doctor_high_risk', COALESCE((
        SELECT jsonb_agg(row_to_json(x) ORDER BY x.very_high_patients DESC, x.high_and_very_high_patients DESC, x.total_latest_patients DESC)
        FROM (
            SELECT
                d.id AS doctor_id,
                d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
                COUNT(ps.patient_id) FILTER (WHERE ps.last_doctor_id = d.id) AS total_latest_patients,
                COUNT(ps.patient_id) FILTER (WHERE ps.last_doctor_id = d.id AND ps.prognosis_level IN ('high', 'very_high')) AS high_and_very_high_patients,
                COUNT(ps.patient_id) FILTER (WHERE ps.last_doctor_id = d.id AND ps.prognosis_level = 'very_high') AS very_high_patients,
                COUNT(ps.patient_id) FILTER (WHERE ps.last_doctor_id = d.id AND ps.flag_incomplete_labs) AS incomplete_latest_patients,
                COUNT(ps.patient_id) FILTER (WHERE ps.last_doctor_id = d.id AND ps.flag_overdue_control) AS overdue_control_patients
            FROM doctors d
            LEFT JOIN patient_snapshot ps ON ps.last_doctor_id = d.id
            GROUP BY d.id, d.last_name, d.first_name, d.patronymic
        ) x
    ), '[]'::jsonb),
    'location_incomplete', COALESCE((
        SELECT jsonb_agg(row_to_json(x) ORDER BY x.incomplete_appointments DESC, x.incomplete_latest_patients DESC, x.appointments_total DESC)
        FROM (
            SELECT
                l.id AS location_id,
                l.name AS location_name,
                b.name AS branch_name,
                COUNT(aq.appointment_id) AS appointments_total,
                COUNT(aq.appointment_id) FILTER (WHERE aq.is_incomplete) AS incomplete_appointments,
                COUNT(ps.patient_id) FILTER (WHERE ps.flag_incomplete_labs) AS incomplete_latest_patients,
                COUNT(ps.patient_id) FILTER (WHERE ps.prognosis_level = 'very_high') AS very_high_latest_patients
            FROM locations l
            JOIN branches b ON b.id = l.branch_id
            LEFT JOIN appointment_quality_marked aq ON aq.location_id = l.id
            LEFT JOIN patient_snapshot ps ON ps.last_location_id = l.id
            GROUP BY l.id, l.name, b.name
        ) x
    ), '[]'::jsonb)
) AS dashboard;
"""


def get_ckd_registry_dashboard() -> Dict[str, Any]:
    """Возвращает данные для страницы регистра ХБП одним обращением к базе."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CKD_REGISTRY_SQL)
            row = cur.fetchone()

    if not row or not row.get("dashboard"):
        return {
            "summary": {},
            "queues": {},
            "doctor_high_risk": [],
            "location_incomplete": [],
        }

    return row["dashboard"]
