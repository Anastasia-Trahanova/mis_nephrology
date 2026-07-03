import threading
from contextlib import contextmanager
from datetime import datetime, date

import psycopg2  # Библиотека для подключения к PostgreSQL
from psycopg2.extras import RealDictCursor  # Результаты запросов как словари
from psycopg2.pool import ThreadedConnectionPool
from dotenv import load_dotenv  # Загружает .env файл
from .calculations import calculate_ckd_prognosis, normalize_ckd_stage_for_storage

from .settings import settings


# =====================================================
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# =====================================================
# Важно: раньше каждое обращение к БД создавало новое соединение.
# На странице пациента таких обращений много, поэтому даже локально набегали секунды.
# Теперь соединения переиспользуются через ThreadedConnectionPool.

DATABASE_URL = settings.psycopg2_dsn

DB_POOL_MIN_CONN = settings.db_pool_min_conn
DB_POOL_MAX_CONN = settings.db_pool_max_conn

_pool = None
_pool_lock = threading.Lock()


def _get_pool():
    """Лениво создаёт пул подключений, чтобы импорт модуля не падал, если БД ещё не поднялась."""
    global _pool
    if _pool is None:
        with _pool_lock:
            if _pool is None:
                _pool = ThreadedConnectionPool(
                    DB_POOL_MIN_CONN,
                    DB_POOL_MAX_CONN,
                    dsn=DATABASE_URL,
                    cursor_factory=RealDictCursor,
                )
    return _pool


class PooledConnection:
    """
    Обёртка, совместимая с текущим кодом:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                ...

    На выходе соединение возвращается в пул, а не закрывается.
    """

    def __init__(self):
        self.pool = _get_pool()
        self.conn = self.pool.getconn()

    def __enter__(self):
        return self.conn

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.pool.putconn(self.conn)
        return False

    def __getattr__(self, item):
        return getattr(self.conn, item)


def get_db_connection():
    """Возвращает pooled connection wrapper вместо нового физического подключения."""
    return PooledConnection()

 
# =====================================================
# ПАЦИЕНТЫ
# =====================================================

def get_all_patients(search: str = None, limit: int = 500, offset: int = 0):
    """Возвращает список пациентов для страницы /patients."""
    limit = max(1, min(int(limit or 500), 1000))
    offset = max(0, int(offset or 0))

    query = """
        SELECT
            id,
            last_name,
            first_name,
            patronymic,
            birth_date,
            phone
        FROM patients
        WHERE 1=1
    """
    params = []

    if search:
        query += """
            AND (
                last_name ILIKE %s
                OR first_name ILIKE %s
                OR patronymic ILIKE %s
                OR phone ILIKE %s
            )
        """
        value = f"%{search}%"
        params.extend([value, value, value, value])

    query += """
        ORDER BY last_name, first_name, patronymic NULLS LAST
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

def get_patient_by_id(patient_id: int):
    """Возвращает основные данные пациента: ФИО, дата рождения, пол.
       Контактные данные (телефон, email) исключены для безопасности и логики.
       Возраст вычисляется на данный момент на основе даты рождения.
    """
    with get_db_connection() as conn: #открывает соединение, автоматически закрывает после блока
        with conn.cursor() as cur:
             #выполняет запрос с подстановкой параметра %s (защита от SQL-инъекций)
            cur.execute("""
                SELECT 
                    id, last_name, first_name, patronymic, birth_date, 
                    CASE WHEN gender THEN 'Мужской' ELSE 'Женский' END AS gender_str
                FROM patients
                WHERE id = %s
            """, (patient_id,))

            # Получаем сырые данные из базы
            patient_data = cur.fetchone()
            # Вычисляем возраст (на основе даты рождения и сегодняшнего дня)
            if patient_data and patient_data['birth_date']:
                from datetime import date
                today = date.today()
                age = today.year - patient_data['birth_date'].year
                # Поправка: если день рождения еще не наступил в этом году
                if (today.month, today.day) < (patient_data['birth_date'].month, patient_data['birth_date'].day):
                    age -= 1
                patient_data['age'] = age
            else:
                patient_data['age'] = None
                
            return patient_data

def get_patient_contact_info(patient_id: int):
    """Отдельная функция для получения контактных данных (телефон, email).
       Вызывается только тогда, когда пользователь перешел в карточку пациента или открыл вкладку с контактами.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT phone, email
                FROM patients
                WHERE id = %s
            """, (patient_id,))
            return cur.fetchone()

# =====================================================
# ПРИЁМЫ
# =====================================================

#Формирует SQL-запрос в зависимости от фильтров, Добавляет условия AND если передан branch_id, location_id, search, 
#Возвращает список приёмов
def get_all_appointments(filters: dict = None):
    """Возвращает список приёмов с фильтрацией, безопасной сортировкой и пагинацией."""
    filters = filters or {}

    query = """
        SELECT 
            a.id AS appointment_id,
            p.id AS patient_id,
            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
            a.appointment_date,
            EXTRACT(YEAR FROM AGE(CURRENT_DATE, p.birth_date)) AS age,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio,
            l.name AS location_name,
            b.name AS branch_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        WHERE 1=1
    """

    params = []

    if filters.get("branch_id"):
        query += " AND b.id = %s"
        params.append(filters["branch_id"])

    if filters.get("location_id"):
        query += " AND l.id = %s"
        params.append(filters["location_id"])

    if filters.get("doctor_id"):
        query += " AND d.id = %s"
        params.append(filters["doctor_id"])

    if filters.get("search"):
        query += """
            AND (
                p.last_name ILIKE %s
                OR p.first_name ILIKE %s
                OR COALESCE(p.patronymic, '') ILIKE %s
            )
        """
        search = f"%{filters['search']}%"
        params.extend([search, search, search])

    if filters.get("date_from"):
        query += " AND a.appointment_date >= %s"
        params.append(filters["date_from"])

    if filters.get("date_to"):
        # date_to приходит как дата без времени.
        # Так включается весь выбранный день.
        query += " AND a.appointment_date < (%s::date + INTERVAL '1 day')"
        params.append(filters["date_to"])

    sort_order = str(filters.get("sort_order", "desc")).lower()
    sort_order = "ASC" if sort_order == "asc" else "DESC"

    try:
        limit = int(filters.get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200

    limit = max(1, min(limit, 500))

    try:
        offset = int(filters.get("offset") or 0)
    except (TypeError, ValueError):
        offset = 0

    offset = max(0, offset)

    query += f" ORDER BY a.appointment_date {sort_order} LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()

#Возвращает список приёмов для конкретного пациента (для левой панели в карточке). Меньше полей, только основные.
def get_patient_appointments(patient_id: int):
    """Возвращает все приёмы конкретного пациента"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    a.id AS appointment_id,
                    a.appointment_date,
                    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
                    l.name AS location_name,
                    b.name AS branch_name
                FROM appointments a
                JOIN doctors d ON a.doctor_id = d.id
                JOIN locations l ON a.location_id = l.id
                JOIN branches b ON l.branch_id = b.id
                WHERE a.patient_id = %s
                ORDER BY a.appointment_date DESC
            """, (patient_id,))
            return cur.fetchall()

#возвращает все лекарства по пациенту
def get_appointment_medications(appointment_id: int):
    """Возвращает список всех лекарств для приёма"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, medication, dosage, schedule
                FROM prescriptions
                WHERE appointment_id = %s
                ORDER BY id
            """, (appointment_id,))
            return cur.fetchall()
        
def get_appointment_diet(appointment_id: int):
    """Возвращает диету, дату следующего контроля и рекомендации для приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT diet, next_control_date, recommendations
                FROM appointment_diets
                WHERE appointment_id = %s
                LIMIT 1
            """, (appointment_id,))
            return cur.fetchone()

def get_last_appointment_data(patient_id: int):
    """Возвращает основные данные последнего приёма пациента для автоподстановки."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    a.id AS appointment_id, a.doctor_id,
                    a.location_id, a.appointment_date,

                    s.life_anamnesis, s.disease_anamnesis,
                    s.complaints, s.heredity,
                    s.heredity_description, s.comorbidities,

                    e.skin_condition, e.edema_location,
                    e.systolic_pressure, e.diastolic_pressure,
                    e.bp_note, e.heart_rate,
                    e.height, e.weight,

                    diag.main_diagnosis, diag.complications,
                    diag.comorbidities AS diag_comorbidities,

                    ad.diet,
                    ad.next_control_date,
                    ad.recommendations
                FROM appointments a
                LEFT JOIN surveys s ON a.id = s.appointment_id
                LEFT JOIN examinations e ON a.id = e.appointment_id
                LEFT JOIN diagnoses diag ON a.id = diag.appointment_id
                LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
                WHERE a.patient_id = %s
                ORDER BY a.appointment_date DESC
                LIMIT 1
            """, (patient_id,))
            return cur.fetchone()

def get_patient_biochemistry_history(patient_id: int, until_date: date = None):
    """Возвращает историю биохимических анализов пациента до указанной даты"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT 
                        bio.investigation_date,
                        bio.creatinine, bio.urea, bio.uric_acid, bio.glucose,
                        bio.total_protein, bio.albumin, bio.potassium, bio.calcium,
                        bio.phosphorus, bio.ferritin, bio.ptg
                    FROM biochemistry_results bio
                    JOIN appointments a ON bio.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND bio.investigation_date IS NOT NULL
                        AND bio.investigation_date <= %s
                    ORDER BY bio.investigation_date ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT 
                        bio.investigation_date,
                        bio.creatinine, bio.urea, bio.uric_acid, bio.glucose,
                        bio.total_protein, bio.albumin, bio.potassium, bio.calcium,
                        bio.phosphorus, bio.ferritin, bio.ptg
                    FROM biochemistry_results bio
                    JOIN appointments a ON bio.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND bio.investigation_date IS NOT NULL
                    ORDER BY bio.investigation_date ASC
                """, (patient_id,))
            return cur.fetchall()
        
def get_patient_cbc_history(patient_id: int, until_date: date = None):
    """Возвращает историю общего анализа крови (ОАК) пациента до указанной даты"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT 
                        cbc.investigation_date,
                        cbc.hemoglobin, cbc.erythrocytes, cbc.leukocytes,
                        cbc.platelets, cbc.esr, cbc.mcv, cbc.hematocrit
                    FROM cbc_results cbc
                    JOIN appointments a ON cbc.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND cbc.investigation_date IS NOT NULL
                        AND cbc.investigation_date <= %s
                    ORDER BY cbc.investigation_date ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT 
                        cbc.investigation_date,
                        cbc.hemoglobin, cbc.erythrocytes, cbc.leukocytes,
                        cbc.platelets, cbc.esr, cbc.mcv, cbc.hematocrit
                    FROM cbc_results cbc
                    JOIN appointments a ON cbc.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND cbc.investigation_date IS NOT NULL
                    ORDER BY cbc.investigation_date ASC
                """, (patient_id,))
            return cur.fetchall()


def get_patient_urinalysis_history(patient_id: int, until_date: date = None):
    """Возвращает историю ОАМ (уникальные даты с последними значениями)"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT DISTINCT ON (uri.investigation_date)
                        uri.investigation_date,
                        uri.specific_gravity, 
                        uri.protein, 
                        uri.leukocytes,
                        uri.erythrocytes, 
                        uri.bacteria
                    FROM urinalysis_results uri
                    JOIN appointments a ON uri.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND uri.investigation_date IS NOT NULL
                        AND uri.investigation_date <= %s
                    ORDER BY uri.investigation_date ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT DISTINCT ON (uri.investigation_date)
                        uri.investigation_date,
                        uri.specific_gravity, 
                        uri.protein, 
                        uri.leukocytes,
                        uri.erythrocytes, 
                        uri.bacteria
                    FROM urinalysis_results uri
                    JOIN appointments a ON uri.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND uri.investigation_date IS NOT NULL
                    ORDER BY uri.investigation_date ASC
                """, (patient_id,))
            return cur.fetchall()

def get_patient_metrics_history(patient_id: int, until_date: date = None):
    """Возвращает историю расчётных показателей пациента по дате анализа креатинина."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT 
                        COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
                        cm.creatinine,
                        cm.egfr_ckdepi,
                        cm.crcl_cockcroft_gault,
                        cm.ckd_stage
                    FROM calculated_metrics cm
                    JOIN appointments a ON cm.appointment_id = a.id
                    WHERE a.patient_id = %s
                      AND COALESCE(cm.investigation_date, a.appointment_date::date) <= %s
                    ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT 
                        COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
                        cm.creatinine,
                        cm.egfr_ckdepi,
                        cm.crcl_cockcroft_gault,
                        cm.ckd_stage
                    FROM calculated_metrics cm
                    JOIN appointments a ON cm.appointment_id = a.id
                    WHERE a.patient_id = %s
                    ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) ASC
                """, (patient_id,))

            return cur.fetchall()
        
#сохранение расчитаных скф
def save_calculated_metrics(appointment_id: int, egfr_ckdepi, crcl_cockcroft_gault, ckd_stage):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO calculated_metrics (
                    appointment_id,
                    egfr_ckdepi,
                    crcl_cockcroft_gault,
                    ckd_stage
                )
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (appointment_id)
                DO UPDATE SET
                    egfr_ckdepi = EXCLUDED.egfr_ckdepi,
                    crcl_cockcroft_gault = EXCLUDED.crcl_cockcroft_gault,
                    ckd_stage = EXCLUDED.ckd_stage
            """, (
                appointment_id,
                egfr_ckdepi,
                crcl_cockcroft_gault,
                ckd_stage
            ))

            conn.commit()

def get_patient_ultrasound_history(patient_id: int, until_date: date = None):
    """Возвращает историю УЗИ почек пациента до указанной даты"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT 
                        us.investigation_date,
                        us.left_kidney_size, us.right_kidney_size,
                        us.left_parenchyma, us.right_parenchyma, us.description
                    FROM ultrasound_results us
                    JOIN appointments a ON us.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND us.investigation_date IS NOT NULL
                        AND us.investigation_date <= %s
                    ORDER BY us.investigation_date ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT 
                        us.investigation_date,
                        us.left_kidney_size, us.right_kidney_size,
                        us.left_parenchyma, us.right_parenchyma, us.description
                    FROM ultrasound_results us
                    JOIN appointments a ON us.appointment_id = a.id
                    WHERE a.patient_id = %s
                        AND us.investigation_date IS NOT NULL
                    ORDER BY us.investigation_date ASC
                """, (patient_id,))
            return cur.fetchall()

def get_patient_albuminuria_history(patient_id: int, until_date: date = None):
    """Возвращает историю альбуминурии пациента до указанной даты."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if until_date:
                cur.execute("""
                    SELECT
                        ar.investigation_date,
                        ar.urine_albumin,
                        ar.urine_albumin_unit,
                        ar.urine_creatinine,
                        ar.urine_creatinine_unit,
                        ar.albumin_creatinine_ratio,
                        ar.albuminuria_category
                    FROM albuminuria_results ar
                    JOIN appointments a ON ar.appointment_id = a.id
                    WHERE a.patient_id = %s
                      AND ar.investigation_date IS NOT NULL
                      AND ar.investigation_date <= %s
                    ORDER BY ar.investigation_date ASC, ar.id ASC
                """, (patient_id, until_date))
            else:
                cur.execute("""
                    SELECT
                        ar.investigation_date,
                        ar.urine_albumin,
                        ar.urine_albumin_unit,
                        ar.urine_creatinine,
                        ar.urine_creatinine_unit,
                        ar.albumin_creatinine_ratio,
                        ar.albuminuria_category
                    FROM albuminuria_results ar
                    JOIN appointments a ON ar.appointment_id = a.id
                    WHERE a.patient_id = %s
                      AND ar.investigation_date IS NOT NULL
                    ORDER BY ar.investigation_date ASC, ar.id ASC
                """, (patient_id,))

            return cur.fetchall()

#Возвращает все данные одного приёма (опрос, осмотр, анализы, УЗИ, диагнозы, назначения). 
# Здесь много LEFT JOIN, потому что не у каждого приёма могут быть заполнены все анализы.
# Важно: LEFT JOIN означает, что если данных нет (например, нет УЗИ), то в результат придёт NULL вместо отсутствующей строки.
def get_appointment_full_data(appointment_id: int):
    """
    Возвращает основные данные одного приёма.

    Оптимизация: убраны LEFT JOIN к таблицам анализов. Истории анализов уже загружаются
    отдельными функциями, а джойны нескольких one-to-many таблиц могут перемножать строки
    и замедлять карточку пациента.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    a.id,
                    a.appointment_date,
                    a.patient_id,
                    a.location_id,
                    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
                    p.birth_date,
                    EXTRACT(YEAR FROM AGE(a.appointment_date, p.birth_date)) AS age_at_appointment,
                    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
                    l.name AS location_name,
                    b.name AS branch_name,

                    s.life_anamnesis,
                    s.disease_anamnesis,
                    s.complaints,
                    s.heredity,
                    s.heredity_description,
                    s.comorbidities,

                    e.skin_condition,
                    e.edema_location,
                    e.systolic_pressure,
                    e.diastolic_pressure,
                    e.bp_note,
                    e.heart_rate,
                    e.height,
                    e.weight,

                    diag.main_diagnosis,
                    diag.complications,
                    diag.comorbidities AS diag_comorbidities,

                    ad.diet,
                    ad.next_control_date,
                    ad.recommendations
                FROM appointments a
                JOIN patients p ON a.patient_id = p.id
                JOIN doctors d ON a.doctor_id = d.id
                JOIN locations l ON a.location_id = l.id
                JOIN branches b ON l.branch_id = b.id
                LEFT JOIN surveys s ON a.id = s.appointment_id
                LEFT JOIN examinations e ON a.id = e.appointment_id
                LEFT JOIN diagnoses diag ON a.id = diag.appointment_id
                LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
                WHERE a.id = %s
            """, (appointment_id,))
            return cur.fetchone()

def get_doctor_locations(doctor_id: int):
    """Возвращает список отделений, где работает врач"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT l.id, l.name, b.name as branch_name
                FROM doctor_locations dl
                JOIN locations l ON dl.location_id = l.id
                JOIN branches b ON l.branch_id = b.id
                WHERE dl.doctor_id = %s
                ORDER BY b.name, l.name
            """, (doctor_id,))
            return cur.fetchall()
                          
# =====================================================
# СПРАВОЧНИКИ ДЛЯ ФИЛЬТРОВ
# =====================================================

#	Список филиалов
def get_branches():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM branches ORDER BY name")
            return cur.fetchall()

#Список отделений (по фильтру)
def get_locations_by_branch(branch_id: int = None):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            if branch_id:
                cur.execute("SELECT id, name, branch_id FROM locations WHERE branch_id = %s ORDER BY name", (branch_id,))
            else:
                cur.execute("SELECT id, name, branch_id FROM locations ORDER BY name")
            return cur.fetchall()

#Список врачей
def get_doctors():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, last_name, first_name, patronymic FROM doctors ORDER BY last_name")
            return cur.fetchall()

def get_doctors_for_filter(branch_id: int = None, location_id: int = None):
    """
    Возвращает список врачей для фильтра на главной странице.
    Если выбран филиал — только врачи, работающие в этом филиале.
    Если выбрано отделение — только врачи, работающие в этом отделении.
    """
    query = """
        SELECT DISTINCT
            d.id,
            d.last_name,
            d.first_name,
            d.patronymic
        FROM doctors d
        LEFT JOIN doctor_locations dl ON dl.doctor_id = d.id
        LEFT JOIN locations l ON l.id = dl.location_id
        WHERE 1=1
    """

    params = []

    if branch_id:
        query += " AND l.branch_id = %s"
        params.append(branch_id)

    if location_id:
        query += " AND dl.location_id = %s"
        params.append(location_id)

    query += " ORDER BY d.last_name, d.first_name, d.patronymic"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()


def get_locations_for_filter(branch_id: int = None, doctor_id: int = None):
    """
    Возвращает список отделений для фильтра на главной странице.
    Если выбран филиал — только отделения этого филиала.
    Если выбран врач — только отделения, где работает этот врач.
    """
    query = """
        SELECT DISTINCT
            l.id,
            l.name,
            l.branch_id
        FROM locations l
        LEFT JOIN doctor_locations dl ON dl.location_id = l.id
        WHERE 1=1
    """

    params = []

    if branch_id:
        query += " AND l.branch_id = %s"
        params.append(branch_id)

    if doctor_id:
        query += " AND dl.doctor_id = %s"
        params.append(doctor_id)

    query += " ORDER BY l.name"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()       

# Информация об отделении
def get_location_info(location_id: int):
    """Возвращает информацию об отделении, филиале и компании"""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    l.id, 
                    l.name AS location_name, 
                    l.factual_address AS location_address,
                    b.id AS branch_id, 
                    b.name AS branch_name, 
                    b.legal_address AS branch_address, 
                    b.phone AS branch_phone,
                    b.email AS branch_email,
                    c.id AS company_id, 
                    c.name AS company_name,
                    c.legal_address AS company_address, 
                    c.phone AS company_phone, 
                    c.email AS company_email
                FROM locations l
                LEFT JOIN branches b ON l.branch_id = b.id
                LEFT JOIN companies c ON b.company_id = c.id
                WHERE l.id = %s
            """, (location_id,))
            
            result = cur.fetchone()
            
            
            
            return result

# =====================================================
# БЫСТРЫЕ СБОРЩИКИ СТРАНИЦ
# =====================================================
# Эти функции собирают данные для HTML-страниц через одно соединение и один cursor.
# Публичные функции выше оставлены для совместимости с остальным кодом.


def _fetch_patient_by_id(cur, patient_id: int):
    cur.execute("""
        SELECT 
            id, last_name, first_name, patronymic, birth_date,
            CASE WHEN gender THEN 'Мужской' ELSE 'Женский' END AS gender_str
        FROM patients
        WHERE id = %s
    """, (patient_id,))
    patient_data = cur.fetchone()

    if patient_data and patient_data.get('birth_date'):
        today = date.today()
        age = today.year - patient_data['birth_date'].year
        if (today.month, today.day) < (patient_data['birth_date'].month, patient_data['birth_date'].day):
            age -= 1
        patient_data['age'] = age
    elif patient_data:
        patient_data['age'] = None

    return patient_data


def _fetch_patient_appointments(cur, patient_id: int):
    cur.execute("""
        SELECT 
            a.id AS appointment_id,
            a.appointment_date,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
            l.name AS location_name,
            b.name AS branch_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC
    """, (patient_id,))
    return cur.fetchall()


def _fetch_appointment_full_data(cur, appointment_id: int):
    cur.execute("""
        SELECT 
            a.id,
            a.appointment_date,
            a.patient_id,
            a.location_id,
            p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
            p.birth_date,
            EXTRACT(YEAR FROM AGE(a.appointment_date, p.birth_date)) AS age_at_appointment,
            d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_name,
            l.name AS location_name,
            b.name AS branch_name,

            s.life_anamnesis,
            s.disease_anamnesis,
            s.complaints,
            s.heredity,
            s.heredity_description,
            s.comorbidities,

            e.skin_condition,
            e.edema_location,
            e.systolic_pressure,
            e.diastolic_pressure,
            e.bp_note,
            e.heart_rate,
            e.height,
            e.weight,

            diag.main_diagnosis,
            diag.complications,
            diag.comorbidities AS diag_comorbidities,

            ad.diet,
            ad.next_control_date,
            ad.recommendations
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        JOIN locations l ON a.location_id = l.id
        JOIN branches b ON l.branch_id = b.id
        LEFT JOIN surveys s ON a.id = s.appointment_id
        LEFT JOIN examinations e ON a.id = e.appointment_id
        LEFT JOIN diagnoses diag ON a.id = diag.appointment_id
        LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
        WHERE a.id = %s
    """, (appointment_id,))
    return cur.fetchone()


def _fetch_last_appointment_data(cur, patient_id: int):
    cur.execute("""
        SELECT
            a.id AS appointment_id,
            a.doctor_id,
            a.location_id,
            a.appointment_date,

            s.life_anamnesis,
            s.disease_anamnesis,
            s.complaints,
            s.heredity,
            s.heredity_description,
            s.comorbidities,

            e.skin_condition,
            e.edema_location,
            e.systolic_pressure,
            e.diastolic_pressure,
            e.bp_note,
            e.heart_rate,
            e.height,
            e.weight,

            diag.main_diagnosis,
            diag.complications,
            diag.comorbidities AS diag_comorbidities,

            ad.diet,
            ad.next_control_date,
            ad.recommendations
        FROM appointments a
        LEFT JOIN surveys s ON a.id = s.appointment_id
        LEFT JOIN examinations e ON a.id = e.appointment_id
        LEFT JOIN diagnoses diag ON a.id = diag.appointment_id
        LEFT JOIN appointment_diets ad ON a.id = ad.appointment_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date DESC
        LIMIT 1
    """, (patient_id,))
    return cur.fetchone()


def _fetch_appointment_medications(cur, appointment_id: int):
    cur.execute("""
        SELECT id, medication, dosage, schedule
        FROM prescriptions
        WHERE appointment_id = %s
        ORDER BY id
    """, (appointment_id,))
    return cur.fetchall()


def _fetch_appointment_diet(cur, appointment_id: int):
    cur.execute("""
        SELECT diet, next_control_date, recommendations
        FROM appointment_diets
        WHERE appointment_id = %s
        LIMIT 1
    """, (appointment_id,))
    return cur.fetchone()


def _fetch_branches(cur):
    cur.execute("SELECT id, name FROM branches ORDER BY name")
    return cur.fetchall()


def _fetch_locations_by_branch(cur, branch_id: int = None):
    if branch_id:
        cur.execute("SELECT id, name, branch_id FROM locations WHERE branch_id = %s ORDER BY name", (branch_id,))
    else:
        cur.execute("SELECT id, name, branch_id FROM locations ORDER BY name")
    return cur.fetchall()


def _fetch_doctors(cur):
    cur.execute("SELECT id, last_name, first_name, patronymic FROM doctors ORDER BY last_name")
    return cur.fetchall()


def _fetch_patient_biochemistry_history(cur, patient_id: int, until_date: date = None):
    params = [patient_id]
    date_filter = ""
    if until_date:
        date_filter = "AND bio.investigation_date <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT 
            bio.investigation_date,
            bio.creatinine, bio.urea, bio.uric_acid, bio.glucose,
            bio.total_protein, bio.albumin, bio.potassium, bio.calcium,
            bio.phosphorus, bio.ferritin, bio.ptg
        FROM biochemistry_results bio
        JOIN appointments a ON bio.appointment_id = a.id
        WHERE a.patient_id = %s
            AND bio.investigation_date IS NOT NULL
            {date_filter}
        ORDER BY bio.investigation_date ASC
    """, params)
    return cur.fetchall()


def _fetch_patient_cbc_history(cur, patient_id: int, until_date: date = None):
    params = [patient_id]
    date_filter = ""
    if until_date:
        date_filter = "AND cbc.investigation_date <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT 
            cbc.investigation_date,
            cbc.hemoglobin, cbc.erythrocytes, cbc.leukocytes,
            cbc.platelets, cbc.esr, cbc.mcv, cbc.hematocrit
        FROM cbc_results cbc
        JOIN appointments a ON cbc.appointment_id = a.id
        WHERE a.patient_id = %s
            AND cbc.investigation_date IS NOT NULL
            {date_filter}
        ORDER BY cbc.investigation_date ASC
    """, params)
    return cur.fetchall()


def _fetch_patient_urinalysis_history(cur, patient_id: int, until_date: date = None):
    params = [patient_id]
    date_filter = ""
    if until_date:
        date_filter = "AND uri.investigation_date <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT DISTINCT ON (uri.investigation_date)
            uri.investigation_date,
            uri.specific_gravity,
            uri.protein,
            uri.leukocytes,
            uri.erythrocytes,
            uri.bacteria
        FROM urinalysis_results uri
        JOIN appointments a ON uri.appointment_id = a.id
        WHERE a.patient_id = %s
            AND uri.investigation_date IS NOT NULL
            {date_filter}
        ORDER BY uri.investigation_date ASC
    """, params)
    return cur.fetchall()


def _fetch_patient_metrics_history(cur, patient_id: int, until_date: date = None):
    params = [patient_id]
    date_filter = ""
    if until_date:
        date_filter = "AND COALESCE(cm.investigation_date, a.appointment_date::date) <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT 
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date,
            cm.creatinine,
            cm.egfr_ckdepi,
            cm.crcl_cockcroft_gault,
            cm.ckd_stage
        FROM calculated_metrics cm
        JOIN appointments a ON cm.appointment_id = a.id
        WHERE a.patient_id = %s
            {date_filter}
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) ASC
    """, params)
    return cur.fetchall()

def _fetch_patient_ultrasound_history(cur, patient_id: int, until_date: date = None):
    """Возвращает историю УЗИ почек пациента до указанной даты."""
    params = [patient_id]
    date_filter = ""

    if until_date:
        date_filter = "AND us.investigation_date <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT 
            us.investigation_date,
            us.left_kidney_size,
            us.right_kidney_size,
            us.left_parenchyma,
            us.right_parenchyma,
            us.description
        FROM ultrasound_results us
        JOIN appointments a ON us.appointment_id = a.id
        WHERE a.patient_id = %s
            AND us.investigation_date IS NOT NULL
            {date_filter}
        ORDER BY us.investigation_date ASC
    """, params)

    return cur.fetchall()

def _fetch_patient_albuminuria_history(cur, patient_id: int, until_date=None):
    """Возвращает историю альбуминурии пациента до указанной даты."""
    if until_date:
        cur.execute("""
            SELECT
                ar.investigation_date,
                ar.urine_albumin,
                ar.urine_albumin_unit,
                ar.urine_creatinine,
                ar.urine_creatinine_unit,
                ar.albumin_creatinine_ratio,
                ar.albuminuria_category
            FROM albuminuria_results ar
            JOIN appointments a ON ar.appointment_id = a.id
            WHERE a.patient_id = %s
              AND ar.investigation_date IS NOT NULL
              AND ar.investigation_date <= %s
            ORDER BY ar.investigation_date ASC, ar.id ASC
        """, (patient_id, until_date))
    else:
        cur.execute("""
            SELECT
                ar.investigation_date,
                ar.urine_albumin,
                ar.urine_albumin_unit,
                ar.urine_creatinine,
                ar.urine_creatinine_unit,
                ar.albumin_creatinine_ratio,
                ar.albuminuria_category
            FROM albuminuria_results ar
            JOIN appointments a ON ar.appointment_id = a.id
            WHERE a.patient_id = %s
              AND ar.investigation_date IS NOT NULL
            ORDER BY ar.investigation_date ASC, ar.id ASC
        """, (patient_id,))

    return cur.fetchall()

def get_patient_albuminuria_history(patient_id: int, until_date=None):
    """Возвращает историю альбуминурии пациента до указанной даты."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_albuminuria_history(cur, patient_id, until_date)

def _fetch_latest_gfr_category_for_prognosis(cur, patient_id: int, assessment_date):
    """Берёт последнюю категорию СКФ пациента на дату прогноза или раньше."""
    cur.execute("""
        SELECT
            cm.ckd_stage,
            COALESCE(cm.investigation_date, a.appointment_date::date) AS investigation_date
        FROM calculated_metrics cm
        JOIN appointments a ON cm.appointment_id = a.id
        WHERE a.patient_id = %s
          AND cm.ckd_stage IS NOT NULL
          AND COALESCE(cm.investigation_date, a.appointment_date::date) <= %s
        ORDER BY COALESCE(cm.investigation_date, a.appointment_date::date) DESC, cm.id DESC
        LIMIT 1
    """, (patient_id, assessment_date))

    return cur.fetchone()


def _fetch_latest_albuminuria_category_for_prognosis(cur, patient_id: int, assessment_date):
    """Берёт последнюю категорию альбуминурии пациента на дату прогноза или раньше."""
    cur.execute("""
        SELECT
            ar.albuminuria_category,
            ar.investigation_date
        FROM albuminuria_results ar
        JOIN appointments a ON ar.appointment_id = a.id
        WHERE a.patient_id = %s
          AND ar.albuminuria_category IS NOT NULL
          AND ar.investigation_date <= %s
        ORDER BY ar.investigation_date DESC, ar.id DESC
        LIMIT 1
    """, (patient_id, assessment_date))

    return cur.fetchone()




def save_ckd_prognosis_for_appointment(appointment_id: int, cur=None):
    """
    Сохраняет прогноз ХБП по KDIGO для конкретного приема.

    Логика:
    1. Берет последнюю категорию СКФ для этого приема.
    2. Берет последнюю категорию альбуминурии для этого приема.
    3. Если обе категории есть — рассчитывает прогноз и сохраняет в ckd_prognosis_results.
    4. Если для приема уже был прогноз — удаляет старый и записывает актуальный.
    """

    def _save(cursor):
        # Последняя СКФ внутри текущего приема
        cursor.execute(
            """
            SELECT
                investigation_date,
                ckd_stage
            FROM calculated_metrics
            WHERE appointment_id = %s
              AND ckd_stage IS NOT NULL
            ORDER BY investigation_date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (appointment_id,)
        )
        metric = cursor.fetchone()

        # Последняя альбуминурия внутри текущего приема
        cursor.execute(
            """
            SELECT
                investigation_date,
                albuminuria_category
            FROM albuminuria_results
            WHERE appointment_id = %s
              AND albuminuria_category IS NOT NULL
            ORDER BY investigation_date DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (appointment_id,)
        )
        albuminuria = cursor.fetchone()

        if not metric or not albuminuria:
            return None

        gfr_category = normalize_ckd_stage_for_storage(metric.get("ckd_stage"))
        albuminuria_category = albuminuria.get("albuminuria_category")

        prognosis = calculate_ckd_prognosis(gfr_category, albuminuria_category)

        if not prognosis or not prognosis.get("prognosis_level"):
            return None

        metric_date = metric.get("investigation_date")
        albuminuria_date = albuminuria.get("investigation_date")

        assessment_date = albuminuria_date or metric_date

        if metric_date and albuminuria_date:
            assessment_date = max(metric_date, albuminuria_date)

        # Чтобы не плодить дубли, сначала удаляем старый прогноз этого приема
        cursor.execute(
            """
            DELETE FROM ckd_prognosis_results
            WHERE appointment_id = %s
            """,
            (appointment_id,)
        )

        cursor.execute(
            """
            INSERT INTO ckd_prognosis_results (
                appointment_id,
                assessment_date,
                gfr_category,
                albuminuria_category,
                combined_category,
                prognosis_level,
                prognosis_text,
                created_at,
                updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, NOW(), NOW()
            )
            RETURNING *
            """,
            (
                appointment_id,
                assessment_date,
                prognosis["gfr_category"],
                prognosis["albuminuria_category"],
                prognosis["combined_category"],
                prognosis["prognosis_level"],
                prognosis["prognosis_text"],
            )
        )

        return cursor.fetchone()

    if cur is not None:
        return _save(cur)

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            result = _save(cursor)
            conn.commit()
            return result


def recalculate_ckd_prognosis_for_appointment(appointment_id: int, assessment_date=None):
    """Публичная функция для пересчёта прогноза одного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return save_ckd_prognosis_for_appointment(
                cur,
                appointment_id,
                assessment_date
            )


def _fetch_appointment_ckd_prognosis(cur, appointment_id: int):
    """Возвращает сохранённый прогноз ХБП для выбранного приёма."""
    cur.execute("""
        SELECT
            id,
            appointment_id,
            assessment_date,
            gfr_category,
            albuminuria_category,
            combined_category,
            prognosis_level,
            prognosis_text
        FROM ckd_prognosis_results
        WHERE appointment_id = %s
        LIMIT 1
    """, (appointment_id,))

    return cur.fetchone()


def get_appointment_ckd_prognosis(appointment_id: int):
    """Возвращает сохранённый прогноз ХБП по KDIGO для конкретного приёма."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_appointment_ckd_prognosis(cur, appointment_id)


def get_patient_ckd_prognosis_history(patient_id: int, until_date=None):
    """Возвращает историю прогнозов ХБП пациента до указанной даты."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date)


def _fetch_patient_ckd_prognosis_history(cur, patient_id: int, until_date=None):
    """Возвращает историю прогнозов ХБП пациента."""
    params = [patient_id]
    date_filter = ""

    if until_date:
        date_filter = "AND cpr.assessment_date <= %s"
        params.append(until_date)

    cur.execute(f"""
        SELECT
            cpr.id,
            cpr.appointment_id,
            cpr.assessment_date,
            cpr.gfr_category,
            cpr.albuminuria_category,
            cpr.combined_category,
            cpr.prognosis_level,
            cpr.prognosis_text
        FROM ckd_prognosis_results cpr
        JOIN appointments a ON cpr.appointment_id = a.id
        WHERE a.patient_id = %s
          {date_filter}
        ORDER BY cpr.assessment_date ASC, cpr.id ASC
    """, params)

    return cur.fetchall()

def get_patient_card_context(patient_id: int, selected_appointment_id: int = None, show_previous_labs: bool = False, show_form: bool = False):
    """
    Собирает контекст карточки пациента одним соединением к БД.
    Это основная оптимизация для /patient/{patient_id}.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient = _fetch_patient_by_id(cur, patient_id)
            if not patient:
                return None

            appointments = _fetch_patient_appointments(cur, patient_id)
            appointment_data = None

            if show_previous_labs and appointments and len(appointments) > 1:
                prev_appointment_id = appointments[1]['appointment_id']
                appointment_data = _fetch_appointment_full_data(cur, prev_appointment_id)
                if appointment_data:
                    appointment_data['is_previous_labs'] = True
                    appointment_data['previous_labs_date'] = appointment_data.get('appointment_date')

            if not selected_appointment_id and appointments and not show_form:
                selected_appointment_id = appointments[0]['appointment_id']

            medications = []
            diet_info = None
            icd10_diagnoses = []

            if selected_appointment_id and not appointment_data:
                appointment_data = _fetch_appointment_full_data(cur, int(selected_appointment_id))
                if appointment_data and appointment_data.get('patient_id') != patient_id:
                    return {"patient": patient, "forbidden": True}
                if appointment_data:
                    medications = _fetch_appointment_medications(cur, int(selected_appointment_id))
                    diet_info = _fetch_appointment_diet(cur, int(selected_appointment_id))
                    icd10_diagnoses = _fetch_appointment_icd10_diagnoses(cur, int(selected_appointment_id))

            until_date = None
            if not show_form and appointment_data and appointment_data.get('appointment_date'):
                until_date = appointment_data['appointment_date'].date()

            return {
                "patient": patient,
                "appointments": appointments,
                "selected_appointment": appointment_data,
                "medications": medications,
                "diet_info": diet_info,
                "icd10_diagnoses": icd10_diagnoses,
                "biochemistry_history": _fetch_patient_biochemistry_history(cur, patient_id, until_date),
                "cbc_history": _fetch_patient_cbc_history(cur, patient_id, until_date),
                "urinalysis_history": _fetch_patient_urinalysis_history(cur, patient_id, until_date),
                "metrics_history": _fetch_patient_metrics_history(cur, patient_id, until_date),
                "ultrasound_history": _fetch_patient_ultrasound_history(cur, patient_id, until_date),
                "albuminuria_history": _fetch_patient_albuminuria_history(cur, patient_id, until_date),
                "ckd_prognosis_current": _fetch_appointment_ckd_prognosis(cur, int(selected_appointment_id)) if selected_appointment_id else None,
                "ckd_prognosis_history": _fetch_patient_ckd_prognosis_history(cur, patient_id, until_date),
                # Эти ключи оставлены для совместимости с шаблоном/старым кодом,
                # но в обычной карточке они не нужны и больше не создают лишних запросов.
                "branches": [],
                "doctors": [],
                "locations": [],
                "last_appointment": None,
                "last_medications": [],
                "last_diet_info": None,
                "location_info": None,
                
            }

def _fetch_icd10_diagnoses(cur):
    """
    Возвращает активные диагнозы МКБ-10 для формы.
    Диагноз хранится одной строкой:
    'N18.3 — Хроническая болезнь почек, стадия 3'
    """
    cur.execute("""
        SELECT
            id,
            diagnosis
        FROM icd10_diagnoses
        WHERE is_active = TRUE
        ORDER BY diagnosis
    """)
    return cur.fetchall()

def _fetch_appointment_icd10_diagnoses(cur, appointment_id: int):
    """
    Возвращает структурированные диагнозы по МКБ-10 для выбранного приёма.
    """
    cur.execute("""
        SELECT
            id,
            appointment_id,
            diagnosis_type,
            icd10_diagnosis_id,
            icd10_diagnosis,
            doctor_note,
            sort_order
        FROM appointment_icd10_diagnoses_view
        WHERE appointment_id = %s
        ORDER BY
            CASE diagnosis_type
                WHEN 'main' THEN 1
                WHEN 'complication' THEN 2
                WHEN 'comorbidity' THEN 3
                ELSE 4
            END,
            sort_order,
            id
    """, (appointment_id,))

    return cur.fetchall()

def _group_icd10_diagnoses_for_form(icd10_diagnoses):
    """
    Группирует структурированные диагнозы МКБ-10 для подстановки в форму повторного приёма.
    """

    result = {
        "main": None,
        "complications": [],
        "comorbidities": [],
    }

    for item in icd10_diagnoses:
        if item["diagnosis_type"] == "main" and result["main"] is None:
            result["main"] = item

        elif item["diagnosis_type"] == "complication":
            result["complications"].append(item)

        elif item["diagnosis_type"] == "comorbidity":
            result["comorbidities"].append(item)

    return result

def get_new_appointment_context(patient_id: int):
    """Собирает данные для формы нового приёма одним соединением к БД."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            patient = _fetch_patient_by_id(cur, patient_id)
            if not patient:
                return None

            appointments = _fetch_patient_appointments(cur, patient_id)
            last_appointment = _fetch_last_appointment_data(cur, patient_id)
            last_appointment_id = appointments[0]['appointment_id'] if appointments else None
            last_icd10_diagnoses = []
            last_icd10_diagnoses_grouped = {
                "main": None,
                "complications": [],
                "comorbidities": [],
            }

            if last_appointment_id:
                last_icd10_diagnoses = _fetch_appointment_icd10_diagnoses(cur, last_appointment_id)
                last_icd10_diagnoses_grouped = _group_icd10_diagnoses_for_form(last_icd10_diagnoses)

            return {
                "patient": patient,
                "appointments": appointments,
                "branches": _fetch_branches(cur),
                "doctors": _fetch_doctors(cur),
                "locations": _fetch_locations_by_branch(cur),
                "last_appointment": last_appointment,
                "last_icd10_diagnoses": last_icd10_diagnoses,
                "last_icd10_diagnoses_grouped": last_icd10_diagnoses_grouped,
                "last_medications": _fetch_appointment_medications(cur, last_appointment_id) if last_appointment_id else [],
                "last_diet_info": _fetch_appointment_diet(cur, last_appointment_id) if last_appointment_id else None,
                "cbc_history": _fetch_patient_cbc_history(cur, patient_id),
                "biochemistry_history": _fetch_patient_biochemistry_history(cur, patient_id),
                "urinalysis_history": _fetch_patient_urinalysis_history(cur, patient_id),
                "albuminuria_history": _fetch_patient_albuminuria_history(cur, patient_id),
                "ultrasound_history": _fetch_patient_ultrasound_history(cur, patient_id),
                "metrics_history": _fetch_patient_metrics_history(cur, patient_id),
                "icd10_diagnoses": _fetch_icd10_diagnoses(cur),
            }

def get_new_patient_context():
    """
    Собирает данные для формы нового пациента одним соединением к БД.

    Используется для страницы /new-patient.
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            return {
                "branches": _fetch_branches(cur),
                "doctors": _fetch_doctors(cur),
                "locations": _fetch_locations_by_branch(cur),
                "icd10_diagnoses": _fetch_icd10_diagnoses(cur),
            }