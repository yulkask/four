<?php
// Загрузка платежей из банковской выписки (Excel, СберБизнес).
// Шаги: 1) загрузить файл; 2) проверить, к каким квартирам отнесены поступления,
// при необходимости поправить номер квартиры; 3) загрузить выбранные платежи.
// Каждая загрузка сохраняется в bank_imports и может быть отменена целиком.
require __DIR__ . '/lib.php';
require __DIR__ . '/bank_statement.php';

session_start();
$msg = $_GET['msg'] ?? null;
$error = null;

function back(string $msg = ''): never
{
    header('Location: import.php' . ($msg !== '' ? '?msg=' . urlencode($msg) : ''));
    exit;
}

try {
    $action = $_POST['action'] ?? '';

    // ---------- 1. загрузка файла ----------
    if ($action === 'upload') {
        $f = $_FILES['file'] ?? null;
        if (!$f || $f['error'] === UPLOAD_ERR_NO_FILE) {
            throw new RuntimeException('Выберите файл выписки');
        }
        if ($f['error'] !== UPLOAD_ERR_OK) {
            throw new RuntimeException('Файл не загрузился (код ошибки ' . $f['error'] . ')');
        }
        if (!preg_match('/\.xlsx$/i', $f['name'])) {
            throw new RuntimeException('Нужен файл Excel в формате .xlsx');
        }
        $st = parse_statement($f['tmp_name']);
        $_SESSION['bank'] = ['file' => $f['name'], 'account' => $st['account'], 'ops' => $st['ops']];
        header('Location: import.php?step=preview');
        exit;
    }

    if ($action === 'cancel') {
        unset($_SESSION['bank']);
        back();
    }

    // ---------- 3. запись платежей ----------
    if ($action === 'import') {
        $bank = $_SESSION['bank'] ?? throw new RuntimeException('Выписка не загружена или устарела — загрузите файл заново');
        $selected = array_map('intval', array_keys($_POST['sel'] ?? []));
        $flats = $_POST['flat'] ?? [];
        $create = isset($_POST['create']);
        $ops = $bank['ops'];

        $pdo = db();
        $accByFlat = $pdo->query('SELECT flat, id FROM accounts')->fetchAll(PDO::FETCH_KEY_PAIR);
        $exists = $pdo->prepare('SELECT 1 FROM payments WHERE bank_ref = ?');
        $insAcc = $pdo->prepare('INSERT INTO accounts (account_no, flat, owner, area, residents, import_id)
                                 VALUES (?, ?, ?, NULL, 1, ?)');
        $insPay = $pdo->prepare('INSERT INTO payments
            (account_id, pay_date, amount, source, doc_no, payer, purpose, import_id, bank_ref)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)');

        $dates = array_column($ops, 'posted');
        $pdo->beginTransaction();
        $pdo->prepare('INSERT INTO bank_imports (file_name, bank_account, date_from, date_to, ops_total)
                       VALUES (?, ?, ?, ?, ?)')
            ->execute([$bank['file'], $bank['account'], substr(min($dates), 0, 10),
                       substr(max($dates), 0, 10), count($ops)]);
        $importId = (int)$pdo->lastInsertId();

        $loaded = $sum = $newAcc = $skipped = 0;
        foreach ($selected as $i) {
            $op = $ops[$i] ?? null;
            $flat = (int)($flats[$i] ?? 0);
            if (!$op || $op['direction'] !== 'in' || $flat <= 0) {
                $skipped++;
                continue;
            }
            $exists->execute([$op['ref']]);
            if ($exists->fetchColumn()) {
                $skipped++;
                continue;
            }
            if (!isset($accByFlat[$flat])) {
                if (!$create) {
                    $skipped++;
                    continue;
                }
                $insAcc->execute([str_pad((string)$flat, 10, '0', STR_PAD_LEFT), $flat, owner_name($op['payer']), $importId]);
                $accByFlat[$flat] = (int)$pdo->lastInsertId();
                $newAcc++;
            }
            $insPay->execute([
                $accByFlat[$flat], substr($op['posted'], 0, 10), $op['amount'], 'Банк',
                $op['doc_no'], mb_substr(payer_parts($op['payer'])['name'], 0, 255),
                mb_substr($op['purpose'], 0, 500), $importId, $op['ref'],
            ]);
            $loaded++;
            $sum += $op['amount'];
        }
        if ($loaded === 0) {
            $pdo->rollBack();
            throw new RuntimeException('Ни один платёж не загружен: не выбраны строки, не указаны квартиры или платежи уже были загружены');
        }
        $pdo->prepare('UPDATE bank_imports SET ops_loaded = ?, amount = ? WHERE id = ?')
            ->execute([$loaded, $sum, $importId]);
        $pdo->commit();
        unset($_SESSION['bank']);
        back(sprintf('Загружено платежей: %d на сумму %s ₽%s%s', $loaded, money($sum),
            $newAcc ? ", создано лицевых счетов: $newAcc" : '',
            $skipped ? ", пропущено: $skipped" : ''));
    }

    // ---------- отмена загрузки ----------
    // лицевые счета, созданные этой загрузкой, удаляются, если по ним нет других данных
    if ($action === 'undo') {
        $id = (int)$_POST['id'];
        $pdo = db();
        $pdo->beginTransaction();
        $acc = $pdo->prepare('DELETE a FROM accounts a
            WHERE a.import_id = ?
              AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.account_id = a.id AND NOT (p.import_id <=> a.import_id))
              AND NOT EXISTS (SELECT 1 FROM charges c WHERE c.account_id = a.id)
              AND NOT EXISTS (SELECT 1 FROM saldo s WHERE s.account_id = a.id)');
        $acc->execute([$id]);
        $pdo->prepare('DELETE FROM bank_imports WHERE id = ?')->execute([$id]);
        $pdo->commit();
        back('Загрузка отменена: платежи удалены' . ($acc->rowCount() ? ', удалено созданных лицевых счетов: ' . $acc->rowCount() : ''));
    }
} catch (Throwable $e) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    $error = $e->getMessage();
}

// Владелец нового лицевого счёта — плательщик, если похоже на ФИО
function owner_name(string $payer): string
{
    $name = payer_parts($payer)['name'];
    if (preg_match('/^[А-ЯЁа-яё-]+(\s+[А-ЯЁа-яё.-]+){1,3}$/u', $name)) {
        return mb_convert_case(mb_strtolower($name), MB_CASE_TITLE);
    }
    return 'Не указан';
}

// ---------- 2. предварительный просмотр ----------
$bank = ($_GET['step'] ?? '') === 'preview' ? ($_SESSION['bank'] ?? null) : null;
$rows = [];
$stat = ['ok' => 0, 'new' => 0, 'none' => 0, 'dup' => 0];
if ($bank) {
    $pdo = db();
    $accByFlat = $pdo->query('SELECT flat, owner FROM accounts')->fetchAll(PDO::FETCH_KEY_PAIR);
    $known = array_flip($pdo->query('SELECT bank_ref FROM payments WHERE bank_ref IS NOT NULL')->fetchAll(PDO::FETCH_COLUMN));
    // по каким квартирам плательщик платил раньше (в базе) — если квартира одна, используем её
    $history = [];
    foreach ($pdo->query('SELECT p.payer, a.flat FROM payments p JOIN accounts a ON a.id = p.account_id
                          WHERE p.payer IS NOT NULL GROUP BY p.payer, a.flat') as $r) {
        $history[mb_strtoupper($r['payer'])][] = (int)$r['flat'];
    }

    foreach ($bank['ops'] as $i => $op) {
        if ($op['direction'] !== 'in') {
            continue;
        }
        $name = payer_parts($op['payer'])['name'];
        [$flat, $why] = detect_flat($op['purpose'], $op['payer']);
        $rows[$i] = ['op' => $op, 'name' => $name, 'flat' => $flat, 'why' => $why];
    }
    // тот же плательщик в других платежах этой выписки указал квартиру
    $byPayer = [];
    foreach ($rows as $r) {
        if ($r['flat']) $byPayer[mb_strtoupper($r['name'])][$r['flat']] = true;
    }
    foreach ($rows as &$r) {
        $key = mb_strtoupper($r['name']);
        if (!$r['flat'] && count($byPayer[$key] ?? []) === 1) {
            $r['flat'] = array_key_first($byPayer[$key]);
            $r['why'] = 'по другим платежам плательщика';
        } elseif (!$r['flat'] && count(array_unique($history[$key] ?? [])) === 1) {
            $r['flat'] = $history[$key][0];
            $r['why'] = 'по ранее загруженным платежам';
        }
        $r['status'] = isset($known[$r['op']['ref']]) ? 'dup'
                     : (!$r['flat'] ? 'none' : (isset($accByFlat[$r['flat']]) ? 'ok' : 'new'));
        $r['owner'] = $r['flat'] ? ($accByFlat[$r['flat']] ?? null) : null;
        $stat[$r['status']]++;
    }
    unset($r);
    $out = array_filter($bank['ops'], fn($o) => $o['direction'] === 'out');
}

$imports = db()->query('SELECT * FROM bank_imports ORDER BY id DESC')->fetchAll();

$statusText = [
    'ok'   => ['готов к загрузке', 'ok'],
    'new'  => ['новый лицевой счёт', 'warn'],
    'none' => ['квартира не определена', 'debt'],
    'dup'  => ['уже загружен', 'muted'],
];

layout_start('Импорт банковской выписки', 'import.php');
?>
    <?php if ($msg): ?><div class="card ok"><?= h($msg) ?></div><?php endif ?>
    <?php if ($error): ?><div class="card error">Ошибка: <?= h($error) ?></div><?php endif ?>

<?php if (!$bank): ?>
    <form class="card" method="post" enctype="multipart/form-data">
        <h2>Загрузка выписки</h2>
        <input type="hidden" name="action" value="upload">
        <div class="row">
            <div class="field"><label>Файл выписки (Excel .xlsx из СберБизнес)</label>
                <input type="file" name="file" accept=".xlsx" required></div>
            <button type="submit">Прочитать выписку</button>
        </div>
        <p class="muted">Из выписки берутся только поступления на расчётный счёт. Квартира определяется
            по назначению платежа («л/с 164», «кв. 12», «Осенний б-р 12-2-24», «ЛСЧ 0000000111») или
            по адресу плательщика. Перед загрузкой можно проверить и поправить номер квартиры.
            Повторная загрузка той же выписки не создаёт дублей.</p>
    </form>
<?php else: ?>
    <div class="grid">
        <div class="card stat"><b><?= count($bank['ops']) ?></b><span>операций в файле «<?= h($bank['file']) ?>»</span></div>
        <div class="card stat"><b><?= count($rows) ?></b><span>поступлений на сумму <?= money(array_sum(array_map(fn($r) => $r['op']['amount'], $rows))) ?></span></div>
        <div class="card stat"><b><?= $stat['ok'] + $stat['new'] ?></b><span>отнесены к квартирам</span></div>
        <div class="card stat"><b class="<?= $stat['none'] ? 'debt' : '' ?>"><?= $stat['none'] ?></b><span>требуют указать квартиру</span></div>
    </div>

    <form class="card" method="post">
        <input type="hidden" name="action" value="import">
        <div class="row" style="justify-content:space-between">
            <div class="row filters">
                <span class="muted">Показать:</span>
                <button type="button" class="btn light" data-f="all">все (<?= count($rows) ?>)</button>
                <button type="button" class="btn light" data-f="ok">готовы (<?= $stat['ok'] ?>)</button>
                <button type="button" class="btn light" data-f="new">новые счета (<?= $stat['new'] ?>)</button>
                <button type="button" class="btn light" data-f="none">без квартиры (<?= $stat['none'] ?>)</button>
                <button type="button" class="btn light" data-f="dup">уже загружены (<?= $stat['dup'] ?>)</button>
            </div>
        </div>
        <p class="muted">Расчётный счёт <?= h($bank['account']) ?>. Списаний со счёта (комиссии банка,
            оплата подрядчикам): <?= count($out) ?> на сумму <?= money(array_sum(array_column($out, 'amount'))) ?> — не загружаются.</p>

        <div class="table-wrap">
        <table class="import">
            <tr>
                <th><input type="checkbox" id="all" checked title="Выбрать все видимые"></th>
                <th>Дата проводки</th><th>№ док.</th><th>Плательщик</th><th class="num">Сумма</th>
                <th>Назначение платежа</th><th>Квартира</th><th>Статус</th>
            </tr>
            <?php foreach ($rows as $i => $r): $op = $r['op']; [$st, $cls] = $statusText[$r['status']]; ?>
            <tr data-s="<?= $r['status'] ?>">
                <td><input type="checkbox" name="sel[<?= $i ?>]" <?= in_array($r['status'], ['ok', 'new']) ? 'checked' : '' ?>
                           <?= $r['status'] === 'dup' ? 'disabled' : '' ?>></td>
                <td class="nowrap"><?= date('d.m.Y H:i', strtotime($op['posted'])) ?></td>
                <td><?= h($op['doc_no']) ?></td>
                <td><?= h($r['name']) ?></td>
                <td class="num"><?= money($op['amount']) ?></td>
                <td class="purpose"><?= h(preg_replace('/^.*Назначение платежа:\s*/iu', '', $op['purpose'])) ?></td>
                <td>
                    <input type="number" name="flat[<?= $i ?>]" value="<?= $r['flat'] ?: '' ?>" min="1" class="flat"
                           <?= $r['status'] === 'dup' ? 'disabled' : '' ?>>
                    <?php if ($r['why']): ?><div class="muted small"><?= h($r['why']) ?></div><?php endif ?>
                </td>
                <td class="<?= $cls ?> small">
                    <?= $st ?><?php if ($r['owner']): ?><div class="muted"><?= h($r['owner']) ?></div><?php endif ?>
                </td>
            </tr>
            <?php endforeach ?>
        </table>
        </div>

        <div class="row" style="margin-top:14px">
            <label><input type="checkbox" name="create" checked>
                создать лицевые счета для квартир, которых нет в справочнике</label>
        </div>
        <div class="row" style="margin-top:10px">
            <button type="submit">Загрузить выбранные платежи</button>
            <button type="submit" class="btn light" form="cancel">Отмена</button>
            <span class="muted" id="cnt"></span>
        </div>
    </form>
    <form id="cancel" method="post"><input type="hidden" name="action" value="cancel"></form>
<?php endif ?>

    <div class="card">
        <h2>Загруженные выписки</h2>
        <?php if (!$imports): ?>
            <p class="muted">Выписки ещё не загружались.</p>
        <?php else: ?>
        <div class="table-wrap">
        <table>
            <tr><th>№</th><th>Файл</th><th>Расчётный счёт</th><th>Период операций</th><th>Загружена</th>
                <th class="num">Операций</th><th class="num">Платежей</th><th class="num">Сумма</th><th></th></tr>
            <?php foreach ($imports as $im): ?>
            <tr>
                <td class="muted"><?= (int)$im['id'] ?></td>
                <td><?= h($im['file_name']) ?></td>
                <td><?= h($im['bank_account']) ?></td>
                <td class="nowrap"><?= date('d.m.Y', strtotime($im['date_from'])) ?> – <?= date('d.m.Y', strtotime($im['date_to'])) ?></td>
                <td class="nowrap"><?= date('d.m.Y H:i', strtotime($im['imported_at'])) ?></td>
                <td class="num"><?= (int)$im['ops_total'] ?></td>
                <td class="num"><a class="link" href="edit.php?t=payments&import=<?= (int)$im['id'] ?>"><?= (int)$im['ops_loaded'] ?></a></td>
                <td class="num"><?= money($im['amount']) ?></td>
                <td class="num">
                    <form method="post" onsubmit="return confirm('Удалить все платежи этой загрузки?')">
                        <input type="hidden" name="action" value="undo">
                        <input type="hidden" name="id" value="<?= (int)$im['id'] ?>">
                        <button class="link" type="submit">отменить загрузку</button>
                    </form>
                </td>
            </tr>
            <?php endforeach ?>
        </table>
        </div>
        <?php endif ?>
    </div>

<script>
    // фильтр строк по статусу, «выбрать все», счётчик выбранного
    const rows = [...document.querySelectorAll('table.import tr[data-s]')];
    const count = () => {
        const sel = rows.filter(r => r.querySelector('input[type=checkbox]').checked);
        const sum = sel.reduce((s, r) => s + parseFloat(r.querySelector('td.num').textContent.replace(/\s/g, '')), 0);
        const el = document.getElementById('cnt');
        if (el) el.textContent = `Выбрано: ${sel.length} на сумму ${sum.toLocaleString('ru-RU', {minimumFractionDigits: 2})} ₽`;
    };
    document.querySelectorAll('.filters [data-f]').forEach(b => b.addEventListener('click', () => {
        document.querySelectorAll('.filters [data-f]').forEach(x => x.classList.toggle('on', x === b));
        rows.forEach(r => r.hidden = b.dataset.f !== 'all' && r.dataset.s !== b.dataset.f);
    }));
    document.getElementById('all')?.addEventListener('change', e => {
        rows.filter(r => !r.hidden).forEach(r => {
            const c = r.querySelector('input[type=checkbox]');
            if (!c.disabled) c.checked = e.target.checked;
        });
        count();
    });
    // ввели номер квартиры — строку отмечаем для загрузки
    rows.forEach(r => {
        r.querySelector('input[type=checkbox]').addEventListener('change', count);
        r.querySelector('input.flat')?.addEventListener('input', e => {
            const c = r.querySelector('input[type=checkbox]');
            c.checked = e.target.value !== '';
            count();
        });
    });
    count();
</script>
<?php
layout_end();
