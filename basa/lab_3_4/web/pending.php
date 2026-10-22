<?php
// Неразнесённые платежи — временное хранилище поступлений из банковской выписки,
// которые при загрузке не удалось отнести к лицевому счёту (квартира не определена,
// строка не выбрана, нет лицевого счёта). Здесь их дорабатывают: указывают квартиру
// и комментарий, сохраняют, а затем разносят в payments. Платежи, не относящиеся
// к квартплате (аренда, субсидии), можно исключить — они остаются в списке исключённых.
require __DIR__ . '/lib.php';
require __DIR__ . '/bank_statement.php';

$msg = $_GET['msg'] ?? null;
$error = null;

$status = in_array($_GET['status'] ?? '', ['new', 'ignored', 'all']) ? $_GET['status'] : 'new';
$fImport = (int)($_GET['import'] ?? 0);
$q = trim($_GET['q'] ?? '');
$self = 'pending.php?' . http_build_query(array_filter(['status' => $status, 'import' => $fImport ?: null, 'q' => $q ?: null]));

try {
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $pdo = db();
        $ids = array_map('intval', array_keys($_POST['sel'] ?? []));
        $one = (int)($_POST['one'] ?? 0);          // кнопка «разнести» в строке
        $action = $one ? 'post' : ($_POST['action'] ?? 'save');
        if ($one) {
            $ids = [$one];
        }
        $flats = $_POST['flat'] ?? [];
        $notes = $_POST['note'] ?? [];

        $pdo->beginTransaction();
        // доработка сохраняется всегда: квартира и комментарий по всем показанным строкам
        $upd = $pdo->prepare('UPDATE bank_pending SET flat = ?, note = ? WHERE id = ?');
        foreach ($flats as $id => $flat) {
            $note = trim($notes[$id] ?? '');
            $upd->execute([(int)$flat > 0 ? (int)$flat : null, $note !== '' ? mb_substr($note, 0, 255) : null, (int)$id]);
        }

        $text = 'Изменения сохранены';
        if (in_array($action, ['post', 'ignore', 'restore']) && !$ids) {
            throw new InvalidArgumentException('Отметьте строки галочками');
        }
        if ($action === 'post') {
            $accByFlat = $pdo->query('SELECT flat, id FROM accounts')->fetchAll(PDO::FETCH_KEY_PAIR);
            $get = $pdo->prepare("SELECT * FROM bank_pending WHERE id = ? AND status = 'new'");
            $del = $pdo->prepare('DELETE FROM bank_pending WHERE id = ?');
            $why = $pdo->prepare('UPDATE bank_pending SET reason = ? WHERE id = ?');
            $posted = $sum = $newAcc = 0;
            $failed = [];
            foreach ($ids as $id) {
                $get->execute([$id]);
                if (!$p = $get->fetch()) {
                    continue;
                }
                $op = ['posted' => $p['posted'], 'doc_no' => $p['doc_no'], 'amount' => (float)$p['amount'],
                       'payer' => $p['payer_raw'] ?? $p['payer'], 'purpose' => $p['purpose'], 'ref' => $p['bank_ref']];
                $reason = post_bank_payment($pdo, $op, (int)$p['flat'], isset($_POST['create']),
                                            (int)$p['import_id'], $accByFlat, $newAcc);
                if ($reason === null || $reason === 'уже загружен') {
                    $del->execute([$id]);
                }
                if ($reason === null) {
                    $posted++;
                    $sum += $op['amount'];
                } else {
                    $why->execute([$reason, $id]);
                    $failed[] = $reason;
                }
            }
            $text = sprintf('Разнесено в платежи: %d на сумму %s ₽', $posted, money($sum))
                  . ($newAcc ? ", создано лицевых счетов: $newAcc" : '')
                  . ($failed ? '. Не разнесено: ' . count($failed) . ' (' . implode('; ', array_unique($failed)) . ')' : '');
        } elseif ($action === 'ignore' || $action === 'restore') {
            $in = implode(',', array_fill(0, count($ids), '?'));
            $stmt = $pdo->prepare("UPDATE bank_pending SET status = ? WHERE id IN ($in)");
            $stmt->execute([$action === 'ignore' ? 'ignored' : 'new', ...$ids]);
            $text = ($action === 'ignore' ? 'Исключено из разнесения: ' : 'Возвращено к разнесению: ') . $stmt->rowCount();
        }
        $pdo->commit();
        header('Location: ' . $self . '&msg=' . urlencode($text));
        exit;
    }
} catch (Throwable $e) {
    if (isset($pdo) && $pdo->inTransaction()) {
        $pdo->rollBack();
    }
    $error = $e->getMessage();
}

// ---------- список ----------
$where = [];
$params = [];
if ($status !== 'all') {
    $where[] = 'p.status = ?';
    $params[] = $status;
}
if ($fImport) {
    $where[] = 'p.import_id = ?';
    $params[] = $fImport;
}
if ($q !== '') {
    $where[] = '(p.payer LIKE ? OR p.purpose LIKE ? OR p.doc_no LIKE ? OR p.note LIKE ?)';
    array_push($params, ...array_fill(0, 4, '%' . $q . '%'));
}
$stmt = db()->prepare('SELECT p.*, i.file_name FROM bank_pending p JOIN bank_imports i ON i.id = p.import_id'
    . ($where ? ' WHERE ' . implode(' AND ', $where) : '') . ' ORDER BY p.posted');
$stmt->execute($params);
$rows = $stmt->fetchAll();

$totals = db()->query("SELECT status, COUNT(*) n, COALESCE(SUM(amount), 0) s FROM bank_pending GROUP BY status")
              ->fetchAll(PDO::FETCH_UNIQUE);
$owners = db()->query('SELECT flat, owner FROM accounts')->fetchAll(PDO::FETCH_KEY_PAIR);

// подсказки: квартира из назначения/адреса и квартиры, за которые плательщик уже платил
$history = [];
foreach (db()->query('SELECT p.payer, a.flat FROM payments p JOIN accounts a ON a.id = p.account_id
                      WHERE p.payer IS NOT NULL GROUP BY p.payer, a.flat') as $r) {
    $history[mb_strtoupper($r['payer'])][] = (int)$r['flat'];
}
foreach ($rows as &$r) {
    $hints = [];
    [$f, $why] = detect_flat((string)$r['purpose'], (string)($r['payer_raw'] ?? $r['payer']));
    if ($f) {
        $hints[$f] = $why;
    }
    foreach ($history[mb_strtoupper((string)$r['payer'])] ?? [] as $hf) {
        $hints[$hf] ??= 'плательщик платил за эту квартиру';
    }
    $r['hints'] = $hints;
}
unset($r);

$imports = db()->query('SELECT id, file_name FROM bank_imports ORDER BY id DESC')->fetchAll();

layout_start('Неразнесённые платежи', 'pending.php');
?>
    <?php if ($msg): ?><div class="card ok"><?= h($msg) ?></div><?php endif ?>
    <?php if ($error): ?><div class="card error">Ошибка: <?= h($error) ?></div><?php endif ?>

    <div class="grid">
        <div class="card stat"><b class="<?= ($totals['new']['n'] ?? 0) ? 'debt' : '' ?>"><?= (int)($totals['new']['n'] ?? 0) ?></b>
            <span>ждут разнесения на сумму <?= money($totals['new']['s'] ?? 0) ?></span></div>
        <div class="card stat"><b><?= (int)($totals['ignored']['n'] ?? 0) ?></b>
            <span>исключены (не квартплата) на сумму <?= money($totals['ignored']['s'] ?? 0) ?></span></div>
    </div>

    <form class="card row" method="get">
        <div class="field"><label>Показать</label>
            <select name="status" onchange="this.form.submit()">
                <?php foreach (['new' => 'ждут разнесения', 'ignored' => 'исключённые', 'all' => 'все'] as $k => $v): ?>
                    <option value="<?= $k ?>" <?= $k === $status ? 'selected' : '' ?>><?= $v ?></option>
                <?php endforeach ?>
            </select></div>
        <div class="field"><label>Выписка</label>
            <select name="import" onchange="this.form.submit()">
                <option value="0">все загрузки</option>
                <?php foreach ($imports as $im): ?>
                    <option value="<?= (int)$im['id'] ?>" <?= $im['id'] == $fImport ? 'selected' : '' ?>>№ <?= (int)$im['id'] ?> — <?= h(mb_strimwidth($im['file_name'], 0, 50, '…')) ?></option>
                <?php endforeach ?>
            </select></div>
        <div class="field"><label>Поиск по плательщику, назначению, № документа</label>
            <input type="text" name="q" value="<?= h($q) ?>" size="30"></div>
        <button type="submit">Найти</button>
        <a class="btn light" href="pending.php">Сбросить</a>
    </form>

    <form class="card" method="post" action="<?= h($self) ?>">
        <!-- Enter в поле формы только сохраняет изменения, а не разносит первую строку -->
        <button type="submit" name="action" value="save" class="default-submit" tabindex="-1" aria-hidden="true"></button>
        <p class="muted">Укажите квартиру и нажмите «разнести» в строке или отметьте несколько строк и нажмите
            «Разнести выбранные». «Сохранить изменения» запоминает квартиры и комментарии без разнесения —
            к записи можно вернуться позже. Платежи, не относящиеся к квартплате, исключите.</p>
        <?php if (!$rows): ?>
            <p class="muted">Записей нет.</p>
        <?php else: ?>
        <div class="table-wrap">
        <table class="import pending">
            <tr>
                <th><input type="checkbox" id="all" title="Выбрать все"></th>
                <th>Дата проводки</th><th>№ док.</th><th>Плательщик</th><th class="num">Сумма</th>
                <th>Назначение платежа</th><th>Квартира</th><th>Комментарий</th><th></th>
            </tr>
            <?php foreach ($rows as $r): $id = (int)$r['id']; ?>
            <tr class="<?= $r['status'] === 'ignored' ? 'ignored' : '' ?>">
                <td><input type="checkbox" name="sel[<?= $id ?>]"></td>
                <td class="nowrap"><?= date('d.m.Y H:i', strtotime($r['posted'])) ?></td>
                <td><?= h($r['doc_no']) ?></td>
                <td><?= h($r['payer']) ?>
                    <?php $addr = payer_parts((string)$r['payer_raw'])['address']; if ($addr): ?>
                        <div class="muted small"><?= h($addr) ?></div><?php endif ?></td>
                <td class="num"><?= money($r['amount']) ?></td>
                <td class="purpose"><?= h(preg_replace('/^.*Назначение платежа:\s*/iu', '', (string)$r['purpose'])) ?>
                    <div class="small warn"><?= h($r['reason']) ?><?= $r['status'] === 'ignored' ? ' · исключён' : '' ?></div></td>
                <td class="nowrap">
                    <input type="number" name="flat[<?= $id ?>]" value="<?= $r['flat'] ?: '' ?>" min="1" class="flat">
                    <div class="small owner"></div>
                    <?php foreach ($r['hints'] as $hf => $why): if ($hf == $r['flat']) continue; ?>
                        <button type="button" class="hint" data-flat="<?= $hf ?>" title="<?= h($why) ?>">кв. <?= $hf ?>?</button>
                    <?php endforeach ?>
                </td>
                <td><input type="text" name="note[<?= $id ?>]" value="<?= h($r['note']) ?>" size="16" maxlength="255"></td>
                <td><?php if ($r['status'] === 'new'): ?>
                    <button type="submit" name="one" value="<?= $id ?>" class="link go">разнести</button>
                <?php endif ?></td>
            </tr>
            <?php endforeach ?>
        </table>
        </div>
        <div class="row" style="margin-top:14px">
            <label><input type="checkbox" name="create" checked>
                создать лицевой счёт, если квартиры нет в справочнике</label>
        </div>
        <div class="row" style="margin-top:10px">
            <button type="submit" name="action" value="save" class="btn light">Сохранить изменения</button>
            <?php if ($status !== 'ignored'): ?>
                <button type="submit" name="action" value="post">Разнести выбранные в платежи</button>
                <button type="submit" name="action" value="ignore" class="btn light">Исключить выбранные</button>
            <?php endif ?>
            <?php if ($status !== 'new'): ?>
                <button type="submit" name="action" value="restore" class="btn light">Вернуть к разнесению</button>
            <?php endif ?>
            <span class="muted" id="cnt"></span>
        </div>
        <?php endif ?>
    </form>

<script>
    // под номером квартиры — владелец лицевого счёта или «новый лицевой счёт»
    const owners = <?= json_encode($owners, JSON_UNESCAPED_UNICODE | JSON_HEX_TAG) ?>;
    const rows = [...document.querySelectorAll('table.pending tr')].slice(1);
    const showOwner = r => {
        const v = r.querySelector('input.flat').value, el = r.querySelector('.owner');
        el.textContent = !v ? '' : (owners[v] ?? 'новый лицевой счёт');
        el.className = 'small owner ' + (!v ? '' : owners[v] ? 'muted' : 'warn');
    };
    const count = () => {
        const sel = rows.filter(r => r.querySelector('input[type=checkbox]').checked);
        const sum = sel.reduce((s, r) => s + parseFloat(r.querySelector('td.num').textContent.replace(/\s/g, '')), 0);
        const el = document.getElementById('cnt');
        if (el) el.textContent = sel.length ? `Выбрано: ${sel.length} на сумму ${sum.toLocaleString('ru-RU', {minimumFractionDigits: 2})} ₽` : '';
    };
    rows.forEach(r => {
        const flat = r.querySelector('input.flat'), box = r.querySelector('input[type=checkbox]');
        flat.addEventListener('input', () => { showOwner(r); box.checked = flat.value !== ''; count(); });
        box.addEventListener('change', count);
        r.querySelectorAll('.hint').forEach(b => b.addEventListener('click', () => {
            flat.value = b.dataset.flat; flat.dispatchEvent(new Event('input'));
        }));
        showOwner(r);
    });
    document.getElementById('all')?.addEventListener('change', e => {
        rows.forEach(r => r.querySelector('input[type=checkbox]').checked = e.target.checked);
        count();
    });
</script>
<?php
layout_end();
