# Семинар 9. Таблица и графики метода Гаусса–Зейделя.
# Запуск из папки parall_prog: python3 seminar_09/plot.py
import csv

import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.marker import Marker
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

SIZES = [10, 100, 1000, 2000, 3000]
THREADS = [2, 4, 8]

serial = {}
parallel = {}
iters = {}
with open("results/seminar9_gs.csv", newline="") as f:
    for row in csv.DictReader(f):
        n = int(row["n"])
        p = int(row["threads"])
        version = row["version"]
        if version == "serial":
            serial[n] = float(row["time_sec"])
            iters[(n, "serial")] = int(row["iters"])
        else:
            parallel[(n, p)] = float(row["time_sec"])
            iters[(n, p)] = int(row["iters"])

plt.rcParams["font.family"] = "Arial"
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.5, 4.8))

xs = list(range(len(SIZES)))
labels = [str(n) for n in SIZES]
time_series = [
    ("Последовательный", [serial[n] for n in SIZES], "#C4A000"),
    ("2 потока", [parallel[(n, 2)] for n in SIZES], "#548235"),
    ("4 потока", [parallel[(n, 4)] for n in SIZES], "#C65911"),
    ("8 потоков", [parallel[(n, 8)] for n in SIZES], "#7F7F7F"),
]
for label, ys, color in time_series:
    ax1.plot(xs, ys, "o-", color=color, label=label)
ax1.set_title("Время выполнения")
ax1.set_xlabel("Размер сетки N")
ax1.set_ylabel("Время, с")
ax1.set_xticks(xs, labels)
ax1.grid(alpha=0.3)
ax1.legend()

speed_colors = {2: "#2F5496", 4: "#C65911", 8: "#7F7F7F"}
for p in THREADS:
    ys = [serial[n] / parallel[(n, p)] for n in SIZES]
    ax2.plot(xs, ys, "o-", color=speed_colors[p], label=f"Ускорение {p}")
ax2.set_title("Ускорение S = Tпосл / Tp")
ax2.set_xlabel("Размер сетки N")
ax2.set_ylabel("Ускорение")
ax2.set_xticks(xs, labels)
ax2.grid(alpha=0.3)
ax2.legend()

fig.tight_layout()
fig.savefig("results/seminar9_gs.png", dpi=150)
print("Сохранено: results/seminar9_gs.png")

FONT = "Arial"
bold = Font(name=FONT, bold=True)
regular = Font(name=FONT)
title_font = Font(name=FONT, bold=True, size=13)
header_fill = PatternFill("solid", start_color="D9E1F2")
group_fill = PatternFill("solid", start_color="E2EFDA")
thin = Side(style="thin", color="A6A6A6")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center", wrap_text=True)

wb = Workbook()
ws = wb.active
ws.title = "Гаусс–Зейдель"
ws.sheet_view.showGridLines = False
ws.page_setup.orientation = "landscape"
ws.page_setup.fitToPage = True
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 1
ws.page_setup.paperSize = ws.PAPERSIZE_A4
ws.sheet_properties.pageSetUpPr.fitToPage = True
ws.page_margins.left = 0.4
ws.page_margins.right = 0.4
ws.page_margins.top = 0.4
ws.page_margins.bottom = 0.4
ws.print_title_rows = "1:3"
ws.oddHeader.left.text = "Семинар 9. Метод Гаусса–Зейделя"
ws.oddFooter.right.text = "Стр. &P из &N"

ws.merge_cells("A1:A3")
ws["A1"] = "Размер сетки"
ws.merge_cells("B1:B3")
ws["B1"] = "Последовательный алгоритм (время, сек)"
ws.merge_cells("C1:H1")
ws["C1"] = "Параллельный алгоритм (OpenMP)"
for col, text in ((3, "2 процессора"), (5, "4 процессора"), (7, "8 процессоров")):
    ws.merge_cells(start_row=2, start_column=col, end_row=2, end_column=col + 1)
    ws.cell(row=2, column=col, value=text)
for col, text in ((3, "Время"), (4, "Ускорение"), (5, "Время"), (6, "Ускорение"),
                  (7, "Время"), (8, "Ускорение")):
    ws.cell(row=3, column=col, value=text)

for row in range(1, 4):
    for col in range(1, 9):
        cell = ws.cell(row=row, column=col)
        cell.font = bold
        cell.fill = header_fill if col <= 2 or row == 1 else group_fill
        cell.border = border
        cell.alignment = center
ws.row_dimensions[1].height = 22
ws.row_dimensions[2].height = 22
ws.row_dimensions[3].height = 20

ws.column_dimensions["A"].width = 16
ws.column_dimensions["B"].width = 28
for col in range(3, 9):
    ws.column_dimensions[get_column_letter(col)].width = 14

for i, n in enumerate(SIZES):
    r = 4 + i
    ws.cell(row=r, column=1, value=n)
    ws.cell(row=r, column=2, value=serial[n])
    for k, p in enumerate(THREADS):
        ws.cell(row=r, column=3 + 2 * k, value=parallel[(n, p)])
        # Ускорение формулой: Tпосл / T_p
        time_cell = ws.cell(row=r, column=3 + 2 * k).coordinate
        ws.cell(row=r, column=4 + 2 * k, value=f"=$B{r}/{time_cell}")
    for col in range(1, 9):
        cell = ws.cell(row=r, column=col)
        cell.font = regular
        cell.border = border
        cell.alignment = center
        if col == 1:
            cell.number_format = "0"
        elif col % 2 == 0 and col > 2:
            cell.number_format = "0.0000"
        else:
            cell.number_format = "0.000000"
    ws.row_dimensions[r].height = 18

ws["A10"] = "Число итераций до eps = 0.0001"
ws["A10"].font = bold
for col, text in enumerate(["N", "Последовательный", "Красно-чёрный"], start=1):
    cell = ws.cell(row=11, column=col, value=text)
    cell.font = bold
    cell.fill = header_fill
    cell.border = border
    cell.alignment = center
for i, n in enumerate(SIZES):
    r = 12 + i
    values = [n, iters[(n, "serial")], iters[(n, 2)]]
    for col, value in enumerate(values, start=1):
        cell = ws.cell(row=r, column=col, value=value)
        cell.font = regular
        cell.border = border
        cell.alignment = center

ws["A18"] = (
    "Apple M4 (4 производительных + 6 энергоэффективных ядер), clang -O2, лучшее из 5 запусков. "
    "h = 1/(N+1), f = 1, u = 0 на границе. Ускорение считается формулой от столбца B."
)
ws["A18"].font = Font(name=FONT, italic=True, color="595959")
ws.merge_cells("A18:H18")

# Отдельный лист, чтобы у графиков были нормальные подписи серий.
src = wb.create_sheet("Для графиков")
src["A1"] = "N"
src["B1"] = "Последовательный"
src["C1"] = "2 процессора"
src["D1"] = "4 процессора"
src["E1"] = "8 процессоров"
src["G1"] = "N"
src["H1"] = "Ускорение 2"
src["I1"] = "Ускорение 4"
src["J1"] = "Ускорение 8"
for i, n in enumerate(SIZES):
    r = 2 + i
    src.cell(row=r, column=1, value=n)
    src.cell(row=r, column=2, value=f"='Гаусс–Зейдель'!B{r + 2}")
    src.cell(row=r, column=3, value=f"='Гаусс–Зейдель'!C{r + 2}")
    src.cell(row=r, column=4, value=f"='Гаусс–Зейдель'!E{r + 2}")
    src.cell(row=r, column=5, value=f"='Гаусс–Зейдель'!G{r + 2}")
    src.cell(row=r, column=7, value=n)
    src.cell(row=r, column=8, value=f"='Гаусс–Зейдель'!D{r + 2}")
    src.cell(row=r, column=9, value=f"='Гаусс–Зейдель'!F{r + 2}")
    src.cell(row=r, column=10, value=f"='Гаусс–Зейдель'!H{r + 2}")

colors = ["C4A000", "548235", "C65911", "7F7F7F"]
time_chart = LineChart()
time_chart.title = "Время выполнения"
time_chart.y_axis.title = "Время, с"
time_chart.x_axis.title = "Размер сетки"
time_chart.height = 8
time_chart.width = 15
time_chart.add_data(Reference(src, min_col=2, max_col=5, min_row=1, max_row=6), titles_from_data=True)
time_chart.set_categories(Reference(src, min_col=1, min_row=2, max_row=6))
for series, color in zip(time_chart.series, colors):
    series.graphicalProperties.line.solidFill = color
    series.marker = Marker(symbol="circle", size=7)
    series.marker.graphicalProperties.solidFill = color
    series.marker.graphicalProperties.line.solidFill = color
ws.add_chart(time_chart, "A20")

speed_chart = LineChart()
speed_chart.title = "Ускорение"
speed_chart.y_axis.title = "S = Tпосл / Tp"
speed_chart.x_axis.title = "Размер сетки"
speed_chart.height = 8
speed_chart.width = 15
speed_chart.add_data(Reference(src, min_col=8, max_col=10, min_row=1, max_row=6), titles_from_data=True)
speed_chart.set_categories(Reference(src, min_col=7, min_row=2, max_row=6))
for series, color in zip(speed_chart.series, ["2F5496", "C65911", "7F7F7F"]):
    series.graphicalProperties.line.solidFill = color
    series.marker = Marker(symbol="circle", size=7)
    series.marker.graphicalProperties.solidFill = color
    series.marker.graphicalProperties.line.solidFill = color
ws.add_chart(speed_chart, "E20")

wb.calculation.fullCalcOnLoad = True
wb.save("results/seminar9_gs.xlsx")
print("Сохранено: results/seminar9_gs.xlsx")
