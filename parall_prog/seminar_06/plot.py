# Семинар 6. Графики ускорения и эффективности LU-разложения (N = 1000)
# Запуск из папки parall_prog: python3 seminar_06/plot.py
import csv

import matplotlib.pyplot as plt

threads, speedup, efficiency = [], [], []
with open("results/seminar6_lu.csv") as f:
    for row in csv.DictReader(f):
        threads.append(int(row["threads"]))
        speedup.append(float(row["speedup"]))
        efficiency.append(float(row["efficiency"]))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

ax1.plot(threads, threads, "--", color="gray", label="Идеальное")
ax1.plot(threads, speedup, "o-", color="tab:blue", label="LU-разложение")
for t, s in zip(threads, speedup):
    ax1.annotate(f"{s:.2f}", (t, s), textcoords="offset points", xytext=(0, 8), ha="center")
ax1.set_title("Ускорение S = T1 / Tp (N = 1000)")
ax1.set_xlabel("Число потоков")
ax1.set_ylabel("Ускорение")
ax1.set_xticks(threads)
ax1.grid(alpha=0.3)
ax1.legend()

ax2.plot(threads, [1.0] * len(threads), "--", color="gray", label="Идеальная")
ax2.plot(threads, efficiency, "o-", color="tab:orange", label="LU-разложение")
for t, e in zip(threads, efficiency):
    ax2.annotate(f"{e:.2f}", (t, e), textcoords="offset points", xytext=(0, 8), ha="center")
ax2.set_title("Эффективность E = S / p (N = 1000)")
ax2.set_xlabel("Число потоков")
ax2.set_ylabel("Эффективность")
ax2.set_xticks(threads)
ax2.set_ylim(0, 1.15)
ax2.grid(alpha=0.3)
ax2.legend()

fig.tight_layout()
fig.savefig("results/seminar6_lu.png", dpi=150)
print("Сохранено: results/seminar6_lu.png")
