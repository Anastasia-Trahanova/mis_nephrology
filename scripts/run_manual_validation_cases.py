from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.medical_algorithms.common import calculate_age
from app.medical_algorithms.egfr import calculate_ckd_epi_2021
from app.medical_algorithms.cockcroft_gault import calculate_cockcroft_gault
from app.medical_algorithms.ckd_stage import get_ckd_stage
from app.medical_algorithms.albuminuria import calculate_albuminuria_metrics
from app.medical_algorithms.prognosis import calculate_ckd_prognosis


PATIENTS = [
    {
        "name": "Пациент 1 — женщина С1/A1",
        "gender": "Женский",
        "birth_date": "1991-07-15",
        "appointment_date": "2026-01-15",
        "weight_kg": 65,
        "serum_creatinine_umol_l": 62,
        "urine_albumin": 10,
        "urine_albumin_unit": "mg_l",
        "urine_creatinine": 5,
        "urine_creatinine_unit": "mmol_l",
    },
    {
        "name": "Пациент 2 — мужчина С2/A2",
        "gender": "Мужской",
        "birth_date": "1976-03-01",
        "appointment_date": "2026-03-01",
        "weight_kg": 85,
        "serum_creatinine_umol_l": 97.24,
        "urine_albumin": 30,
        "urine_albumin_unit": "mg_l",
        "urine_creatinine": 10,
        "urine_creatinine_unit": "mmol_l",
    },
    {
        "name": "Пациент 3 — женщина С3а/A3",
        "gender": "Женский",
        "birth_date": "1956-10-10",
        "appointment_date": "2026-10-10",
        "weight_kg": 70,
        "serum_creatinine_umol_l": 106.08,
        "urine_albumin": 0.31,
        "urine_albumin_unit": "g_l",
        "urine_creatinine": 10000,
        "urine_creatinine_unit": "umol_l",
    },
    {
        "name": "Пациент 4 — мужчина С3б/A2",
        "gender": "Мужской",
        "birth_date": "1946-05-20",
        "appointment_date": "2026-05-20",
        "weight_kg": 75,
        "serum_creatinine_umol_l": 176.8,
        "urine_albumin": 300,
        "urine_albumin_unit": "mg_l",
        "urine_creatinine": 10000,
        "urine_creatinine_unit": "umol_l",
    },
    {
        "name": "Пациент 5 — защитный сценарий ошибки единиц",
        "gender": "Женский",
        "birth_date": "1986-01-01",
        "appointment_date": "2026-01-01",
        "weight_kg": 60,
        "serum_creatinine_umol_l": 1.2,
        "urine_albumin": 0.03,
        "urine_albumin_unit": "g_l",
        "urine_creatinine": 10,
        "urine_creatinine_unit": "mmol_l",
    },
]


for patient in PATIENTS:
    age = calculate_age(patient["birth_date"], patient["appointment_date"])

    egfr = calculate_ckd_epi_2021(
        creatinine_umol_l=patient["serum_creatinine_umol_l"],
        age=age,
        gender=patient["gender"],
    )

    crcl = calculate_cockcroft_gault(
        creatinine_umol_l=patient["serum_creatinine_umol_l"],
        age=age,
        weight_kg=patient["weight_kg"],
        gender=patient["gender"],
    )

    ckd_stage = get_ckd_stage(egfr)

    albuminuria = calculate_albuminuria_metrics(
        urine_albumin=patient["urine_albumin"],
        urine_albumin_unit=patient["urine_albumin_unit"],
        urine_creatinine=patient["urine_creatinine"],
        urine_creatinine_unit=patient["urine_creatinine_unit"],
    )

    prognosis = calculate_ckd_prognosis(
        ckd_stage,
        albuminuria["albuminuria_category"],
    )

    print("=" * 80)
    print(patient["name"])
    print("-" * 80)
    print(f"Возраст: {age}")
    print(f"eGFR CKD-EPI 2021: {egfr}")
    print(f"Cockcroft–Gault: {crcl}")
    print(f"Стадия ХБП: {ckd_stage}")
    print(f"ACR мг/ммоль: {albuminuria['albumin_creatinine_ratio']}")
    print(f"ACR мг/г: {albuminuria['albumin_creatinine_ratio_mg_g']}")
    print(f"Категория альбуминурии: {albuminuria['albuminuria_category']}")
    print(f"KDIGO-риск: {prognosis['level']} / {prognosis['text']}")
