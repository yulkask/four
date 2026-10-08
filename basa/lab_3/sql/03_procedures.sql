-- Пункт 4. Модули вывода информации на основе хранимых процедур
--   sp_turnover_sheet      — оборотная ведомость за год по всем квартирам
--   sp_account_turnover    — оборотная ведомость по одной квартире
--   sp_debtors             — сводка по категориям должников
-- Вспомогательные:
--   fn_saldo               — сальдо лицевого счёта на заданную дату
--   sp_close_month         — закрытие месяца (запись сальдо на начало следующего)

SET NAMES utf8mb4;
USE kvartplata;

DROP FUNCTION  IF EXISTS fn_saldo;
DROP PROCEDURE IF EXISTS sp_turnover_sheet;
DROP PROCEDURE IF EXISTS sp_account_turnover;
DROP PROCEDURE IF EXISTS sp_debtors;
DROP PROCEDURE IF EXISTS sp_close_month;

DELIMITER $$

-- Сальдо на начало дня p_date: последнее зафиксированное в saldo значение
-- плюс начисления и минус платежи после него и до p_date
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

-- Оборотная ведомость за год.
-- Строка = квартира × месяц: начислено, оплачено, сальдо на конец месяца.
-- Месяцы после последнего месяца с движением в этом году не выводятся.
CREATE PROCEDURE sp_turnover_sheet(IN p_year SMALLINT)
    COMMENT 'Оборотная ведомость за год по всем квартирам'
BEGIN
    DECLARE v_start DATE DEFAULT MAKEDATE(p_year, 1);
    DECLARE v_last  TINYINT;

    SELECT MAX(m) INTO v_last FROM (
        SELECT MONTH(period) AS m FROM charges WHERE YEAR(period) = p_year
        UNION ALL
        SELECT MONTH(pay_date) FROM payments WHERE YEAR(pay_date) = p_year
    ) t;

    WITH RECURSIVE months AS (
        SELECT 1 AS m
        UNION ALL
        SELECT m + 1 FROM months WHERE m < COALESCE(v_last, 0)
    ),
    ch AS (
        SELECT account_id, MONTH(period) AS m, SUM(amount) AS amount
        FROM charges WHERE YEAR(period) = p_year
        GROUP BY account_id, MONTH(period)
    ),
    pay AS (
        SELECT account_id, MONTH(pay_date) AS m, SUM(amount) AS amount
        FROM payments WHERE YEAR(pay_date) = p_year
        GROUP BY account_id, MONTH(pay_date)
    ),
    grid AS (
        SELECT a.id AS account_id, a.flat, fn_saldo(a.id, v_start) AS saldo_in,
               mo.m, COALESCE(ch.amount, 0) AS charged, COALESCE(pay.amount, 0) AS paid
        FROM accounts a
        CROSS JOIN months mo
        LEFT JOIN ch  ON ch.account_id  = a.id AND ch.m  = mo.m
        LEFT JOIN pay ON pay.account_id = a.id AND pay.m = mo.m
    )
    SELECT account_id, flat, saldo_in, m AS month, charged, paid,
           saldo_in + SUM(charged - paid) OVER (PARTITION BY account_id ORDER BY m) AS saldo_out
    FROM grid
    ORDER BY flat, m;
END$$

-- Оборотная ведомость по квартире за год. Два набора результатов:
--   1) по месяцам: начислено, оплачено, сальдо на конец месяца;
--   2) итоги: сальдо на начало года, всего начислено/оплачено,
--      долг (+) / переплата (−) за предыдущие периоды, итого к оплате.
CREATE PROCEDURE sp_account_turnover(IN p_account_id INT UNSIGNED, IN p_year SMALLINT)
    COMMENT 'Начисления и платежи по месяцам для одной квартиры'
BEGIN
    DECLARE v_start   DATE DEFAULT MAKEDATE(p_year, 1);
    DECLARE v_saldo   DECIMAL(12,2) DEFAULT fn_saldo(p_account_id, v_start);
    DECLARE v_charged, v_paid, v_last_charge DECIMAL(12,2);

    WITH RECURSIVE months AS (
        SELECT 1 AS m UNION ALL SELECT m + 1 FROM months WHERE m < 12
    ),
    grid AS (
        SELECT mo.m,
               (SELECT COALESCE(SUM(amount), 0) FROM charges
                 WHERE account_id = p_account_id
                   AND period = DATE_ADD(v_start, INTERVAL mo.m - 1 MONTH)) AS charged,
               (SELECT COALESCE(SUM(amount), 0) FROM payments
                 WHERE account_id = p_account_id
                   AND YEAR(pay_date) = p_year AND MONTH(pay_date) = mo.m) AS paid
        FROM months mo
    )
    SELECT m AS month, charged, paid,
           v_saldo + SUM(charged - paid) OVER (ORDER BY m) AS saldo_out
    FROM grid
    ORDER BY m;

    SELECT COALESCE(SUM(amount), 0) INTO v_charged
    FROM charges WHERE account_id = p_account_id AND YEAR(period) = p_year;

    SELECT COALESCE(SUM(amount), 0) INTO v_paid
    FROM payments WHERE account_id = p_account_id AND YEAR(pay_date) = p_year;

    -- начисление последнего месяца с начислениями (текущий счёт к оплате)
    SELECT COALESCE(SUM(amount), 0) INTO v_last_charge
    FROM charges
    WHERE account_id = p_account_id
      AND period = (SELECT MAX(period) FROM charges
                    WHERE account_id = p_account_id AND YEAR(period) = p_year);

    SELECT a.account_no, a.flat, a.owner,
           v_saldo                                   AS saldo_in,
           v_charged                                 AS total_charged,
           v_paid                                    AS total_paid,
           v_saldo + v_charged - v_paid - v_last_charge AS debt_prev,
           v_saldo + v_charged - v_paid              AS to_pay
    FROM accounts a
    WHERE a.id = p_account_id;
END$$

-- Сводка по категориям должников на дату p_date (берётся 1-е число месяца).
-- Задолженность относится к категории «N месяцев», где N — наименьшее число
-- последних месяцев, начисления за которые покрывают сумму долга.
CREATE PROCEDURE sp_debtors(IN p_date DATE)
    COMMENT 'Должники по категориям (1, 2, 3, свыше 3 месяцев)'
BEGIN
    DECLARE v_date DATE DEFAULT DATE_FORMAT(p_date, '%Y-%m-01');

    WITH monthly AS (
        SELECT account_id, period, SUM(amount) AS amount
        FROM charges
        WHERE period < v_date
        GROUP BY account_id, period
    ),
    cum AS (
        SELECT account_id, period, amount,
               SUM(amount) OVER (PARTITION BY account_id ORDER BY period DESC) AS total
        FROM monthly
    ),
    debt AS (
        SELECT a.id, a.flat, a.account_no, a.owner,
               fn_saldo(a.id, v_date) AS saldo,
               (SELECT COALESCE(SUM(amount), 0) FROM monthly
                 WHERE account_id = a.id
                   AND period = DATE_SUB(v_date, INTERVAL 1 MONTH)) AS last_charge
        FROM accounts a
    ),
    graded AS (
        SELECT d.*,
               1 + (SELECT COUNT(*) FROM cum
                     WHERE cum.account_id = d.id AND cum.total < d.saldo) AS months
        FROM debt d
        WHERE d.saldo > 0
    )
    SELECT flat, account_no, owner, last_charge, saldo, months,
           IF(months = 1, saldo, NULL) AS debt_1,
           IF(months = 2, saldo, NULL) AS debt_2,
           IF(months = 3, saldo, NULL) AS debt_3,
           IF(months > 3, saldo, NULL) AS debt_over_3
    FROM graded
    ORDER BY flat;
END$$

-- Закрытие месяца: фиксирует сальдо на начало месяца, следующего за p_period.
-- Повторный вызов пересчитывает ранее записанные значения.
CREATE PROCEDURE sp_close_month(IN p_period DATE)
    COMMENT 'Записать в saldo сальдо на начало следующего месяца'
BEGIN
    DECLARE v_next DATE DEFAULT DATE_ADD(DATE_FORMAT(p_period, '%Y-%m-01'), INTERVAL 1 MONTH);

    -- старая запись мешала бы расчёту: fn_saldo взял бы её как отправную точку
    DELETE FROM saldo WHERE period = v_next;

    DROP TEMPORARY TABLE IF EXISTS tmp_saldo;
    CREATE TEMPORARY TABLE tmp_saldo AS
        SELECT id AS account_id, fn_saldo(id, v_next) AS amount FROM accounts;

    INSERT INTO saldo (account_id, period, amount)
    SELECT account_id, v_next, amount FROM tmp_saldo;

    SELECT COUNT(*) AS accounts, v_next AS period FROM tmp_saldo;
    DROP TEMPORARY TABLE tmp_saldo;
END$$

DELIMITER ;
