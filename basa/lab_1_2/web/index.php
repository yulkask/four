<?php
// Пункт 6. Интерфейс для ввода поисковых запросов к базе данных library.
// Поиск выполняется через хранимые процедуры sp_search_books и sp_fulltext_search.

$fields = [
    'authors'    => 'Авторы',
    'title'      => 'Название',
    'publisher'  => 'Издательство',
    'pub_year'   => 'Год издания',
    'annotation' => 'Аннотация',
    'any'        => 'Любое поле',
];
$ftModes = [
    'natural'   => 'Естественный язык',
    'boolean'   => 'Логический режим (+ - * "…")',
    'expansion' => 'С расширением запроса',
];
$examples = [
    ['regexp', 'authors',    '(^|, )Толст',        'Фамилия начинается на «Толст»'],
    ['regexp', 'authors',    ',',                  'Несколько авторов'],
    ['regexp', 'title',      '[0-9]',              'В названии есть цифры'],
    ['regexp', 'title',      '\bи\b',              'Название вида «X и Y»'],
    ['regexp', 'publisher',  '^(АСТ|Эксмо)$',      'АСТ или Эксмо'],
    ['regexp', 'publisher',  '^[a-z]',             'Зарубежные издательства'],
    ['regexp', 'pub_year',   '^19[0-9]{2}$',       'Изданы в XX веке'],
    ['regexp', 'pub_year',   '^201[5-9]$',         '2015–2019 годы'],
    ['regexp', 'annotation', 'программ[а-яё]*',    'Про программирование'],
    ['regexp', 'annotation', '\bлюб(овь|ви)\b',    'Про любовь'],
    ['fulltext', 'natural',  'антиутопия',         'Антиутопии'],
    ['fulltext', 'boolean',  '+MySQL -репликация', 'MySQL без репликации'],
    ['fulltext', 'boolean',  'алгоритм*',          'Слова на «алгоритм…»'],
    ['fulltext', 'boolean',  '"хранимые процедуры"', 'Точная фраза'],
];

$type    = ($_GET['type'] ?? 'regexp') === 'fulltext' ? 'fulltext' : 'regexp';
$field   = array_key_exists($_GET['field'] ?? '', $fields) ? $_GET['field'] : 'title';
$mode    = array_key_exists($_GET['mode'] ?? '', $ftModes) ? $_GET['mode'] : 'natural';
$query   = trim($_GET['q'] ?? '');
$caseSen = isset($_GET['cs']) ? 1 : 0;

$rows = null;
$error = null;
$call = null;

if ($query !== '') {
    try {
        $pdo = new PDO(
            sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4',
                getenv('DB_HOST') ?: '127.0.0.1', getenv('DB_NAME') ?: 'library'),
            getenv('DB_USER') ?: 'library',
            getenv('DB_PASS') ?: 'library',
            [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
             PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
        );
        if ($type === 'regexp') {
            $stmt = $pdo->prepare('CALL sp_search_books(?, ?, ?)');
            $stmt->execute([$field, $query, $caseSen]);
            $call = sprintf("CALL sp_search_books('%s', %s, %d);", $field, $pdo->quote($query), $caseSen);
        } else {
            $stmt = $pdo->prepare('CALL sp_fulltext_search(?, ?)');
            $stmt->execute([$query, $mode]);
            $call = sprintf("CALL sp_fulltext_search(%s, '%s');", $pdo->quote($query), $mode);
        }
        $rows = $stmt->fetchAll();
        $stmt->closeCursor();
    } catch (PDOException $e) {
        $error = $e->getMessage();
    }
}

function h(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

// Подсветка найденного фрагмента (для регулярных выражений)
function mark(string $text, string $pattern, bool $cs): string
{
    $re = '/' . str_replace('/', '\/', $pattern) . '/u' . ($cs ? '' : 'i');
    $out = @preg_replace_callback($re, fn($m) => "\x01" . $m[0] . "\x02", $text);
    if ($out === null || $pattern === '') {
        return h($text);
    }
    return str_replace(["\x01", "\x02"], ['<mark>', '</mark>'], h($out));
}
?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Поиск книг</title>
<style>
    :root {
        --bg: #f5f6f8; --card: #fff; --text: #1d2330; --muted: #6b7280;
        --accent: #2f5bd3; --border: #dfe3ea; --mark: #ffe58a; --err: #b42318;
    }
    @media (prefers-color-scheme: dark) {
        :root {
            --bg: #14171d; --card: #1d212a; --text: #e6e8ec; --muted: #9aa1ad;
            --accent: #7aa2ff; --border: #2e3440; --mark: #6b5a12; --err: #ff8a80;
        }
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: var(--bg); color: var(--text);
           font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
    main { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
    h1 { font-size: 24px; margin: 0 0 4px; }
    .sub { color: var(--muted); margin: 0 0 20px; }
    .card { background: var(--card); border: 1px solid var(--border);
            border-radius: 10px; padding: 16px; margin-bottom: 16px; }
    .tabs { display: flex; gap: 8px; margin-bottom: 14px; }
    .tabs label { cursor: pointer; padding: 6px 14px; border-radius: 999px;
                  border: 1px solid var(--border); }
    .tabs input { display: none; }
    .tabs input:checked + span { color: var(--accent); font-weight: 600; }
    .row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
    input[type=text], select { font: inherit; color: var(--text); background: var(--bg);
            border: 1px solid var(--border); border-radius: 8px; padding: 8px 10px; }
    input[type=text] { flex: 1 1 280px; font-family: ui-monospace, Menlo, monospace; }
    button { font: inherit; background: var(--accent); color: #fff; border: 0;
             border-radius: 8px; padding: 8px 18px; cursor: pointer; }
    .hidden { display: none !important; }
    .examples { display: flex; flex-wrap: wrap; gap: 6px; }
    .examples a { font-size: 13px; text-decoration: none; color: var(--accent);
                  border: 1px solid var(--border); border-radius: 6px; padding: 3px 8px; }
    code, .sql { font-family: ui-monospace, Menlo, monospace; font-size: 13px; }
    .sql { color: var(--muted); margin: 0 0 10px; word-break: break-all; }
    .error { color: var(--err); }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; vertical-align: top; padding: 8px;
             border-bottom: 1px solid var(--border); }
    th { font-size: 13px; color: var(--muted); font-weight: 600; }
    td.ann { font-size: 13px; color: var(--muted); min-width: 280px; }
    mark { background: var(--mark); color: inherit; border-radius: 2px; }
    .help { font-size: 13px; color: var(--muted); margin-top: 10px; }
</style>
</head>
<body>
<main>
    <h1>Поиск по каталогу книг</h1>
    <p class="sub">База данных <code>library</code>, таблица <code>books</code></p>

    <form class="card" method="get">
        <div class="tabs">
            <label><input type="radio" name="type" value="regexp" <?= $type === 'regexp' ? 'checked' : '' ?>>
                <span>Регулярное выражение</span></label>
            <label><input type="radio" name="type" value="fulltext" <?= $type === 'fulltext' ? 'checked' : '' ?>>
                <span>Полнотекстовый поиск по аннотации</span></label>
        </div>
        <div class="row">
            <select name="field" id="field" class="<?= $type === 'fulltext' ? 'hidden' : '' ?>">
                <?php foreach ($fields as $k => $v): ?>
                    <option value="<?= $k ?>" <?= $k === $field ? 'selected' : '' ?>><?= $v ?></option>
                <?php endforeach ?>
            </select>
            <select name="mode" id="mode" class="<?= $type === 'regexp' ? 'hidden' : '' ?>">
                <?php foreach ($ftModes as $k => $v): ?>
                    <option value="<?= $k ?>" <?= $k === $mode ? 'selected' : '' ?>><?= $v ?></option>
                <?php endforeach ?>
            </select>
            <input type="text" name="q" value="<?= h($query) ?>" placeholder="Поисковый запрос" autofocus>
            <label id="cs" class="<?= $type === 'fulltext' ? 'hidden' : '' ?>">
                <input type="checkbox" name="cs" <?= $caseSen ? 'checked' : '' ?>> учитывать регистр</label>
            <button type="submit">Найти</button>
        </div>
        <p class="help" id="help-regexp" <?= $type === 'fulltext' ? 'hidden' : '' ?>>
            Синтаксис MySQL 8 (ICU): <code>^</code> <code>$</code> <code>.</code> <code>[а-я]</code>
            <code>(a|b)</code> <code>*</code> <code>+</code> <code>{n,m}</code> <code>\b</code> — граница слова.
        </p>
        <p class="help" id="help-ft" <?= $type === 'regexp' ? 'hidden' : '' ?>>
            Логический режим: <code>+слово</code> — обязательно, <code>-слово</code> — исключить,
            <code>слово*</code> — по началу слова, <code>"фраза"</code> — точная фраза.
            Слова короче 3 букв не индексируются.
        </p>
    </form>

    <div class="card">
        <div class="examples">
            <?php foreach ($examples as [$t, $f, $q, $label]):
                $params = $t === 'regexp' ? ['type' => $t, 'field' => $f, 'q' => $q]
                                          : ['type' => $t, 'mode' => $f, 'q' => $q]; ?>
                <a href="?<?= h(http_build_query($params)) ?>" title="<?= h($q) ?>"><?= h($label) ?></a>
            <?php endforeach ?>
        </div>
    </div>

    <?php if ($error !== null): ?>
        <div class="card error">Ошибка: <?= h($error) ?></div>
    <?php elseif ($rows !== null): ?>
        <div class="card">
            <p class="sql"><?= h($call) ?></p>
            <p>Найдено книг: <b><?= count($rows) ?></b></p>
            <?php if ($rows): ?>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>#</th><th>Авторы</th><th>Название</th><th>Издательство</th><th>Год</th><th>Аннотация</th>
                    <?php if ($type === 'fulltext'): ?><th>Релевантность</th><?php endif ?>
                </tr>
                <?php foreach ($rows as $r):
                    $hl = fn($col) => $type === 'regexp' && ($field === $col || $field === 'any')
                        ? mark($r[$col], $query, (bool)$caseSen) : h($r[$col]); ?>
                    <tr>
                        <td><?= (int)$r['id'] ?></td>
                        <td><?= $hl('authors') ?></td>
                        <td><?= $hl('title') ?></td>
                        <td><?= $hl('publisher') ?></td>
                        <td><?= $hl('pub_year') ?></td>
                        <td class="ann"><?= $hl('annotation') ?></td>
                        <?php if ($type === 'fulltext'): ?>
                            <td><?= number_format((float)$r['score'], 4) ?></td>
                        <?php endif ?>
                    </tr>
                <?php endforeach ?>
            </table>
            </div>
            <?php endif ?>
        </div>
    <?php endif ?>
</main>
<script>
    // переключение между режимами поиска
    document.querySelectorAll('input[name=type]').forEach(r => r.addEventListener('change', () => {
        const ft = r.value === 'fulltext' && r.checked;
        document.getElementById('field').classList.toggle('hidden', ft);
        document.getElementById('cs').classList.toggle('hidden', ft);
        document.getElementById('mode').classList.toggle('hidden', !ft);
        document.getElementById('help-regexp').hidden = ft;
        document.getElementById('help-ft').hidden = !ft;
    }));
</script>
</body>
</html>
