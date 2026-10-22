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

DROP TABLE IF EXISTS bank_pending;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS charges;
DROP TABLE IF EXISTS saldo;
DROP TABLE IF EXISTS accounts;
DROP TABLE IF EXISTS bank_imports;

-- Загрузки банковских выписок (для истории и отмены загрузки)
CREATE TABLE bank_imports (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    file_name   VARCHAR(255)  NOT NULL COMMENT 'Имя загруженного файла',
    bank_account VARCHAR(20)  NULL COMMENT 'Расчётный счёт из выписки',
    date_from   DATE          NULL COMMENT 'Первая операция в выписке',
    date_to     DATE          NULL COMMENT 'Последняя операция в выписке',
    imported_at DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Когда загружена',
    ops_total   INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT 'Операций в выписке',
    ops_loaded  INT UNSIGNED  NOT NULL DEFAULT 0 COMMENT 'Загружено платежей',
    amount      DECIMAL(14,2) NOT NULL DEFAULT 0 COMMENT 'Сумма загруженных платежей',
    PRIMARY KEY (id)
) ENGINE = InnoDB COMMENT = 'Загрузки банковских выписок';

-- Справочник лицевых счетов (на него ссылаются три основные таблицы)
CREATE TABLE accounts (
    id         INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    account_no VARCHAR(10)   NOT NULL COMMENT 'Номер лицевого счёта',
    flat       SMALLINT UNSIGNED NOT NULL COMMENT 'Номер квартиры',
    owner      VARCHAR(150)  NOT NULL COMMENT 'Ответственный квартиросъёмщик',
    area       DECIMAL(6,2)  NULL COMMENT 'Общая площадь, м² (у счетов из банковской выписки может быть неизвестна)',
    residents  TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT 'Число проживающих',
    import_id  INT UNSIGNED  NULL COMMENT 'Загрузка выписки, при которой счёт создан автоматически',
    PRIMARY KEY (id),
    UNIQUE KEY uq_account_no (account_no),
    UNIQUE KEY uq_flat (flat),
    CONSTRAINT chk_account_no CHECK (account_no REGEXP '^[0-9]{6,10}$'),
    CONSTRAINT fk_accounts_import FOREIGN KEY (import_id) REFERENCES bank_imports (id)
        ON DELETE SET NULL,
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
    payer      VARCHAR(255)  NULL COMMENT 'Плательщик (из банковской выписки)',
    purpose    VARCHAR(500)  NULL COMMENT 'Назначение платежа (из банковской выписки)',
    import_id  INT UNSIGNED  NULL COMMENT 'Загрузка выписки, из которой получен платёж',
    bank_ref   CHAR(40)      NULL COMMENT 'Отпечаток операции выписки: защита от повторной загрузки',
    PRIMARY KEY (id),
    KEY ix_payments_account_date (account_id, pay_date),
    UNIQUE KEY uq_payments_bank_ref (bank_ref),
    CONSTRAINT fk_payments_account FOREIGN KEY (account_id) REFERENCES accounts (id)
        ON DELETE CASCADE,
    CONSTRAINT fk_payments_import FOREIGN KEY (import_id) REFERENCES bank_imports (id)
        ON DELETE CASCADE,
    CONSTRAINT chk_payments_amount CHECK (amount > 0)
) ENGINE = InnoDB COMMENT = 'Платежи по лицевому счёту';

-- Неразнесённые платежи из выписки: поступления, которые не удалось сразу отнести
-- к лицевому счёту. Хранятся до доработки, затем переносятся в payments
CREATE TABLE bank_pending (
    id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
    import_id   INT UNSIGNED  NOT NULL COMMENT 'Загрузка выписки',
    posted      DATETIME      NOT NULL COMMENT 'Дата проводки',
    doc_no      VARCHAR(20)   NULL COMMENT 'Номер платёжного документа',
    amount      DECIMAL(12,2) NOT NULL COMMENT 'Сумма',
    payer       VARCHAR(255)  NULL COMMENT 'Плательщик',
    payer_raw   VARCHAR(500)  NULL COMMENT 'Реквизиты плательщика из выписки (с адресом)',
    purpose     VARCHAR(1000) NULL COMMENT 'Назначение платежа',
    flat        SMALLINT UNSIGNED NULL COMMENT 'Квартира (указывается при доработке)',
    reason      VARCHAR(100)  NOT NULL COMMENT 'Почему платёж не разнесён при загрузке',
    note        VARCHAR(255)  NULL COMMENT 'Комментарий',
    status      ENUM('new', 'ignored') NOT NULL DEFAULT 'new' COMMENT 'new — ждёт разнесения, ignored — исключён (не квартплата)',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    bank_ref    CHAR(40)      NOT NULL COMMENT 'Отпечаток операции выписки',
    PRIMARY KEY (id),
    UNIQUE KEY uq_pending_bank_ref (bank_ref),
    KEY ix_pending_status (status, posted),
    CONSTRAINT fk_pending_import FOREIGN KEY (import_id) REFERENCES bank_imports (id)
        ON DELETE CASCADE,
    CONSTRAINT chk_pending_amount CHECK (amount > 0)
) ENGINE = InnoDB COMMENT = 'Неразнесённые платежи из банковских выписок';
