<?php
// Пункт 4, модуль 3. Сводка по категориям должников (процедура sp_debtors).
require __DIR__ . '/lib.php';

layout_start('Должники по категориям', 'debtors.php');
try {
    $date = preg_match('/^\d{4}-\d{2}-\d{2}$/', $_GET['date'] ?? '') ? $_GET['date']
          : (db()->query("SELECT DATE_ADD(MAX(period), INTERVAL 1 MONTH) FROM charges")->fetchColumn() ?: date('Y-m-01'));
    $date = date('Y-m-01', strtotime($date));
    [$rows] = call_proc('sp_debtors', [$date]);
    $cols = ['debt_1' => '1 месяц', 'debt_2' => '2 месяца', 'debt_3' => '3 месяца', 'debt_over_3' => 'Свыше 3 месяцев'];
    ?>
    <form class="card row" method="get">
        <div class="field"><label>По состоянию на (1-е число месяца)</label>
            <input type="date" name="date" value="<?= h($date) ?>" onchange="this.form.submit()"></div>
        <button type="button" class="btn light" onclick="print()">Печать</button>
        <span class="sql">CALL sp_debtors('<?= h($date) ?>');</span>
    </form>

    <div class="card">
        <h2 style="text-align:center">Должники по категориям по состоянию на <?= date('d.m.Y', strtotime($date)) ?></h2>
        <div class="table-wrap">
        <table class="acc">
            <tr>
                <th rowspan="2">Квартира</th><th rowspan="2">Лицевой счёт</th><th rowspan="2">Квартиросъёмщик</th>
                <th rowspan="2">Начислено<br>за последний месяц</th><th rowspan="2">Сальдо</th>
                <th colspan="4">Задолженность</th>
            </tr>
            <tr><?php foreach ($cols as $label): ?><th><?= $label ?></th><?php endforeach ?></tr>
            <?php foreach ($rows as $r): ?>
            <tr>
                <td><?= (int)$r['flat'] ?></td>
                <td><?= h($r['account_no']) ?></td>
                <td style="text-align:left"><?= h($r['owner']) ?></td>
                <td class="num"><?= money($r['last_charge']) ?></td>
                <td class="num debt"><?= money($r['saldo']) ?></td>
                <?php foreach ($cols as $c => $_): ?><td class="num"><?= money($r[$c]) ?></td><?php endforeach ?>
            </tr>
            <?php endforeach ?>
            <tr class="total">
                <td colspan="3" style="text-align:left">Итого (должников: <?= count($rows) ?>)</td>
                <td class="num"><?= money(array_sum(array_column($rows, 'last_charge'))) ?></td>
                <td class="num debt"><?= money(array_sum(array_column($rows, 'saldo'))) ?></td>
                <?php foreach ($cols as $c => $_): ?><td class="num"><?= money(array_sum(array_column($rows, $c)), true) ?></td><?php endforeach ?>
            </tr>
        </table>
        </div>
        <p class="muted">Категория — наименьшее число последних месяцев, начисления за которые покрывают сумму долга.</p>
    </div>
    <?php
} catch (PDOException $e) {
    error_card($e);
}
layout_end();
