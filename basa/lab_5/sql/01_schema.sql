-- Лабораторная 5. База учёта квартплаты для планировщика событий.
-- Те же сущности, что в лабораторных 3–4, но данных мало: их можно сверить руками.

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS kvartplata
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE kvartplata;

DROP TABLE IF EXISTS event_log;
DROP TABLE IF EXISTS notices;
DROP TABLE IF EXISTS monthly_summary;
DROP TABLE IF EXISTS payments_archive;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS charges;
DROP TABLE IF EXISTS saldo;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS scheduler_settings;

CREATE TABLE accounts (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_no VARCHAR(10)  NOT NULL,
    flat       SMALLINT UNSIGNED NOT NULL,
    owner      VARCHAR(150) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_account_no (account_no)
) ENGINE = InnoDB COMMENT = 'Лицевые счета';

CREATE TABLE saldo (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED NOT NULL,
    period     DATE         NOT NULL COMMENT 'Месяц, на начало которого зафиксировано сальдо',
    amount     DECIMAL(12,2) NOT NULL COMMENT '+ долг / − переплата',
    PRIMARY KEY (id),
    UNIQUE KEY uq_saldo (account_id, period),
    CONSTRAINT fk_saldo_account FOREIGN KEY (account_id) REFERENCES accounts (id)
) ENGINE = InnoDB COMMENT = 'Входящее сальдо';

CREATE TABLE charges (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED NOT NULL,
    period     DATE         NOT NULL,
    service    VARCHAR(50)  NOT NULL,
    amount     DECIMAL(12,2) NOT NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uq_charge (account_id, period, service),
    CONSTRAINT fk_charges_account FOREIGN KEY (account_id) REFERENCES accounts (id)
) ENGINE = InnoDB COMMENT = 'Начисления';

CREATE TABLE payments (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED NOT NULL,
    pay_date   DATE         NOT NULL,
    amount     DECIMAL(12,2) NOT NULL,
    source     VARCHAR(30)  NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_payments_account FOREIGN KEY (account_id) REFERENCES accounts (id),
    CONSTRAINT chk_payments_amount CHECK (amount > 0)
) ENGINE = InnoDB COMMENT = 'Платежи';

-- Сюда событие переносит платежи старше границы из scheduler_settings.
CREATE TABLE payments_archive (
    id          INT UNSIGNED NOT NULL,
    account_id  INT UNSIGNED NOT NULL,
    pay_date    DATE         NOT NULL,
    amount      DECIMAL(12,2) NOT NULL,
    source      VARCHAR(30)  NOT NULL,
    archived_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE = InnoDB COMMENT = 'Архив старых платежей';

-- Агрегат, который пересчитывает повторяющееся событие.
-- closing_balance — сальдо на конец месяца (на начало следующего).
CREATE TABLE monthly_summary (
    account_id       INT UNSIGNED NOT NULL,
    period           DATE         NOT NULL,
    charged          DECIMAL(12,2) NOT NULL,
    paid             DECIMAL(12,2) NOT NULL,
    closing_balance  DECIMAL(12,2) NOT NULL,
    updated_at       DATETIME     NOT NULL,
    PRIMARY KEY (account_id, period),
    CONSTRAINT fk_summary_account FOREIGN KEY (account_id) REFERENCES accounts (id)
) ENGINE = InnoDB COMMENT = 'Помесячные итоги';

-- Объявления с датой устаревания. Просроченные удаляет событие очистки.
CREATE TABLE notices (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    body       VARCHAR(255) NOT NULL,
    expires_at DATETIME     NOT NULL,
    PRIMARY KEY (id)
) ENGINE = InnoDB COMMENT = 'Объявления для жильцов';

-- Журнал запусков. У планировщика MySQL нет истории выполнений,
-- только LAST_EXECUTED у самого события, поэтому журнал ведём сами.
CREATE TABLE event_log (
    id         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    event_name VARCHAR(64)  NOT NULL,
    ran_at     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    affected   INT          NOT NULL,
    message    VARCHAR(255) NOT NULL,
    PRIMARY KEY (id)
) ENGINE = InnoDB COMMENT = 'Журнал выполнения событий';

CREATE TABLE scheduler_settings (
    name  VARCHAR(50)  NOT NULL,
    value VARCHAR(100) NOT NULL,
    PRIMARY KEY (name)
) ENGINE = InnoDB COMMENT = 'Параметры событий';

INSERT INTO scheduler_settings (name, value) VALUES
    ('archive_before', '2024-01-01');

INSERT INTO accounts (id, account_no, flat, owner) VALUES
    (1, '1000001', 1, 'Иванов Иван Петрович'),
    (2, '1000002', 2, 'Петрова Анна Сергеевна'),
    (3, '1000003', 3, 'Сидоров Олег Викторович');

INSERT INTO saldo (account_id, period, amount) VALUES
    (1, '2026-09-01', 1000.00),
    (2, '2026-09-01',  200.00),
    (3, '2026-09-01',    0.00);

INSERT INTO charges (account_id, period, service, amount) VALUES
    (1, '2026-09-01', 'Содержание жилья', 500.00),
    (1, '2026-10-01', 'Содержание жилья', 400.00),
    (2, '2026-09-01', 'Содержание жилья', 300.00),
    (2, '2026-10-01', 'Содержание жилья', 300.00),
    (3, '2026-09-01', 'Содержание жилья', 150.00),
    (3, '2026-10-01', 'Содержание жилья', 150.00);

-- Два платежа старше 2024-01-01 уйдут в архив. Остальные остаются в payments.
INSERT INTO payments (account_id, pay_date, amount, source) VALUES
    (1, '2022-03-01',  50.00, 'Банк'),
    (2, '2021-12-15',  80.00, 'Касса'),
    (1, '2026-10-05', 300.00, 'Онлайн'),
    (2, '2026-09-20', 300.00, 'Банк'),
    (3, '2026-10-10', 100.00, 'Касса');

INSERT INTO notices (body, expires_at) VALUES
    ('Отключение горячей воды 1 сентября', '2026-09-02 00:00:00'),
    ('Протокол собрания за 2024 год',        '2025-01-15 00:00:00'),
    ('Поверка счётчиков до 31 декабря 2030', '2030-12-31 00:00:00');
