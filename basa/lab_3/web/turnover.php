<?php
// Пункт 4, модуль 1. Оборотная ведомость за год (процедура sp_turnover_sheet).
// В клетке за месяц: 1-я строка — начислено, 2-я — оплачено, 3-я — сальдо на конец месяца.
require __DIR__ . '/lib.php';

layout_start('Оборотная ведомость', 'turnover.php');
try {
    $years = years();
    $year = in_array((int)($_GET['year'] ?? 0), $years) ? (int)$_GET['year'] : $years[0];
    [$rows] = call_proc('sp_turnover_sheet', [$year]);

    // сворачиваем «квартира × месяц» в строки по квартирам
    $sheet = [];
    foreach ($rows as $r) {
        $sheet[$r['flat']] ??= ['saldo_in' => $r['saldo_in'], 'months' => [], 'saldo_out' => $r['saldo_in']];
        $sheet[$r['flat']]['months'][(int)$r['month']] = $r;
        $sheet[$r['flat']]['saldo_out'] = $r['saldo_out'];
    }
    // итоги по дому
    $tot = ['saldo_in' => 0, 'saldo_out' => 0, 'months' => []];
    foreach ($sheet as $s) {
        $tot['saldo_in'] += $s['saldo_in'];
        $tot['saldo_out'] += $s['saldo_out'];
        foreach ($s['months'] as $m => $r) {
            $tot['months'][$m]['charged'] = ($tot['months'][$m]['charged'] ?? 0) + $r['charged'];
            $tot['months'][$m]['paid'] = ($tot['months'][$m]['paid'] ?? 0) + $r['paid'];
            $tot['months'][$m]['saldo_out'] = ($tot['months'][$m]['saldo_out'] ?? 0) + $r['saldo_out'];
        }
    }
    ?>
    <form class="card row" method="get">
        <div class="field"><label>Год</label>
            <select name="year" onchange="this.form.submit()">
                <?php foreach ($years as $y): ?><option <?= $y == $year ? 'selected' : '' ?>><?= $y ?></option><?php endforeach ?>
            </select></div>
        <button type="button" class="btn light" onclick="print()">Печать</button>
        <span class="sql">CALL sp_turnover_sheet(<?= $year ?>);</span>
    </form>

    <div class="card">
        <h2 style="text-align:center">Оборотная ведомость за <?= $year ?> год</h2>
        <div class="legend"><span>В клетке: 1 — начислено</span><span>2 — оплачено</span>
            <span><b>3 — сальдо на конец месяца</b> (<span class="debt">+ долг</span> / <span class="over">− переплата</span>)</span></div>
        <div class="table-wrap">
        <table class="sheet">
            <thead><tr>
                <th>Квартира</th><th>Вх. сальдо</th>
                <?php foreach (MONTHS as $name): ?><th><?= $name ?></th><?php endforeach ?>
                <th>Исх. сальдо</th>
            </tr></thead>
            <tbody>
            <?php foreach ($sheet + ['Итого' => $tot] as $flat => $s): ?>
            <tr <?= $flat === 'Итого' ? 'class="total"' : '' ?>>
                <td><b><?= h((string)$flat) ?></b></td>
                <td class="num <?= sign_class($s['saldo_in']) ?>"><?= money($s['saldo_in']) ?></td>
                <?php foreach (MONTHS as $m => $_): $r = $s['months'][$m] ?? null; ?>
                    <?php if ($r): ?>
                        <td class="cell"><div><?= money($r['charged']) ?></div><div><?= money($r['paid']) ?></div>
                            <div class="<?= sign_class($r['saldo_out']) ?>"><?= money($r['saldo_out']) ?></div></td>
                    <?php else: ?>
                        <td class="cell muted">—</td>
                    <?php endif ?>
                <?php endforeach ?>
                <td class="num <?= sign_class($s['saldo_out']) ?>"><b><?= money($s['saldo_out']) ?></b></td>
            </tr>
            <?php endforeach ?>
            </tbody>
        </table>
        </div>
    </div>
    <?php
} catch (PDOException $e) {
    error_card($e);
}
layout_end();
