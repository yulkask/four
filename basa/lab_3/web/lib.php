<?php
// Общие функции: подключение к БД, форматирование, шапка и подвал страниц.

const MONTHS = [1 => 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
                'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'];

const SERVICES = ['Содержание жилья', 'Отопление', 'Холодная вода', 'Горячая вода',
                  'Водоотведение', 'Электроэнергия', 'Обращение с ТКО', 'Капитальный ремонт',
                  'Перерасчёт'];

const PAY_SOURCES = ['Банк', 'Онлайн', 'Касса', 'Почта'];

function db(): PDO
{
    static $pdo = null;
    return $pdo ??= new PDO(
        sprintf('mysql:host=%s;dbname=%s;charset=utf8mb4',
            getenv('DB_HOST') ?: '127.0.0.1', getenv('DB_NAME') ?: 'kvartplata'),
        getenv('DB_USER') ?: 'kvartplata',
        getenv('DB_PASS') ?: 'kvartplata',
        [PDO::ATTR_ERRMODE => PDO::ERRMODE_EXCEPTION,
         PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC]
    );
}

// Вызов хранимой процедуры; возвращает все наборы результатов
function call_proc(string $name, array $args): array
{
    $stmt = db()->prepare(sprintf('CALL %s(%s)', $name, implode(', ', array_fill(0, count($args), '?'))));
    $stmt->execute($args);
    $sets = [];
    do {
        if ($stmt->columnCount() > 0) {
            $sets[] = $stmt->fetchAll();
        }
    } while ($stmt->nextRowset());
    return $sets;
}

function h(?string $s): string
{
    return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8');
}

function money($v, bool $blankZero = false): string
{
    if ($v === null || ($blankZero && (float)$v == 0)) {
        return '';
    }
    return number_format((float)$v, 2, '.', ' ');
}

// Класс ячейки по знаку сальдо: долг / переплата
function sign_class($v): string
{
    return (float)$v > 0 ? 'debt' : ((float)$v < 0 ? 'over' : '');
}

function accounts(): array
{
    return db()->query('SELECT id, account_no, flat, owner FROM accounts ORDER BY flat')->fetchAll();
}

function years(): array
{
    $ys = db()->query('SELECT DISTINCT YEAR(period) y FROM charges
                       UNION SELECT DISTINCT YEAR(pay_date) FROM payments ORDER BY 1 DESC')
              ->fetchAll(PDO::FETCH_COLUMN);
    return $ys ?: [(int)date('Y')];
}

function layout_start(string $title, string $active): void
{
    $nav = [
        'index.php'                 => 'Главная',
        'edit.php?t=accounts'       => 'Лицевые счета',
        'edit.php?t=saldo'          => 'Сальдо',
        'edit.php?t=charges'        => 'Начисления',
        'edit.php?t=payments'       => 'Платежи',
        'turnover.php'              => 'Оборотная ведомость',
        'account.php'               => 'По квартире',
        'debtors.php'               => 'Должники',
    ];
    ?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title><?= h($title) ?> — Квартплата</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<header>
    <div class="brand">Учёт квартплаты <span>БД kvartplata</span></div>
    <nav>
        <?php foreach ($nav as $href => $label): ?>
            <a href="<?= h($href) ?>" class="<?= $href === $active ? 'active' : '' ?>"><?= h($label) ?></a>
        <?php endforeach ?>
    </nav>
</header>
<main>
    <h1><?= h($title) ?></h1>
<?php
}

function layout_end(): void
{
    echo "</main>\n</body>\n</html>\n";
}

function error_card(Throwable $e): void
{
    echo '<div class="card error">Ошибка: ' . h($e->getMessage()) . '</div>';
}
