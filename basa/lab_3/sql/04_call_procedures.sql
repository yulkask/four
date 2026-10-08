-- Проверка хранимых процедур 

SET NAMES utf8mb4;
USE kvartplata;

-- Сальдо отдельных счетов на дату
SELECT flat, owner,
       fn_saldo(id, '2026-01-01') AS saldo_01_01,
       fn_saldo(id, '2026-10-01') AS saldo_01_10
FROM accounts ORDER BY flat;

-- Модуль 1. Оборотная ведомость за год (квартира × месяц)
CALL sp_turnover_sheet(2026);

-- Модуль 2. Оборотная ведомость по квартире: помесячно + итоги (два набора)
CALL sp_account_turnover(1, 2026);
CALL sp_account_turnover(6, 2026);       -- квартира с переплатой

-- Модуль 3. Должники по категориям
CALL sp_debtors('2026-10-01');
CALL sp_debtors('2026-07-01');

-- Закрытие месяца: сальдо на 01.10.2026 записывается в таблицу saldo
CALL sp_close_month('2026-09-01');
SELECT a.flat, s.period, s.amount
FROM saldo s JOIN accounts a ON a.id = s.account_id
WHERE s.period = '2026-10-01' ORDER BY a.flat;

-- Сверка: сальдо на конец = сальдо на начало + начислено − оплачено
SELECT a.flat,
       fn_saldo(a.id, '2026-01-01')
         + (SELECT COALESCE(SUM(amount), 0) FROM charges  WHERE account_id = a.id AND period   < '2026-10-01')
         - (SELECT COALESCE(SUM(amount), 0) FROM payments WHERE account_id = a.id AND pay_date < '2026-10-01') AS by_hand,
       fn_saldo(a.id, '2026-10-01') AS by_function
FROM accounts a ORDER BY a.flat;
