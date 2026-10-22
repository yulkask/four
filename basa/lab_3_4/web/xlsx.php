<?php
// Чтение .xlsx без сторонних библиотек.
// Файл .xlsx — это zip-архив: список листов лежит в xl/workbook.xml,
// строки листа — в xl/worksheets/sheetN.xml, тексты — в xl/sharedStrings.xml.
// Листы читаются потоково (XMLReader), поэтому большой файл не грузится в память целиком.

class XlsxReader
{
    private ZipArchive $zip;
    private array $strings = [];
    private array $sheets = [];   // имя листа => путь внутри архива

    public function __construct(string $file)
    {
        $this->zip = new ZipArchive();
        if ($this->zip->open($file) !== true) {
            throw new RuntimeException('Файл не является книгой Excel (.xlsx)');
        }
        $this->loadSheets();
        $this->loadStrings();
    }

    public function sheetNames(): array
    {
        return array_keys($this->sheets);
    }

    // Строки листа: [номер строки => [индекс столбца с 0 => значение]], пустые ячейки пропущены.
    // Числа (в т. ч. даты Excel) возвращаются как float, тексты — как string.
    public function rows(string $sheet): Generator
    {
        $xml = $this->read($this->sheets[$sheet] ?? throw new RuntimeException("Нет листа $sheet"));
        $r = new XMLReader();
        $r->XML($xml, null, LIBXML_NONET | LIBXML_COMPACT | LIBXML_PARSEHUGE);

        $row = [];
        $rowNum = 0;
        while ($r->read()) {
            if ($r->nodeType === XMLReader::ELEMENT && $r->localName === 'row') {
                $rowNum = (int)$r->getAttribute('r');
                $row = [];
                if ($r->isEmptyElement) {
                    continue;
                }
            } elseif ($r->nodeType === XMLReader::END_ELEMENT && $r->localName === 'row') {
                if ($row) {
                    yield $rowNum => $row;
                }
            } elseif ($r->nodeType === XMLReader::ELEMENT && $r->localName === 'c') {
                $col = self::colIndex($r->getAttribute('r'));
                $type = $r->getAttribute('t');
                $value = $this->cellValue($r->readOuterXml(), $type);
                if ($value !== null && $value !== '') {
                    $row[$col] = $value;
                }
            }
        }
        $r->close();
    }

    // Дата Excel (число дней с 30.12.1899) -> 'Y-m-d H:i:s'
    public static function date(float $serial): string
    {
        return gmdate('Y-m-d H:i:s', (int)round(($serial - 25569) * 86400));
    }

    private function cellValue(string $xml, ?string $type): string|float|null
    {
        $c = simplexml_load_string($xml);
        return match ($type) {
            's'       => $this->strings[(int)$c->v] ?? '',
            'inlineStr' => self::text($c->is),
            'str', 'e' => (string)$c->v,
            'b'       => (string)$c->v,
            default   => isset($c->v) && (string)$c->v !== '' ? (float)$c->v : null,
        };
    }

    // Текст ячейки: простой <t> или форматированный <r><t>…</t></r>
    private static function text(?SimpleXMLElement $si): string
    {
        if ($si === null) {
            return '';
        }
        if (isset($si->t)) {
            return (string)$si->t;
        }
        $s = '';
        foreach ($si->r as $run) {
            $s .= (string)$run->t;
        }
        return $s;
    }

    private static function colIndex(string $ref): int
    {
        $n = 0;
        foreach (str_split(preg_replace('/\d+/', '', $ref)) as $ch) {
            $n = $n * 26 + (ord($ch) - 64);
        }
        return $n - 1;
    }

    private function loadSheets(): void
    {
        $wb = simplexml_load_string($this->read('xl/workbook.xml'));
        $rels = simplexml_load_string($this->read('xl/_rels/workbook.xml.rels'));
        $target = [];
        foreach ($rels->Relationship as $rel) {
            $target[(string)$rel['Id']] = (string)$rel['Target'];
        }
        $ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
        foreach ($wb->sheets->sheet as $sh) {
            $id = (string)$sh->attributes($ns)['id'];
            $path = ltrim($target[$id] ?? '', '/');
            $this->sheets[(string)$sh['name']] = str_starts_with($path, 'xl/') ? $path : 'xl/' . $path;
        }
    }

    private function loadStrings(): void
    {
        $xml = $this->zip->getFromName('xl/sharedStrings.xml');
        if ($xml === false) {
            return;
        }
        $r = new XMLReader();
        $r->XML($xml, null, LIBXML_NONET | LIBXML_COMPACT | LIBXML_PARSEHUGE);
        while ($r->read()) {
            if ($r->nodeType === XMLReader::ELEMENT && $r->localName === 'si') {
                $this->strings[] = self::text(simplexml_load_string($r->readOuterXml()));
            }
        }
        $r->close();
    }

    private function read(string $name): string
    {
        $data = $this->zip->getFromName($name);
        if ($data === false) {
            throw new RuntimeException("В файле нет части $name — это не книга Excel");
        }
        return $data;
    }
}
