SET client_encoding = 'UTF8';

-- Идемпотентное добавление второго места приёма для Возовой Анны Маркосовны.
-- Структуру БД не меняет: используются существующие companies/branches/locations/doctor_locations.
DO $$
DECLARE
    v_company_id INTEGER;
    v_branch_id INTEGER;
    v_location_id INTEGER;
    v_doctor_id INTEGER;
BEGIN
    SELECT id INTO v_company_id
    FROM companies
    WHERE name = 'ГОРОДСКАЯ БОЛЬНИЦА № 33'
    ORDER BY id
    LIMIT 1;

    IF v_company_id IS NULL THEN
        INSERT INTO companies (name, legal_address, phone, email)
        VALUES (
            'ГОРОДСКАЯ БОЛЬНИЦА № 33',
            'г. Н. Новгород, пр. Ленина 54',
            '267-33-34',
            NULL
        )
        RETURNING id INTO v_company_id;
    END IF;

    SELECT id INTO v_branch_id
    FROM branches
    WHERE company_id = v_company_id
      AND name = 'ГОРОДСКАЯ БОЛЬНИЦА № 33'
    ORDER BY id
    LIMIT 1;

    IF v_branch_id IS NULL THEN
        INSERT INTO branches (company_id, name, legal_address, phone, email)
        VALUES (
            v_company_id,
            'ГОРОДСКАЯ БОЛЬНИЦА № 33',
            'г. Н. Новгород, пр. Ленина 54',
            '267-33-34',
            NULL
        )
        RETURNING id INTO v_branch_id;
    END IF;

    SELECT id INTO v_location_id
    FROM locations
    WHERE branch_id = v_branch_id
      AND name = 'ГОРОДСКОЙ НЕФРОЛОГИЧЕСКИЙ ЦЕНТР'
      AND factual_address = 'г. Н. Новгород, пр. Ленина 54'
    ORDER BY id
    LIMIT 1;

    IF v_location_id IS NULL THEN
        INSERT INTO locations (
            branch_id,
            company_id,
            name,
            factual_address,
            phone,
            email,
            fax
        )
        VALUES (
            v_branch_id,
            v_company_id,
            'ГОРОДСКОЙ НЕФРОЛОГИЧЕСКИЙ ЦЕНТР',
            'г. Н. Новгород, пр. Ленина 54',
            '267-33-34',
            NULL,
            NULL
        )
        RETURNING id INTO v_location_id;
    END IF;

    SELECT id INTO v_doctor_id
    FROM doctors
    WHERE last_name = 'Возова'
      AND first_name = 'Анна'
      AND COALESCE(patronymic, '') = 'Маркосовна'
    ORDER BY id
    LIMIT 1;

    IF v_doctor_id IS NULL THEN
        RAISE EXCEPTION 'Не найдена Возова Анна Маркосовна в таблице doctors';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM doctor_locations
        WHERE doctor_id = v_doctor_id
          AND location_id = v_location_id
    ) THEN
        INSERT INTO doctor_locations (doctor_id, location_id)
        VALUES (v_doctor_id, v_location_id);
    END IF;
END
$$;

-- Контроль: у Возовой должны отображаться ФЕСФАРМ и ГБ № 33.
SELECT
    d.id AS doctor_id,
    d.last_name,
    d.first_name,
    d.patronymic,
    l.id AS location_id,
    l.name AS location_name,
    b.name AS branch_name,
    c.name AS company_name,
    l.factual_address,
    l.phone
FROM doctors d
JOIN doctor_locations dl ON dl.doctor_id = d.id
JOIN locations l ON l.id = dl.location_id
LEFT JOIN branches b ON b.id = l.branch_id
LEFT JOIN companies c ON c.id = COALESCE(l.company_id, b.company_id)
WHERE d.last_name = 'Возова'
  AND d.first_name = 'Анна'
  AND COALESCE(d.patronymic, '') = 'Маркосовна'
ORDER BY l.id;
