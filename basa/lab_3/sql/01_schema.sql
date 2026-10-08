-- Пункт 1. База данных учёта квартплаты
-- Пункт 2. Таблицы saldo, charges, payments (+ справочник лицевых счетов)
--
-- Знак сальдо: «+» — долг жильца, «−» — переплата (аванс).
-- Сальдо на конец месяца = сальдо на начало + начислено − оплачено.

SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS kvartplata
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE kvartplata;

DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS charges;
DROP TABLE IF EXISTS saldo;
DROP TABLE IF EXISTS accounts;

-- Справочник лицевых счетов (на него ссылаются три основные таблицы)
CREATE TABLE accounts (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    account_no VARCHAR(10)   NOT NULL COMMENT 'Номер лицевого счёта',
    flat       SMALLINT UNSIGNED NOT NULL COMMENT 'Номер квартиры',
    owner      VARCHAR(150)  NOT NULL COMMENT 'Ответственный квартиросъёмщик',
    area       DECIMAL(6,2)  NOT NULL COMMENT 'Общая площадь, м²',
    residents  TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT 'Число проживающих',
    PRIMARY KEY (id),
    UNIQUE KEY uq_account_no (account_no),
    UNIQUE KEY uq_flat (flat),
    CONSTRAINT chk_account_no CHECK (account_no REGEXP '^[0-9]{6,10}$'),
    CONSTRAINT chk_area CHECK (area > 0)
) ENGINE = InnoDB COMMENT = 'Лицевые счета';

-- Сальдо по лицевому счёту на начало месяца
CREATE TABLE saldo (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED  NOT NULL COMMENT 'Лицевой счёт',
    period     DATE          NOT NULL COMMENT 'Месяц (1-е число), на начало которого зафиксировано сальдо',
    amount     DECIMAL(12,2) NOT NULL COMMENT 'Сальдо: + долг / − переплата',
    PRIMARY KEY (id),
    UNIQUE KEY uq_saldo (account_id, period),
    CONSTRAINT fk_saldo_account FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON DELETE CASCADE,
    CONSTRAINT chk_saldo_period CHECK (DAYOFMONTH(period) = 1)
) ENGINE = InnoDB COMMENT = 'Сальдо по лицевому счёту';

-- Начисления по лицевому счёту (по услугам за месяц)
CREATE TABLE charges (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED  NOT NULL COMMENT 'Лицевой счёт',
    period     DATE          NOT NULL COMMENT 'Расчётный месяц (1-е число)',
    service    VARCHAR(50)   NOT NULL COMMENT 'Услуга',
    amount     DECIMAL(12,2) NOT NULL COMMENT 'Сумма начисления (отрицательная — перерасчёт)',
    PRIMARY KEY (id),
    UNIQUE KEY uq_charge (account_id, period, service),
    KEY ix_charges_period (period),
    CONSTRAINT fk_charges_account FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON DELETE CASCADE,
    CONSTRAINT chk_charges_period CHECK (DAYOFMONTH(period) = 1)
) ENGINE = InnoDB COMMENT = 'Начисления по лицевому счёту';

-- Платежи по лицевому счёту (учитываются в месяце поступления)
CREATE TABLE payments (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    account_id INT UNSIGNED  NOT NULL COMMENT 'Лицевой счёт',
    pay_date   DATE          NOT NULL COMMENT 'Дата поступления на расчётный счёт',
    amount     DECIMAL(12,2) NOT NULL COMMENT 'Сумма платежа',
    source     VARCHAR(30)   NOT NULL DEFAULT 'Банк' COMMENT 'Способ оплаты',
    doc_no     VARCHAR(20)   NULL COMMENT 'Номер платёжного документа',
    PRIMARY KEY (id),
    KEY ix_payments_account_date (account_id, pay_date),
    CONSTRAINT fk_payments_account FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON DELETE CASCADE,
    CONSTRAINT chk_payments_amount CHECK (amount > 0)
) ENGINE = InnoDB COMMENT = 'Платежи по лицевому счёту';
