# Семинар 8. Графики времени и ускорения MPI-умножения матрицы на вектор.
# Запуск из папки parall_prog: python3 seminar_08/plot.py
import csv
from collections import OrderedDict

import matplotlib.pyplot as plt
from openpyxl import Workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

with open("results/seminar8_matvec.csv", newline="") as f:
    raw = list(csv.DictReader(f))

best = OrderedDict()
t_seq = min(float(row["time_sequential"]) for row in raw)
for row in raw:
    p = int(row["processes"])
    if p not in best or float(row["time_parallel"]) < float(best[p]["time_parallel"]):
        best[p] = row

summary = []
for p, row in best.items():
    total = float(row["time_parallel"])
    summary.append({
        "processes": p,
        "time_parallel": total,
        "scatter": float(row["scatter"]),
        "bcast": float(row["bcast"]),
        "compute": float(row["compute"]),
        "gather": float(row["gather"]),
        "time_sequential": t_seq,
        "speedup": t_seq / total,
        "max_diff": float(row["max_diff"]),
    })

with open("results/seminar8_matvec.csv", "w", newline="") as f:
    fields = ["processes", "time_parallel", "scatter", "bcast", "compute", "gather",
              "time_sequential", "speedup", "max_diff"]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in summary:
        writer.writerow({
            "processes": row["processes"],
            "time_parallel": f"{row['time_parallel']:.8f}",
            "scatter": f"{row['scatter']:.8f}",
            "bcast": f"{row['bcast']:.8f}",
            "compute": f"{row['compute']:.8f}",
            "gather": f"{row['gather']:.8f}",
            "time_sequential": f"{row['time_sequential']:.8f}",
            "speedup": f"{row['speedup']:.6f}",
            "max_diff": f"{row['max_diff']:.3e}",
        })

procs = [r["processes"] for r in summary]
total = [r["time_parallel"] * 1e3 for r in summary]
speedup = [r["speedup"] for r in summary]
scatter = [r["scatter"] * 1e3 for r in summary]
compute = [r["compute"] * 1e3 for r in summary]
gather = [r["gather"] * 1e3 for r in summary]

plt.rcParams["font.family"] = "Arial"
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6))

ax1.plot(procs, total, "o-", color="#2F5496", label="Весь параллельный алгоритм")
ax1.plot(procs, compute, "s--", color="#548235", label="Только умножение")
ax1.set_title("Время, матрица 1000×1000")
ax1.set_xlabel("Число процессов")
ax1.set_ylabel("Время, мс")
ax1.set_xticks(procs)
ax1.grid(alpha=0.3)
ax1.legend()

ax2.plot(procs, procs, "--", color="gray", label="Идеальное S = p")
ax2.plot(procs, speedup, "o-", color="#C65911", label="S = Tпосл / Tmpi")
for p, s in zip(procs, speedup):
    ax2.annotate(f"{s:.2f}", (p, s), textcoords="offset points", xytext=(0, 8), ha="center")
ax2.set_title("Ускорение относительно последовательного кода")
ax2.set_xlabel("Число процессов")
ax2.set_ylabel("Ускорение")
ax2.set_xticks(procs)
ax2.set_ylim(0, max(procs) + 1)
ax2.grid(alpha=0.3)
ax2.legend()

fig.tight_layout()
fig.savefig("results/seminar8_matvec.png", dpi=150)
print("Сохранено: results/seminar8_matvec.png")
print(f"Tпосл = {t_seq * 1e3:.3f} мс")
for r in summary:
    print(f"p={r['processes']:<3} T={r['time_parallel']*1e3:.3f} мс  "
          f"scatter={r['scatter']*1e3:.3f}  compute={r['compute']*1e3:.3f}  "
          f"gather={r['gather']*1e3:.3f}  S={r['speedup']:.2f}")

FONT = "Arial"
bold = Font(name=FONT, bold=True)
regular = Font(name=FONT)
title_font = Font(name=FONT, bold=True, size=12)
header_fill = PatternFill("solid", start_color="D9E1F2")
thin = Side(style="thin", color="A6A6A6")
border = Border(left=thin, right=thin, top=thin, bottom=thin)
center = Alignment(horizontal="center", vertical="center", wrap_text=True)

wb = Workbook()
ws = wb.active
ws.title = "MPI matvec"
ws["A1"] = "Умножение матрицы 1000×1000 на вектор, MPI"
ws["A1"].font = title_font
ws["A2"] = "Apple M4, OpenMPI, mpicxx -O2. Время — лучший запуск из 20 повторов. Ускорение от одного и того же Tпосл."
ws["A2"].font = Font(name=FONT, italic=True, color="595959")
ws.merge_cells("A2:H2")

headers = ["Процессы", "Время, с", "Scatter, с", "Bcast, с", "Умножение, с",
           "Gather, с", "Tпосл, с", "Ускорение"]
for col, text in enumerate(headers, start=1):
    cell = ws.cell(row=4, column=col, value=text)
    cell.font = bold
    cell.fill = header_fill
    cell.border = border
    cell.alignment = center
widths = [14, 14, 14, 14, 16, 14, 14, 14]
for i, w in enumerate(widths, start=1):
    ws.column_dimensions[chr(64 + i)].width = w

for i, r in enumerate(summary):
    values = [r["processes"], r["time_parallel"], r["scatter"], r["bcast"],
              r["compute"], r["gather"], r["time_sequential"], r["speedup"]]
    formats = ["0", "0.000000", "0.000000", "0.000000", "0.000000", "0.000000", "0.000000", "0.00"]
    for col, (value, fmt) in enumerate(zip(values, formats), start=1):
        cell = ws.cell(row=5 + i, column=col, value=value)
        cell.font = regular
        cell.border = border
        cell.alignment = center
        cell.number_format = fmt

last = 4 + len(summary)
chart = LineChart()
chart.title = "Время параллельного алгоритма"
chart.y_axis.title = "Время, с"
chart.x_axis.title = "Процессы"
chart.height = 7
chart.width = 15
chart.add_data(Reference(ws, min_col=2, max_col=2, min_row=4, max_row=last), titles_from_data=True)
chart.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
chart.shape = 4
ws.add_chart(chart, "A11")

chart_s = LineChart()
chart_s.title = "Ускорение"
chart_s.y_axis.title = "S"
chart_s.x_axis.title = "Процессы"
chart_s.height = 7
chart_s.width = 15
chart_s.add_data(Reference(ws, min_col=8, max_col=8, min_row=4, max_row=last), titles_from_data=True)
chart_s.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
ws.add_chart(chart_s, "E11")

bar = BarChart()
bar.type = "col"
bar.grouping = "stacked"
bar.title = "Куда уходит время"
bar.y_axis.title = "Время, с"
bar.height = 7
bar.width = 15
bar.add_data(Reference(ws, min_col=3, max_col=6, min_row=4, max_row=last), titles_from_data=True)
bar.set_categories(Reference(ws, min_col=1, min_row=5, max_row=last))
ws.add_chart(bar, "A26")

wb.save("results/seminar8_matvec.xlsx")
print("Сохранено: results/seminar8_matvec.xlsx")
