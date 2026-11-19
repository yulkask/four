-- Лабораторная 5. Шесть пунктов задания подряд.
-- Планировщик при старте сервера выключен (--event-scheduler=OFF).

USE kvartplata;

-- ---------------------------------------------------------------- 1
SELECT '1. Планировщик до включения' AS step;
SHOW VARIABLES LIKE 'event_scheduler';

SET GLOBAL event_scheduler = ON;

SELECT '1. Планировщик после SET GLOBAL event_scheduler = ON' AS step;
SHOW VARIABLES LIKE 'event_scheduler';

-- ---------------------------------------------------------------- 2, 3
-- Повторяющееся событие: в учебной базе каждые 10 секунд,
-- чтобы выполнение было видно сразу. Боевое расписание — раз в месяц,
-- его ставим ниже командой ALTER EVENT.
SELECT '2–3. Создание событий' AS step;

DROP EVENT IF EXISTS ev_refresh_summary;
CREATE EVENT ev_refresh_summary
    ON SCHEDULE EVERY 10 SECOND
    STARTS CURRENT_TIMESTAMP
    ON COMPLETION PRESERVE
    ENABLE
    COMMENT 'Пересчёт помесячных итогов квартплаты'
    DO CALL sp_refresh_summary();

DROP EVENT IF EXISTS ev_purge_notices;
CREATE EVENT ev_purge_notices
    ON SCHEDULE EVERY 10 SECOND
    STARTS CURRENT_TIMESTAMP
    ON COMPLETION PRESERVE
    ENABLE
    COMMENT 'Очистка объявлений с истёкшим сроком'
    DO CALL sp_purge_notices();

-- Однократное событие: сработает через 5 секунд и останется в списке
-- (ON COMPLETION PRESERVE), статус станет DISABLED.
DROP EVENT IF EXISTS ev_archive_old_payments;
CREATE EVENT ev_archive_old_payments
    ON SCHEDULE AT CURRENT_TIMESTAMP + INTERVAL 5 SECOND
    ON COMPLETION PRESERVE
    ENABLE
    COMMENT 'Однократный перенос старых платежей в архив'
    DO CALL sp_archive_payments();

SELECT '3. Расписание сразу после создания' AS step;
SELECT EVENT_NAME, EVENT_TYPE, STATUS, INTERVAL_VALUE, INTERVAL_FIELD,
       EXECUTE_AT, STARTS, LAST_EXECUTED, EVENT_COMMENT
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'kvartplata'
ORDER BY EVENT_NAME;

-- ---------------------------------------------------------------- 4, 5
SELECT 'Ожидание 25 секунд, пока события выполнятся' AS step;
DO SLEEP(25);

SELECT '4. Статус и время последнего запуска' AS step;
SELECT EVENT_NAME, STATUS, EVENT_TYPE, LAST_EXECUTED
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'kvartplata'
ORDER BY EVENT_NAME;

SELECT '4. Журнал выполнения' AS step;
SELECT id, event_name, ran_at, affected, message
FROM event_log
ORDER BY id;

SELECT '5. Помесячные итоги (начислено, оплачено, сальдо на конец месяца)' AS step;
SELECT a.flat, s.period, s.charged, s.paid, s.closing_balance, s.updated_at
FROM monthly_summary s
JOIN accounts a ON a.id = s.account_id
ORDER BY a.flat, s.period;

SELECT '5. Сверка итогов с ручным расчётом' AS step;
SELECT a.flat, s.period, s.charged, s.paid, s.closing_balance,
       CASE
           WHEN a.flat = 1 AND s.period = '2026-09-01' THEN 1500.00
           WHEN a.flat = 1 AND s.period = '2026-10-01' THEN 1600.00
           WHEN a.flat = 2 AND s.period = '2026-09-01' THEN  200.00
           WHEN a.flat = 2 AND s.period = '2026-10-01' THEN  500.00
           WHEN a.flat = 3 AND s.period = '2026-09-01' THEN  150.00
           WHEN a.flat = 3 AND s.period = '2026-10-01' THEN  200.00
       END AS expected,
       s.closing_balance = CASE
           WHEN a.flat = 1 AND s.period = '2026-09-01' THEN 1500.00
           WHEN a.flat = 1 AND s.period = '2026-10-01' THEN 1600.00
           WHEN a.flat = 2 AND s.period = '2026-09-01' THEN  200.00
           WHEN a.flat = 2 AND s.period = '2026-10-01' THEN  500.00
           WHEN a.flat = 3 AND s.period = '2026-09-01' THEN  150.00
           WHEN a.flat = 3 AND s.period = '2026-10-01' THEN  200.00
       END AS ok
FROM monthly_summary s
JOIN accounts a ON a.id = s.account_id
ORDER BY a.flat, s.period;

SELECT '5. Архив и оставшиеся платежи' AS step;
SELECT id, account_id, pay_date, amount, source, archived_at
FROM payments_archive
ORDER BY pay_date;

SELECT id, account_id, pay_date, amount, source
FROM payments
ORDER BY pay_date;

SELECT '5. Объявления после очистки' AS step;
SELECT id, body, expires_at FROM notices ORDER BY id;

-- ---------------------------------------------------------------- 3 (изменение расписания), 6
SELECT '3. Перевод пересчёта итогов на ежемесячное расписание' AS step;
ALTER EVENT ev_refresh_summary
    ON SCHEDULE EVERY 1 MONTH
    STARTS '2026-12-01 00:05:00'
    COMMENT 'Пересчёт итогов: 1-го числа в 00:05';

SELECT EVENT_NAME, INTERVAL_VALUE, INTERVAL_FIELD, STARTS, STATUS
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'kvartplata' AND EVENT_NAME = 'ev_refresh_summary';

SELECT '6. Отключение очистки объявлений' AS step;
ALTER EVENT ev_purge_notices DISABLE;

SELECT EVENT_NAME, STATUS
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'kvartplata'
ORDER BY EVENT_NAME;

SELECT '6. Удаление всех трёх событий' AS step;
DROP EVENT IF EXISTS ev_refresh_summary;
DROP EVENT IF EXISTS ev_purge_notices;
DROP EVENT IF EXISTS ev_archive_old_payments;

SELECT COUNT(*) AS events_left
FROM information_schema.EVENTS
WHERE EVENT_SCHEMA = 'kvartplata';

SELECT '6. Итог: события удалены, результат их работы на месте' AS step;
SELECT event_name, COUNT(*) AS runs, SUM(affected) AS affected_sum
FROM event_log
GROUP BY event_name
ORDER BY event_name;

SELECT
    (SELECT COUNT(*) FROM payments_archive) AS archived_payments,
    (SELECT COUNT(*) FROM payments)         AS payments_left,
    (SELECT COUNT(*) FROM monthly_summary)  AS summary_rows,
    (SELECT COUNT(*) FROM notices)          AS notices_left;
