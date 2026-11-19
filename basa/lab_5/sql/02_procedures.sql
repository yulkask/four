-- Процедуры, которые вызывают события. Тело события — один CALL,
-- поэтому его видно в information_schema.EVENTS целиком.

SET NAMES utf8mb4;
USE kvartplata;

DELIMITER $$

-- Сальдо на начало даты: последняя запись saldo плюс начисления
-- минус платежи с этой даты и до p_date.
CREATE FUNCTION fn_saldo(p_account_id INT UNSIGNED, p_date DATE)
    RETURNS DECIMAL(12,2)
    READS SQL DATA
    COMMENT 'Сальдо лицевого счёта на начало даты'
BEGIN
    DECLARE v_from   DATE DEFAULT '1000-01-01';
    DECLARE v_amount DECIMAL(12,2) DEFAULT 0;
    DECLARE v_charged, v_paid DECIMAL(12,2);

    SELECT period, amount INTO v_from, v_amount
    FROM saldo
    WHERE account_id = p_account_id AND period <= p_date
    ORDER BY period DESC
    LIMIT 1;

    SELECT COALESCE(SUM(amount), 0) INTO v_charged
    FROM charges
    WHERE account_id = p_account_id AND period >= v_from AND period < p_date;

    SELECT COALESCE(SUM(amount), 0) INTO v_paid
    FROM payments
    WHERE account_id = p_account_id AND pay_date >= v_from AND pay_date < p_date;

    RETURN v_amount + v_charged - v_paid;
END$$

-- Пункт 5, обновление агрегированных показателей.
-- По каждой квартире и каждому месяцу, где есть начисления:
-- начислено, оплачено, сальдо на конец месяца.
CREATE PROCEDURE sp_refresh_summary()
    COMMENT 'Пересчитать помесячные итоги'
BEGIN
    DECLARE v_rows INT DEFAULT 0;

    DELETE FROM monthly_summary;

    INSERT INTO monthly_summary (account_id, period, charged, paid, closing_balance, updated_at)
    SELECT a.id,
           m.period,
           COALESCE(c.charged, 0),
           COALESCE(p.paid, 0),
           fn_saldo(a.id, DATE_ADD(m.period, INTERVAL 1 MONTH)),
           NOW()
    FROM accounts a
    JOIN (SELECT DISTINCT period FROM charges) m
    LEFT JOIN (
        SELECT account_id, period, SUM(amount) AS charged
        FROM charges
        GROUP BY account_id, period
    ) c ON c.account_id = a.id AND c.period = m.period
    LEFT JOIN (
        SELECT account_id,
               CAST(DATE_FORMAT(pay_date, '%Y-%m-01') AS DATE) AS period,
               SUM(amount) AS paid
        FROM payments
        GROUP BY account_id, CAST(DATE_FORMAT(pay_date, '%Y-%m-01') AS DATE)
    ) p ON p.account_id = a.id AND p.period = m.period;

    SET v_rows = ROW_COUNT();
    INSERT INTO event_log (event_name, affected, message)
    VALUES ('ev_refresh_summary', v_rows, 'пересчитаны помесячные итоги');
END$$

-- Пункт 5, архивирование. Платежи раньше границы archive_before
-- копируются в payments_archive и удаляются из payments.
-- Повторный вызов ничего не переносит: таких платежей уже нет.
CREATE PROCEDURE sp_archive_payments()
    COMMENT 'Перенести старые платежи в архив'
BEGIN
    DECLARE v_before DATE;
    DECLARE v_rows INT DEFAULT 0;

    SELECT CAST(value AS DATE) INTO v_before
    FROM scheduler_settings
    WHERE name = 'archive_before';

    INSERT INTO payments_archive (id, account_id, pay_date, amount, source)
    SELECT id, account_id, pay_date, amount, source
    FROM payments
    WHERE pay_date < v_before;

    SET v_rows = ROW_COUNT();

    DELETE FROM payments WHERE pay_date < v_before;

    INSERT INTO event_log (event_name, affected, message)
    VALUES ('ev_archive_old_payments', v_rows,
            CONCAT('в архив перенесено платежей старше ', v_before));
END$$

-- Пункт 5, очистка устаревших записей.
CREATE PROCEDURE sp_purge_notices()
    COMMENT 'Удалить объявления с истёкшим сроком'
BEGIN
    DECLARE v_rows INT DEFAULT 0;

    DELETE FROM notices WHERE expires_at < NOW();
    SET v_rows = ROW_COUNT();

    INSERT INTO event_log (event_name, affected, message)
    VALUES ('ev_purge_notices', v_rows, 'удалены просроченные объявления');
END$$

DELIMITER ;
