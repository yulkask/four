-- Неразнесённые платежи: изменения для уже созданной БД
-- (на новой БД то же самое создаёт 01_schema.sql)
SET NAMES utf8mb4;
USE kvartplata;

-- Неразнесённые платежи из выписки: поступления, которые не удалось сразу отнести
-- к лицевому счёту. Хранятся до доработки, затем переносятся в payments
CREATE TABLE IF NOT EXISTS bank_pending (
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
