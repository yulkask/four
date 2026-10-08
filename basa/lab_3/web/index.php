<?php
// Главная страница: краткая сводка и ссылки на разделы.
require __DIR__ . '/lib.php';

layout_start('Учёт квартплаты', 'index.php');
try {
    $s = db()->query("SELECT
        (SELECT COUNT(*) FROM accounts)                AS accounts,
        (SELECT COALESCE(SUM(amount), 0) FROM charges)  AS charged,
        (SELECT COALESCE(SUM(amount), 0) FROM payments) AS paid,
        (SELECT MAX(period) FROM charges)               AS last_period,
        (SELECT SUM(GREATEST(fn_saldo(id, CURDATE() + INTERVAL 1 DAY), 0)) FROM accounts) AS debt")->fetch();
    ?>
    <div class="grid">
        <div class="card stat"><b><?= (int)$s['accounts'] ?></b><span>лицевых счетов</span></div>
        <div class="card stat"><b><?= money($s['charged']) ?></b><span>начислено всего</span></div>
        <div class="card stat"><b><?= money($s['paid']) ?></b><span>оплачено всего</span></div>
        <div class="card stat"><b class="debt"><?= money($s['debt']) ?></b><span>текущая задолженность</span></div>
    </div>
    <div class="grid">
        <div class="card">
            <h2>Ввод данных</h2>
            <p><a href="edit.php?t=accounts">Лицевые счета</a> — квартиры и квартиросъёмщики</p>
            <p><a href="edit.php?t=saldo">Сальдо</a> — входящее сальдо, закрытие месяца</p>
            <p><a href="edit.php?t=charges">Начисления</a> — по услугам за месяц
                <?php if ($s['last_period']): ?><span class="muted">(последний: <?= MONTHS[(int)substr($s['last_period'], 5, 2)] . ' ' . substr($s['last_period'], 0, 4) ?>)</span><?php endif ?></p>
            <p><a href="edit.php?t=payments">Платежи</a> — поступления на расчётный счёт</p>
        </div>
        <div class="card">
            <h2>Отчёты (хранимые процедуры)</h2>
            <p><a href="turnover.php">Оборотная ведомость</a> <span class="sql">sp_turnover_sheet</span></p>
            <p><a href="account.php">Оборотная ведомость по квартире</a> <span class="sql">sp_account_turnover</span></p>
            <p><a href="debtors.php">Сводка по категориям должников</a> <span class="sql">sp_debtors</span></p>
            <p class="muted">phpMyAdmin: <a href="http://localhost:8081">localhost:8081</a></p>
        </div>
    </div>
    <?php
} catch (PDOException $e) {
    error_card($e);
}
layout_end();
