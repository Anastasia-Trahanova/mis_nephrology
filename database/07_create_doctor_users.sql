SET client_encoding = 'UTF8';

-- Файл: 07_create_doctor_users.sql
-- Назначение: создаёт или обновляет учётные записи врачей для тестовой/демонстрационной БД.
--
-- ВАЖНО:
-- - открытые пароли в этом файле не хранятся;
-- - здесь сохранены только password_hash в формате pbkdf2_sha256, который использует app/routers/auth.py;
-- - файл можно запускать повторно: существующие логины будут обновлены, отсутствующие — созданы;
-- - если врач не найден в таблице doctors по ФИО, выполнение остановится с ошибкой.

CREATE OR REPLACE FUNCTION _mis_upsert_doctor_user(
    p_login VARCHAR,
    p_password_hash VARCHAR,
    p_last_name VARCHAR,
    p_first_name VARCHAR,
    p_patronymic VARCHAR
)
RETURNS VOID AS $$
DECLARE
    v_doctor_id INTEGER;
BEGIN
    SELECT d.id
      INTO v_doctor_id
      FROM doctors d
     WHERE d.last_name = p_last_name
       AND d.first_name = p_first_name
       AND COALESCE(d.patronymic, '') = COALESCE(p_patronymic, '')
     LIMIT 1;

    IF v_doctor_id IS NULL THEN
        RAISE EXCEPTION 'Не найден врач: % % %', p_last_name, p_first_name, COALESCE(p_patronymic, '');
    END IF;

    UPDATE users
       SET password_hash = p_password_hash,
           role = 'doctor',
           doctor_id = v_doctor_id,
           patient_id = NULL
     WHERE login = p_login;

    IF NOT FOUND THEN
        INSERT INTO users (login, password_hash, role, doctor_id, patient_id)
        VALUES (p_login, p_password_hash, 'doctor', v_doctor_id, NULL);
    END IF;
END;
$$ LANGUAGE plpgsql;

SELECT _mis_upsert_doctor_user(
    'zakharova_m',
    'pbkdf2_sha256$260000$vVH1K7YWjtmZqz+cPwur8w==$uOZri4tM+wQF8qOgjreFRxWJc88Vx4dQf1O/4r5Jo4A=',
    'Захарова',
    'Марина',
    'Валерьевна'
);

SELECT _mis_upsert_doctor_user(
    'kazarkin_d',
    'pbkdf2_sha256$260000$B6VPFUEBKrySqbitknZ7iQ==$Dk2OrH+Bs/U9FyJxHxpCPHozhJuwasvaUHzFfmDr4d4=',
    'Казаркин',
    'Дмитрий',
    'Геннадьевич'
);

SELECT _mis_upsert_doctor_user(
    'vozova_a',
    'pbkdf2_sha256$260000$jLtpSLX76X3ils/SGWkITA==$qmXztsvVdWWv83KGp0aEmPPzIPrp97HAOdL+BU5F5uw=',
    'Возова',
    'Анна',
    'Маркосовна'
);

SELECT _mis_upsert_doctor_user(
    'lobanova_n',
    'pbkdf2_sha256$260000$n68auTOBp/blxbEn3J5RnA==$gYjyJCKLmZNPGLWR0cWE2y/uOYNqFL3oVKEsTx6E1LQ=',
    'Лобанова',
    'Надежда',
    'Анатольевна'
);

SELECT _mis_upsert_doctor_user(
    'kuznetsova_t',
    'pbkdf2_sha256$260000$xn11l1zkfIBONw2JUW5wcw==$qddc1JWR4c8rGadCnZa/0ZVAFaWWujETUzXxstHHU98=',
    'Кузнецова',
    'Татьяна',
    'Евгеньевна'
);

DROP FUNCTION _mis_upsert_doctor_user(VARCHAR, VARCHAR, VARCHAR, VARCHAR, VARCHAR);

-- Контроль 1: все врачебные учётные записи и привязанные врачи.
SELECT
    u.login,
    u.role,
    u.doctor_id,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio
FROM users u
JOIN doctors d ON d.id = u.doctor_id
WHERE u.role = 'doctor'
ORDER BY d.last_name, d.first_name, d.patronymic;

-- Контроль 2: врачи без учётной записи. В норме запрос должен вернуть 0 строк.
SELECT
    d.id,
    d.last_name || ' ' || d.first_name || ' ' || COALESCE(d.patronymic, '') AS doctor_fio
FROM doctors d
LEFT JOIN users u
    ON u.role = 'doctor'
   AND u.doctor_id = d.id
WHERE u.id IS NULL
ORDER BY d.last_name, d.first_name, d.patronymic;

-- Контроль 3: несколько врачебных учёток на одного врача. В норме запрос должен вернуть 0 строк.
SELECT
    doctor_id,
    COUNT(*) AS users_count
FROM users
WHERE role = 'doctor'
GROUP BY doctor_id
HAVING COUNT(*) > 1;
