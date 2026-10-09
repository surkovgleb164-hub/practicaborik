-- Схема БД стоматологической клиники «Дентал+» (SQLite)
-- Запуск: python init_db.py

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS appointment_services;
DROP TABLE IF EXISTS appointments;
DROP TABLE IF EXISTS materials;
DROP TABLE IF EXISTS diagnoses;
DROP TABLE IF EXISTS services;
DROP TABLE IF EXISTS cabinets;
DROP TABLE IF EXISTS doctors;
DROP TABLE IF EXISTS patients;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS backup_history;
DROP VIEW  IF EXISTS v_appointments_full;
DROP VIEW  IF EXISTS v_doctor_load;
DROP VIEW  IF EXISTS v_debtors;

CREATE TABLE employees (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL CHECK (role IN ('admin','doctor','registrator','accountant')),
    login         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL
);

CREATE TABLE patients (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name         TEXT NOT NULL,
    birth_date        TEXT,
    phone             TEXT,
    email             TEXT UNIQUE,
    address           TEXT,
    registration_date TEXT NOT NULL DEFAULT (DATE('now')),
    notes             TEXT
);

CREATE TABLE doctors (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name  TEXT NOT NULL,
    specialty  TEXT NOT NULL,
    phone      TEXT,
    email      TEXT,
    hire_date  TEXT NOT NULL DEFAULT (DATE('now')),
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

CREATE TABLE cabinets (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    number   TEXT NOT NULL UNIQUE,
    name     TEXT,
    floor    INTEGER
);

CREATE TABLE services (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    code     TEXT NOT NULL UNIQUE,
    name     TEXT NOT NULL,
    category TEXT NOT NULL,
    price    REAL NOT NULL CHECK (price > 0),
    duration INTEGER NOT NULL DEFAULT 30 CHECK (duration > 0)
);

CREATE TABLE diagnoses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    description TEXT
);

CREATE TABLE materials (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     TEXT NOT NULL,
    unit     TEXT NOT NULL DEFAULT 'шт',
    qty      REAL NOT NULL DEFAULT 0 CHECK (qty >= 0),
    min_qty  REAL NOT NULL DEFAULT 0 CHECK (min_qty >= 0),
    price    REAL NOT NULL DEFAULT 0 CHECK (price >= 0)
);

CREATE TABLE appointments (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id   INTEGER NOT NULL REFERENCES patients(id)   ON DELETE RESTRICT ON UPDATE CASCADE,
    doctor_id    INTEGER NOT NULL REFERENCES doctors(id)    ON DELETE RESTRICT ON UPDATE CASCADE,
    cabinet_id   INTEGER NOT NULL REFERENCES cabinets(id)   ON DELETE RESTRICT ON UPDATE CASCADE,
    diagnosis_id INTEGER          REFERENCES diagnoses(id)  ON DELETE SET NULL ON UPDATE CASCADE,
    visit_date   TEXT NOT NULL,
    visit_time   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'planned'
                 CHECK (status IN ('planned','done','cancelled','no_show')),
    complaint    TEXT,
    notes        TEXT,
    total_price  REAL NOT NULL DEFAULT 0 CHECK (total_price >= 0),
    UNIQUE (doctor_id, visit_date, visit_time)
);

CREATE TABLE appointment_services (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE ON UPDATE CASCADE,
    service_id     INTEGER NOT NULL REFERENCES services(id)     ON DELETE RESTRICT ON UPDATE CASCADE,
    qty            INTEGER NOT NULL DEFAULT 1 CHECK (qty > 0),
    price          REAL NOT NULL CHECK (price > 0)
);

CREATE TABLE payments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE ON UPDATE CASCADE,
    pay_date       TEXT NOT NULL DEFAULT (DATE('now')),
    amount         REAL NOT NULL CHECK (amount > 0),
    method         TEXT NOT NULL DEFAULT 'cash'
                   CHECK (method IN ('cash','card','transfer')),
    note           TEXT
);

CREATE TABLE backup_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_type   TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    status        TEXT NOT NULL,
    error_message TEXT,
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_appointments_date        ON appointments(visit_date);
CREATE INDEX idx_appointments_doctor_date ON appointments(doctor_id, visit_date);
CREATE INDEX idx_patients_name            ON patients(full_name);
CREATE INDEX idx_payments_date            ON payments(pay_date);
CREATE INDEX idx_services_category        ON services(category);

CREATE VIEW v_appointments_full AS
  SELECT a.id, a.visit_date, a.visit_time, a.status, a.total_price,
         p.full_name AS patient, d.full_name AS doctor, c.number AS cabinet,
         dg.name AS diagnosis
  FROM appointments a
  JOIN patients  p ON p.id = a.patient_id
  JOIN doctors   d ON d.id = a.doctor_id
  JOIN cabinets  c ON c.id = a.cabinet_id
  LEFT JOIN diagnoses dg ON dg.id = a.diagnosis_id;

CREATE VIEW v_doctor_load AS
  SELECT d.id, d.full_name,
         COUNT(a.id) AS appointments_total,
         SUM(CASE WHEN a.status = 'done' THEN 1 ELSE 0 END) AS appointments_done,
         COALESCE(SUM(CASE WHEN a.status = 'done' THEN a.total_price END), 0) AS revenue
  FROM doctors d
  LEFT JOIN appointments a ON a.doctor_id = d.id
  GROUP BY d.id, d.full_name;

CREATE VIEW v_debtors AS
  SELECT a.id AS appointment_id, p.id AS patient_id, p.full_name AS patient,
         a.visit_date, a.total_price,
         COALESCE((SELECT SUM(amount) FROM payments WHERE appointment_id = a.id), 0) AS paid,
         a.total_price - COALESCE((SELECT SUM(amount) FROM payments WHERE appointment_id = a.id), 0) AS debt
  FROM appointments a
  JOIN patients p ON p.id = a.patient_id
  WHERE a.status = 'done';

CREATE TRIGGER trg_payments_check AFTER INSERT ON payments
BEGIN
    SELECT RAISE(ABORT, 'Сумма платежей превышает стоимость приёма')
    WHERE (SELECT SUM(amount) FROM payments WHERE appointment_id = NEW.appointment_id)
        > (SELECT total_price FROM appointments WHERE id = NEW.appointment_id);
END;

CREATE TRIGGER trg_appointment_services_total AFTER INSERT ON appointment_services
BEGIN
    UPDATE appointments
       SET total_price = COALESCE((
             SELECT SUM(qty * price) FROM appointment_services WHERE appointment_id = NEW.appointment_id
           ), 0)
     WHERE id = NEW.appointment_id;
END;

CREATE TRIGGER trg_appointments_bd BEFORE DELETE ON appointments
WHEN EXISTS (SELECT 1 FROM payments WHERE appointment_id = OLD.id)
BEGIN
    SELECT RAISE(ABORT, 'Нельзя удалить приём: по нему есть платежи');
END;

INSERT INTO employees(full_name, role, login, password_hash) VALUES
  ('Администратор',       'admin',       'admin',       '0F1E2D3C4B5A6978$B96EC7C7E012DE244EA98FC09C96023A1DBD2D7A776B25D21DE2C15D961088BC'),
  ('Смирнова А.П.',       'doctor',      'doctor',      'A1B2C3D4E5F60718$E6AB384853E8F861E820A40B53E65F9FD45E2378607AB611A8B16C6862849FBB'),
  ('Кузнецова М.И.',      'registrator', 'registrator', '1122334455667788$DF3A84655D876D9A9E49FF3989A3CBB4DF6CD85CF5A7CC1859B7C2976FD09977'),
  ('Орлова Е.В.',         'accountant',  'accountant',  '99AABBCCDDEEFF00$4B3E4C9F1D2A7E5C6F8B0D1E2A3C4B5D6E7F8091A2B3C4D5E6F708192A3B4C5D');

INSERT INTO patients(full_name, birth_date, phone, email, address) VALUES
  ('Иванов Иван Иванович',        '1985-04-12', '+7-900-111-22-33', 'ivanov@example.com',  'ул. Ленина, 10'),
  ('Петрова Мария Сергеевна',     '1992-11-03', '+7-900-222-33-44', 'petrova@example.com', 'ул. Мира, 5, кв. 7'),
  ('Сидоров Алексей Петрович',    '1978-06-25', '+7-900-333-44-55', 'sidorov@example.com', 'пр. Победы, 22'),
  ('Козлова Анна Дмитриевна',     '2001-02-17', '+7-900-444-55-66', 'kozlova@example.com', 'ул. Садовая, 3'),
  ('Николаев Пётр Олегович',      '1966-09-30', '+7-900-555-66-77', NULL,                  'ул. Гагарина, 14');

INSERT INTO doctors(full_name, specialty, phone, email) VALUES
  ('Смирнова Анна Павловна',    'Терапевт-стоматолог',  '+7-495-100-10-10', 'smirnova@dental.plus'),
  ('Волков Дмитрий Игоревич',   'Хирург-имплантолог',   '+7-495-100-10-11', 'volkov@dental.plus'),
  ('Морозова Елена Юрьевна',    'Ортодонт',             '+7-495-100-10-12', 'morozova@dental.plus');

INSERT INTO cabinets(number, name, floor) VALUES
  ('101', 'Терапевтический', 1),
  ('102', 'Хирургический',   1),
  ('201', 'Ортодонтический', 2);

INSERT INTO services(code, name, category, price, duration) VALUES
  ('T001', 'Осмотр стоматолога',            'Диагностика', 800,  20),
  ('T002', 'Лечение кариеса (1 зуб)',       'Терапия',     4500, 60),
  ('T003', 'Профессиональная чистка',       'Гигиена',     5500, 60),
  ('T004', 'Удаление зуба',                 'Хирургия',    3200, 40),
  ('T005', 'Имплантация (1 имплант)',       'Имплантация', 45000, 120),
  ('T006', 'Установка брекет-системы',      'Ортодонтия',  80000, 90),
  ('T007', 'Рентгеновский снимок',          'Диагностика', 1200, 15);

INSERT INTO diagnoses(code, name, description) VALUES
  ('K02.1', 'Кариес дентина',              'Кариес на стадии поражения дентина'),
  ('K05.1', 'Хронический гингивит',        'Воспаление дёсен'),
  ('K08.1', 'Утрата зубов',                'Потеря зуба вследствие травмы или заболевания'),
  ('K07.1', 'Аномалия положения зубов',    'Неправильный прикус / положение зубов');

INSERT INTO materials(name, unit, qty, min_qty, price) VALUES
  ('Анестетик Ультракаин', 'амп', 45, 20, 120),
  ('Пломбировочный материал', 'г', 300, 100, 45),
  ('Имплант Titanium 4.0', 'шт', 8, 5, 18000),
  ('Брекет металлический', 'шт', 120, 40, 350);

INSERT INTO appointments(patient_id, doctor_id, cabinet_id, diagnosis_id, visit_date, visit_time, status, complaint) VALUES
  (1, 1, 1, 1, '2026-09-10', '09:00', 'done',    'Боль в зубе справа снизу'),
  (2, 1, 1, 2, '2026-09-12', '10:30', 'done',    'Кровоточивость дёсен'),
  (3, 2, 2, 3, '2026-09-15', '14:00', 'done',    'Отсутствует зуб 36'),
  (4, 3, 3, 4, '2026-10-01', '11:00', 'planned', 'Консультация по брекетам'),
  (5, 1, 1, NULL,'2026-10-03','15:30', 'planned', 'Профилактический осмотр');

INSERT INTO appointment_services(appointment_id, service_id, qty, price) VALUES
  (1, 1, 1, 800),
  (1, 2, 1, 4500),
  (2, 3, 1, 5500),
  (3, 4, 1, 3200),
  (4, 1, 1, 800),
  (5, 1, 1, 800);

INSERT INTO payments(appointment_id, pay_date, amount, method) VALUES
  (1, '2026-09-10', 5300, 'card'),
  (2, '2026-09-12', 5500, 'cash'),
  (3, '2026-09-15', 3200, 'transfer');