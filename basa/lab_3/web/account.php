<?php
// Пункт 4, модуль 2. Оборотная ведомость по квартире (процедура sp_account_turnover).
require __DIR__ . '/lib.php';

layout_start('Оборотная ведомость по квартире', 'account.php');
try {
    $accounts = accounts();
    $years = years();
    $year = in_array((int)($_GET['year'] ?? 0), $years) ? (int)$_GET['year'] : $years[0];
    $ids = array_column($accounts, 'id');
    $id = in_array((int)($_GET['account'] ?? 0), $ids) ? (int)$_GET['account'] : ($ids[0] ?? 0);
    [$months, [$sum]] = call_proc('sp_account_turnover', [$id, $year]);
    ?>
    <form class="card row" method="get">
        <div class="field"><label>Квартира</label>
            <select name="account" onchange="this.form.submit()">
                <?php foreach ($accounts as $a): ?>
                    <option value="<?= $a['id'] ?>" <?= $a['id'] == $id ? 'selected' : '' ?>>кв. <?= $a['flat'] ?> — <?= h($a['owner']) ?></option>
                <?php endforeach ?>
            </select></div>
        <div class="field"><label>Год</label>
            <select name="year" onchange="this.form.submit()">
                <?php foreach ($years as $y): ?><option <?= $y == $year ? 'selected' : '' ?>><?= $y ?></option><?php endforeach ?>
            </select></div>
        <button type="button" class="btn light" onclick="print()">Печать</button>
        <span class="sql">CALL sp_account_turnover(<?= $id ?>, <?= $year ?>);</span>
    </form>

    <div class="card">
        <h2 style="text-align:center">Начисления и платежи по месяцам за <?= $year ?> год
            <span class="muted">(платежи учитываются в месяце поступления на расчётный счёт)</span></h2>
        <p>Квартира <b><?= (int)$sum['flat'] ?></b>, лицевой счёт <b><?= h($sum['account_no']) ?></b>, <?= h($sum['owner']) ?></p>
        <div class="table-wrap">
        <table class="acc">
            <tr>
                <th>На начало года<br>(+ долг / − переплата)</th><th></th>
                <?php foreach (MONTHS as $m => $_): ?><th><?= sprintf('%02d', $m) ?></th><?php endforeach ?>
                <th>Итого</th>
                <th>+ долг / − переплата<br>(за пред. период)</th>
            </tr>
            <tr>
                <td rowspan="2" class="big <?= sign_class($sum['saldo_in']) ?>"><?= money($sum['saldo_in']) ?></td>
                <th>Начис.</th>
                <?php foreach ($months as $r): ?><td class="num"><?= money($r['charged']) ?></td><?php endforeach ?>
                <td class="num"><b><?= money($sum['total_charged']) ?></b></td>
                <td rowspan="2" class="big <?= sign_class($sum['debt_prev']) ?>"><?= money($sum['debt_prev']) ?></td>
            </tr>
            <tr>
                <th>Опл.</th>
                <?php foreach ($months as $r): ?><td class="num"><?= money($r['paid']) ?></td><?php endforeach ?>
                <td class="num"><b><?= money($sum['total_paid']) ?></b></td>
            </tr>
            <tr>
                <th colspan="2" class="num">Сальдо на конец месяца</th>
                <?php foreach ($months as $r): ?><td class="num <?= sign_class($r['saldo_out']) ?>"><?= money($r['saldo_out']) ?></td><?php endforeach ?>
                <td colspan="2"></td>
            </tr>
            <tr class="total">
                <td colspan="<?= count(MONTHS) + 3 ?>" class="num"><?= (float)$sum['to_pay'] >= 0 ? 'Итого к оплате:' : 'Переплата:' ?></td>
                <td class="big <?= sign_class($sum['to_pay']) ?>"><?= money(abs((float)$sum['to_pay'])) ?></td>
            </tr>
        </table>
        </div>
    </div>
    <?php
} catch (PDOException $e) {
    error_card($e);
}
layout_end();
