# Запуск и проверка базы данных через CMD

Эта инструкция нужна для воспроизводимого создания базы данных **без DBeaver**.  
DBeaver можно использовать потом только для визуальной проверки таблиц.

Инструкция рассчитана на Windows CMD, не PowerShell.

## Что должно быть заранее

1. PostgreSQL установлен на компьютере.
2. Команда `psql` доступна из CMD.
3. Ты находишься в корневой папке проекта, где лежит папка `database`.

Пример корневой папки проекта:

```cmd
D:\python\ckd\mis_for_registrations
```

---

## 1. Подготовить CMD к работе с русским текстом

Выполни:

```cmd
chcp 65001
set PGCLIENTENCODING=UTF8
```

Это нужно, чтобы PostgreSQL нормально прочитал SQL-файлы с русскими буквами.

---

## 2. Ввести пароль PostgreSQL один раз

В этой же CMD-сессии выполни:

```cmd
set PGPASSWORD=ТВОЙ_ПАРОЛЬ_ОТ_POSTGRES
```

После этого `psql` не должен спрашивать пароль при каждой команде.

Важно: пароль хранится только в текущем окне CMD. После закрытия окна он исчезнет.

---

## 3. Пересоздать базу данных

Внимание: команда `DROP DATABASE` удаляет базу `mis_for_registrations`, если она уже существует. Не запускай это на базе с реальными данными.

```cmd
psql -h localhost -U postgres -d postgres -c "DROP DATABASE IF EXISTS mis_for_registrations;"
psql -h localhost -U postgres -d postgres -c "CREATE DATABASE mis_for_registrations WITH ENCODING 'UTF8' TEMPLATE template0;"
```

Если всё хорошо, появятся сообщения примерно:

```text
DROP DATABASE
CREATE DATABASE
```

---

## 4. Создать таблицы, связи, МКБ и тестовые данные

Запускай файлы строго по порядку.

### 4.1. Создание таблиц

```cmd
psql -h localhost -U postgres -d mis_for_registrations -v ON_ERROR_STOP=1 -f ".\database\01 создание таблиц.sql"
```

### 4.2. Настройка связей, ключей и ограничений

```cmd
psql -h localhost -U postgres -d mis_for_registrations -v ON_ERROR_STOP=1 -f ".\database\02 настройка связей ключей и ограничений.sql"
```

Сообщения вида:

```text
ЗАМЕЧАНИЕ: ограничение ... не существует, пропускается
```

не являются ошибкой. Это нормально: файл сначала пытается удалить старое ограничение, если оно было, а потом добавить его заново.

### 4.3. Создание и заполнение таблиц МКБ

```cmd
psql -h localhost -U postgres -d mis_for_registrations -v ON_ERROR_STOP=1 -f ".\database\03 создание и заполнение таблиц МКБ.sql"
```

### 4.4. Заполнение тестовыми данными

```cmd
psql -h localhost -U postgres -d mis_for_registrations -v ON_ERROR_STOP=1 -f ".\database\04 заполнение тестовыми данными.sql"
```

Этот файл нужен только для разработки и демонстрации. В боевой базе с реальными пациентами его запускать не надо.

---

## 5. Проверить, что таблицы создались

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "\dt"
```

Должны быть таблицы вроде:

```text
companies
branches
locations
doctors
doctor_locations
patients
users
appointments
surveys
examinations
cbc_results
biochemistry_results
urinalysis_results
albuminuria_results
ultrasound_results
calculated_metrics
ckd_prognosis_results
diagnoses
appointment_diets
prescriptions
icd10_diagnoses
appointment_icd10_diagnoses
```

---

## 6. Проверить, что view создалась

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "\dv"
```

Должна быть view:

```text
appointment_icd10_diagnoses_view
```

Проверить запросом:

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "SELECT * FROM appointment_icd10_diagnoses_view LIMIT 10;"
```

Если в тестовых данных пока нет связанных диагнозов МКБ по приемам, view может быть пустой. Это не ошибка. Главное, чтобы запрос не падал.

---

## 7. Проверить наполнение ключевых таблиц

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "SELECT 'companies' AS table_name, COUNT(*) FROM companies UNION ALL SELECT 'branches', COUNT(*) FROM branches UNION ALL SELECT 'locations', COUNT(*) FROM locations UNION ALL SELECT 'doctors', COUNT(*) FROM doctors UNION ALL SELECT 'patients', COUNT(*) FROM patients UNION ALL SELECT 'users', COUNT(*) FROM users UNION ALL SELECT 'appointments', COUNT(*) FROM appointments UNION ALL SELECT 'icd10_diagnoses', COUNT(*) FROM icd10_diagnoses;"
```

В результате напротив таблиц должны быть числа. Если запускался файл `04 заполнение тестовыми данными.sql`, то `patients`, `appointments`, `users` и другие тестовые таблицы должны быть не пустые.

Отдельно можно проверить МКБ:

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "SELECT COUNT(*) FROM icd10_diagnoses;"
```

И посмотреть первые диагнозы:

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "SELECT id, diagnosis FROM icd10_diagnoses ORDER BY sort_order, diagnosis LIMIT 20;"
```

---

## 8. Проверить стадии ХБП

```cmd
psql -h localhost -U postgres -d mis_for_registrations -c "SELECT ckd_stage, COUNT(*) FROM calculated_metrics GROUP BY ckd_stage ORDER BY ckd_stage;"
```

Должны использоваться стадии с русской буквой `С`

---

## 9. Запустить файл проверки целостности

```cmd
psql -h localhost -U postgres -d mis_for_registrations -f ".\database\05 оценка целостности.sql"
```

Этот файл проверяет базу на логические и структурные проблемы.

Если критических ошибок нет, базу можно считать созданной корректно.

---

## 10. Открыть базу в DBeaver для визуальной проверки

После командной проверки можно открыть DBeaver и подключиться к базе:

```text
Host: localhost
Port: 5432
Database: mis_for_registrations
User: postgres
Password: твой пароль
```

Смотреть:

```text
public → Tables
public → Views
icd10_diagnoses
patients
appointments
calculated_metrics
appointment_icd10_diagnoses_view
```

---

## Частые проблемы

### Ошибка: `psql` не является внутренней или внешней командой

Значит `psql` не добавлен в PATH. Можно использовать полный путь, например:

```cmd
"C:\Program Files\PostgreSQL\16\bin\psql.exe" --version
```

Если версия PostgreSQL другая, путь может отличаться.

### Ошибка кодировки `WIN1251` / `UTF8`

Проверь, что в начале CMD-сессии выполнено:

```cmd
chcp 65001
set PGCLIENTENCODING=UTF8
```

### Ошибка пароля

Проверь пароль:

```cmd
set PGPASSWORD=ТВОЙ_ПАРОЛЬ_ОТ_POSTGRES
```

И попробуй снова.

### Сообщения `ЗАМЕЧАНИЕ: ограничение ... не существует, пропускается`

Это нормально. Это не ошибка.

### База уже была создана раньше

Для чистого запуска используй:

```cmd
psql -h localhost -U postgres -d postgres -c "DROP DATABASE IF EXISTS mis_for_registrations;"
psql -h localhost -U postgres -d postgres -c "CREATE DATABASE mis_for_registrations WITH ENCODING 'UTF8' TEMPLATE template0;"
```

Но не делай это на базе с реальными данными.
