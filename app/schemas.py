from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List

# =====================================================
# БАЗОВЫЕ СПРАВОЧНИКИ
# =====================================================

class Branch(BaseModel):
    """Филиал медицинской организации"""
    id: int
    name: str

class Location(BaseModel):
    """Место приёма (отделение/кабинет)"""
    id: int
    name: str
    branch_id: Optional[int] = None
    factual_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    fax: Optional[str] = None

class Doctor(BaseModel):
    """Врач"""
    id: int
    last_name: str
    first_name: str
    patronymic: Optional[str] = None
    position: Optional[str] = None
    qualification: Optional[str] = None
    phone: Optional[str] = None

class Company(BaseModel):
    """Юридическое лицо"""
    id: int
    name: str
    legal_address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


# =====================================================
# ПАЦИЕНТЫ
# =====================================================

class Patient(BaseModel):
    """Пациент (полные данные)"""
    id: int
    last_name: str
    first_name: str
    patronymic: Optional[str] = None
    birth_date: date
    gender: bool
    gender_str: Optional[str] = None  # 'Мужской' / 'Женский'
    phone: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None  # возраст на сегодня


# =====================================================
# ПРИЁМЫ
# =====================================================

class Appointment(BaseModel):
    """Приём (основные данные)"""
    id: int
    appointment_date: datetime
    doctor_name: Optional[str] = None
    location_name: Optional[str] = None
    branch_name: Optional[str] = None


# =====================================================
# ОПРОС
# =====================================================

class Survey(BaseModel):
    """Опрос пациента (анамнез, жалобы)"""
    id: int
    appointment_id: int
    life_anamnesis: Optional[str] = None
    disease_anamnesis: Optional[str] = None
    complaints: Optional[str] = None
    heredity: Optional[bool] = None
    heredity_description: Optional[str] = None
    comorbidities: Optional[str] = None


# =====================================================
# ОСМОТР
# =====================================================

class Examination(BaseModel):
    """Физикальный осмотр"""
    id: int
    appointment_id: int
    skin_condition: Optional[str] = None
    edema_location: Optional[str] = None
    systolic_pressure: Optional[int] = None
    diastolic_pressure: Optional[int] = None
    bp_note: Optional[str] = None
    heart_rate: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None


# =====================================================
# ОБЩИЙ АНАЛИЗ КРОВИ (CBC)
# =====================================================

class CBCResult(BaseModel):
    """Общий анализ крови"""
    id: int
    appointment_id: int
    hemoglobin: Optional[float] = None      # г/л
    erythrocytes: Optional[float] = None    # ×10¹²/л
    leukocytes: Optional[float] = None      # ×10⁹/л
    platelets: Optional[float] = None       # ×10⁹/л
    esr: Optional[float] = None             # СОЭ, мм/ч
    mcv: Optional[float] = None             # фл
    hematocrit: Optional[float] = None      # %


# =====================================================
# БИОХИМИЯ КРОВИ
# =====================================================

class BiochemistryResult(BaseModel):
    """Биохимический анализ крови"""
    id: int
    appointment_id: int
    creatinine: Optional[float] = None       # мкмоль/л
    urea: Optional[float] = None            # ммоль/л
    uric_acid: Optional[float] = None       # мкмоль/л
    glucose: Optional[float] = None         # ммоль/л
    total_protein: Optional[float] = None   # г/л
    albumin: Optional[float] = None         # г/л
    potassium: Optional[float] = None       # ммоль/л
    calcium: Optional[float] = None         # ммоль/л
    phosphorus: Optional[float] = None      # ммоль/л
    ferritin: Optional[float] = None        # нг/мл
    ptg: Optional[float] = None             # пг/мл


# =====================================================
# ОБЩИЙ АНАЛИЗ МОЧИ
# =====================================================

class UrinalysisResult(BaseModel):
    """Общий анализ мочи"""
    id: int
    appointment_id: int
    specific_gravity: Optional[float] = None
    protein: Optional[float] = None         # г/л
    leukocytes: Optional[int] = None
    erythrocytes: Optional[int] = None
    bacteria: Optional[str] = None


# =====================================================
# УЗИ ПОЧЕК
# =====================================================

class UltrasoundResult(BaseModel):
    """УЗИ почек"""
    id: int
    appointment_id: int
    left_kidney_size: Optional[str] = None
    right_kidney_size: Optional[str] = None
    left_parenchyma: Optional[float] = None
    right_parenchyma: Optional[float] = None
    description: Optional[str] = None


# =====================================================
# ДИАГНОЗЫ
# =====================================================

class Diagnosis(BaseModel):
    """Диагноз"""
    id: int
    appointment_id: int
    main_diagnosis: Optional[str] = None
    complications: Optional[str] = None
    comorbidities: Optional[str] = None


# =====================================================
# НАЗНАЧЕНИЯ
# =====================================================

class Prescription(BaseModel):
    """Назначения и лечение"""
    id: int
    appointment_id: int
    diet: Optional[str] = None
    medication: Optional[str] = None
    dosage: Optional[str] = None
    schedule: Optional[str] = None
    next_control_date: Optional[date] = None


# =====================================================
# РАСЧЁТНЫЕ ПОКАЗАТЕЛИ
# =====================================================

class CalculatedMetric(BaseModel):
    """Расчётные показатели (СКФ, стадия ХБП)"""
    id: int
    appointment_id: int
    creatinine: Optional[float] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    weight_at_appointment: Optional[float] = None
    egfr_ckdepi: Optional[float] = None
    crcl_cockcroft_gault: Optional[float] = None
    ckd_stage: Optional[int] = None
    calculation_date: Optional[datetime] = None


# =====================================================
# ПОЛНЫЕ ДАННЫЕ ПРИЁМА (для карточки пациента)
# =====================================================

class AppointmentFullData(BaseModel):
    """Полные данные приёма (объединяет все таблицы)"""
    # Основное
    id: int
    appointment_date: datetime
    doctor_name: str
    location_name: str
    branch_name: str
    
    # Пациент
    patient_fio: Optional[str] = None
    birth_date: Optional[date] = None
    age_at_appointment: Optional[int] = None
    
    # Опрос
    life_anamnesis: Optional[str] = None
    disease_anamnesis: Optional[str] = None
    complaints: Optional[str] = None
    heredity: Optional[bool] = None
    heredity_description: Optional[str] = None
    comorbidities: Optional[str] = None
    
    # Осмотр
    skin_condition: Optional[str] = None
    edema_location: Optional[str] = None
    systolic_pressure: Optional[int] = None
    diastolic_pressure: Optional[int] = None
    bp_note: Optional[str] = None
    heart_rate: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    
    # Общий анализ крови
    hemoglobin: Optional[float] = None
    erythrocytes: Optional[float] = None
    leukocytes: Optional[float] = None
    platelets: Optional[float] = None
    esr: Optional[float] = None
    mcv: Optional[float] = None
    hematocrit: Optional[float] = None
    
    # Биохимия
    creatinine: Optional[float] = None
    urea: Optional[float] = None
    uric_acid: Optional[float] = None
    glucose: Optional[float] = None
    total_protein: Optional[float] = None
    albumin: Optional[float] = None
    potassium: Optional[float] = None
    calcium: Optional[float] = None
    phosphorus: Optional[float] = None
    ferritin: Optional[float] = None
    ptg: Optional[float] = None
    
    # Анализ мочи
    specific_gravity: Optional[float] = None
    urine_protein: Optional[float] = None
    urine_leukocytes: Optional[int] = None
    urine_erythrocytes: Optional[int] = None
    bacteria: Optional[str] = None
    
    # УЗИ
    left_kidney_size: Optional[str] = None
    right_kidney_size: Optional[str] = None
    left_parenchyma: Optional[float] = None
    right_parenchyma: Optional[float] = None
    ultrasound_desc: Optional[str] = None
    
    # Диагнозы
    main_diagnosis: Optional[str] = None
    complications: Optional[str] = None
    diag_comorbidities: Optional[str] = None
    
    # Назначения
    diet: Optional[str] = None
    medication: Optional[str] = None
    dosage: Optional[str] = None
    schedule: Optional[str] = None
    next_control_date: Optional[date] = None
    
    # Расчётные показатели
    egfr_ckdepi: Optional[float] = None
    crcl_cockcroft_gault: Optional[float] = None
    ckd_stage: Optional[int] = None


# =====================================================
# СПИСОК ПРИЁМОВ НА ГЛАВНОЙ СТРАНИЦЕ
# =====================================================

class AppointmentListItem(BaseModel):
    """Строка списка приёмов на главной странице"""
    appointment_id: int
    patient_id: int
    patient_fio: str
    appointment_date: datetime
    doctor_fio: str
    location_name: str
    branch_name: str
    age: Optional[int] = None


# =====================================================
# ОШИБКИ
# =====================================================

class ErrorResponse(BaseModel):
    """Стандартный ответ с ошибкой"""
    detail: str