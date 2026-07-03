-- ЛЕГЕНДА
-- Файл: 03_seed_full_test_data_clinically_aligned.sql
-- Назначение: заполняет базу твоими тестовыми данными и сразу формирует клинически согласованные расчёты.
-- Что делает: создаёт организацию, филиалы, отделения, врачей, пользователей, пациентов, приёмы, опросы, осмотры, анализы, УЗИ, назначения.
-- После биохимии и альбуминурии файл рассчитывает категории СКФ, ACR, категории A1/A2/A3, прогноз ХБП KDIGO и диагнозы.
-- Когда запускать: после файлов 01, 02 и 03.
-- Версия v3: DBeaver-safe, без явного BEGIN/COMMIT.

-- На случай, если 01b_add_recommendations_to_appointment_diets.sql не был запущен отдельно.
ALTER TABLE appointment_diets
    ADD COLUMN IF NOT EXISTS recommendations TEXT;

-- =====================================================
-- 1. ЮРИДИЧЕСКОЕ ЛИЦО
-- =====================================================
INSERT INTO companies (id, name, legal_address, phone, email) VALUES
(1, 'ООО «КОМПАНИЯ «ФЕСФАРМ»', '121293, г. Москва, ул. Неверовского, д. 10/3, ком. 27', '+7 (499) 142-68-02', 'info@fesfarm.ru');

SELECT setval(pg_get_serial_sequence('companies', 'id'), COALESCE((SELECT MAX(id) FROM companies), 1), true);

-- =====================================================
-- 2. ФИЛИАЛЫ
-- =====================================================
INSERT INTO branches (id, company_id, name, legal_address, phone, email) VALUES
(1, 1, 'ФЕСФАРМ НН', '603065, Нижегородская обл., г. Нижний Новгород, ул. Дьяконова, д. 2/6, литер А', '+7 (831) 282-33-82', 'nn@fesfarm.ru'),
(2, 1, 'ФЕСФАРМ-КОМИ', '167001, Республика Коми, г. Сыктывкар, ул. Коммунистическая, д. 48/2', '+7 (8212) 30-25-61', 'info@fesfarmkomi.ru');

SELECT setval(pg_get_serial_sequence('branches', 'id'), COALESCE((SELECT MAX(id) FROM branches), 1), true);

-- =====================================================
-- 3. МЕСТА ПРИЁМА / ОТДЕЛЕНИЯ
-- =====================================================
INSERT INTO locations (id, branch_id, company_id, name, factual_address, phone, email) VALUES
(1, 1, 1, 'Отделение гемодиализа №1 (Автозаводский р-н)', '603065, г. Нижний Новгород, ул. Дьяконова, д. 2/6, лит А', '+7 (831) 282-44-82', NULL),
(2, 1, 1, 'Отделение гемодиализа №2', '603003, г. Нижний Новгород, ул. Васенко, д. 11, лит А', '+7 (831) 265-52-43', NULL),
(3, 1, 1, 'Отделение гемодиализа в г.Дзержинске', '606030, г. Дзержинск, Окская набережная, д. 5, П4', '+7 (831) 35-09-95', NULL),
(4, 1, 1, 'Отделение гемодиализа №3', '606520, г. Заволжье, ул. Пирогова, д. 26', '+7 (831) 987-90-96', NULL),
(5, 1, 1, 'Отделение гемодиализа №4', '603035, г. Н. Новгород, ул. Черняховского, д. 5', '+7 (831) 957-90-96', NULL),
(6, 2, 1, 'Отделение гемодиализа', '167001, Республика Коми, г. Сыктывкар, ул. Коммунистическая, д. 48/2', '+7 (8212) 30-25-61', NULL);

SELECT setval(pg_get_serial_sequence('locations', 'id'), COALESCE((SELECT MAX(id) FROM locations), 1), true);

-- =====================================================
-- 4. ВРАЧИ
-- =====================================================
INSERT INTO doctors (id, last_name, first_name, patronymic, position, initial_education, retraining_institution, certificate, qualification, phone) VALUES
(1, 'Захарова', 'Марина', 'Валерьевна', 'Врач-нефролог Первой категории',
 'ДВС 0069103 от 29.06.1999, врач',
 'ФГБОУ ВО НижГМА Минздрава России',
 'Уд-ие 080000326588 от 14.12.22г. (144 час)',
 'нефрология', NULL),
(2, 'Казаркин', 'Дмитрий', 'Геннадьевич', 'Врач-нефролог (внешний совместитель)',
 'ИВС № 0386094 от 17.07.2003, врач',
 'ФГБОУ ВО "Приволжский исследовательский медицинский университет" МЗ РФ',
 'сертификат 0152310539290 от 04.12.20г. (144 час), удост. 523101146574 от 04.12.20г.(144 час)',
 'нефрология', NULL),
(3, 'Возова', 'Анна', 'Маркосовна', 'Заведующий отделением - врач-нефролог',
 'ВСА 0299136 23.05.2005, врач. ПП-1 052655 от 20.04.2007, нефрология',
 'ФГБОУ ВО "Приволжский исследовательский медицинский университет" МЗ РФ; ФГАОУ ВО Национальный исследовательский Нижегородский государственный университет им. Н.И. Лобачевского',
 'Удост. 771803897385 от 20.01.25г. (нефрология 144 час) удост. 522413305488 от 16.11.21г.(144 час)',
 'нефрология; организация здравоохранения и общественное здоровье', NULL),
(4, 'Лобанова', 'Надежда', 'Анатольевна', 'Главный врач Филиала',
 'ИВС 0216273 от 24.06.2003, врач; ДКН № 152640 от 15.11.2011 КМН; диплом ПП № 404556 от 21.02.2006, нефрология',
 'ГОУВПО "Нижегородская государственная академия Фед. агентства по здравоохранению и соц. развитию"; ФГБОУ ВО "Приволжский исследовательский медицинский университет" МЗ РФ',
 'Уд.-ие 771802413126 от 16.11.2021 (144 час); Уд. 771803897380 от 19.01.2025 (144 час); Уд. 771803898016 от 06.02.2025 (144 час)',
 'контроль (экспертиза) качества мед.помощи в ОМС; организация здравоохранения и общественное здоровье; нефрология', NULL),
(5, 'Кузнецова', 'Татьяна', 'Евгеньевна', 'и.о. заведующей отделением - врач-нефролог',
 'ВСА 1072626 от 24.06.2011, врач',
 'НижГУ им. Н.И. Лобачевского',
 'Уд - ие 23102100024 от 21.10.23г. (144 час)',
 'нефрология', NULL);

SELECT setval(pg_get_serial_sequence('doctors', 'id'), COALESCE((SELECT MAX(id) FROM doctors), 1), true);

-- =====================================================
-- 5. СВЯЗЬ ВРАЧЕЙ С ОТДЕЛЕНИЯМИ
-- =====================================================
INSERT INTO doctor_locations (doctor_id, location_id) VALUES
(1, 3),
(2, 4),
(3, 1),
(4, 2),
(5, 5);

-- =====================================================
-- 6. ПАЦИЕНТЫ
-- gender: TRUE = мужской, FALSE = женский
-- =====================================================
INSERT INTO patients (id, last_name, first_name, patronymic, birth_date, gender, phone, email) VALUES
(1, 'Иванов', 'Иван', 'Иванович', '1975-03-15', TRUE, '+7 (901) 123-45-67', 'ivanov@mail.ru'),
(2, 'Петрова', 'Мария', 'Петровна', '1982-07-22', FALSE, '+7 (901) 234-56-78', 'petrova@mail.ru'),
(3, 'Сидоров', 'Алексей', 'Сидорович', '1990-11-05', TRUE, '+7 (901) 345-67-89', 'sidorov@mail.ru'),
(4, 'Кузнецова', 'Елена', 'Андреевна', '1978-01-30', FALSE, '+7 (901) 456-78-90', 'kuznetsova@mail.ru'),
(5, 'Морозов', 'Дмитрий', 'Сергеевич', '1965-09-12', TRUE, '+7 (901) 567-89-01', 'morozov@mail.ru'),
(6, 'Волкова', 'Татьяна', 'Николаевна', '1988-12-03', FALSE, '+7 (901) 678-90-12', 'volkova@mail.ru'),
(7, 'Новиков', 'Павел', 'Александрович', '1972-04-25', TRUE, '+7 (901) 789-01-23', 'novikov@mail.ru');

SELECT setval(pg_get_serial_sequence('patients', 'id'), COALESCE((SELECT MAX(id) FROM patients), 1), true);

-- =====================================================
-- 7. ПОЛЬЗОВАТЕЛИ
-- role: admin, doctor, patient
-- Врачебные логины привязаны к врачам по ФИО: Возова = 3, Лобанова = 4.
-- =====================================================
INSERT INTO users (id, login, password_hash, role, doctor_id, patient_id) VALUES
(1, 'admin', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'admin', NULL, NULL),
(2, 'vozova_a', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'doctor', 3, NULL),
(3, 'lobanova_n', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'doctor', 4, NULL),
(4, 'ivanov_i', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 1),
(5, 'petrova_m', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 2),
(6, 'sidorov_a', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 3),
(7, 'kuznetsova_e', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 4),
(8, 'morozov_d', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 5),
(9, 'volkova_t', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 6),
(10, 'novikov_p', '$2b$12$abcdefghijklmnopqrstuvwxyz0123456789', 'patient', NULL, 7);

SELECT setval(pg_get_serial_sequence('users', 'id'), COALESCE((SELECT MAX(id) FROM users), 1), true);

-- =====================================================
-- 8. ПРИЁМЫ
-- =====================================================
INSERT INTO appointments (id, patient_id, doctor_id, location_id, appointment_date) VALUES
(1, 1, 3, 1, '2025-10-15 10:00:00'),
(2, 1, 3, 1, '2026-01-20 11:00:00'),
(3, 1, 3, 1, '2026-04-10 09:30:00'),
(4, 2, 4, 2, '2025-11-05 14:00:00'),
(5, 2, 4, 2, '2026-02-10 15:00:00'),
(6, 3, 1, 3, '2025-09-20 09:00:00'),
(7, 3, 1, 3, '2025-12-15 10:30:00'),
(8, 3, 1, 3, '2026-03-25 08:45:00'),
(9, 4, 2, 4, '2025-08-10 11:00:00'),
(10, 4, 2, 4, '2025-11-20 12:00:00'),
(11, 5, 5, 5, '2025-10-01 13:30:00'),
(12, 5, 5, 5, '2026-01-15 14:00:00'),
(13, 5, 5, 5, '2026-04-05 11:00:00'),
(14, 6, 3, 1, '2025-11-25 15:30:00'),
(15, 6, 3, 1, '2026-02-28 09:00:00'),
(16, 7, 4, 2, '2025-12-10 08:30:00'),
(17, 7, 4, 2, '2026-03-20 10:00:00');

SELECT setval(pg_get_serial_sequence('appointments', 'id'), COALESCE((SELECT MAX(id) FROM appointments), 1), true);

-- =====================================================
-- 9. ОПРОСЫ
-- =====================================================
INSERT INTO surveys (appointment_id, life_anamnesis, disease_anamnesis, complaints, heredity, heredity_description, comorbidities) VALUES
(1, 'Курит 30 лет. Работает на заводе.', 'АГ с 2010, ХП с 2015, ХБП с 2020.', 'Головные боли, слабость, отеки ног.', TRUE, 'У матери ГБ, у отца СД 2', 'ГБ, ХП'),
(2, 'Курит 30 лет. Работает на заводе.', 'АГ с 2010, ХП с 2015, ХБП с 2020.', 'Головные боли усилились, отеки ног, одышка.', TRUE, 'У матери ГБ, у отца СД 2', 'ГБ, ХП'),
(3, 'Курит 30 лет. Работает на заводе.', 'АГ с 2010, ХП с 2015, ХБП с 2020.', 'Сильные головные боли, отеки, слабость.', TRUE, 'У матери ГБ, у отца СД 2', 'ГБ, ХП'),
(4, 'Медсестра, вредных привычек нет.', 'СД 2 с 2015, ДН с 2018.', 'Жажда, сухость во рту, отеки лица.', TRUE, 'У матери СД 2', 'СД 2, ожирение'),
(5, 'Медсестра, вредных привычек нет.', 'СД 2 с 2015, ДН с 2018.', 'Жажда усилилась, отеки ног, слабость.', TRUE, 'У матери СД 2', 'СД 2, ожирение'),
(6, 'Не курит, спортсмен.', 'ХГН с 2010, ХБП с 2015.', 'Повышение АД, пенистая моча, утомляемость.', FALSE, 'Не отягощена', 'ХГН'),
(7, 'Не курит, спортсмен.', 'ХГН с 2010, ХБП с 2015.', 'АД высокое, моча пенистая, слабость.', FALSE, 'Не отягощена', 'ХГН'),
(8, 'Не курит, спортсмен.', 'ХГН с 2010, ХБП с 2015.', 'Сильная слабость, тошнота, снижение аппетита.', FALSE, 'Не отягощена', 'ХГН'),
(9, 'Курит 15 лет, бухгалтер.', 'СД 1 с 1995, ДН с 2005.', 'Снижение зрения, онемение стоп, отеки.', FALSE, 'Не отягощена', 'СД 1, ретинопатия, полинейропатия'),
(10, 'Курит 15 лет, бухгалтер.', 'СД 1 с 1995, ДН с 2005.', 'Зрение ухудшилось, отеки ног, одышка.', FALSE, 'Не отягощена', 'СД 1, ретинопатия, полинейропатия'),
(11, 'Курит 40 лет, химик.', 'ГБ с 1995, ХСН.', 'Одышка в покое, отеки, кашель, перебои.', TRUE, 'У отца ИМ в 55', 'ГБ III, ИБС, ХСН 2б, ХОБЛ'),
(12, 'Курит 40 лет, химик.', 'ГБ с 1995, ХСН.', 'Одышка сильнее, отеки выше колен, слабость.', TRUE, 'У отца ИМ в 55', 'ГБ III, ИБС, ХСН 2б, ХОБЛ'),
(13, 'Курит 40 лет, химик.', 'ГБ с 1995, ХСН.', 'Одышка в покое, отеки до бедер, аритмия.', TRUE, 'У отца ИМ в 55', 'ГБ III, ИБС, ХСН 2б, ХОБЛ'),
(14, 'Не курит, учитель.', 'АИТ с 2010, ГБ с 2018.', 'Головные боли, сердцебиение, раздражительность.', TRUE, 'У матери АИТ', 'АИТ, ГБ'),
(15, 'Не курит, учитель.', 'АИТ с 2010, ГБ с 2018.', 'Головные боли, слабость, бессонница.', TRUE, 'У матери АИТ', 'АИТ, ГБ'),
(16, 'Курит 25 лет, водитель.', 'Подагра с 2010, МКБ с 2015, ХБП с 2020.', 'Боли в суставах, пояснице, отеки ног.', TRUE, 'У отца подагра', 'Подагра, МКБ, ГБ'),
(17, 'Курит 25 лет, водитель.', 'Подагра с 2010, МКБ с 2015, ХБП с 2020.', 'Сильные боли в суставах, пояснице, отеки.', TRUE, 'У отца подагра', 'Подагра, МКБ, ГБ');

-- =====================================================
-- 10. ОСМОТРЫ
-- =====================================================
INSERT INTO examinations (appointment_id, skin_condition, edema_location, systolic_pressure, diastolic_pressure, bp_note, heart_rate, height, weight) VALUES
(1, 'Бледноватые', 'Голени, стопы', 145, 90, 'лежа', 78, 175, 85),
(2, 'Бледноватые', 'Голени, стопы', 150, 95, 'лежа', 80, 175, 84),
(3, 'Бледные', 'Голени, стопы, лицо', 155, 95, 'лежа', 82, 175, 83),
(4, 'Обычной окраски', 'Лицо, голени', 135, 85, NULL, 72, 165, 78),
(5, 'Обычной окраски', 'Лицо, голени', 140, 85, NULL, 75, 165, 77),
(6, 'Чистые', 'Нет', 130, 80, 'сидя', 70, 180, 75),
(7, 'Чистые', 'Нет', 135, 85, 'сидя', 72, 180, 74),
(8, 'Бледноватые', 'Голени', 140, 85, 'сидя', 75, 180, 73),
(9, 'Бледные, сухие', 'Голени', 140, 85, NULL, 80, 162, 70),
(10, 'Бледные, сухие', 'Голени, стопы', 145, 85, NULL, 82, 162, 69),
(11, 'Цианотичные', 'Голени, стопы, крестец', 150, 90, 'лежа', 90, 170, 82),
(12, 'Цианотичные', 'Голени, стопы, крестец, поясница', 155, 90, 'лежа', 92, 170, 81),
(13, 'Цианотичные, мраморный', 'Голени, стопы, крестец, поясница', 160, 95, 'лежа', 95, 170, 80),
(14, 'Обычной окраски', 'Нет', 125, 80, NULL, 75, 168, 65),
(15, 'Обычной окраски', 'Нет', 130, 80, NULL, 78, 168, 65),
(16, 'Чистые', 'Голени', 140, 85, NULL, 72, 172, 88),
(17, 'Чистые', 'Голени, стопы', 145, 85, NULL, 75, 172, 87);

-- =====================================================
-- 11. ОАК
-- Даты исследования вставляются сразу, без последующего UPDATE.
-- =====================================================
WITH src(appointment_id, hemoglobin, erythrocytes, leukocytes, platelets, esr, mcv, hematocrit) AS (
    VALUES
    (1, 120, 3.8, 6.5, 220, 25, 85, 38),
    (2, 118, 3.7, 7.0, 215, 28, 84, 37),
    (3, 115, 3.6, 7.5, 210, 30, 83, 36),
    (4, 115, 3.6, 7.2, 210, 30, 82, 36),
    (5, 112, 3.5, 7.8, 205, 33, 81, 35),
    (6, 135, 4.2, 5.8, 250, 15, 88, 42),
    (7, 132, 4.1, 6.2, 245, 18, 87, 41),
    (8, 128, 4.0, 6.5, 240, 20, 86, 40),
    (9, 110, 3.5, 8.0, 200, 35, 80, 35),
    (10, 105, 3.3, 8.5, 190, 40, 78, 33),
    (11, 100, 3.2, 9.0, 180, 45, 78, 32),
    (12, 95, 3.0, 9.5, 170, 50, 76, 30),
    (13, 90, 2.9, 10.0, 160, 55, 75, 28),
    (14, 128, 4.0, 6.0, 240, 18, 86, 40),
    (15, 125, 3.9, 6.5, 235, 20, 85, 39),
    (16, 118, 3.7, 7.5, 215, 28, 83, 37),
    (17, 115, 3.6, 8.0, 210, 32, 82, 36)
)
INSERT INTO cbc_results (appointment_id, investigation_date, hemoglobin, erythrocytes, leukocytes, platelets, esr, mcv, hematocrit)
SELECT
    src.appointment_id,
    a.appointment_date::date - CASE WHEN src.appointment_id IN (2, 4, 6, 8, 10) THEN 1 ELSE 0 END,
    src.hemoglobin,
    src.erythrocytes,
    src.leukocytes,
    src.platelets,
    src.esr,
    src.mcv,
    src.hematocrit
FROM src
JOIN appointments a ON a.id = src.appointment_id;

-- =====================================================
-- 12. БИОХИМИЯ
-- Гиперкалиемия у Морозова и Новикова уже внесена в итоговые значения.
-- =====================================================
WITH src(appointment_id, creatinine, urea, uric_acid, glucose, total_protein, albumin, potassium, calcium, phosphorus, ferritin, ptg) AS (
    VALUES
    (1, 95, 6.5, 380, 5.2, 70, 42, 4.2, 2.3, 1.2, 150, 55),
    (2, 105, 7.2, 390, 5.3, 69, 41, 4.3, 2.3, 1.2, 145, 58),
    (3, 115, 8.0, 400, 5.4, 68, 40, 4.4, 2.2, 1.3, 140, 60),
    (4, 110, 7.8, 400, 7.8, 68, 40, 4.5, 2.2, 1.3, 140, 60),
    (5, 125, 8.5, 410, 8.0, 66, 39, 4.6, 2.1, 1.3, 135, 63),
    (6, 130, 9.0, 420, 5.0, 65, 38, 4.8, 2.1, 1.4, 130, 70),
    (7, 140, 9.8, 430, 5.1, 63, 37, 4.9, 2.0, 1.4, 125, 73),
    (8, 155, 10.5, 440, 5.2, 61, 36, 5.0, 2.0, 1.5, 120, 76),
    (9, 85, 5.5, 350, 5.5, 72, 44, 4.0, 2.4, 1.1, 160, 50),
    (10, 95, 6.0, 360, 5.6, 70, 43, 4.1, 2.3, 1.1, 155, 53),
    (11, 145, 10.5, 480, 5.8, 62, 35, 5.0, 2.0, 1.5, 120, 80),
    (12, 160, 11.5, 490, 6.0, 60, 34, 5.1, 1.9, 1.6, 115, 85),
    (13, 175, 12.5, 500, 6.2, 58, 33, 6.2, 1.9, 1.6, 110, 90),
    (14, 75, 4.5, 320, 4.8, 74, 45, 4.1, 2.4, 1.1, 170, 45),
    (15, 80, 5.0, 330, 4.9, 73, 44, 4.2, 2.4, 1.1, 165, 47),
    (16, 160, 11.2, 550, 5.2, 60, 33, 4.9, 2.1, 1.5, 110, 85),
    (17, 175, 12.0, 560, 5.3, 58, 32, 5.8, 2.0, 1.5, 105, 88)
)
INSERT INTO biochemistry_results (appointment_id, investigation_date, creatinine, urea, uric_acid, glucose, total_protein, albumin, potassium, calcium, phosphorus, ferritin, ptg)
SELECT
    src.appointment_id,
    a.appointment_date::date - CASE
        WHEN src.appointment_id IN (1, 3, 5, 7, 9) THEN 1
        WHEN src.appointment_id IN (2, 4, 6, 8, 10) THEN 2
        ELSE 0
    END,
    src.creatinine,
    src.urea,
    src.uric_acid,
    src.glucose,
    src.total_protein,
    src.albumin,
    src.potassium,
    src.calcium,
    src.phosphorus,
    src.ferritin,
    src.ptg
FROM src
JOIN appointments a ON a.id = src.appointment_id;

-- =====================================================
-- 13. ОАМ
-- =====================================================
WITH src(appointment_id, specific_gravity, protein, leukocytes, erythrocytes, bacteria) AS (
    VALUES
    (1, 1.015, 0.15, 2, 1, 'отсутствуют'),
    (2, 1.014, 0.20, 3, 2, 'отсутствуют'),
    (3, 1.013, 0.25, 4, 3, 'единичные'),
    (4, 1.012, 0.20, 3, 2, 'отсутствуют'),
    (5, 1.011, 0.30, 4, 3, 'единичные'),
    (6, 1.018, 0.30, 5, 3, 'единичные'),
    (7, 1.017, 0.35, 6, 4, 'единичные'),
    (8, 1.016, 0.40, 7, 5, '++'),
    (9, 1.010, 0.10, 1, 0, 'отсутствуют'),
    (10, 1.009, 0.15, 2, 1, 'отсутствуют'),
    (11, 1.008, 0.40, 8, 5, '++'),
    (12, 1.007, 0.50, 10, 7, '+++'),
    (13, 1.006, 0.60, 12, 10, '+++'),
    (14, 1.016, 0.12, 2, 1, 'отсутствуют'),
    (15, 1.015, 0.15, 3, 2, 'отсутствуют'),
    (16, 1.014, 0.25, 4, 2, 'единичные'),
    (17, 1.013, 0.30, 5, 3, 'единичные')
)
INSERT INTO urinalysis_results (appointment_id, investigation_date, specific_gravity, protein, leukocytes, erythrocytes, bacteria)
SELECT
    src.appointment_id,
    a.appointment_date::date - CASE WHEN src.appointment_id IN (1, 3, 5, 7, 9) THEN 2 ELSE 0 END,
    src.specific_gravity,
    src.protein,
    src.leukocytes,
    src.erythrocytes,
    src.bacteria
FROM src
JOIN appointments a ON a.id = src.appointment_id;

-- =====================================================
-- 14. УЗИ ПОЧЕК
-- =====================================================
WITH src(appointment_id, left_kidney_size, right_kidney_size, left_parenchyma, right_parenchyma, description) AS (
    VALUES
    (1, '110x50', '108x48', 15, 14, 'Контуры ровные, структура однородная.'),
    (2, '108x49', '106x47', 14, 13, 'Небольшое снижение эхогенности.'),
    (3, '105x48', '103x46', 13, 12, 'Контуры слегка неровные, эхогенность повышена.'),
    (4, '105x48', '102x46', 13, 12, 'Небольшое снижение эхогенности коркового слоя.'),
    (5, '103x47', '100x45', 12, 11, 'Эхогенность повышена, контуры неровные.'),
    (6, '100x45', '98x44', 11, 10, 'Контуры неровные, структура неоднородная, кисты.'),
    (7, '98x44', '96x43', 10, 9, 'Размеры уменьшены, паренхима истончена.'),
    (8, '95x42', '93x41', 9, 8, 'Атрофия коркового слоя.'),
    (9, '112x52', '110x50', 16, 15, 'Без патологических изменений.'),
    (10, '110x51', '108x49', 15, 14, 'Без патологических изменений.'),
    (11, '95x42', '92x40', 9, 8, 'Атрофия коркового слоя, размеры уменьшены.'),
    (12, '93x41', '90x39', 8, 7, 'Выраженная атрофия.'),
    (13, '90x40', '88x38', 7, 6, 'Терминальные изменения.'),
    (14, '108x50', '105x48', 14, 13, 'Контуры ровные, эхогенность повышена.'),
    (15, '106x49', '103x47', 13, 12, 'Эхогенность повышена.'),
    (16, '100x46', '98x45', 10, 9, 'Множественные конкременты 3-4 мм в лоханках.'),
    (17, '98x45', '95x44', 9, 8, 'Множественные конкременты, гидронефроз 1 ст.')
)
INSERT INTO ultrasound_results (appointment_id, investigation_date, left_kidney_size, right_kidney_size, left_parenchyma, right_parenchyma, description)
SELECT
    src.appointment_id,
    a.appointment_date::date,
    src.left_kidney_size,
    src.right_kidney_size,
    src.left_parenchyma,
    src.right_parenchyma,
    src.description
FROM src
JOIN appointments a ON a.id = src.appointment_id;

-- =====================================================
-- 15. РАСЧЁТНЫЕ ПОКАЗАТЕЛИ
-- eGFR/CrCl сохранены из твоего тестового файла.
-- ckd_stage рассчитывается заново по eGFR и записывается в формате G-категорий.
-- =====================================================
WITH src(appointment_id, creatinine, age, gender, weight_at_appointment, egfr_ckdepi, crcl_cockcroft_gault) AS (
    VALUES
    (1, 95, 50, TRUE, 85, 72, 78),
    (2, 105, 50, TRUE, 84, 65, 70),
    (3, 115, 50, TRUE, 83, 58, 63),
    (4, 110, 43, FALSE, 78, 58, 65),
    (5, 125, 43, FALSE, 77, 50, 56),
    (6, 130, 34, TRUE, 75, 45, 52),
    (7, 140, 34, TRUE, 74, 40, 47),
    (8, 155, 34, TRUE, 73, 35, 41),
    (9, 85, 47, FALSE, 70, 85, 88),
    (10, 95, 47, FALSE, 69, 78, 80),
    (11, 145, 58, TRUE, 82, 38, 42),
    (12, 160, 58, TRUE, 81, 33, 37),
    (13, 175, 58, TRUE, 80, 28, 32),
    (14, 75, 36, FALSE, 65, 95, 100),
    (15, 80, 36, FALSE, 65, 90, 95),
    (16, 160, 52, TRUE, 88, 32, 38),
    (17, 175, 52, TRUE, 87, 28, 34)
), calculated AS (
    SELECT
        src.*,
        b.investigation_date,
        CASE
            WHEN src.egfr_ckdepi >= 90 THEN 'С1'
            WHEN src.egfr_ckdepi >= 60 THEN 'С2'
            WHEN src.egfr_ckdepi >= 45 THEN 'С3а'
            WHEN src.egfr_ckdepi >= 30 THEN 'С3б'
            WHEN src.egfr_ckdepi >= 15 THEN 'С4'
            ELSE 'С5'
        END AS ckd_stage
    FROM src
    LEFT JOIN biochemistry_results b ON b.appointment_id = src.appointment_id
)
INSERT INTO calculated_metrics (
    appointment_id,
    investigation_date,
    creatinine,
    age,
    gender,
    weight_at_appointment,
    egfr_ckdepi,
    crcl_cockcroft_gault,
    ckd_stage,
    calculation_date
)
SELECT
    appointment_id,
    investigation_date,
    creatinine,
    age,
    gender,
    weight_at_appointment,
    egfr_ckdepi,
    crcl_cockcroft_gault,
    ckd_stage,
    CURRENT_TIMESTAMP
FROM calculated;

-- =====================================================
-- 16. АЛЬБУМИНУРИЯ
-- Исходный основной файл не содержал готовых INSERT в albuminuria_results.
-- Поэтому здесь сохранён расчётный подход из твоего отдельного файла:
--  ACR задаётся как тестовое клиническое значение,
--  urine_albumin = ACR × urine_creatinine,
--  категория A1/A2/A3 считается автоматически.
-- =====================================================
WITH generated AS (
    SELECT
        a.id AS appointment_id,
        a.appointment_date::date AS investigation_date,
        (
            CASE a.id % 8
                WHEN 0 THEN 3.8
                WHEN 1 THEN 4.6
                WHEN 2 THEN 5.5
                WHEN 3 THEN 6.7
                WHEN 4 THEN 8.2
                WHEN 5 THEN 9.4
                WHEN 6 THEN 11.0
                ELSE 13.5
            END
        )::numeric AS urine_creatinine,
        (
            CASE
                WHEN a.id % 20 IN (0, 1, 2, 3, 4, 5, 6) THEN
                    CASE a.id % 7
                        WHEN 0 THEN 0.6
                        WHEN 1 THEN 0.9
                        WHEN 2 THEN 1.2
                        WHEN 3 THEN 1.6
                        WHEN 4 THEN 2.0
                        WHEN 5 THEN 2.4
                        ELSE 2.8
                    END
                WHEN a.id % 20 IN (7, 8, 9, 10, 11, 12, 13, 14) THEN
                    CASE a.id % 8
                        WHEN 0 THEN 3.5
                        WHEN 1 THEN 4.8
                        WHEN 2 THEN 6.2
                        WHEN 3 THEN 8.5
                        WHEN 4 THEN 11.0
                        WHEN 5 THEN 15.0
                        WHEN 6 THEN 21.0
                        ELSE 28.0
                    END
                ELSE
                    CASE a.id % 5
                        WHEN 0 THEN 35.0
                        WHEN 1 THEN 48.0
                        WHEN 2 THEN 75.0
                        WHEN 3 THEN 120.0
                        ELSE 180.0
                    END
            END
        )::numeric AS acr
    FROM appointments a
)
INSERT INTO albuminuria_results (
    appointment_id,
    investigation_date,
    urine_albumin,
    urine_albumin_unit,
    urine_creatinine,
    urine_creatinine_unit,
    albumin_creatinine_ratio,
    albuminuria_category
)
SELECT
    appointment_id,
    investigation_date,
    ROUND((acr * urine_creatinine)::numeric, 2) AS urine_albumin,
    'mg_l' AS urine_albumin_unit,
    urine_creatinine,
    'mmol_l' AS urine_creatinine_unit,
    ROUND(acr::numeric, 2) AS albumin_creatinine_ratio,
    CASE
        WHEN acr < 3 THEN 'A1'
        WHEN acr <= 30 THEN 'A2'
        ELSE 'A3'
    END AS albuminuria_category
FROM generated;

-- =====================================================
-- 17. ПРОГНОЗ ХБП ПО KDIGO
-- =====================================================
WITH source_data AS (
    SELECT
        a.id AS appointment_id,
        a.appointment_date::date AS assessment_date,
        cm.ckd_stage AS gfr_category,
        ar.albuminuria_category AS albuminuria_category
    FROM appointments a
    JOIN calculated_metrics cm ON cm.appointment_id = a.id
    JOIN albuminuria_results ar ON ar.appointment_id = a.id
), calculated AS (
    SELECT
        appointment_id,
        assessment_date,
        gfr_category,
        albuminuria_category,
        gfr_category || albuminuria_category AS combined_category,
        CASE
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A1' THEN 'low'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A2' THEN 'moderate'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A3' THEN 'high'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A1' THEN 'moderate'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A2' THEN 'high'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A3' THEN 'very_high'
            WHEN gfr_category = 'С3б' AND albuminuria_category = 'A1' THEN 'high'
            WHEN gfr_category = 'С3б' AND albuminuria_category IN ('A2', 'A3') THEN 'very_high'
            WHEN gfr_category IN ('С4', 'С5') THEN 'very_high'
        END AS prognosis_level,
        CASE
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A1' THEN 'низкий'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A2' THEN 'умеренно повышенный'
            WHEN gfr_category IN ('С1', 'С2') AND albuminuria_category = 'A3' THEN 'высокий'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A1' THEN 'умеренно повышенный'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A2' THEN 'высокий'
            WHEN gfr_category = 'С3а' AND albuminuria_category = 'A3' THEN 'очень высокий'
            WHEN gfr_category = 'С3б' AND albuminuria_category = 'A1' THEN 'высокий'
            WHEN gfr_category = 'С3б' AND albuminuria_category IN ('A2', 'A3') THEN 'очень высокий'
            WHEN gfr_category IN ('С4', 'С5') THEN 'очень высокий'
        END AS prognosis_text
    FROM source_data
)
INSERT INTO ckd_prognosis_results (
    appointment_id,
    assessment_date,
    gfr_category,
    albuminuria_category,
    combined_category,
    prognosis_level,
    prognosis_text
)
SELECT
    appointment_id,
    assessment_date,
    gfr_category,
    albuminuria_category,
    combined_category,
    prognosis_level,
    prognosis_text
FROM calculated
WHERE prognosis_level IS NOT NULL;

-- =====================================================
-- 18. ДИАГНОЗЫ
-- Диагнозы заполняются после расчёта G/A/KDIGO, чтобы текст не расходился с категориями.
-- Complications и comorbidities сохранены из твоего исходного файла.
-- =====================================================
WITH diagnosis_source(appointment_id, diagnosis_basis, complications, comorbidities) AS (
    VALUES
    (1, 'Хроническая болезнь почек на фоне артериальной гипертензии и хронического пиелонефрита', 'Анемия легкой степени', 'ГБ, ХП'),
    (2, 'Хроническая болезнь почек на фоне артериальной гипертензии и хронического пиелонефрита', 'Анемия легкой степени', 'ГБ, ХП'),
    (3, 'Хроническая болезнь почек на фоне артериальной гипертензии и хронического пиелонефрита', 'Анемия легкой степени', 'ГБ, ХП'),
    (4, 'Диабетическая нефропатия', 'Анемия легкой степени', 'СД 2, ожирение'),
    (5, 'Диабетическая нефропатия', 'Анемия средней степени', 'СД 2, ожирение'),
    (6, 'Хронический гломерулонефрит', 'Анемия легкой степени', 'ХГН'),
    (7, 'Хронический гломерулонефрит', 'Анемия средней степени', 'ХГН'),
    (8, 'Хронический гломерулонефрит', 'Анемия средней степени, гиперкалиемия', 'ХГН'),
    (9, 'Диабетическая нефропатия', 'Нет', 'СД 1'),
    (10, 'Диабетическая нефропатия', 'Нет', 'СД 1'),
    (11, 'Хроническая болезнь почек на фоне гипертонической болезни, ИБС и ХСН', 'Анемия средней степени, гиперкалиемия', 'ГБ III, ИБС, ХСН, ХОБЛ'),
    (12, 'Хроническая болезнь почек на фоне гипертонической болезни, ИБС и ХСН', 'Анемия тяжелой степени, гиперкалиемия', 'ГБ III, ИБС, ХСН, ХОБЛ'),
    (13, 'Хроническая болезнь почек на фоне гипертонической болезни, ИБС и ХСН', 'Терминальная ПН, анемия тяжелой степени', 'ГБ III, ИБС, ХСН, ХОБЛ'),
    (14, 'Хроническая болезнь почек', 'Нет', 'АИТ, ГБ'),
    (15, 'Хроническая болезнь почек', 'Нет', 'АИТ, ГБ'),
    (16, 'Подагрическая нефропатия, МКБ', 'МКБ, анемия средней степени', 'Подагра, ГБ'),
    (17, 'Подагрическая нефропатия, МКБ', 'МКБ, анемия средней степени', 'Подагра, ГБ')
)
INSERT INTO diagnoses (appointment_id, main_diagnosis, complications, comorbidities)
SELECT
    ds.appointment_id,
    ds.diagnosis_basis
        || ', ХБП ' || cpr.combined_category
        || ' (категория СКФ ' || cpr.gfr_category
        || ', категория альбуминурии ' || cpr.albuminuria_category
        || '), прогноз ХБП: ' || cpr.prognosis_text AS main_diagnosis,
    ds.complications,
    ds.comorbidities
FROM diagnosis_source ds
JOIN ckd_prognosis_results cpr ON cpr.appointment_id = ds.appointment_id;

-- =====================================================
-- 19. ДИЕТА, ДАТА КОНТРОЛЯ И ОБЩИЕ РЕКОМЕНДАЦИИ
-- Диета и дата контроля перенесены из исходного блока prescriptions.
-- recommendations формируются с учётом KDIGO-прогноза и гиперкалиемии.
-- =====================================================
WITH diet_source(appointment_id, diet, next_control_date) AS (
    VALUES
    (1, 'Стол №7 с ограничением соли до 5 г/сут', DATE '2025-10-15'),
    (2, 'Стол №7 с ограничением соли до 5 г/сут', DATE '2026-01-20'),
    (3, 'Стол №7 с ограничением соли до 5 г/сут', DATE '2026-04-10'),
    (4, 'Стол №9 с ограничением углеводов', DATE '2025-11-20'),
    (5, 'Стол №9 с ограничением углеводов', DATE '2026-02-10'),
    (6, 'Стол №7 с ограничением белка до 0,6 г/кг/сут', DATE '2025-12-15'),
    (7, 'Стол №7 с ограничением белка до 0,6 г/кг/сут', DATE '2026-03-25'),
    (8, 'Стол №7 с ограничением белка до 0,6 г/кг/сут', DATE '2026-07-01'),
    (9, 'Стол №9 с ограничением углеводов', DATE '2025-11-20'),
    (10, 'Стол №9 с ограничением углеводов', DATE '2026-02-28'),
    (11, 'Стол №7 с ограничением белка до 0,6 г/кг/сут, жидкости до 1000 мл/сут', DATE '2025-12-01'),
    (12, 'Стол №7 с ограничением белка до 0,6 г/кг/сут, жидкости до 1000 мл/сут', DATE '2026-01-15'),
    (13, 'Стол №7 с ограничением белка до 0,6 г/кг/сут, жидкости до 1000 мл/сут', DATE '2026-04-05'),
    (14, 'Стол №10 с ограничением соли до 5 г/сут', DATE '2025-10-20'),
    (15, 'Стол №10 с ограничением соли до 5 г/сут', DATE '2026-02-28'),
    (16, 'Стол №6 с ограничением пуринов', DATE '2025-11-05'),
    (17, 'Стол №6 с ограничением пуринов', DATE '2026-03-20')
)
INSERT INTO appointment_diets (appointment_id, diet, next_control_date, recommendations)
SELECT
    ds.appointment_id,
    ds.diet,
    ds.next_control_date,
    'Категория ХБП: ' || cpr.combined_category || '. Прогноз по KDIGO: ' || cpr.prognosis_text || '. '
    || 'Контроль АД, креатинина, мочевины, калия, ОАК, ОАМ и альбумин/креатинин мочи к следующему визиту.'
    || CASE
        WHEN cpr.prognosis_level = 'very_high' THEN ' Учитывая очень высокий риск — динамическое наблюдение нефролога, контроль осложнений ХБП и оценка показаний к подготовке к заместительной почечной терапии.'
        WHEN cpr.prognosis_level = 'high' THEN ' Учитывая высокий риск — усилить контроль факторов прогрессирования ХБП.'
        WHEN cpr.prognosis_level = 'moderate' THEN ' Учитывая умеренно повышенный риск — плановый контроль функции почек и альбуминурии.'
        ELSE ' Учитывая низкий риск — продолжить плановое наблюдение.'
    END
    || CASE
        WHEN EXISTS (
            SELECT 1
            FROM biochemistry_results b
            WHERE b.appointment_id = ds.appointment_id
              AND b.potassium >= 5.5
        ) THEN ' В связи с гиперкалиемией — внеплановый контроль калия и коррекция калийсберегающих факторов по решению врача.'
        ELSE ''
    END AS recommendations
FROM diet_source ds
JOIN ckd_prognosis_results cpr ON cpr.appointment_id = ds.appointment_id;

-- =====================================================
-- 20. ЛЕКАРСТВЕННЫЕ НАЗНАЧЕНИЯ
-- Лекарства, дозировки и схемы перенесены из исходного файла.
-- Диета/дата контроля вынесены в appointment_diets, как предусмотрено финальной структурой БД.
-- =====================================================
INSERT INTO prescriptions (appointment_id, medication, dosage, schedule) VALUES
(1, 'Эналаприл', '10 мг', '1 раз в день утром'),
(1, 'Фуросемид', '40 мг', '2 раза в день'),
(1, 'Ацетилсалициловая кислота', '100 мг', '1 раз в день после еды'),
(2, 'Эналаприл', '10 мг', '1 раз в день утром'),
(2, 'Фуросемид', '40 мг', '2 раза в день'),
(2, 'Ацетилсалициловая кислота', '100 мг', '1 раз в день после еды'),
(3, 'Эналаприл', '10 мг', '1 раз в день утром'),
(3, 'Фуросемид', '40 мг', '2 раза в день'),
(3, 'Ацетилсалициловая кислота', '100 мг', '1 раз в день после еды'),
(4, 'Метформин', '1000 мг', '2 раза в день после еды'),
(4, 'Лизиноприл', '10 мг', '1 раз в день утром'),
(5, 'Метформин', '1000 мг', '2 раза в день после еды'),
(5, 'Лизиноприл', '10 мг', '1 раз в день утром'),
(6, 'Преднизолон', '20 мг', '1 раз в день утром'),
(6, 'Индапамид', '2,5 мг', '1 раз в день утром'),
(7, 'Преднизолон', '20 мг', '1 раз в день утром'),
(7, 'Индапамид', '2,5 мг', '1 раз в день утром'),
(8, 'Преднизолон', '15 мг', '1 раз в день утром'),
(8, 'Индапамид', '2,5 мг', '1 раз в день утром'),
(9, 'Инсулин Лантус', '12 ЕД', 'на ночь'),
(9, 'Инсулин Новорапид', '8 ЕД', 'перед едой 3 раза в день'),
(9, 'Лизиноприл', '10 мг', '1 раз в день утром'),
(10, 'Инсулин Лантус', '12 ЕД', 'на ночь'),
(10, 'Инсулин Новорапид', '8 ЕД', 'перед едой 3 раза в день'),
(10, 'Лизиноприл', '10 мг', '1 раз в день утром'),
(11, 'Торасемид', '20 мг', '1 раз в день утром'),
(11, 'Карведилол', '25 мг', '2 раза в день'),
(11, 'Аспирин', '100 мг', '1 раз в день'),
(12, 'Торасемид', '30 мг', '1 раз в день утром'),
(12, 'Карведилол', '25 мг', '2 раза в день'),
(12, 'Аспирин', '100 мг', '1 раз в день'),
(13, 'Торасемид', '40 мг', '1 раз в день утром'),
(13, 'Карведилол', '25 мг', '2 раза в день'),
(13, 'Аспирин', '100 мг', '1 раз в день'),
(14, 'Эналаприл', '5 мг', '1 раз в день утром'),
(14, 'Бисопролол', '5 мг', '1 раз в день'),
(15, 'Эналаприл', '5 мг', '1 раз в день утром'),
(15, 'Бисопролол', '5 мг', '1 раз в день'),
(16, 'Аллопуринол', '300 мг', '1 раз в день'),
(16, 'Эналаприл', '10 мг', '1 раз в день утром'),
(16, 'Фуросемид', '40 мг', '2 раза в день'),
(17, 'Аллопуринол', '300 мг', '1 раз в день'),
(17, 'Эналаприл', '10 мг', '1 раз в день утром'),
(17, 'Фуросемид', '40 мг', '2 раза в день');

-- =====================================================
-- 21. КОНТРОЛЬНЫЕ ВЫБОРКИ ПОСЛЕ ЗАПОЛНЕНИЯ
-- Эти SELECT не меняют данные, а показывают, что заполнение прошло корректно.
-- =====================================================

-- Количество строк в ключевых таблицах.
SELECT 'companies' AS table_name, COUNT(*) AS row_count FROM companies
UNION ALL SELECT 'branches', COUNT(*) FROM branches
UNION ALL SELECT 'locations', COUNT(*) FROM locations
UNION ALL SELECT 'doctors', COUNT(*) FROM doctors
UNION ALL SELECT 'patients', COUNT(*) FROM patients
UNION ALL SELECT 'appointments', COUNT(*) FROM appointments
UNION ALL SELECT 'biochemistry_results', COUNT(*) FROM biochemistry_results
UNION ALL SELECT 'albuminuria_results', COUNT(*) FROM albuminuria_results
UNION ALL SELECT 'calculated_metrics', COUNT(*) FROM calculated_metrics
UNION ALL SELECT 'ckd_prognosis_results', COUNT(*) FROM ckd_prognosis_results
UNION ALL SELECT 'diagnoses', COUNT(*) FROM diagnoses
UNION ALL SELECT 'appointment_diets', COUNT(*) FROM appointment_diets
UNION ALL SELECT 'prescriptions', COUNT(*) FROM prescriptions
ORDER BY table_name;

-- Проверка клинической связки СКФ + альбуминурия + прогноз.
SELECT
    p.last_name || ' ' || p.first_name || ' ' || COALESCE(p.patronymic, '') AS patient_fio,
    a.id AS appointment_id,
    a.appointment_date::date AS appointment_date,
    cm.egfr_ckdepi,
    cm.ckd_stage,
    ar.albumin_creatinine_ratio AS acr_mg_mmol,
    ar.albuminuria_category,
    cpr.combined_category,
    cpr.prognosis_text,
    d.main_diagnosis
FROM appointments a
JOIN patients p ON p.id = a.patient_id
LEFT JOIN calculated_metrics cm ON cm.appointment_id = a.id
LEFT JOIN albuminuria_results ar ON ar.appointment_id = a.id
LEFT JOIN ckd_prognosis_results cpr ON cpr.appointment_id = a.id
LEFT JOIN diagnoses d ON d.appointment_id = a.id
ORDER BY p.id, a.appointment_date;
