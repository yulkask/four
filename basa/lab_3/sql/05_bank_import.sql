-- Импорт банковской выписки: изменения для уже созданной БД
-- (на новой БД то же самое создаёт 01_schema.sql)
SET NAMES utf8mb4;
USE kvartplata;

CREATE TABLE IF NOT EXISTS bank_imports (
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

ALTER TABLE accounts
    MODIFY area DECIMAL(6,2) NULL COMMENT 'Общая площадь, м² (у счетов из банковской выписки может быть неизвестна)',
    ADD COLUMN import_id INT UNSIGNED NULL COMMENT 'Загрузка выписки, при которой счёт создан автоматически' AFTER residents,
    ADD CONSTRAINT fk_accounts_import FOREIGN KEY (import_id) REFERENCES bank_imports (id)
        ON DELETE SET NULL;

ALTER TABLE payments
    ADD COLUMN payer     VARCHAR(255) NULL COMMENT 'Плательщик (из банковской выписки)',
    ADD COLUMN purpose   VARCHAR(500) NULL COMMENT 'Назначение платежа (из банковской выписки)',
    ADD COLUMN import_id INT UNSIGNED NULL COMMENT 'Загрузка выписки, из которой получен платёж',
    ADD COLUMN bank_ref  CHAR(40)     NULL COMMENT 'Отпечаток операции выписки: защита от повторной загрузки',
    ADD UNIQUE KEY uq_payments_bank_ref (bank_ref),
    ADD CONSTRAINT fk_payments_import FOREIGN KEY (import_id) REFERENCES bank_imports (id)
        ON DELETE CASCADE;
