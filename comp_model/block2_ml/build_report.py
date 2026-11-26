"""Собирает Word-отчёт: условие, решение и ответ по каждой из 20 задач."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import solve_all

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = os.path.dirname(os.path.abspath(__file__))
RES = json.load(open(os.path.join(ROOT, "results", "results.json"), encoding="utf-8"))
OUT_DOC = os.path.join(os.path.dirname(ROOT), "КМ_Блок_2_решения.docx")

# легенда графика задачи 10 сдвинута; пересохраняем рисунок теми же числами
solve_all.task_10()


def f4(x):
    return f"{x:.4f}"


def ms(sec):
    v = sec * 1000
    return f"{v:.2f} мс" if sec < 0.1 else f"{v:.0f} мс"


def f3(x):
    return f"{x:.3f}"


def f2(x):
    return f"{x:.2f}"


def pct(x):
    return f"{100 * x:.1f}%"


def set_run_font(run, name="Times New Roman", size=12, bold=False, italic=False, color=None):
    run.font.name = name
    run.bold = bold
    run.italic = italic
    run.font.size = Pt(size)
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if color is not None:
        run.font.color.rgb = RGBColor(*color)


def shade_cell(cell, fill):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def set_cell_border(cell, color="BFBFBF"):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), color)
        tcBorders.append(el)
    tcPr.append(tcBorders)


def set_cell_margins(cell):
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, w in (("top", "40"), ("left", "80"), ("bottom", "40"), ("right", "80")):
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), w)
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def prevent_row_split(row):
    tr = row._tr
    trPr = tr.get_or_add_trPr()
    cant = OxmlElement("w:cantSplit")
    trPr.append(cant)


def para(doc, text="", size=12, bold=False, italic=False, before=0, after=6,
         align="justify", font="Times New Roman", color=None, keep_next=False):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = 1.15
    pf.widow_control = True
    if keep_next:
        pf.keep_together = True
        pf.keep_with_next = True
    p.alignment = {
        "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        "left": WD_ALIGN_PARAGRAPH.LEFT,
        "center": WD_ALIGN_PARAGRAPH.CENTER,
    }[align]
    if text:
        r = p.add_run(text)
        set_run_font(r, name=font, size=size, bold=bold, italic=italic, color=color)
    return p


def add_runs(p, parts):
    for text, kwargs in parts:
        r = p.add_run(text)
        set_run_font(r, **kwargs)
    return p


def heading_block(doc, text):
    p = para(doc, text, size=16, bold=True, before=16, after=8, align="left", keep_next=True)
    pPr = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "1F4E79")
    pBdr.append(bottom)
    pPr.append(pBdr)
    return p


def heading_task(doc, text):
    return para(doc, text, size=14, bold=True, before=14, after=4, align="left",
                color=(31, 78, 121), keep_next=True)


def condition(doc, text):
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:w"), str(int(17.4 * 567)))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)
    cell = table.cell(0, 0)
    cell.width = Cm(17.4)
    cell.text = ""
    shade_cell(cell, "F7F4EE")
    set_cell_border(cell, "C4B8A5")
    set_cell_margins(cell)
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    add_runs(p, [
        ("Условие. ", {"size": 12, "bold": True, "italic": True}),
        (text, {"size": 12, "italic": True}),
    ])
    para(doc, "", size=6, after=2)


def solution_label(doc):
    para(doc, "Решение", size=12, bold=True, before=8, after=4, align="left", keep_next=True)


def answer_label(doc):
    para(doc, "Ответ", size=12, bold=True, before=8, after=2, align="left", keep_next=True)


def formula(doc, text):
    para(doc, text, size=12, italic=True, before=2, after=2, align="center")


def image(doc, path, width=15.6, caption=None):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(path, width=Cm(width))
    if caption:
        para(doc, caption, size=10, italic=True, before=0, after=8, align="center",
             color=(80, 80, 80))


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement("w:tblPr")
    tblW = OxmlElement("w:tblW")
    total = int(sum(widths) * 567)
    tblW.set(qn("w:w"), str(total))
    tblW.set(qn("w:type"), "dxa")
    tblPr.append(tblW)

    for j, h in enumerate(headers):
        cell = table.rows[0].cells[j]
        cell.text = ""
        shade_cell(cell, "1F4E79")
        set_cell_margins(cell)
        set_cell_border(cell, "1F4E79")
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        set_run_font(r, size=10, bold=True, color=(255, 255, 255))
    prevent_row_split(table.rows[0])
    trPr = table.rows[0]._tr.get_or_add_trPr()
    hdr = OxmlElement("w:tblHeader")
    trPr.append(hdr)

    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.rows[i + 1].cells[j]
            cell.text = ""
            if i % 2 == 1:
                shade_cell(cell, "F3F6FA")
            set_cell_margins(cell)
            set_cell_border(cell, "D0D7E2")
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(str(val))
            set_run_font(r, size=10)
        prevent_row_split(table.rows[i + 1])

    for row in table.rows:
        for j, cell in enumerate(row.cells):
            cell.width = Cm(widths[j])
    # строка не остаётся одна внизу страницы: она держится вместе со следующей
    for row in table.rows[:-1]:
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.keep_with_next = True
    para(doc, "", size=4, after=2)
    return table


def code_block(doc, text):
    for line in text.rstrip("\n").split("\n"):
        para(doc, line if line else " ", size=10, before=0, after=0, align="left",
             font="Courier New")
    para(doc, "", size=4, after=2)


def build():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(1.7)
    sec.bottom_margin = Cm(1.7)
    sec.left_margin = Cm(1.8)
    sec.right_margin = Cm(1.7)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal.font.size = Pt(12)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")

    footer = sec.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("Компьютерное моделирование  ·  блок 2  ·  стр. ")
    set_run_font(r, size=9, color=(90, 90, 90))
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run2 = fp.add_run()
    set_run_font(run2, size=9, color=(90, 90, 90))
    run2._r.append(fld_begin)
    run2._r.append(instr)
    run2._r.append(fld_end)

    para(doc, "20 задач по теме «Простейшие модели машинного обучения»",
         size=18, bold=True, before=0, after=2, align="center")
    para(doc, "Решения и ответы", size=14, italic=True, before=0, after=2, align="center",
         color=(31, 78, 121))
    para(doc, "Дисциплина: Компьютерное моделирование    Направление: МОиАИС    Курс: 4",
         size=11, before=0, after=8, align="center")
    para(
        doc,
        "Условия приведены по исходному файлу и не изменялись. Там, где в условии нет числовой таблицы, "
        "выборка зафиксирована генератором NumPy с seed = 42; все числа ниже получены прямым счётом. "
        "Готовые модели sklearn используются только там, где условие просит сравнить свою реализацию с библиотекой "
        "или подобрать параметры через GridSearchCV. МНК, градиентный спуск, softmax, k-NN, гауссовский и "
        "мультиномиальный наивный Байес, дерево, бэггинг и k-fold реализованы самостоятельно.",
        size=11, after=6,
    )

    t1 = RES["t1"]
    t3 = RES["t3"]
    t5 = RES["t5"]
    t6 = RES["t6"]
    t8 = RES["t8"]
    t9 = RES["t9"]
    t10 = RES["t10"]
    t11 = RES["t11"]
    t12 = RES["t12"]
    t13 = RES["t13"]
    t14 = RES["t14"]
    t15 = RES["t15"]
    t16 = RES["t16"]
    t17 = RES["t17"]
    t19 = RES["t19"]
    t20 = RES["t20"]

    # ------------------------------------------------------------------
    heading_block(doc, "Блок 1. Линейная регрессия (задачи 1–5)")

    heading_task(doc, "Задача 1. Одномерная линейная регрессия «вручную»")
    condition(
        doc,
        "Дана выборка из 10 точек (xᵢ, yᵢ). Реализуйте метод наименьших квадратов (МНК) без использования "
        "готовых ML-библиотек: вычислите коэффициенты a и b модели ŷ = ax + b по аналитическим формулам. "
        "Постройте график исходных точек и прямой. Вычислите MSE и R².",
    )
    solution_label(doc)
    para(doc, "В файле с заданием координаты десяти точек не заданы, поэтому взята модельная выборка с известной прямой и шумом:")
    formula(doc, "xᵢ = i,    yᵢ = 2xᵢ + 3 + εᵢ,    εᵢ ~ N(0, 1.5²),    i = 1, …, 10.")
    para(doc, "Реализация шума — numpy.random.default_rng(42). Полученные ординаты:")
    add_table(
        doc,
        ["i", "x", "y"],
        [[str(i), str(int(x)), f3(y)] for i, (x, y) in enumerate(zip(t1["x"], t1["y"]), start=1)],
        [2.2, 3.0, 4.0],
    )
    para(doc, "Минимум суммы квадратов остатков для модели ŷ = ax + b достигается в точке")
    formula(doc, "a = Σ(xᵢ − x̄)(yᵢ − ȳ) / Σ(xᵢ − x̄)²,    b = ȳ − a x̄.")
    para(
        doc,
        f"Суммы по выборке: x̄ = {t1['x_bar']:.1f}, ȳ = {t1['y_bar']:.4f}, "
        f"Sₓₓ = Σ(xᵢ − x̄)² = {t1['sxx']:.1f}, Sₓᵧ = Σ(xᵢ − x̄)(yᵢ − ȳ) = {t1['sxy']:.4f}. "
        f"Отсюда a = {t1['sxy']:.4f} / {t1['sxx']:.1f} = {t1['a']:.4f}, "
        f"b = {t1['y_bar']:.4f} − {t1['a']:.4f} · 5.5 = {t1['b']:.4f}.",
    )
    para(doc, "Ошибки считаются по определениям")
    formula(doc, "MSE = (1/n) Σ(yᵢ − ŷᵢ)²,    R² = 1 − Σ(yᵢ − ŷᵢ)² / Σ(yᵢ − ȳ)².")
    para(
        doc,
        f"Сумма квадратов остатков SS_res = {t1['ss_res']:.4f}, полная сумма SS_tot = {t1['ss_tot']:.4f}. "
        f"Значит MSE = {t1['mse']:.4f}, R² = {t1['r2']:.4f}. "
        f"Оценка a близка к заложенному коэффициенту 2, оценка b — к свободному члену 3: шум не сдвинул прямую сильно.",
    )
    image(doc, os.path.join(ROOT, "results", "task01_regression.png"),
          caption="Рис. 1. Наблюдения и прямая МНК.")
    answer_label(doc)
    para(doc, f"a = {t1['a']:.4f},  b = {t1['b']:.4f},  MSE = {t1['mse']:.4f},  R² = {t1['r2']:.4f}.", bold=True)

    heading_task(doc, "Задача 2. Сравнение МНК и градиентного спуска")
    condition(
        doc,
        "Для той же выборки реализуйте обучение линейной регрессии методом градиентного спуска. "
        "Исследуйте влияние скорости обучения η ∈ {0.001, 0.01, 0.1, 0.5} на сходимость. "
        "Постройте графики зависимости функции потерь от номера итерации. Сравните результат с аналитическим решением.",
    )
    solution_label(doc)
    para(doc, "Минимизируется та же функция, что и в МНК:")
    formula(doc, "L(a, b) = (1/n) Σ (a xᵢ + b − yᵢ)².")
    para(doc, "Градиент и шаг:")
    formula(doc, "∂L/∂a = (2/n) Σ eᵢ xᵢ,    ∂L/∂b = (2/n) Σ eᵢ,    eᵢ = a xᵢ + b − yᵢ.")
    para(
        doc,
        "Старт — (a, b) = (0, 0), число итераций — 20 000. Для квадратичной L гессиан по вектору (a, b) равен",
    )
    formula(doc, "H = (2/n) [[Σ xᵢ², Σ xᵢ], [Σ xᵢ, n]] = [[77, 11], [11, 2]].")
    para(
        doc,
        "Его старшее собственное число λ_max ≈ 78.6, поэтому градиентный спуск с постоянным шагом устойчив при "
        "η < 2/λ_max ≈ 0.025. Скорости 0.001 и 0.01 попадают в этот интервал, скорости 0.1 и 0.5 — нет.",
    )
    gd_rows = []
    for eta in ("0.001", "0.01", "0.1", "0.5"):
        g = t1["gd"][eta]
        if g["status"] == "сошёлся":
            gd_rows.append([eta, "сходится", f4(g["a"]), f4(g["b"]), f4(g["loss"]), "20 000"])
        else:
            gd_rows.append([eta, "расходится", "—", "—", "—", f"шаг {g['diverge_at']}"])
    add_table(
        doc,
        ["η", "поведение", "a", "b", "MSE", "итерации"],
        gd_rows,
        [2.2, 2.8, 2.4, 2.4, 2.4, 2.6],
    )
    para(
        doc,
        f"При η = 0.01 коэффициенты совпали с аналитическими до ошибки порядка 10⁻¹⁴ "
        f"(Δa = {t1['gd']['0.01']['delta_a']:.1e}, Δb = {t1['gd']['0.01']['delta_b']:.1e}). "
        f"При η = 0.001 за 20 000 шагов решение ещё чуть не дошло: a = {t1['gd']['0.001']['a']:.4f}, "
        f"b = {t1['gd']['0.001']['b']:.4f}, MSE отличается от МНК в шестом знаке. "
        "При η = 0.1 потеря превысила 10⁸ на 4-й итерации, при η = 0.5 — на 2-й: шаг перескакивает минимум, и ошибка растёт.",
    )
    image(doc, os.path.join(ROOT, "results", "task02_gd.png"),
          caption="Рис. 2. Слева — первые итерации (логарифм MSE), справа — две сходящиеся скорости.")
    answer_label(doc)
    para(
        doc,
        f"Аналитическое решение: a = {t1['a']:.4f}, b = {t1['b']:.4f}, MSE = {t1['mse']:.4f}. "
        "Градиентный спуск повторяет его при η = 0.01. При η = 0.001 сходится к той же точке медленнее. "
        "При η = 0.1 и η = 0.5 метод расходится.",
        bold=True,
    )

    heading_task(doc, "Задача 3. Множественная линейная регрессия")
    condition(
        doc,
        "Дан датасет с 4 признаками (например, прогноз цены квартиры: площадь, этаж, расстояние до метро, год постройки). "
        "Реализуйте множественную линейную регрессию в матричной форме: ŷ = Xw. "
        "Найдите веса через псевдообратную матрицу Мура–Пенроуза. Проверьте обусловленность матрицы XᵀX.",
    )
    solution_label(doc)
    para(
        doc,
        "Сгенерировано n = 120 квартир (seed = 42). Признаки: площадь (м²) из U(28, 110), этаж — целое от 1 до 17, "
        "расстояние до метро (км) из U(0.2, 6), год постройки — целое от 1965 до 2023. Цена (тыс. у. е.) задана линейно:",
    )
    formula(doc, "price = 90·площадь + 12·этаж − 35·до_метро + 1.8·(год − 2000) + 400 + ε,   ε ~ N(0, 80²).")
    para(doc, "В матрицу плана добавлен столбец единиц. Вектор весов — решение наименьших квадратов через псевдообратную:")
    formula(doc, "w = X⁺ y,    X⁺ = (XᵀX)⁻¹ Xᵀ  для матрицы полного столбцового ранга.")
    para(
        doc,
        "Та же формула, записанная через год целиком, имеет свободный член 400 − 1.8·2000 = −3200 и коэффициент при годе 1.8. "
        "Именно с этими числами сравниваются оценки.",
    )
    names = ["свободный член", "площадь", "этаж", "до метро", "год"]
    true = ["−3200", "90", "12", "−35", "1.8"]
    est = [f2(w) if i == 0 else f4(w) for i, w in enumerate(t3["weights"])]
    add_table(doc, ["", *names], [["заложено", *true], ["оценка МНК", *est]], [3.2, 2.6, 2.3, 2.0, 2.3, 2.0])
    para(
        doc,
        f"Число обусловленности cond(XᵀX) = {t3['cond_xtx']:.4e}. Матрица формально обратима, но плохо обусловлена: "
        f"столбец единиц и столбец «год» (значения около 2000) сильно различаются по масштабу со столбцом «этаж». "
        f"После стандартизации четырёх признаков cond(XᵀX) падает до {t3['cond_xtx_standardized']:.3f}. "
        f"На качестве прогноза это почти не сказалось: MSE = {t3['mse']:.1f} при дисперсии шума 6400, "
        f"R² = {t3['r2']:.4f}. Сдвиг свободного члена и коэффициента года относительно −3200 и 1.8 — следствие "
        "этой почти коллинеарной пары «константа / год» и шума, а не ошибка псевдообратной.",
    )
    answer_label(doc)
    para(
        doc,
        f"w = ({t3['weights'][0]:.2f};  {t3['weights'][1]:.2f};  {t3['weights'][2]:.2f};  "
        f"{t3['weights'][3]:.2f};  {t3['weights'][4]:.2f}) для (1, площадь, этаж, до метро, год). "
        f"cond(XᵀX) = {t3['cond_xtx']:.3e}; после стандартизации признаков — {t3['cond_xtx_standardized']:.3f}. "
        f"R² = {t3['r2']:.4f}.",
        bold=True,
    )

    heading_task(doc, "Задача 4. Регуляризация: Ridge и Lasso")
    condition(
        doc,
        "На данных задачи 3 реализуйте Ridge- (L2) и Lasso-регрессию (L1). "
        "Исследуйте зависимость коэффициентов модели от параметра регуляризации λ. "
        "Объясните, почему Lasso приводит к разреженным решениям, а Ridge — нет.",
    )
    solution_label(doc)
    para(
        doc,
        "Признаки стандартизованы по обучающей выборке (она здесь совпадает со всей выборкой задачи 3), отклик центрирован. "
        "Штраф на свободный член не накладывается. Минимизируются",
    )
    formula(doc, "L₂:  (1/(2n))‖Zw − y‖² + (λ/2)‖w‖²,      L₁:  (1/(2n))‖Zw − y‖² + λ‖w‖₁.")
    para(
        doc,
        "Ridge считается по замкнутой формуле (ZᵀZ + nλ I)⁻¹ Zᵀy. Lasso — покоординатным спуском: "
        "частное обновление признака j есть мягкий порог ρⱼ на уровне λ, где ρⱼ = (1/n) zⱼᵀ rⱼ и столбец zⱼ имеет единичную выборочную дисперсию. "
        "Коэффициенты затем возвращены в исходный масштаб признаков.",
    )

    def nearest(path, target):
        return min(path, key=lambda p: abs(__import__("math").log(p["lambda"]) - __import__("math").log(target)))

    targets = [0.01, 0.58, 4.4, 34, 260]
    head = ["λ"] + t3["names"] + ["нулей"]
    ridge_rows, lasso_rows = [], []
    for t in targets:
        for path, bucket in ((t3["ridge"], ridge_rows), (t3["lasso"], lasso_rows)):
            p = nearest(path, t)
            bucket.append(
                [f"{p['lambda']:.3g}"] + [f2(c) for c in p["coef"]] + [str(p["n_zero"])]
            )
    para(doc, "Коэффициенты Ridge в исходном масштабе:")
    add_table(doc, head, ridge_rows, [2.2, 2.5, 2.2, 2.6, 2.2, 2.0])
    para(doc, "Коэффициенты Lasso в исходном масштабе:")
    add_table(doc, head, lasso_rows, [2.2, 2.5, 2.2, 2.6, 2.2, 2.0])
    para(
        doc,
        "У Ridge все четыре коэффициента остаются ненулевыми на всей сетке λ и одновременно тянутся к нулю. "
        "У Lasso при λ ≈ 34 обнуляется коэффициент года, при λ ≈ 258 ненулевой остаётся только площадь. "
        "Площадь в этой модели — самый сильный признак, поэтому она уходит последней.",
    )
    para(
        doc,
        "Геометрическая причина разная. Линии уровня ошибки — эллипсоиды. Ограничение L2 — шар, его граница гладкая, "
        "точка касания с эллипсоидом почти всегда имеет все координаты ненулевые: штраф λwⱼ в уравнении для каждого коэффициента "
        "уменьшает его, но не заставляет пересечь ноль за конечный шаг. Ограничение L1 — октаэдр с вершинами на осях. "
        "Касание часто происходит в вершине или на ребре, и тогда часть координат решения равна нулю. "
        "В покоординатном виде это и есть мягкое пороговое правило: если корреляция остатка с признаком меньше λ, вес ставится в ноль.",
    )
    image(doc, os.path.join(ROOT, "results", "task04_paths.png"),
          caption="Рис. 3. Пути коэффициентов. У Lasso линии ложатся на ноль, у Ridge — только приближаются к нему.")
    answer_label(doc)
    para(
        doc,
        "При росте λ Ridge уменьшает все веса, не обнуляя их. Lasso обнуляет слабые признаки: сначала год, затем этаж и расстояние до метро; "
        "при большом λ остаётся площадь. Разреженность даёт угловая геометрия L1-ограничения и мягкий порог в покоординатном спуске.",
        bold=True,
    )

    heading_task(doc, "Задача 5. Полиномиальная регрессия и переобучение")
    condition(
        doc,
        "Для нелинейной зависимости y = sin(x) + ε постройте полиномиальные модели степеней 1, 3, 7, 15. "
        "Разделите данные на обучающую и тестовую выборки. Покажите эффект переобучения через графики и значения ошибок на train/test.",
    )
    solution_label(doc)
    para(
        doc,
        f"Взято n = {t5['n']} точек, x ~ U(−π, π), ε ~ N(0, {t5['noise_std']}²), seed = 42. "
        f"Случайное разбиение 70/30: {t5['n_train']} точек в обучении и {t5['n_test']} в тесте. "
        "Полином строится по аргументу z = x/π ∈ [−1, 1], чтобы матрица Вандермонда степени 15 оставалась вычислимой; "
        "это тот же класс полиномов степени d от x. Коэффициенты — numpy.polynomial.polynomial.polyfit, то есть МНК.",
    )
    add_table(
        doc,
        ["степень", "MSE train", "MSE test", "R² train", "R² test"],
        [[
            str(r["degree"]), f4(r["train_mse"]), f4(r["test_mse"]), f4(r["train_r2"]), f4(r["test_r2"])
        ] for r in t5["rows"]],
        [2.6, 3.0, 3.0, 3.0, 3.0],
    )
    para(
        doc,
        "Степень 1 даёт прямую вместо волны: обе ошибки около 0.22. Степени 3 и 7 уже повторяют синус, тестовая ошибка "
        "падает до 0.073 и почти совпадает с дисперсией шума 0.0625. Степень 15 ещё чуть снижает ошибку на обучении "
        f"({t5['rows'][3]['train_mse']:.4f}), но на тесте MSE вырастает до {t5['rows'][3]['test_mse']:.2f}, а R² становится отрицательным "
        f"({t5['rows'][3]['test_r2']:.2f}): модель описывает шум обучающей выборки и между узлами колеблется. "
        "На графике степени 15 это видно по выбросам кривой у краёв отрезка.",
    )
    image(doc, os.path.join(ROOT, "results", "task05_poly.png"), width=16.0,
          caption="Рис. 4. Полиномы четырёх степеней. Ось y ограничена отрезком [−2.2, 2.2], чтобы были видны колебания степени 15.")
    answer_label(doc)
    para(
        doc,
        "Переобучение наступает на степени 15: MSE train = 0.0334 при MSE test = 8.91. "
        "Рабочие модели — степени 3 и 7 (MSE test ≈ 0.073). Степень 1 недообучена (MSE test = 0.229).",
        bold=True,
    )

    # ------------------------------------------------------------------
    heading_block(doc, "Блок 2. Логистическая регрессия и классификация (задачи 6–10)")

    heading_task(doc, "Задача 6. Логистическая регрессия с нуля")
    condition(
        doc,
        "Реализуйте бинарный классификатор на основе логистической регрессии. Используйте сигмоиду σ(z) = 1/(1 + e^(−z)) "
        "и кросс-энтропийную функцию потерь. Обучите модель градиентным спуском на датасете «две луны» (make_moons). "
        "Визуализируйте разделяющую границу.",
    )
    solution_label(doc)
    m = t6["metrics"]
    w = t6["weights"]
    para(
        doc,
        f"Выборка make_moons: n = {t6['n']}, шум = {t6['noise']}, seed = 42. Стратифицированное разбиение 70/30, "
        f"в тесте {t6['n_test']} точек. Признаки стандартизованы по обучающей части. Модель линейна по этим признакам:",
    )
    formula(doc, "P(y = 1 | x) = σ(w₀ + wᵀx),    σ(z) = 1 / (1 + e^(−z)).")
    formula(doc, "L(w) = −(1/n) Σ [yᵢ log pᵢ + (1 − yᵢ) log(1 − pᵢ)].")
    para(
        doc,
        "Градиент равен (1/n) X̃ᵀ(p − y), где X̃ — матрица со столбцом единиц. Аргумент сигмоиды обрезается на [−30, 30], "
        "чтобы экспонента не переполнялась. Шаг 0.8, 3000 итераций, старт из нуля.",
    )
    para(
        doc,
        f"Получены веса (свободный член, z₁, z₂) = ({w[0]:.4f}, {w[1]:.4f}, {w[2]:.4f}). "
        f"Кросс-энтропия на обучении в конце спуска равна {m['loss_last']:.4f}. "
        f"На тесте при пороге 0.5 доля верных ответов {m['accuracy']:.4f}. "
        "Граница σ = 0.5 — прямая в координатах стандартизованных признаков и потому гладкая кривая-полоса на рисунке исходных «лун». "
        "Луны линейно не разделимы, часть красных точек остаётся над прямой, часть синих — под ней. Это ограничение модели, а не недообучение спуска: потеря вышла на плато.",
    )
    image(doc, os.path.join(ROOT, "results", "task06_boundary.png"),
          caption="Рис. 5. Вероятность класса 1 и граница 0.5 на make_moons.")
    answer_label(doc)
    para(
        doc,
        f"Веса: w = ({w[0]:.4f}, {w[1]:.4f}, {w[2]:.4f}). Точность на тесте {m['accuracy']:.4f}. "
        "Разделяющая граница линейна и не повторяет изгиб лун.",
        bold=True,
    )

    heading_task(doc, "Задача 7. Метрики качества классификации")
    condition(
        doc,
        "Для модели из задачи 6 вычислите матрицу ошибок, accuracy, precision, recall, F1-меру. "
        "Постройте ROC-кривую и вычислите AUC. Объясните, в каких случаях accuracy может вводить в заблуждение.",
    )
    solution_label(doc)
    para(doc, "Порог решения — 0.5, положительный класс — метка 1. На тестовых 90 точках:")
    add_table(
        doc,
        ["", "прогноз 0", "прогноз 1"],
        [["истина 0", str(m["tn"]), str(m["fp"])], ["истина 1", str(m["fn"]), str(m["tp"])]],
        [3.5, 3.5, 3.5],
    )
    para(doc, "Определения, по которым посчитаны доли:")
    formula(doc, "precision = TP/(TP+FP),   recall = TP/(TP+FN),   F1 = 2·precision·recall/(precision+recall).")
    para(
        doc,
        f"accuracy = (TP+TN)/n = ({m['tp']}+{m['tn']})/90 = {m['accuracy']:.4f}; "
        f"precision = {m['tp']}/({m['tp']}+{m['fp']}) = {m['precision']:.4f}; "
        f"recall = {m['tp']}/({m['tp']}+{m['fn']}) = {m['recall']:.4f}; "
        f"F1 = {m['f1']:.4f}.",
    )
    para(
        doc,
        "ROC строится по убыванию предсказанной вероятности: по горизонтали доля ложных тревог FPR = FP/(FP+TN), "
        "по вертикали доля найденных объектов положительного класса TPR = TP/(TP+FN). "
        f"Площадь под кривой, посчитанная трапециями, AUC = {m['auc']:.4f}. "
        "Это выше accuracy, потому что ранжирование вероятностей удачнее жёсткого порога 0.5: многие ошибки лежат близко к границе.",
    )
    para(
        doc,
        "Accuracy — доля любых верных ответов. Она близка к доле крупнейшего класса, если модель почти всегда называет этот класс. "
        "При соотношении 95:5 постоянный ответ «большинство» имеет accuracy 0.95 и recall редкого класса 0. "
        "В задаче 9 это видно численно: accuracy без балансировки равна 0.965, а recall редкого класса — только 0.438. "
        "Там, где классы сопоставимы по цене ошибки и по численности, как на этих лунах, accuracy читается прямо.",
    )
    image(doc, os.path.join(ROOT, "results", "task07_roc.png"),
          caption="Рис. 6. Матрица ошибок и ROC модели из задачи 6.")
    answer_label(doc)
    para(
        doc,
        f"Матрица [[TN, FP], [FN, TP]] = [[{m['tn']}, {m['fp']}], [{m['fn']}, {m['tp']}]]. "
        f"accuracy = {m['accuracy']:.4f}, precision = {m['precision']:.4f}, recall = {m['recall']:.4f}, "
        f"F1 = {m['f1']:.4f}, AUC = {m['auc']:.4f}.",
        bold=True,
    )

    heading_task(doc, "Задача 8. Многоклассовая классификация (Softmax)")
    condition(
        doc,
        "Реализуйте softmax-регрессию для классификации ирисов Фишера (3 класса, 4 признака). "
        "Используйте one-hot кодирование меток. Сравните результаты с попарной стратегией «один против всех» (One-vs-Rest).",
    )
    solution_label(doc)
    para(
        doc,
        f"Iris: 150 цветков, 4 признака, классы setosa, versicolor, virginica. Стратифицированное разбиение 70/30, "
        f"обучение {t8['n_train']}, тест {t8['n_test']}, стандартизация по обучению. "
        "Метка класса c кодируется вектором длины 3 с единицей в позиции c.",
    )
    formula(doc, "P(y = c | x) = exp(z_c) / Σ_k exp(z_k),    z = X̃ W.")
    para(
        doc,
        "Потеря — средняя кросс-энтропия между one-hot и softmax. Градиент по матрице весов: (1/n) X̃ᵀ(P − Y). "
        "Шаг 0.5, 3000 итераций. В схеме «один против всех» обучаются три независимые логистические регрессии "
        "«класс c против остальных»; на прогнозе выбирается класс с наибольшей сигмоидой.",
    )
    add_table(
        doc,
        ["модель", "accuracy train", "accuracy test"],
        [
            ["softmax", f4(t8["softmax_train"]), f4(t8["softmax_test"])],
            ["один против всех", f4(t8["ovr_train"]), f4(t8["ovr_test"])],
        ],
        [5.0, 4.5, 4.5],
    )
    para(
        doc,
        "На тесте обе схемы дают 0.9333, то есть 42 верных ответа из 45. На обучении softmax выше (0.9905 против 0.9619): "
        "одна совместная нормировка вероятностей согласует три класса между собой, а три отдельных сигмоиды этого ограничения не имеют "
        "и чуть хуже подгоняют обучающие точки versicolor и virginica. Для этой выборки разница на тесте не проявляется.",
    )
    answer_label(doc)
    para(
        doc,
        f"Softmax: train {t8['softmax_train']:.4f}, test {t8['softmax_test']:.4f}. "
        f"One-vs-Rest: train {t8['ovr_train']:.4f}, test {t8['ovr_test']:.4f}. На тесте результаты совпали.",
        bold=True,
    )

    heading_task(doc, "Задача 9. Дисбаланс классов")
    condition(
        doc,
        "Дан датасет с соотношением классов 95:5. Обучите логистическую регрессию без учёта дисбаланса. "
        "Затем примените: (а) взвешивание классов, (б) oversampling (SMOTE), (в) undersampling. "
        "Сравните метрики precision/recall/F1.",
    )
    solution_label(doc)
    para(
        doc,
        "Синтетическая выборка make_classification: 2000 объектов, 10 признаков, 6 информативных, доля классов 0.95 и 0.05, "
        "flip_y = 0.01, seed = 42. Положительный класс — редкий. Стратифицированный тест 30%. "
        f"В обучении {t9['train_counts']['0']} объектов класса 0 и {t9['train_counts']['1']} класса 1, "
        f"в тесте {t9['test_counts']['0']} и {t9['test_counts']['1']}. "
        f"Ответ «всегда 0» имеет accuracy {t9['majority_accuracy']:.4f}.",
    )
    para(
        doc,
        "Базовая модель — логистическая регрессия с равными весами объектов. "
        "(а) Вес класса c равен n / (2 n_c), то есть редкий класс весит примерно в 17 раз больше; градиент каждого объекта умножается на этот вес. "
        "(б) SMOTE (imbalanced-learn, k = 5) дополняет редкий класс синтетическими точками на отрезках до ближайших соседей того же класса; "
        f"после балансировки в обучении {t9['smote_n']} объектов. "
        f"(в) Случайный undersampling оставляет у большинства столько же объектов, сколько у меньшинства: {t9['under_n']} точек. "
        "Порог везде 0.5, метрики — по редкому классу на одном и том же тесте.",
    )
    def row9(name, d):
        return [name, f4(d["accuracy"]), f4(d["precision"]), f4(d["recall"]), f4(d["f1"])]
    add_table(
        doc,
        ["вариант", "accuracy", "precision", "recall", "F1"],
        [
            row9("без баланса", t9["base"]),
            row9("веса классов", t9["weighted"]),
            row9("SMOTE", t9["smote"]),
            row9("undersampling", t9["undersample"]),
        ],
        [3.6, 2.8, 2.8, 2.6, 2.4],
    )
    para(
        doc,
        f"Без баланса модель почти не ошибается на большинстве: precision редкого класса {t9['base']['precision']:.3f}, "
        f"но из {t9['test_counts']['1']} редких тестовых объектов найдено только {t9['base']['tp']} (recall {t9['base']['recall']:.3f}). "
        f"Все три приёма поднимают recall до 0.78–0.84 и одновременно роняют precision до 0.23–0.26: модель начинает чаще называть класс 1. "
        f"F1 при этом ниже, чем у несбалансированной модели ({t9['base']['f1']:.3f}), потому что F1 наказывает падение precision. "
        f"Среди трёх приёмов наибольший F1 у SMOTE ({t9['smote']['f1']:.3f}), наибольший recall у undersampling ({t9['undersample']['recall']:.3f}). "
        "Какой вариант брать, решает цена пропуска редкого класса, а не accuracy.",
    )
    answer_label(doc)
    para(
        doc,
        f"Без баланса: precision {t9['base']['precision']:.3f}, recall {t9['base']['recall']:.3f}, F1 {t9['base']['f1']:.3f}. "
        f"Веса: {t9['weighted']['precision']:.3f} / {t9['weighted']['recall']:.3f} / {t9['weighted']['f1']:.3f}. "
        f"SMOTE: {t9['smote']['precision']:.3f} / {t9['smote']['recall']:.3f} / {t9['smote']['f1']:.3f}. "
        f"Undersampling: {t9['undersample']['precision']:.3f} / {t9['undersample']['recall']:.3f} / {t9['undersample']['f1']:.3f}. "
        "Балансировка меняет высокий precision на высокий recall.",
        bold=True,
    )

    heading_task(doc, "Задача 10. Регуляризация в логистической регрессии")
    condition(
        doc,
        "Добавьте L2-регуляризацию к логистической регрессии. Исследуйте, как параметр λ влияет на норму весов и качество классификации. "
        "Постройте зависимость accuracy на train/test от λ.",
    )
    solution_label(doc)
    para(
        doc,
        "Датасет Breast Cancer Wisconsin, 569 объектов, 30 признаков, стратифицированное разбиение 70/30, стандартизация по обучению. "
        "К кросс-энтропии добавлен штраф (λ/2)‖w‖² на все веса, кроме свободного члена. "
        "Шаг спуска равен 0.5 / (1 + λ): при большом λ слагаемое λw в градиенте иначе делает итерацию неустойчивой. Итераций 5000.",
    )
    show = t10["rows"]
    add_table(
        doc,
        ["λ", "‖w‖", "accuracy train", "accuracy test"],
        [[f"{r['lambda']:.4g}", f3(r["weight_norm"]), f4(r["train_acc"]), f4(r["test_acc"])] for r in show],
        [2.8, 2.6, 4.0, 4.0],
    )
    b = t10["best"]
    para(
        doc,
        f"Норма весов монотонно падает с 7.81 при λ = 10⁻⁴ до 0.014 при λ = 100. "
        f"Пока λ ≤ 0.003, тестовая точность держится на {b['test_acc']:.4f}. "
        "Дальше штраф начинает занулять полезный сигнал: при λ = 1 точность теста 0.953, при λ = 10 — 0.760, "
        "при λ ≥ 30 модель близка к константе и точность падает к доле большего класса. "
        "На этой выборке классы хорошо разделимы, поэтому слабая регуляризация почти не поднимает тест над обучением, "
        "а сильная его портит. Разрыв train/test остаётся маленьким до λ ≈ 1 и не является здесь главным эффектом; главный эффект — сжатие ‖w‖.",
    )
    image(doc, os.path.join(ROOT, "results", "task10_l2.png"),
          caption="Рис. 7. Точность и норма весов в зависимости от λ.")
    answer_label(doc)
    para(
        doc,
        f"Лучший тест при λ = {b['lambda']:.4g}: accuracy train = {b['train_acc']:.4f}, test = {b['test_acc']:.4f}, ‖w‖ = {b['weight_norm']:.3f}. "
        "С ростом λ норма весов падает, и после λ ≈ 1 падает точность на обеих выборках.",
        bold=True,
    )

    # ------------------------------------------------------------------
    heading_block(doc, "Блок 3. Метод k-ближайших соседей (k-NN) (задачи 11–13)")

    heading_task(doc, "Задача 11. Реализация k-NN с нуля")
    condition(
        doc,
        "Реализуйте алгоритм k-ближайших соседей без библиотек. Используйте евклидову и манхэттенскую метрики. "
        "Проверьте работу на датасете ирисов. Исследуйте зависимость accuracy от k ∈ {1, 3, 5, 7, 15, 25}.",
    )
    solution_label(doc)
    para(
        doc,
        f"Ирисы, стратифицированное разбиение 70/30 (обучение {t11['n_train']}, тест {t11['n_test']}), стандартизация по обучению. "
        "Для каждого тестового объекта считаются расстояния до всех обучающих. Евклидово расстояние — корень из суммы квадратов разностей координат, "
        "манхэттенское — сумма модулей. Класс — большинство среди k ближайших. При равенстве голосов берётся метка, которая первой встретилась в np.unique.",
    )
    ks = [1, 3, 5, 7, 15, 25]
    by = {(r["metric"], r["k"]): r["accuracy"] for r in t11["rows"]}
    add_table(
        doc,
        ["k", "евклидова", "манхэттен"],
        [[str(k), f4(by[("euclidean", k)]), f4(by[("manhattan", k)])] for k in ks],
        [3.0, 4.5, 4.5],
    )
    para(
        doc,
        "При k = 1 граница проходит по отдельным точкам и ловит шум: точность 0.911 и 0.889. "
        "Евклидова метрика лучше всего при k = 7 (0.9556). При k = 25 окрестность уже слишком велика для 105 обучающих точек, "
        "и точность падает до 0.8667: в голосование попадают чужие классы. "
        "Манхэттенская метрика ровнее: от k = 3 до k = 15 точность одна и та же, 0.9333, и при k = 25 проседает слабее.",
    )
    image(doc, os.path.join(ROOT, "results", "task11_knn.png"),
          caption="Рис. 8. Точность k-NN на тестовых ирисах.")
    answer_label(doc)
    para(
        doc,
        "Лучший результат — евклидова метрика, k = 7, accuracy = 0.9556. "
        "Манхэттенская метрика на этой выборке не выше 0.9333. Слишком большое k снижает качество.",
        bold=True,
    )

    heading_task(doc, "Задача 12. Проклятие размерности")
    condition(
        doc,
        "Сгенерируйте синтетические данные с числом признаков d ∈ {2, 5, 10, 50, 100}. "
        "Для каждого d обучите k-NN и постройте график accuracy. Объясните, почему качество падает с ростом размерности. "
        "Рассчитайте среднее расстояние между точками.",
    )
    solution_label(doc)
    para(
        doc,
        "Для каждого d взято 240 точек из N(0, I_d), seed зависит от d. Метка определяется только первой координатой: класс 1, если x₁ > 0. "
        "Остальные координаты — чистый шум той же дисперсии. k-NN с k = 5 и евклидовой метрикой, тест 30%. "
        "Среднее расстояние — по всем парам случайной подвыборки из 80 точек.",
    )
    add_table(
        doc,
        ["d", "accuracy", "среднее расстояние", "σ расстояния"],
        [[str(r["d"]), f4(r["accuracy"]), f3(r["mean_distance"]), f3(r["std_distance"])] for r in t12["rows"]],
        [2.2, 3.2, 4.6, 4.2],
    )
    para(
        doc,
        "Для двух независимых стандартных нормальных векторов квадрат расстояния имеет среднее 2d, то есть само расстояние растёт как √(2d): "
        "примерно 2, 3.2, 4.5, 10, 14 при d = 2, 5, 10, 50, 100. Посчитанные средние 1.90, 2.88, 4.43, 9.99, 13.99 ложатся на эту кривую. "
        "Стандартное отклонение расстояния при этом остаётся около 1, поэтому относительный разброс σ/среднее сжимается. "
        "Ближайший и дальний сосед становятся похожи по дистанции: шумные координаты перевешивают единственную информативную. "
        "Точность падает с 0.958 при d = 2 до 0.556 при d = 100, то есть почти до угадывания.",
    )
    image(doc, os.path.join(ROOT, "results", "task12_curse.png"),
          caption="Рис. 9. Точность k-NN и среднее расстояние при росте размерности.")
    answer_label(doc)
    para(
        doc,
        "Accuracy: 0.958 (d=2), 0.917 (d=5), 0.750 (d=10), 0.653 (d=50), 0.556 (d=100). "
        "Средние расстояния: 1.90, 2.88, 4.43, 9.99, 13.99. Качество падает, потому что расстояния определяются шумовыми координатами и перестают отражать соседство по полезному признаку.",
        bold=True,
    )

    heading_task(doc, "Задача 13. Взвешенный k-NN")
    condition(
        doc,
        "Модифицируйте k-NN так, чтобы голоса соседей взвешивались обратно пропорционально расстоянию: wᵢ = 1/(dᵢ + ε). "
        "Сравните качество с классическим k-NN на нескольких датасетах.",
    )
    solution_label(doc)
    para(
        doc,
        "Голос соседа с расстоянием dᵢ умножается на 1/(dᵢ + 10⁻⁹). Класс с наибольшей суммой весов побеждает. "
        "Сравнение на ирисах, вине (13 признаков, 3 класса) и Breast Cancer Wisconsin. "
        "Везде стандартизация по обучающей части и один и тот же стратифицированный разрез 70/30, евклидова метрика, k = 3 и k = 7.",
    )
    add_table(
        doc,
        ["датасет", "k", "обычный k-NN", "взвешенный"],
        [[r["dataset"], str(r["k"]), f4(r["uniform"]), f4(r["distance"])] for r in t13["rows"]],
        [4.2, 2.0, 4.0, 4.0],
    )
    para(
        doc,
        "На пяти из шести строк числа совпали. Единственное отличие — ирисы при k = 7: обычное большинство даёт 0.9556, взвешенное — 0.9333. "
        "После стандартизации соседи лежат на сопоставимых расстояниях, поэтому веса 1/dᵢ почти не переворачивают голос. "
        "Взвешивание полезно, когда один сосед намного ближе остальных и его класс стоит учесть сильнее; на этих трёх выборках такой ситуации на тесте почти не возникло.",
    )
    answer_label(doc)
    para(
        doc,
        "Взвешенный k-NN не улучшил точность. На ирисах, вине и Breast Cancer при k = 3 результаты совпали; "
        "на ирисах при k = 7 обычный k-NN выше: 0.9556 против 0.9333.",
        bold=True,
    )

    # ------------------------------------------------------------------
    heading_block(doc, "Блок 4. Наивный байесовский классификатор и деревья решений (задачи 14–17)")

    heading_task(doc, "Задача 14. Наивный байесовский классификатор (Gaussian NB)")
    condition(
        doc,
        "Реализуйте гауссовский наивный байесовский классификатор с нуля. Обучите на датасете ирисов. "
        "Сравните с реализацией из библиотеки. Объясните предположение о независимости признаков.",
    )
    solution_label(doc)
    para(doc, "По формуле Байеса и предположению о независимости признаков при фиксированном классе")
    formula(doc, "log P(c | x) = log P(c) + Σⱼ log φ(xⱼ; μ_{cⱼ}, σ²_{cⱼ}) + const.")
    para(
        doc,
        "φ — плотность нормального закона. Для каждого класса по обучающим точкам считаются доля класса, среднее и дисперсия каждого признака. "
        "К дисперсии добавлено 10⁻⁹, как var_smoothing в sklearn, чтобы не делить на ноль. Прогноз — класс с наибольшим log P(c|x). "
        f"Разбиение ирисов то же, что в соседних задачах: тест из {t14['n_test']} цветков. Априорные доли на обучении равны 1/3.",
    )
    para(
        doc,
        f"Точность своей реализации на тесте {t14['scratch_test']:.4f}, sklearn.naive_bayes.GaussianNB — {t14['sklearn_test']:.4f}. "
        f"Доля совпавших прогнозов {t14['agree']:.0%}: пообъектно ответы одинаковые.",
    )
    para(
        doc,
        "Предположение о независимости означает, что совместная плотность внутри класса равна произведению одномерных плотностей. "
        "Ковариации в модель не входят: оценка — это 3 вектора средних и 3 вектора дисперсий, а не три матрицы 4×4. "
        "У ирисов длина и ширина лепестка сильно связаны, так что предположение не выполнено буквально. "
        "Классификатор всё равно работает, потому что для отделения setosa от остальных хватает сдвига средних. Корреляция сильнее портит численные значения вероятностей, чем итоговый выбор класса.",
    )
    answer_label(doc)
    para(
        doc,
        f"Своя реализация и sklearn дали одну и ту же тестовую точность {t14['scratch_test']:.4f} и совпали на всех тестовых объектах. "
        "Модель перемножает одномерные нормальные плотности и тем самым считает признаки условно независимыми.",
        bold=True,
    )

    heading_task(doc, "Задача 15. Наивный Байес для текстов (Multinomial NB)")
    condition(
        doc,
        "Реализуйте мультиномиальный наивный Байес для классификации текстов (например, SMS spam / not spam). "
        "Постройте bag-of-words с помощью CountVectorizer. Оцените precision и recall. Исследуйте влияние сглаживания Лапласа.",
    )
    solution_label(doc)
    para(
        doc,
        f"Коллекция SMS Spam Collection: {t15['n']} сообщений, из них ham {t15['ham']} и spam {t15['spam']}. "
        f"Стратифицированное разбиение 70/30: обучение {t15['n_train']}, тест {t15['n_test']}. "
        "CountVectorizer приводит текст к нижнему регистру, берёт токены по границе слова и отбрасывает слова, встретившиеся меньше двух раз. "
        f"Размер словаря — {t15['vocab']}. Документ представлен вектором счётчиков.",
    )
    para(doc, "Для класса c и слова j со сглаживанием α:")
    formula(doc, "P(wⱼ | c) = (N_{cj} + α) / (N_c + α V),    log P(c | x) ∝ log P(c) + Σⱼ xⱼ log P(wⱼ | c).")
    para(
        doc,
        "N_{cj} — сколько раз слово встретилось в сообщениях класса c, V — размер словаря. Прогноз — класс с большим счётом. "
        "Метрики ниже относятся к классу spam. Рядом указан F1 реализации sklearn.naive_bayes.MultinomialNB с тем же α: он совпадает с собственным счётом.",
    )
    add_table(
        doc,
        ["α", "precision", "recall", "F1", "F1 sklearn"],
        [[f2(r["alpha"]) if r["alpha"] >= 1 else f"{r['alpha']:.1f}",
          f4(r["precision"]), f4(r["recall"]), f4(r["f1"]), f4(r["sklearn_f1"])] for r in t15["rows"]],
        [2.0, 3.2, 3.0, 3.2, 3.2],
    )
    para(
        doc,
        "При α = 0.5 достигается лучший F1 = 0.9550 (precision 0.9636, recall 0.9464). "
        "Малое α = 0.1 почти так же хорошо. При α = 5 сглаживание слишком сильное: редкие «спамовые» слова теряют вес, "
        "recall падает до 0.8571, хотя precision вырастает до 0.9846 — модель реже объявляет спам и чаще его пропускает. "
        "Сглаживание нужно, чтобы слово, ни разу не виденное в спаме на обучении, не обнуляло всю вероятность сообщения.",
    )
    answer_label(doc)
    para(
        doc,
        "Лучшее сглаживание на тесте — α = 0.5: precision = 0.9636, recall = 0.9464, F1 = 0.9550. "
        "При α = 5 recall снижается до 0.8571. Своя реализация совпала с MultinomialNB из sklearn.",
        bold=True,
    )

    heading_task(doc, "Задача 16. Дерево решений: критерий Джини и энтропия")
    condition(
        doc,
        "Реализуйте построение дерева решений с нуля, используя информационный выигрыш (энтропия) и индекс Джини. "
        "Ограничьте глубину дерева. Сравните два критерия на одном датасете. Визуализируйте дерево.",
    )
    solution_label(doc)
    gini = t16["criteria"]["gini"]
    ent = t16["criteria"]["entropy"]
    para(doc, "На узле с долями классов p_k два критерия неоднородности:")
    formula(doc, "Gini = 1 − Σ p_k²,    H = − Σ p_k log₂ p_k.")
    para(
        doc,
        "Выигрыш разбиения — неоднородность родителя минус взвешенная неоднородность детей. "
        "Перебираются признаки и пороги (середины между различными значениями, не больше 40 квантилей). "
        "Берётся разбиение с наибольшим выигрышем. Дерево на ирисах ограничено глубиной 3, "
        "в лист не ставится узел меньше 4 объектов при попытке деления и лист не меньше 2 объектов. "
        f"Обучение {t16['n_train']}, тест {t16['n_test']}.",
    )
    add_table(
        doc,
        ["критерий", "accuracy train", "accuracy test"],
        [["Джини", f4(gini["train"]), f4(gini["test"])],
         ["энтропия", f4(ent["train"]), f4(ent["test"])]],
        [4.5, 4.5, 4.5],
    )
    para(
        doc,
        "На этой выборке оба критерия выбрали одни и те же пороги, поэтому деревья и точности совпали: "
        "train 0.9810, test 0.9111. Корень — длина лепестка ≤ 2.60 (это setosa, класс 0, 35 объектов без ошибок). "
        "Дальше ширина лепестка ≤ 1.75 отделяет virginica. Мелкий лист из 4 объектов с 2 ошибками — зона пересечения versicolor и virginica; "
        "глубина 3 не даёт его дробить дальше.",
    )
    para(doc, "Текст дерева (он одинаков для обоих критериев):")
    code_block(doc, gini["text"])
    image(doc, os.path.join(ROOT, "results", "task16_tree.png"),
          caption="Рис. 10. Дерево глубины 3 по критерию Джини. Дерево по энтропии совпало с ним.")
    answer_label(doc)
    para(
        doc,
        "Джини и энтропия дали одно и то же дерево. Точность на обучении 0.9810, на тесте 0.9111. "
        "Первый порог — длина лепестка 2.60.",
        bold=True,
    )

    heading_task(doc, "Задача 17. Переобучение деревьев и pruning")
    condition(
        doc,
        "Обучите дерево решений без ограничения глубины. Покажите переобучение (accuracy на train ≈ 1, на test — ниже). "
        "Примените предварительную (max_depth, min_samples_split) и пост-обрезку (cost-complexity pruning). Сравните результаты.",
    )
    solution_label(doc)
    full = t17["full"]
    pre = t17["preprune"]
    best = t17["ccp_best"]
    para(
        doc,
        f"Синтетическая выборка make_classification: n = {t17['n']}, признаков {t17['d']}, 6 информативных, "
        "flip_y = 0.04, class_sep = 0.9, seed = 42. Стратифицированный тест 30%. "
        "Дерево — своя реализация с критерием Джини.",
    )
    para(
        doc,
        f"Без ограничений дерево доходит до {full['leaves']} листьев и запоминает обучение: "
        f"accuracy train = {full['train']:.4f}. На тесте {full['test']:.4f}. "
        f"Предварительная обрезка: max_depth = {pre['max_depth']}, min_samples_split = {pre['min_samples_split']}, "
        f"min_samples_leaf = {pre['min_samples_leaf']}. Обучение падает до {pre['train']:.4f}, тест поднимается до {pre['test']:.4f}.",
    )
    para(
        doc,
        "Пост-обрезка — cost-complexity. Для внутреннего узла t считается",
    )
    formula(doc, "g(t) = (R(t) − R(T_t)) / (|T_t| − 1),")
    para(
        doc,
        "где R — доля ошибок на всей обучающей выборке, |T_t| — число листьев в поддереве. "
        "На каждом шаге в лист превращается узел с наименьшим g(t); это значение и есть α данного шага. "
        f"Полный путь содержит от {t17['ccp_path'][0]['leaves']} листьев до одного. "
        f"Наибольшая тестовая точность на пути — у дерева с {best['leaves']} листьями, α = {best['alpha']:.4f}: "
        f"train {best['train_acc']:.4f}, test {best['test_acc']:.4f}.",
    )
    add_table(
        doc,
        ["модель", "листьев", "train", "test"],
        [
            ["без ограничений", str(full["leaves"]), f4(full["train"]), f4(full["test"])],
            ["max_depth=4, min_samples_split=20", "—", f4(pre["train"]), f4(pre["test"])],
            [f"CCP, α={best['alpha']:.4f}", str(best["leaves"]), f4(best["train_acc"]), f4(best["test_acc"])],
        ],
        [7.0, 2.2, 2.6, 2.6],
    )
    para(
        doc,
        "Оба способа обрезки поднимают тест и снижают train. Cost-complexity на этой выборке дошла до более удачного размера, чем жёсткая глубина 4: "
        "тест 0.792 против 0.736. Дальнейшая обрезка до корня возвращает точность к 0.5.",
    )
    image(doc, os.path.join(ROOT, "results", "task17_prune.png"),
          caption="Рис. 11. Точность вдоль пути обрезки. По горизонтали — число оставшихся листьев.")
    answer_label(doc)
    para(
        doc,
        f"Полное дерево: train {full['train']:.3f}, test {full['test']:.3f} ({full['leaves']} листьев). "
        f"Предварительная обрезка: train {pre['train']:.3f}, test {pre['test']:.3f}. "
        f"Лучшая пост-обрезка: {best['leaves']} листьев, α = {best['alpha']:.4f}, train {best['train_acc']:.3f}, test {best['test_acc']:.3f}.",
        bold=True,
    )

    # ------------------------------------------------------------------
    heading_block(doc, "Блок 5. Ансамбли и оценка моделей (задачи 18–20)")

    heading_task(doc, "Задача 18. Бэггинг и случайный лес")
    condition(
        doc,
        "Реализуйте бэггинг над деревьями решений (обучение на bootstrap-выборках с усреднением/голосованием). "
        "Сравните с одиночным деревом. Затем добавьте случайный выбор подмножества признаков — получите упрощённый Random Forest. "
        "Оцените качество на тестовой выборке.",
    )
    solution_label(doc)
    bag = t17["bagging"]
    rf = t17["forest"]
    para(
        doc,
        "Та же синтетическая выборка и тот же разрез, что в задаче 17, чтобы сравнение с одиночным деревом было прямым. "
        f"Ансамбль из {bag['n_estimators']} деревьев. Каждое учится на bootstrap-выборке длины обучающей (объекты берутся с возвращением). "
        f"Глубина базового дерева ограничена {bag['max_depth']}, чтобы 40 деревьев строились по одной и той же схеме. "
        "Прогноз — большинство голосов. В бэггинге на каждом узле видны все признаки. "
        f"В упрощённом случайном лесе на каждом узле случайно берётся max_features = ⌊√d⌋ = {rf['max_features']} признака из {t17['d']}.",
    )
    add_table(
        doc,
        ["модель", "accuracy train", "accuracy test"],
        [
            ["одно дерево без ограничения глубины", f4(full["train"]), f4(full["test"])],
            ["бэггинг, 40 деревьев", f4(bag["train"]), f4(bag["test"])],
            ["случайный лес, 40 деревьев", f4(rf["train"]), f4(rf["test"])],
        ],
        [8.0, 3.6, 3.6],
    )
    para(
        doc,
        f"Одиночное глубокое дерево запомнило обучение (train 1.000) и на тесте дало {full['test']:.3f}. "
        f"Бэггинг поднял тест до {bag['test']:.3f}: усреднение по bootstrap-выборкам гасит разброс глубоких деревьев. "
        f"Случайный лес получил ту же тестовую точность {rf['test']:.3f} и чуть меньшую обучающую ({rf['train']:.3f}). "
        f"Случайный набор признаков не улучшил эту конкретную выборку, но ускорил построение: "
        f"{rf['time_sec']:.2f} с против {bag['time_sec']:.2f} с у бэггинга, потому что в каждом узле перебираются 3 признака, а не 10. "
        "Оба ансамбля выше и полного дерева (тест 0.708), и лучшей обрезки из задачи 17 (тест 0.792).",
    )
    answer_label(doc)
    para(
        doc,
        f"Тест: одно дерево {full['test']:.3f}, бэггинг {bag['test']:.3f}, случайный лес {rf['test']:.3f}. "
        f"Ансамбль снижает переобучение. На этих данных лес и бэггинг совпали по тесту; у леса на узле {rf['max_features']} случайных признака.",
        bold=True,
    )

    heading_task(doc, "Задача 19. Кросс-валидация и подбор гиперпараметров")
    condition(
        doc,
        "Реализуйте k-fold кросс-валидацию (k = 5) с нуля. Примените её для подбора гиперпараметров: "
        "k в k-NN, глубина дерева, λ в Ridge. Сравните с GridSearchCV из sklearn. "
        "Постройте графики зависимости среднего качества от гиперпараметра.",
    )
    solution_label(doc)
    knn, tree, ridge = t19["knn"], t19["tree"], t19["ridge"]
    para(
        doc,
        "Своя k-fold перемешивает индексы генератором seed = 42 и режет их на 5 блоков. Для классификации разбиение стратифицированное: "
        "объекты каждого класса раскладываются по блокам по кругу. На каждом из пяти шагов модель учится на четырёх блоках и оценивается на пятом, "
        "затем пять оценок усредняются. Те же пары индексов переданы в GridSearchCV, поэтому библиотека считает ровно те же фолды.",
    )
    para(
        doc,
        "Три постановки. k-NN (со стандартизацией внутри каждого фолда) на ирисах, метрика accuracy, сетка k ∈ {1, 3, 5, 7, 15, 25}. "
        "Дерево sklearn с фиксированным random_state на датасете вина, сетка глубины {1, 2, 3, 4, 6, 8, 12}. "
        "Ridge со стандартизацией на датасете Diabetes, метрика R², λ на логарифмической сетке от 10⁻³ до 10³.",
    )
    add_table(
        doc,
        ["модель", "сетка: среднее качество", "лучший параметр", "GridSearchCV"],
        [
            ["k-NN, ирисы", "см. ниже", f"k = {knn['best']}, accuracy {knn['best_score']:.4f}",
             f"k = {knn['sklearn_best']}, {knn['sklearn_score']:.4f}"],
            ["дерево, вино", "см. ниже", f"глубина {tree['best']}, accuracy {tree['best_score']:.4f}",
             f"глубина {tree['sklearn_best']}, {tree['sklearn_score']:.4f}"],
            ["Ridge, diabetes", "см. ниже", f"λ = {ridge['best']:.4g}, R² {ridge['best_score']:.4f}",
             f"λ = {ridge['sklearn_best']:.4g}, {ridge['sklearn_score']:.4f}"],
        ],
        [3.4, 2.6, 5.2, 4.4],
    )
    para(doc, "Средняя accuracy k-NN по фолдам: " + ", ".join(
        f"k={k} → {s:.4f}" for k, s in zip(knn["grid"], knn["mean_score"])
    ) + ". У k = 7 и k = 25 одинаковый максимум 0.9533; выбирается первый, k = 7.")
    para(doc, "Средняя accuracy дерева: " + ", ".join(
        f"d={d} → {s:.4f}" for d, s in zip(tree["grid"], tree["mean_score"])
    ) + ".")
    para(
        doc,
        "R² гребневой регрессии почти не меняется от λ = 0.001 (0.4907) до λ = 10 (0.4903). "
        f"Максимум при λ = {ridge['best']:.0f}: R² = {ridge['best_score']:.4f}. "
        "При λ = 1000 R² падает до 0.335: штраф уже уничтожает регрессию. "
        "Для Diabetes уровень R² около 0.49 — обычный потолок линейной модели на этих признаках.",
    )
    para(
        doc,
        "Выбранный параметр и среднее качество своей кросс-валидации и GridSearchCV совпали во всех трёх постановках до последней цифры. "
        "Расхождение возникло бы только при разных фолдах или разной предобработке внутри фолда.",
    )
    image(doc, os.path.join(ROOT, "results", "task19_cv.png"), width=16.2,
          caption="Рис. 12. Среднее качество 5-fold в зависимости от гиперпараметра.")
    answer_label(doc)
    para(
        doc,
        f"k-NN: k = {knn['best']} (accuracy {knn['best_score']:.4f}). "
        f"Дерево: глубина {tree['best']} (accuracy {tree['best_score']:.4f}). "
        f"Ridge: λ = {ridge['best']:.0f} (R² {ridge['best_score']:.4f}). "
        "GridSearchCV на тех же фолдах вернул те же значения.",
        bold=True,
    )

    heading_task(doc, "Задача 20. Комплексное сравнение моделей")
    condition(
        doc,
        "На выбранном датасете (например, Breast Cancer Wisconsin или Titanic) обучите 5 моделей: "
        "логистическую регрессию, k-NN, наивный Байес, дерево решений и случайный лес. "
        "Проведите стратифицированную кросс-валидацию. Постройте сводную таблицу метрик "
        "(accuracy, precision, recall, F1, AUC, время обучения). Сделайте вывод о применимости каждой модели.",
    )
    solution_label(doc)
    para(
        doc,
        f"Датасет Breast Cancer Wisconsin из sklearn: {t20['n']} объектов, {t20['n_features']} признаков. "
        "В библиотеке метка 0 означает злокачественную опухоль. Метка перевёрнута, поэтому ниже класс 1 — злокачественная, "
        "и precision, recall, F1, AUC относятся к выявлению рака. "
        "Оценка — стратифицированные 5 фолдов своей функции из задачи 19, seed = 42. В каждой ячейке — среднее по фолдам. "
        "Время — среднее время одного fit.",
    )
    para(
        doc,
        "Состав. Логистическая регрессия и k-NN (k = 7) стоят в конвейере со стандартизацией, которая учится только на обучающем фолде. "
        "Наивный Байес — гауссовский, своя реализация из задачи 14; для AUC берётся апостериорная вероятность класса 1. "
        "Дерево — sklearn, max_depth = 4. Случайный лес — sklearn, 200 деревьев. "
        "k = 7 и глубина 4 взяты по порядку величин из задач 11 и 19, без дополнительного подбора на этой выборке.",
    )
    add_table(
        doc,
        ["модель", "accuracy", "prec.", "recall", "F1", "AUC", "время"],
        [[
            r["model"], f4(r["accuracy"]), f4(r["precision"]), f4(r["recall"]),
            f4(r["f1"]), f4(r["auc"]),
            (f"{r['time_sec']*1000:.2f} мс" if r["time_sec"] < 0.1 else f"{r['time_sec']*1000:.0f} мс"),
        ] for r in t20["rows"]],
        [4.3, 1.9, 1.9, 1.7, 1.7, 1.7, 2.0],
    )
    para(
        doc,
        f"Логистическая регрессия лидирует по accuracy (0.9754), F1 (0.9663) и AUC (0.9947) и обучается за {ms(t20['rows'][0]['time_sec'])}. "
        "После стандартизации 30 признаков классы здесь почти линейно разделимы, поэтому линейная модель с вероятностями хорошо подходит и как классификатор, и как ранжировщик.",
    )
    para(
        doc,
        "k-NN близок по качеству (accuracy 0.9701, AUC 0.9880) и почти ничего не тратит на обучение, потому что обучение — это запоминание выборки. "
        "Предсказание требует хранить все объекты и зависит от масштаба признаков: без стандартизации расстояния по разным анализам несравнимы. "
        "Модель уместна как сильный ориентир на небольшом наборе и неудобна, если выборка постоянно пополняется.",
    )
    para(
        doc,
        f"Случайный лес даёт accuracy 0.9613 и AUC 0.9894 при обучении {ms(t20['rows'][4]['time_sec'])}. "
        "Он не требует линейной границы и устойчив к монотонным преобразованиям отдельных признаков. "
        "На этих данных линейная модель его опережает: зависимость близка к линейной, а лес тратит ёмкость на кусочно-постоянную аппроксимацию.",
    )
    para(
        doc,
        f"Гауссовский наивный Байес самый быстрый ({ms(t20['rows'][2]['time_sec'])}) и хорошо ранжирует (AUC 0.9874), но F1 ниже — 0.9161, accuracy 0.9385. "
        "Тридцать лабораторных признаков коррелированы, а модель перемножает одномерные плотности. Для грубого и очень дешёвого фильтра он применим, для окончательного решения — слабее логистической регрессии.",
    )
    para(
        doc,
        "Дерево глубины 4 даёт читаемые пороги и accuracy 0.9367, но AUC только 0.9381: внутри листа вероятность постоянна, ранжирование грубое. "
        "Его место — объяснение правил врачу, а не максимальная чувствительность. Полное дерево без ограничения глубины на этих данных запомнило бы фолды; глубина 4 как раз удерживает его от этого.",
    )
    answer_label(doc)
    para(
        doc,
        "На Breast Cancer Wisconsin при 5-fold и положительном классе «злокачественная» лучшая модель — логистическая регрессия: "
        f"accuracy 0.9754, precision 0.9808, recall 0.9527, F1 0.9663, AUC 0.9947, обучение {ms(t20['rows'][0]['time_sec'])}. "
        "Дальше по качеству идут k-NN (accuracy 0.9701) и случайный лес (0.9613). "
        "Наивный Байес и дерево глубины 4 остаются около accuracy 0.94 и уступают по F1.",
        bold=True,
    )

    para(
        doc,
        "Исходный файл с условиями не изменялся. Расчёты воспроизводятся скриптом solve_all.py при seed = 42.",
        size=10, italic=True, before=12, after=0, color=(90, 90, 90),
    )
    doc.save(OUT_DOC)
    print(OUT_DOC)


if __name__ == "__main__":
    build()
