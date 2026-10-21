<?php
// Разбор банковской выписки СберБизнес (.xlsx) и распознавание квартиры по платежу.
//
// В книге два вида листов, оба поддерживаются:
//   1) «Выписка операций по лицевому счёту» — таблица: дата проводки, счета дебета/кредита,
//      суммы по дебету/кредиту, № документа, назначение платежа;
//   2) «operations» — копии платёжных документов (платёжные поручения, банковские ордера).
// Операции с обоих листов объединяются по отпечатку «дата проводки | № документа | сумма»,
// поэтому одна операция, встречающаяся на двух листах, не дублируется.

require_once __DIR__ . '/xlsx.php';

const DOC_TITLE = '/(ПЛАТЕЖНОЕ\s+ПОРУЧЕНИЕ|ПЛАТЕЖНЫЙ\s+ОРДЕР|БАНКОВСКИЙ\s+ОРДЕР|ИНКАССОВОЕ\s+ПОРУЧЕНИЕ|МЕМОРИАЛЬНЫЙ\s+ОРДЕР)\s*№\s*(\S+)/u';

// Результат: ['account' => расчётный счёт владельца выписки, 'ops' => [операция, ...]]
// Операция: posted, doc_no, amount, direction (in|out), payer, payer_account,
//           recipient_account, purpose, ref
function parse_statement(string $file): array
{
    $x = new XlsxReader($file);
    $own = null;
    $ops = [];
    foreach ($x->sheetNames() as $name) {
        $rows = iterator_to_array($x->rows($name), true);
        if (!$rows) {
            continue;
        }
        if ($table = find_statement_table($rows)) {
            $own ??= $table['account'];
            foreach (parse_statement_table($rows, $table) as $op) {
                $ops[$op['ref']] ??= $op;
            }
        } elseif (find_cell($rows, DOC_TITLE)) {
            foreach (parse_documents($rows) as $op) {
                $ops[$op['ref']] ??= $op;
            }
        }
    }
    if (!$ops) {
        throw new RuntimeException('В файле не найдено ни одной операции. Нужна выписка СберБизнес в формате Excel.');
    }
    // счёт владельца выписки: из заголовка, а если его нет — тот, что участвует во всех операциях
    if ($own === null) {
        $cnt = [];
        foreach ($ops as $op) {
            foreach (array_unique([$op['payer_account'], $op['recipient_account']]) as $a) {
                $cnt[$a] = ($cnt[$a] ?? 0) + 1;
            }
        }
        arsort($cnt);
        $own = (string)array_key_first($cnt);
    }
    foreach ($ops as &$op) {
        $op['direction'] = $op['recipient_account'] === $own ? 'in' : 'out';
    }
    unset($op);
    uasort($ops, fn($a, $b) => strcmp($a['posted'], $b['posted']));
    return ['account' => $own, 'ops' => array_values($ops)];
}

// ---------- лист 1: таблица операций ----------

function find_statement_table(array $rows): ?array
{
    $account = null;
    foreach ($rows as $n => $row) {
        $line = implode(' ', array_filter($row, 'is_string'));
        if (str_contains(mb_strtoupper($line), 'ВЫПИСКА ОПЕРАЦИЙ') && preg_match('/\b(\d{20})\b/', $line, $m)) {
            $account = $m[1];
        }
        $cols = [];
        foreach ($row as $c => $v) {
            if (!is_string($v)) {
                continue;
            }
            $v = mb_strtolower(trim($v));
            match (true) {
                $v === 'дата проводки'        => $cols['date'] = $c,
                $v === 'счет' || $v === 'счёт' => $cols['acc'] = $c,
                $v === 'сумма по дебету'      => $cols['debit'] = $c,
                $v === 'сумма по кредиту'     => $cols['credit'] = $c,
                $v === '№ документа'          => $cols['doc'] = $c,
                $v === 'назначение платежа'   => $cols['purpose'] = $c,
                default => null,
            };
        }
        if (isset($cols['date'], $cols['debit'], $cols['credit'], $cols['purpose'])) {
            // под заголовком «Счет» — подзаголовки «Дебет» и «Кредит»
            $sub = $rows[$n + 1] ?? [];
            foreach ($sub as $c => $v) {
                if ($v === 'Дебет') $cols['acc_debit'] = $c;
                if ($v === 'Кредит') $cols['acc_credit'] = $c;
            }
            return ['header' => $n, 'cols' => $cols, 'account' => $account];
        }
    }
    return null;
}

function parse_statement_table(array $rows, array $t): Generator
{
    $c = $t['cols'];
    foreach ($rows as $n => $row) {
        if ($n <= $t['header'] || !is_float($row[$c['date']] ?? null)) {
            continue;
        }
        $debit = (float)($row[$c['debit']] ?? 0);
        $credit = (float)($row[$c['credit']] ?? 0);
        $amount = $credit ?: $debit;
        if ($amount <= 0) {
            continue;
        }
        // ячейка счёта: «номер счёта \n ИНН \n наименование» (ИНН бывает пропущен)
        $split = function ($s) {
            $lines = array_values(array_filter(array_map('trim', explode("\n", (string)$s)), 'strlen'));
            $acc = array_shift($lines) ?? '';
            if ($lines && preg_match('/^\d+$/', $lines[0])) array_shift($lines);
            return [$acc, implode(' ', $lines)];
        };
        [$dAcc, $dName] = $split($row[$c['acc_debit'] ?? -1] ?? '');
        [$kAcc] = $split($row[$c['acc_credit'] ?? -1] ?? '');
        yield make_op(
            XlsxReader::date($row[$c['date']]),
            trim((string)($row[$c['doc']] ?? '')),
            $amount,
            $dName, $dAcc, $kAcc,
            trim((string)($row[$c['purpose']] ?? ''))
        );
    }
}

// ---------- лист 2: платёжные документы ----------

function parse_documents(array $rows): Generator
{
    // документ начинается со строки-колонтитула «СберБизнес …»; режем лист на блоки по ней
    $block = [];
    foreach ($rows as $n => $row) {
        $first = (string)($row[1] ?? '') . ' ' . (string)($row[3] ?? '');
        if (str_contains($first, 'СберБизнес') && $block) {
            if ($op = parse_document($block)) yield $op;
            $block = [];
        }
        $block[$n] = $row;
    }
    if ($block && ($op = parse_document($block))) {
        yield $op;
    }
}

function parse_document(array $b): ?array
{
    $title = find_cell($b, DOC_TITLE);
    if (!$title) {
        return null;
    }
    preg_match(DOC_TITLE, $title[2], $m);
    $docNo = $m[2];
    $keys = array_keys($b);
    $pos = array_flip($keys);   // номер строки => порядковый номер в блоке

    // сумма: справа от метки «Сумма» или под ней («311-27», «1700=»)
    $amount = null;
    if ($lbl = find_cell($b, '/^Сумма$/u')) {
        [$r, $c] = $lbl;
        $next = $b[$keys[$pos[$r] + 1] ?? -1] ?? [];
        $cand = array_filter($b[$r], fn($cc) => $cc > $c, ARRAY_FILTER_USE_KEY)
              + array_filter($next, fn($cc) => $cc >= $c, ARRAY_FILTER_USE_KEY);
        foreach ($cand as $v) {
            if (is_string($v) && preg_match('/^(\d+)(?:[-.,](\d{1,2}))?=?$/', trim($v), $mm)) {
                $amount = (float)($mm[1] . '.' . ($mm[2] ?? '0'));
                break;
            }
        }
    }
    if (!$amount) {
        return null;
    }

    // счета: первый 20-значный — плательщика, последний — получателя
    $accounts = [];
    foreach ($b as $row) {
        foreach ($row as $v) {
            if (is_string($v) && preg_match('/^\d{20}$/', trim($v))) {
                $accounts[] = trim($v);
            }
        }
    }
    if (count($accounts) < 2) {
        return null;
    }

    // плательщик: текст в столбце B между строкой суммы и меткой «Плательщик»
    // (в банковском ордере — сразу под меткой)
    $payer = '';
    $lblPayer = find_cell($b, '/^Плательщик$/u');
    if ($lblPayer) {
        $from = $lbl ? $pos[$lbl[0]] + 1 : 0;
        for ($i = $from; $i < $pos[$lblPayer[0]]; $i++) {
            $v = $b[$keys[$i]][1] ?? null;
            if (is_string($v) && !preg_match('/^(ИНН|КПП)$/u', $v)) {
                $payer .= ($payer === '' ? '' : ' ') . trim($v);
            }
        }
        if ($payer === '') {
            $payer = trim((string)($b[$keys[$pos[$lblPayer[0]] + 1]][1] ?? ''));
        }
    }

    // назначение: текст в столбце B между меткой «Получатель» и «Назначение платежа»,
    // а если там пусто — под меткой «Назначение платежа»
    $purpose = '';
    $lblPurpose = find_cell($b, '/^Назначение платежа$/u');
    $lblRecipient = find_cell($b, '/^Получатель$/u');
    if ($lblPurpose) {
        $labels = '/^(№ ч\. плат\.|Содержание операции:|Получатель|Назначение платежа)$/u';
        $collect = function (int $from, int $to) use ($b, $keys, $labels) {
            $s = [];
            for ($i = $from; $i < $to; $i++) {
                $v = $b[$keys[$i]][1] ?? null;
                if (is_string($v) && !preg_match($labels, trim($v))) {
                    $s[] = trim($v);
                }
            }
            return implode(' ', $s);
        };
        if ($lblRecipient && $pos[$lblRecipient[0]] < $pos[$lblPurpose[0]]) {
            $purpose = $collect($pos[$lblRecipient[0]] + 1, $pos[$lblPurpose[0]]);
        }
        if ($purpose === '') {
            $p = $pos[$lblPurpose[0]] + 1;
            $end = $p;
            while ($end < count($keys) && is_string($b[$keys[$end]][1] ?? null)) $end++;
            $purpose = $collect($p, $end);
        }
    }

    // дата проводки — отметка банка «ИСПОЛНЕНО» и время под ней
    $posted = null;
    if ($done = find_cell($b, '/^ИСПОЛНЕНО$/u')) {
        for ($i = $pos[$done[0]] + 1; $i < count($keys) && $posted === null; $i++) {
            foreach ($b[$keys[$i]] as $v) {
                if (is_float($v) && $v > 30000 && $v < 80000) {
                    $posted = XlsxReader::date($v);
                    break;
                }
            }
        }
    }
    if ($posted === null) {
        return null;
    }
    return make_op($posted, $docNo, $amount, $payer, $accounts[0], end($accounts), $purpose);
}

function make_op(string $posted, string $docNo, float $amount, string $payer,
                 string $payerAcc, string $recipientAcc, string $purpose): array
{
    $purpose = preg_replace('/\s+/u', ' ', $purpose);
    return [
        'posted'            => $posted,
        'doc_no'            => mb_substr($docNo, 0, 20),
        'amount'            => round($amount, 2),
        'payer'             => preg_replace('/\s+/u', ' ', $payer),
        'payer_account'     => $payerAcc,
        'recipient_account' => $recipientAcc,
        'purpose'           => $purpose,
        'ref'               => sha1($posted . '|' . $docNo . '|' . number_format($amount, 2, '.', '')),
    ];
}

// Первая ячейка, текст которой подходит под шаблон: [номер строки, столбец, текст]
function find_cell(array $rows, string $re): ?array
{
    foreach ($rows as $n => $row) {
        foreach ($row as $c => $v) {
            if (is_string($v) && preg_match($re, trim($v))) {
                return [$n, $c, trim($v)];
            }
        }
    }
    return null;
}

// ---------- плательщик и квартира ----------

// «ПАО СБЕРБАНК//ИВАНОВ ИВАН ИВАНОВИЧ//326320605993//АДРЕС//» -> ['name' => …, 'address' => …]
function payer_parts(string $payer): array
{
    if (str_contains($payer, '//')) {
        $p = array_values(array_filter(array_map('trim', explode('//', $payer)), 'strlen'));
        $name = $p[1] ?? $p[0];
        $address = '';
        foreach (array_slice($p, 2) as $part) {
            if (!preg_match('/^\d+$/', $part)) $address .= ' ' . $part;
        }
        return ['name' => $name, 'address' => trim($address)];
    }
    // «АО "ТИНЬКОФФ БАНК" / ФАМИЛИЯ ИМЯ»
    if (preg_match('~\s/\s+([^/]+)$~u', $payer, $m)) {
        return ['name' => trim($m[1]), 'address' => ''];
    }
    // «ФАМИЛИЯ ИМЯ ОТЧЕСТВО р/с 408… в АО "АЛЬФА-БАНК"»
    return ['name' => trim(preg_replace('~\s+р/с\s.*$~u', '', $payer)), 'address' => ''];
}

// Номер квартиры из назначения платежа или реквизитов плательщика.
// Возвращает [номер, как найден] или [null, null].
function detect_flat(string $purpose, string $payer): array
{
    // у Сбербанка назначение начинается со служебного «Дата оплаты …,сумма …,Назначение платежа:»
    $p = trim(preg_replace('/^.*Назначение платежа:\s*/iu', '', $purpose));
    $n = '0*(\d{1,4})(?!\d)';
    $house = '12\s*(?:[-\/]|\s*к\.?\s*|\s+)\s*2\s*[-,\s]\s*(?:кв\.?\s*)?';   // дом 12 корпус 2
    $rules = [
        // л/с 164, лс 144, л.с 187, ЛСЧ 0000000111, л/сч 36, л/с№106
        ['/(?<![а-яё])(?:л[\s.\/]*с\s*ч?|лсч|лиц\.?\s*сч(?:[её]т)?)[\s.:№#]*' . $n . '/iu', 'лицевой счёт в назначении'],
        // кв 160, кв.183, КВ100, квартира 161, квартиры 159, кв номер 142
        ['/(?<![а-яё])(?:кв|квартир[аыеу]?)[\s.:№#-]*(?:номер\s*)?' . $n . '/iu', 'квартира в назначении'],
        // Осенний б-р 12-2-24, 12/2-148
        ['/\b' . $house . $n . '/iu', 'адрес в назначении'],
        // «л 52 за 01 2018»
        ['/(?<![а-яё])л[\s.]+' . $n . '/iu', 'лицевой счёт в назначении'],
        // «12 2017 124»: месяц, год, лицевой счёт
        ['/^(?:0?[1-9]|1[0-2])[\s.,\/-]+20\d\d\s+' . $n . '$/u', 'код «месяц год л/с»'],
        // «079 12 2017»: лицевой счёт, месяц, год
        ['/^' . $n . '\s+(?:0?[1-9]|1[0-2])[\s.,\/-]+20\d\d$/u', 'код «л/с месяц год»'],
        // «0000000087 08090809»: лицевой счёт с ведущими нулями
        ['/^0{3,}(\d{1,4})\b/u', 'лицевой счёт в назначении'],
        // назначение — только номер: «141»
        ['/^' . $n . '$/u', 'номер в назначении'],
    ];
    foreach ($rules as [$re, $why]) {
        if (preg_match($re, $p, $m) && (int)$m[1] > 0) {
            return [(int)$m[1], $why];
        }
    }
    // адрес плательщика из реквизитов банка: «ОСЕННИЙ Д 12 К 2 КВ 164», «ОСЕННИЙ Б-Р 12-2-28»,
    // «Б-Р ОСЕННИЙ 12 2, 46», «Осенний б-р, д. 12К2, кв. 88»
    // только если это наш дом: Осенний б-р, д. 12, корп. 2
    if (preg_match('/ОСЕНН[^\/]*?(?<!\d)(?:Д\.?\s*)?12(?:\b|К)/iu', $payer)) {
        foreach ([
            '/(?<![А-ЯЁ])КВ[\s.]*' . $n . '/iu',
            '/ОСЕНН\S*\s+(?:Б-Р\s+|БУЛЬВАР\s+)?(?:Д\.?\s*)?' . $house . $n . '/iu',
            '/(?<!\d)12\s*-\s*2\s*-\s*' . $n . '/u',
        ] as $re) {
            if (preg_match($re, $payer, $m) && (int)$m[1] > 0) {
                return [(int)$m[1], 'адрес плательщика'];
            }
        }
    }
    return [null, null];
}
