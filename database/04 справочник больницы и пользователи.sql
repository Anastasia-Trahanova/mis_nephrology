SET client_encoding = 'UTF8';

-- =====================================================
-- 1. ЮРИДИЧЕСКОЕ ЛИЦО
-- =====================================================
INSERT INTO companies (id, name, legal_address, phone, email) VALUES
(1, 'ООО «КОМПАНИЯ «ФЕСФАРМ»', '121293, г. Москва, ул. Неверовского, д. 10/3, ком. 27', '+7 (499) 142-68-02', 'info@fesfarm.ru'),
(2, 'ГОРОДСКАЯ БОЛЬНИЦА № 33', 'г. Н. Новгород, пр. Ленина 54', '267-33-34', NULL);

SELECT setval(pg_get_serial_sequence('companies', 'id'), COALESCE((SELECT MAX(id) FROM companies), 1), true);

-- =====================================================
-- 2. ФИЛИАЛЫ
-- =====================================================
INSERT INTO branches (id, company_id, name, legal_address, phone, email) VALUES
(1, 1, 'ФЕСФАРМ НН', '603065, Нижегородская обл., г. Нижний Новгород, ул. Дьяконова, д. 2/6, литер А', '+7 (831) 282-33-82', 'nn@fesfarm.ru'),
(2, 1, 'ФЕСФАРМ-КОМИ', '167001, Республика Коми, г. Сыктывкар, ул. Коммунистическая, д. 48/2', '+7 (8212) 30-25-61', 'info@fesfarmkomi.ru'),
(3, 2, 'ГОРОДСКАЯ БОЛЬНИЦА № 33', 'г. Н. Новгород, пр. Ленина 54', '267-33-34', NULL);

SELECT setval(pg_get_serial_sequence('branches', 'id'), COALESCE((SELECT MAX(id) FROM branches), 1), true);

-- =====================================================
-- 3. МЕСТА ПРИЁМА / ОТДЕЛЕНИЯ
-- =====================================================
INSERT INTO locations (id, branch_id, company_id, name, factual_address, phone, email, fax) VALUES
(1, 1, 1, 'Отделение гемодиализа', '603065, г. Нижний Новгород, ул. Дьяконова, д. 2/6, лит А', '282-44-82, +7 964 831 4200', 'fesfarm.avtozavod@yandex.ru', '282-33-82'),
(2, 1, 1, 'Отделение гемодиализа №2', '603003, г. Нижний Новгород, ул. Васенко, д. 11, лит А', '+7 (831) 265-52-43', NULL, NULL),
(3, 1, 1, 'Отделение гемодиализа в г.Дзержинске', '606030, г. Дзержинск, Окская набережная, д. 5, П4', '+7 (831) 35-09-95', NULL, NULL),
(4, 1, 1, 'Отделение гемодиализа №3', '606520, г. Заволжье, ул. Пирогова, д. 26', '+7 (831) 987-90-96', NULL, NULL),
(5, 1, 1, 'Отделение гемодиализа №4', '603035, г. Н. Новгород, ул. Черняховского, д. 5', '+7 (831) 957-90-96', NULL, NULL),
(6, 2, 1, 'Отделение гемодиализа', '167001, Республика Коми, г. Сыктывкар, ул. Коммунистическая, д. 48/2', '+7 (8212) 30-25-61', NULL, NULL),
(7, 3, 2, 'ГОРОДСКОЙ НЕФРОЛОГИЧЕСКИЙ ЦЕНТР', 'г. Н. Новгород, пр. Ленина 54', '267-33-34', NULL, NULL);

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
(3, 7),
(4, 1),
(5, 5);

INSERT INTO doctors (last_name, first_name, patronymic)
VALUES
    ('Белякова','Е.','С.'),
    ('Гордеева','Е.','М.'),
    ('Одинцова','С.','В.'),
    ('Палавин','А.','С.'),
    ('Родионова','О.','А.'),
    ('Серова','А.','Б.'),
    ('Юрченко','М.','Л.')
ON CONFLICT DO NOTHING;
SELECT setval(pg_get_serial_sequence('doctors','id'),COALESCE((SELECT MAX(id) FROM doctors),1),true);

SET client_encoding = 'UTF8';

-- Создаёт/обновляет тестовые врачебные учётные записи.
-- Лобанова: главный врач. Возова: заведующий отделением.
CREATE OR REPLACE FUNCTION _mis_upsert_doctor_user(
    p_login VARCHAR,
    p_password_hash VARCHAR,
    p_role VARCHAR,
    p_last_name VARCHAR,
    p_first_name VARCHAR,
    p_patronymic VARCHAR
)
RETURNS VOID AS $$
DECLARE
    v_doctor_id INTEGER;
BEGIN
    IF p_role NOT IN ('doctor', 'chief_physician', 'department_head') THEN
        RAISE EXCEPTION 'Недопустимая врачебная роль: %', p_role;
    END IF;

    SELECT d.id
      INTO v_doctor_id
      FROM doctors d
     WHERE d.last_name = p_last_name
       AND d.first_name = p_first_name
       AND COALESCE(d.patronymic, '') = COALESCE(p_patronymic, '')
     LIMIT 1;

    IF v_doctor_id IS NULL THEN
        RAISE EXCEPTION 'Не найден врач: % % %',
            p_last_name, p_first_name, COALESCE(p_patronymic, '');
    END IF;

    UPDATE users
       SET password_hash = p_password_hash,
           role = p_role,
           doctor_id = v_doctor_id,
           patient_id = NULL
     WHERE login = p_login;

    IF NOT FOUND THEN
        INSERT INTO users (login, password_hash, role, doctor_id, patient_id)
        VALUES (p_login, p_password_hash, p_role, v_doctor_id, NULL);
    END IF;
END;
$$ LANGUAGE plpgsql;

SELECT _mis_upsert_doctor_user(
    'zakharova_m',
    'pbkdf2_sha256$260000$vVH1K7YWjtmZqz+cPwur8w==$uOZri4tM+wQF8qOgjreFRxWJc88Vx4dQf1O/4r5Jo4A=',
    'doctor', 'Захарова', 'Марина', 'Валерьевна'
);
SELECT _mis_upsert_doctor_user(
    'kazarkin_d',
    'pbkdf2_sha256$260000$B6VPFUEBKrySqbitknZ7iQ==$Dk2OrH+Bs/U9FyJxHxpCPHozhJuwasvaUHzFfmDr4d4=',
    'doctor', 'Казаркин', 'Дмитрий', 'Геннадьевич'
);
SELECT _mis_upsert_doctor_user(
    'vozova_a',
    'pbkdf2_sha256$260000$jLtpSLX76X3ils/SGWkITA==$qmXztsvVdWWv83KGp0aEmPPzIPrp97HAOdL+BU5F5uw=',
    'department_head', 'Возова', 'Анна', 'Маркосовна'
);
SELECT _mis_upsert_doctor_user(
    'lobanova_n',
    'pbkdf2_sha256$260000$n68auTOBp/blxbEn3J5RnA==$gYjyJCKLmZNPGLWR0cWE2y/uOYNqFL3oVKEsTx6E1LQ=',
    'chief_physician', 'Лобанова', 'Надежда', 'Анатольевна'
);
SELECT _mis_upsert_doctor_user(
    'kuznetsova_t',
    'pbkdf2_sha256$260000$xn11l1zkfIBONw2JUW5wcw==$qddc1JWR4c8rGadCnZa/0ZVAFaWWujETUzXxstHHU98=',
    'doctor', 'Кузнецова', 'Татьяна', 'Евгеньевна'
);

DROP FUNCTION _mis_upsert_doctor_user(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);

-- Контроль: все врачебные учётные записи.
SELECT
    u.login,
    u.role,
    u.doctor_id,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio
FROM users u
JOIN doctors d ON d.id = u.doctor_id
WHERE u.role IN ('doctor', 'chief_physician', 'department_head')
ORDER BY d.last_name, d.first_name, d.patronymic;

-- Врачи без учётной записи. В норме 0 строк.
SELECT
    d.id,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio
FROM doctors d
LEFT JOIN users u
    ON u.role IN ('doctor', 'chief_physician', 'department_head')
   AND u.doctor_id = d.id
WHERE u.id IS NULL
ORDER BY d.last_name, d.first_name, d.patronymic;

-- Несколько врачебных учёток на одного врача. В норме 0 строк.
SELECT doctor_id, COUNT(*) AS users_count
FROM users
WHERE role IN ('doctor', 'chief_physician', 'department_head')
GROUP BY doctor_id
HAVING COUNT(*) > 1;

INSERT INTO users (login,password_hash,role,doctor_id,patient_id)
VALUES ('registrar','pbkdf2_sha256$260000$bWlzLXJlZ2lzdHJhci12Mg==$8nieSA6pSy8c7K21jrET0UVlqM/TqSjN4gRXfOxL9vE=','registrar',NULL,NULL)
ON CONFLICT (login) DO UPDATE SET password_hash=EXCLUDED.password_hash,role='registrar',doctor_id=NULL,patient_id=NULL;
SELECT setval(pg_get_serial_sequence('users','id'),COALESCE((SELECT MAX(id) FROM users),1),true);
