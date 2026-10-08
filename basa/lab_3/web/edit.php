<?php
// Пункт 3. WEB-интерфейс для заполнения таблиц accounts, saldo, charges, payments.
// Одна страница на все таблицы: описание полей задаётся в $tables.
require __DIR__ . '/lib.php';

$tables = [
    'accounts' => [
        'title'  => 'Лицевые счета',
        'order'  => 'a.flat',
        'fields' => [
            'account_no' => ['Лицевой счёт', 'text', 'pattern' => '[0-9]{6,10}'],
            'flat'       => ['Квартира', 'int'],
            'owner'      => ['Квартиросъёмщик', 'text', 'size' => 32],
            'area'       => ['Площадь, м²', 'money'],
            'residents'  => ['Проживает', 'int'],
        ],
    ],
    'saldo' => [
        'title'  => 'Сальдо на начало месяца',
        'order'  => 't.period DESC, a.flat',
        'filter' => 'period',
        'fields' => [
            'account_id' => ['Квартира', 'account'],
            'period'     => ['Месяц', 'month'],
            'amount'     => ['Сальдо (+ долг / − переплата)', 'money', 'signed' => true],
        ],
        'help'   => 'Входящее сальдо вводится на начало года (или при открытии счёта). '
                  . 'Сальдо следующих месяцев процедуры считают сами: последнее сальдо + начисления − платежи. '
                  . 'Кнопка «Закрыть месяц» записывает рассчитанное сальдо на начало следующего месяца.',
    ],
    'charges' => [
        'title'  => 'Начисления',
        'order'  => 't.period DESC, a.flat, t.service',
        'filter' => 'period',
        'fields' => [
            'account_id' => ['Квартира', 'account'],
            'period'     => ['Расчётный месяц', 'month'],
            'service'    => ['Услуга', 'select', 'options' => SERVICES],
            'amount'     => ['Сумма', 'money', 'signed' => true],
        ],
        'help'   => 'Отрицательная сумма — перерасчёт (уменьшение начисления).',
    ],
    'payments' => [
        'title'  => 'Платежи',
        'order'  => 't.pay_date DESC, a.flat',
        'filter' => 'pay_date',
        'fields' => [
            'account_id' => ['Квартира', 'account'],
            'pay_date'   => ['Дата поступления', 'date'],
            'amount'     => ['Сумма', 'money'],
            'source'     => ['Способ', 'select', 'options' => PAY_SOURCES],
            'doc_no'     => ['№ документа', 'text', 'optional' => true],
        ],
        'help'   => 'Платёж учитывается в месяце поступления на расчётный счёт.',
    ],
];

$t = array_key_exists($_GET['t'] ?? '', $tables) ? $_GET['t'] : 'accounts';
$cfg = $tables[$t];
$fields = $cfg['fields'];
$self = 'edit.php?t=' . $t;

// фильтры списка
$fAccount = (int)($_GET['account'] ?? 0);
$fMonth = preg_match('/^\d{4}-\d{2}$/', $_GET['month'] ?? '') ? $_GET['month'] : null;
// начислений много — по умолчанию показываем последний месяц
if ($t === 'charges' && !isset($_GET['month'])) {
    $fMonth = db()->query("SELECT DATE_FORMAT(MAX(period), '%Y-%m') FROM charges")->fetchColumn() ?: null;
}

$msg = $_GET['msg'] ?? null;
$error = null;
$form = [];          // значения формы (при редактировании или ошибке)
$editId = (int)($_GET['edit'] ?? 0);

try {
    // ---------- запись ----------
    if ($_SERVER['REQUEST_METHOD'] === 'POST') {
        $action = $_POST['action'] ?? '';
        $back = $self . ($fAccount ? "&account=$fAccount" : '') . ($fMonth ? "&month=$fMonth" : '');

        if ($action === 'delete') {
            db()->prepare("DELETE FROM $t WHERE id = ?")->execute([(int)$_POST['id']]);
            header("Location: $back&msg=" . urlencode('Запись удалена'));
            exit;
        }

        if ($action === 'close_month') {
            [$res] = call_proc('sp_close_month', [$_POST['close'] . '-01']);
            header("Location: $back&msg=" . urlencode(sprintf('Сальдо на %s записано для %d счетов',
                date('d.m.Y', strtotime($res[0]['period'])), $res[0]['accounts'])));
            exit;
        }

        if ($action === 'save') {
            $values = [];
            foreach ($fields as $name => $f) {
                $v = trim($_POST[$name] ?? '');
                $form[$name] = $v;
                if ($v === '') {
                    if (!empty($f['optional'])) {
                        $values[$name] = null;
                        continue;
                    }
                    throw new InvalidArgumentException("Не заполнено поле «{$f[0]}»");
                }
                $values[$name] = match ($f[1]) {
                    'month' => $v . '-01',
                    'money' => str_replace([',', ' '], ['.', ''], $v),
                    default => $v,
                };
            }
            $id = (int)($_POST['id'] ?? 0);
            $cols = array_keys($values);
            if ($id) {
                $set = implode(', ', array_map(fn($c) => "$c = ?", $cols));
                db()->prepare("UPDATE $t SET $set WHERE id = ?")->execute([...array_values($values), $id]);
                $text = 'Запись изменена';
            } else {
                db()->prepare(sprintf('INSERT INTO %s (%s) VALUES (%s)', $t, implode(', ', $cols),
                    implode(', ', array_fill(0, count($cols), '?'))))->execute(array_values($values));
                $text = 'Запись добавлена';
            }
            header("Location: $back&msg=" . urlencode($text));
            exit;
        }
    }

    if ($editId) {
        $stmt = db()->prepare("SELECT * FROM $t WHERE id = ?");
        $stmt->execute([$editId]);
        $form = $stmt->fetch() ?: [];
        if (isset($form['period'])) {
            $form['period'] = substr($form['period'], 0, 7);
        }
    }
} catch (PDOException $e) {
    $editId = (int)($_POST['id'] ?? 0);
    $error = match ($e->errorInfo[1] ?? 0) {
        1062    => 'Такая запись уже существует (нарушена уникальность)',
        3819    => 'Значение не прошло проверку (CHECK): ' . $e->getMessage(),
        1451    => 'Запись используется в других таблицах',
        default => $e->getMessage(),
    };
} catch (InvalidArgumentException $e) {
    $editId = (int)($_POST['id'] ?? 0);
    $error = $e->getMessage();
}

// ---------- список ----------
$where = [];
$params = [];
if ($t !== 'accounts') {
    if ($fAccount) {
        $where[] = 't.account_id = ?';
        $params[] = $fAccount;
    }
    if ($fMonth) {
        $where[] = "DATE_FORMAT(t.{$cfg['filter']}, '%Y-%m') = ?";
        $params[] = $fMonth;
    }
    $sql = "SELECT t.*, a.flat, a.account_no FROM $t t JOIN accounts a ON a.id = t.account_id"
         . ($where ? ' WHERE ' . implode(' AND ', $where) : '') . " ORDER BY {$cfg['order']}";
} else {
    $sql = "SELECT a.* FROM accounts a ORDER BY {$cfg['order']}";
}
$stmt = db()->prepare($sql);
$stmt->execute($params);
$rows = $stmt->fetchAll();
$accounts = accounts();

function input(string $name, array $f, $value): string
{
    $v = h((string)$value);
    $req = empty($f['optional']) ? 'required' : '';
    switch ($f[1]) {
        case 'account':
            global $accounts;
            $o = '<option value="">—</option>';
            foreach ($accounts as $a) {
                $sel = (string)$a['id'] === (string)$value ? 'selected' : '';
                $o .= sprintf('<option value="%d" %s>кв. %d — %s</option>', $a['id'], $sel, $a['flat'], h($a['owner']));
            }
            return "<select name=\"$name\" $req>$o</select>";
        case 'select':
            $o = '';
            foreach ($f['options'] as $opt) {
                $sel = $opt === $value ? 'selected' : '';
                $o .= sprintf('<option %s>%s</option>', $sel, h($opt));
            }
            return "<select name=\"$name\" $req>$o</select>";
        case 'month':
            return "<input type=\"month\" name=\"$name\" value=\"$v\" $req>";
        case 'date':
            return "<input type=\"date\" name=\"$name\" value=\"$v\" $req>";
        case 'int':
            return "<input type=\"number\" name=\"$name\" value=\"$v\" min=\"1\" style=\"width:90px\" $req>";
        case 'money':
            $min = empty($f['signed']) ? 'min="0.01"' : '';
            return "<input type=\"number\" step=\"0.01\" $min name=\"$name\" value=\"$v\" style=\"width:140px\" $req>";
        default:
            $p = isset($f['pattern']) ? "pattern=\"{$f['pattern']}\"" : '';
            $s = $f['size'] ?? 14;
            return "<input type=\"text\" name=\"$name\" value=\"$v\" size=\"$s\" $p $req>";
    }
}

function cell(string $name, array $f, array $r): string
{
    $v = $r[$name];
    return match ($f[1]) {
        'account' => sprintf('<td>%d <span class="muted">%s</span></td>', $r['flat'], h($r['account_no'])),
        'money'   => sprintf('<td class="num %s">%s</td>', empty($f['signed']) ? '' : sign_class($v), money($v)),
        'month'   => sprintf('<td>%s %s</td>', MONTHS[(int)substr($v, 5, 2)], substr($v, 0, 4)),
        'date'    => '<td>' . date('d.m.Y', strtotime($v)) . '</td>',
        default   => '<td>' . h((string)$v) . '</td>',
    };
}

// значения формы по умолчанию для нового ввода — подставляем фильтр
if (!$form && !$editId) {
    $form = ['account_id' => $fAccount ?: '', 'period' => $fMonth ?? '',
             'pay_date' => date('Y-m-d'), 'residents' => 1];
}

layout_start($cfg['title'], $self);
?>
    <?php if ($msg): ?><div class="card ok"><?= h($msg) ?></div><?php endif ?>
    <?php if ($error): ?><div class="card error">Ошибка: <?= h($error) ?></div><?php endif ?>

    <form class="card" method="post" action="<?= h($self . ($fAccount ? "&account=$fAccount" : '') . ($fMonth ? "&month=$fMonth" : '')) ?>">
        <h2><?= $editId ? 'Изменение записи №' . $editId : 'Новая запись' ?></h2>
        <input type="hidden" name="action" value="save">
        <input type="hidden" name="id" value="<?= $editId ?: '' ?>">
        <div class="row">
            <?php foreach ($fields as $name => $f): ?>
                <div class="field"><label><?= h($f[0]) ?></label><?= input($name, $f, $form[$name] ?? '') ?></div>
            <?php endforeach ?>
            <button type="submit"><?= $editId ? 'Сохранить' : 'Добавить' ?></button>
            <?php if ($editId): ?><a class="btn light" href="<?= h($self) ?>">Отмена</a><?php endif ?>
        </div>
        <?php if (!empty($cfg['help'])): ?><p class="muted"><?= h($cfg['help']) ?></p><?php endif ?>
    </form>

    <?php if ($t === 'saldo'): ?>
    <form class="card row" method="post" action="<?= h($self) ?>">
        <input type="hidden" name="action" value="close_month">
        <div class="field"><label>Закрываемый месяц</label>
            <input type="month" name="close" required value="<?= h(date('Y-m', strtotime('first day of last month'))) ?>"></div>
        <button type="submit">Закрыть месяц</button>
        <span class="sql">CALL sp_close_month(…)</span>
    </form>
    <?php endif ?>

    <div class="card">
        <?php if ($t !== 'accounts'): ?>
        <form class="row" method="get" style="margin-bottom:12px">
            <input type="hidden" name="t" value="<?= h($t) ?>">
            <div class="field"><label>Квартира</label>
                <select name="account" onchange="this.form.submit()">
                    <option value="0">все</option>
                    <?php foreach ($accounts as $a): ?>
                        <option value="<?= $a['id'] ?>" <?= $a['id'] == $fAccount ? 'selected' : '' ?>>кв. <?= $a['flat'] ?></option>
                    <?php endforeach ?>
                </select></div>
            <div class="field"><label>Месяц</label>
                <input type="month" name="month" value="<?= h($fMonth ?? '') ?>" onchange="this.form.submit()"></div>
            <a class="btn light" href="<?= h($self) ?>&month=">Все записи</a>
        </form>
        <?php endif ?>

        <p class="muted">Записей: <?= count($rows) ?></p>
        <div class="table-wrap">
        <table>
            <tr>
                <th>№</th>
                <?php foreach ($fields as $name => $f): ?>
                    <th class="<?= $f[1] === 'money' ? 'num' : '' ?>"><?= h($f[0]) ?></th>
                <?php endforeach ?>
                <th></th>
            </tr>
            <?php foreach ($rows as $r): ?>
            <tr>
                <td class="muted"><?= (int)$r['id'] ?></td>
                <?php foreach ($fields as $name => $f) echo cell($name, $f, $r); ?>
                <td class="num">
                    <a class="link" href="<?= h($self . '&edit=' . $r['id'] . ($fAccount ? "&account=$fAccount" : '') . ($fMonth ? "&month=$fMonth" : '')) ?>">изменить</a>
                    <form method="post" style="display:inline" onsubmit="return confirm('Удалить запись?')"
                          action="<?= h($self . ($fAccount ? "&account=$fAccount" : '') . ($fMonth ? "&month=$fMonth" : '')) ?>">
                        <input type="hidden" name="action" value="delete">
                        <input type="hidden" name="id" value="<?= (int)$r['id'] ?>">
                        <button class="link" type="submit">удалить</button>
                    </form>
                </td>
            </tr>
            <?php endforeach ?>
            <?php if ($t !== 'accounts' && $rows): ?>
            <tr class="total">
                <td colspan="<?= array_search('amount', array_keys($fields)) + 1 ?>">Итого</td>
                <td class="num"><?= money(array_sum(array_column($rows, 'amount'))) ?></td>
                <td colspan="<?= count($fields) - array_search('amount', array_keys($fields)) ?>"></td>
            </tr>
            <?php endif ?>
        </table>
        </div>
    </div>
<?php
layout_end();
