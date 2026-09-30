"""
Все численные эксперименты: результаты (рисунки, анимации, метрики)
сохраняются в папку results/.

    python run_all.py            # все сценарии (~1-2 минуты)
    python run_all.py normal     # только выбранные: normal avblock infarct reentry
"""

import os
import sys
import time

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from matplotlib.animation import FuncAnimation, PillowWriter

from geometry import (Heart, ellipse, NAMES, NONE, ATRIA, AVN, HIS, PURK,
                      VENT, SCAR, BORDER)
from heart_model import Tissue, PseudoECG, AlievPanfilov, to_mv, T_MS
from simulate import run

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.grid": False})

TYPE_COLORS = {
    NONE: "#ffffff", ATRIA: "#f4a261", AVN: "#2a9d8f", HIS: "#e63946",
    PURK: "#7b2cbf", VENT: "#c9a18a", SCAR: "#555555", BORDER: "#a8a8a8",
}
LEAD_COLORS = {"I": "#1f77b4", "II": "#d62728", "III": "#2ca02c"}
metrics = []


def log(s):
    print(s, flush=True)
    metrics.append(s)


def extent(h):
    ny, nx = h.shape
    return [0, nx * h.dx, ny * h.dx, 0]


def draw_types(ax, h, title="Типы тканей"):
    cmap = ListedColormap([TYPE_COLORS[k] for k in range(8)])
    ax.imshow(h.type, cmap=cmap, vmin=-0.5, vmax=7.5, extent=extent(h),
              interpolation="nearest")
    sy, sx = np.nonzero(h.sa)
    ax.plot(sx.mean() * h.dx, sy.mean() * h.dx, "k*", ms=12, label="синусовый узел")
    ax.set_title(title)
    ax.set_xlabel("x, мм")
    ax.set_ylabel("y, мм")


def draw_map(ax, h, field, title, cmap="jet", label="мс", isolines=None):
    m = np.where(h.D > 0, field, np.nan)
    ax.imshow(np.where(h.D > 0, np.nan, 0.0), cmap="gray_r", vmin=0, vmax=4,
              extent=extent(h))
    im = ax.imshow(m, cmap=cmap, extent=extent(h), interpolation="nearest")
    if isolines is not None:
        ny, nx = h.shape
        xs, ys = np.arange(nx) * h.dx, np.arange(ny) * h.dx
        ax.contour(xs, ys, np.nan_to_num(m, nan=np.nanmax(m) + 100),
                   levels=isolines, colors="k", linewidths=0.5)
    plt.colorbar(im, ax=ax, label=label, shrink=0.8)
    ax.set_title(title)
    ax.set_xticks([])
    ax.set_yticks([])


def plot_ecg(ax, r, scale, leads=("I", "II", "III"), offset=1.6, t0=0):
    for i, name in enumerate(leads):
        y = r["leads"][name] / scale - i * offset
        ax.plot(r["t"] - t0, y, color=LEAD_COLORS[name], lw=1.3)
        ax.text(r["t"][0] - t0 - 5, -i * offset, name, ha="right", va="center",
                fontweight="bold")
    ax.set_xlabel("время, мс")
    ax.set_yticks([])
    # "миллиметровка" ЭКГ: крупная клетка 200 мс
    ax.set_xticks(np.arange(0, r["t"][-1] - t0 + 1, 200))
    ax.grid(True, which="major", color="#f4b6b6", lw=0.8)
    ax.set_xlim(r["t"][0] - t0, r["t"][-1] - t0)


def intervals(h, r, beat_start=0.0):
    """Интервалы ЭКГ по картам активации/реполяризации (одно сокращение)."""
    a, rep, t = r["act"], r["rep"], h.type
    atr = a[t == ATRIA]
    ven = a[np.isin(t, (VENT, BORDER))]
    ven_rep = rep[np.isin(t, (VENT, BORDER))]
    return {
        "P": np.nanmax(atr) - np.nanmin(atr),
        "PR": np.nanmin(ven) - np.nanmin(atr),
        "QRS": np.nanmax(ven) - np.nanmin(ven),
        "QT": np.nanmax(ven_rep) - np.nanmin(ven),
    }


def ecg_qrs_width(t, sig, t_from, t_to, frac=0.05):
    """Ширина QRS по ЭКГ: участок, где |dV/dt| превышает долю от максимума."""
    w = (t >= t_from) & (t <= t_to)
    d = np.abs(np.gradient(sig[w], t[w]))
    on = np.nonzero(d > frac * d.max())[0]
    return t[w][on[-1]] - t[w][on[0]]


def animate(h, r, fname, t_range, scale, lead="II", fps=12):
    ts = r["snap_t"]
    idx = np.nonzero((ts >= t_range[0]) & (ts <= t_range[1]))[0]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4),
                                 gridspec_kw={"width_ratios": [1, 1.25]})
    bg = np.where(h.D > 0, np.nan, 0.0)
    a1.imshow(bg, cmap="gray_r", vmin=0, vmax=4, extent=extent(h))
    im = a1.imshow(np.where(h.D > 0, to_mv(r["snaps"][idx[0]]), np.nan),
                   cmap="inferno", vmin=-85, vmax=25, extent=extent(h))
    plt.colorbar(im, ax=a1, label="V, мВ", shrink=0.8)
    a1.set_xticks([]); a1.set_yticks([])
    title = a1.set_title("")
    w = (r["t"] >= t_range[0]) & (r["t"] <= t_range[1])
    a2.plot(r["t"][w], r["leads"][lead][w] / scale, color=LEAD_COLORS[lead])
    a2.set_title(f"псевдо-ЭКГ, отведение {lead}")
    a2.set_xlabel("время, мс")
    a2.grid(True, color="#f4b6b6")
    cur = a2.axvline(ts[idx[0]], color="k", lw=1)
    fig.tight_layout()

    def upd(j):
        i = idx[j]
        im.set_data(np.where(h.D > 0, to_mv(r["snaps"][i]), np.nan))
        title.set_text(f"t = {ts[i]:.0f} мс")
        cur.set_xdata([ts[i], ts[i]])
        return im, cur, title

    anim = FuncAnimation(fig, upd, frames=len(idx), blit=False)
    anim.save(os.path.join(OUT, fname), writer=PillowWriter(fps=fps), dpi=65)
    plt.close(fig)


def snapshots(h, r, times, fname, suptitle):
    fig, axs = plt.subplots(1, len(times), figsize=(2.6 * len(times), 3))
    for ax, tt in zip(axs, times):
        i = np.argmin(np.abs(r["snap_t"] - tt))
        ax.imshow(np.where(h.D > 0, np.nan, 0.0), cmap="gray_r", vmin=0, vmax=4,
                  extent=extent(h))
        ax.imshow(np.where(h.D > 0, to_mv(r["snaps"][i]), np.nan), cmap="inferno",
                  vmin=-85, vmax=25, extent=extent(h))
        ax.set_title(f"{r['snap_t'][i]:.0f} мс")
        ax.axis("off")
    fig.suptitle(suptitle)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, fname), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 1. Норма: синусовый ритм 75 уд/мин
# ---------------------------------------------------------------------------
def scenario_normal():
    log("\n=== 1. Нормальный синусовый ритм, 75 уд/мин ===")
    h = Heart()
    t0 = time.time()
    r = run(h, 2400, bpm=75)
    log(f"время счёта: {time.time() - t0:.1f} с, клеток ткани: {(h.D > 0).sum()}")
    scale = np.abs(r["leads"]["II"]).max()   # нормировка: max|II| = 1

    # --- геометрия ---
    fig, ax = plt.subplots(1, 2, figsize=(12, 5.5))
    draw_types(ax[0], h)
    ax[0].legend(handles=[Patch(color=TYPE_COLORS[k], label=NAMES[k])
                          for k in (ATRIA, AVN, HIS, PURK, VENT)]
                 + [plt.Line2D([], [], color="k", marker="*", ls="", ms=10,
                               label="синусовый узел")],
                 loc="lower left", fontsize=8)
    el = h.electrodes()
    ax[1].imshow(np.where(h.D > 0, 1.0, np.nan), cmap="Reds", vmin=0, vmax=1.5,
                 extent=extent(h))
    pts = np.array([el["RA"], el["LA"], el["LL"], el["RA"]])
    ax[1].plot(pts[:, 0], pts[:, 1], "k--", lw=1)
    for n, (x, y) in el.items():
        ax[1].plot(x, y, "ko")
        ax[1].text(x, y - 8, n, ha="center", fontweight="bold")
    ax[1].set_xlim(-110, 200); ax[1].set_ylim(220, -90)
    ax[1].set_aspect("equal")
    ax[1].set_title("Треугольник Эйнтховена: I = LA-RA, II = LL-RA, III = LL-LA")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "01_geometry.png"), dpi=110)
    plt.close(fig)

    # --- карты: активация, реполяризация, ПД ---
    fig, ax = plt.subplots(1, 3, figsize=(15, 5))
    draw_map(ax[0], h, r["act"], "Время активации (1-й цикл)",
             isolines=np.arange(0, 400, 20))
    draw_map(ax[1], h, r["rep"], "Время реполяризации", cmap="viridis",
             isolines=np.arange(200, 700, 20))
    draw_map(ax[2], h, r["apd"], "Длительность ПД (APD50)", cmap="plasma")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "02_normal_maps.png"), dpi=110)
    plt.close(fig)

    snapshots(h, r, [30, 90, 150, 200, 230, 260, 400, 480, 540],
              "03_normal_snapshots.png",
              "Распространение возбуждения: P (предсердия) → задержка в АВ-узле → "
              "QRS (желудочки) → плато (ST) → реполяризация (T)")

    # --- ЭКГ ---
    fig, ax = plt.subplots(2, 1, figsize=(13, 7.5), gridspec_kw={"height_ratios": [2.2, 1]})
    plot_ecg(ax[0], r, scale)
    ax[0].set_title("Псевдо-ЭКГ, стандартные отведения (норма, 75 уд/мин)")
    tt, ii = r["t"], r["leads"]["II"] / scale
    b = (tt < 800)
    iv = intervals(h, r)
    ax[1].plot(tt[b], ii[b], color=LEAD_COLORS["II"], lw=1.6)
    for x0, x1, lab, yy in [(20, 20 + iv["P"], "P", 0.45),
                            (20, 20 + iv["PR"], "PR", -0.55),
                            (20 + iv["PR"], 20 + iv["PR"] + iv["QRS"], "QRS", 1.1),
                            (20 + iv["PR"], 20 + iv["PR"] + iv["QT"], "QT", -0.85)]:
        ax[1].annotate("", (x0, yy), (x1, yy), arrowprops=dict(arrowstyle="<->"))
        ax[1].text((x0 + x1) / 2, yy + 0.07, f"{lab} {x1 - x0:.0f} мс", ha="center")
    ax[1].set_ylim(-1.1, 1.35)
    ax[1].set_xlabel("время, мс")
    ax[1].set_title("Отведение II, один сердечный цикл: интервалы по картам активации")
    ax[1].grid(True, color="#f4b6b6")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "04_normal_ecg.png"), dpi=110)
    plt.close(fig)

    log("Интервалы (по картам активации/реполяризации, 1-й цикл):")
    for k, v in iv.items():
        log(f"  {k:4s} = {v:6.1f} мс")
    log(f"  QRS по ЭКГ (отведение II) = {ecg_qrs_width(tt, ii, 150, 380):.1f} мс")
    at = r["act"]
    log(f"Активация: предсердия {np.nanmin(at[h.type == ATRIA]):.0f}-{np.nanmax(at[h.type == ATRIA]):.0f} мс, "
        f"АВ-узел {np.nanmin(at[h.type == AVN]):.0f}-{np.nanmax(at[h.type == AVN]):.0f} мс, "
        f"пучок Гиса {np.nanmin(at[h.type == HIS]):.0f}-{np.nanmax(at[h.type == HIS]):.0f} мс, "
        f"Пуркинье {np.nanmin(at[h.type == PURK]):.0f}-{np.nanmax(at[h.type == PURK]):.0f} мс")
    apd = r["apd"][h.type == VENT]
    log(f"APD50 желудочков: {np.nanmin(apd):.0f}-{np.nanmax(apd):.0f} мс; "
        f"APD50 предсердий: {np.nanmean(r['apd'][h.type == ATRIA]):.0f} мс")
    ven = np.isin(h.type, (VENT, PURK, HIS))
    log(f"Все клетки желудочков возбуждены 3 раза: {np.all(r['n_act'][ven] == 3)}")

    animate(h, r, "normal_beat.gif", (0, 700), scale)
    return scale


# ---------------------------------------------------------------------------
# 2. Полная АВ-блокада (III степени) с идиовентрикулярным ритмом
# ---------------------------------------------------------------------------
def scenario_avblock(scale):
    log("\n=== 2. Полная атриовентрикулярная блокада ===")
    h = Heart(av_block=True)
    # выскальзывающий водитель ритма в миокарде ЛЖ у верхушки, 35 уд/мин
    esc = ellipse(h.X, h.Y, 8.0, 50.0, 2.0, 2.0) & (h.type == VENT)
    esc_times = np.arange(600.0, 4000.0, 60000.0 / 35)
    r = run(h, 4000, bpm=75, extra_stim=[(t, esc) for t in esc_times])
    ven = h.type == VENT
    log(f"Предсердия возбуждены {r['n_act'][h.type == ATRIA].max()} раз (синусовый ритм 75/мин), "
        f"желудочки - {r['n_act'][ven].max()} раз (выскальзывающий ритм 35/мин)")
    at = r["act"]
    log(f"Первая активация желудочков от эктопического очага: "
        f"{np.nanmin(at[ven]):.0f}-{np.nanmax(at[ven]):.0f} мс "
        f"(QRS {np.nanmax(at[ven]) - np.nanmin(at[ven]):.0f} мс - широкий, без участия Пуркинье)")

    fig = plt.figure(figsize=(14, 7))
    g = fig.add_gridspec(2, 3)
    ax0 = fig.add_subplot(g[0, 0])
    draw_types(ax0, h, "АВ-узел перерезан; ★ - синусовый узел,\n● - эктопический очаг")
    sy, sx = np.nonzero(esc)
    ax0.plot(sx.mean() * h.dx, sy.mean() * h.dx, "ko", ms=8)
    ax1 = fig.add_subplot(g[0, 1])
    draw_map(ax1, h, at, "Активация (1-й цикл)", isolines=np.arange(0, 1000, 20))
    ax2 = fig.add_subplot(g[0, 2])
    i = np.argmin(np.abs(r["snap_t"] - 660))
    ax2.imshow(np.where(h.D > 0, to_mv(r["snaps"][i]), np.nan), cmap="inferno",
               vmin=-85, vmax=25, extent=extent(h))
    ax2.set_title("t = 660 мс: желудочки возбуждаются\nот очага, минуя проводящую систему")
    ax2.axis("off")
    ax3 = fig.add_subplot(g[1, :])
    tt, ii = r["t"], r["leads"]["II"] / scale
    ax3.plot(tt, ii, color=LEAD_COLORS["II"])
    for k in range(int(4000 / 800) + 1):
        ax3.text(k * 800 + 55, 0.35, "P", ha="center", color="#264653", fontweight="bold")
    for te in esc_times:
        ax3.text(te + 60, ii.max() * 1.05, "QRS", ha="center", color="#6a040f",
                 fontweight="bold")
    ax3.set_ylim(ii.min() * 1.2, ii.max() * 1.3)
    ax3.set_xlabel("время, мс")
    ax3.set_title("Отведение II: зубцы P (75/мин) не связаны с широкими комплексами QRS (35/мин) - "
                  "АВ-диссоциация")
    ax3.grid(True, color="#f4b6b6")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "05_av_block.png"), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 3. Постинфарктный рубец + желудочковая экстрасистола
# ---------------------------------------------------------------------------
def scenario_infarct(scale):
    log("\n=== 3. Постинфарктный рубец в боковой стенке ЛЖ ===")
    hn, hi = Heart(), Heart(scar=True)
    rn = run(hn, 800)
    pvc = ellipse(hi.X, hi.Y, 17.0, 42.0, 1.5, 1.5) & np.isin(hi.type, (VENT, BORDER))
    ri = run(hi, 2400, extra_stim=[(1450.0, pvc)])

    ivn, ivi = intervals(hn, rn), intervals(hi, ri)
    log(f"{'':6s} {'норма':>8s} {'инфаркт':>8s}")
    for k in ivn:
        log(f"{k:6s} {ivn[k]:8.1f} {ivi[k]:8.1f} мс")
    for name, h, r in (("норма", hn, rn), ("инфаркт", hi, ri)):
        w = r["t"] < 800
        log(f"QRS по ЭКГ (II), {name}: "
            f"{ecg_qrs_width(r['t'][w], r['leads']['II'][w] / scale, 150, 450):.1f} мс")
    bz = hi.type == BORDER
    log(f"Пограничная зона активируется в {np.nanmin(ri['act'][bz]):.0f}-{np.nanmax(ri['act'][bz]):.0f} мс; "
        f"последняя клетка желудочков - {ivi['PR'] + ivi['QRS'] + 20:.0f} мс")
    n_v = ri["n_act"][hi.type == VENT]
    log(f"За 2400 мс желудочки возбуждены {np.bincount(n_v).argmax()} раза "
        f"(2 синусовых + экстрасистола; 3-й синусовый импульс блокирован - компенсаторная пауза)")

    fig = plt.figure(figsize=(14, 8.5))
    g = fig.add_gridspec(2, 3, height_ratios=[1, 0.9])
    ax = fig.add_subplot(g[0, 0])
    draw_types(ax, hi, "Рубец (серый) и пограничная зона")
    ax.legend(handles=[Patch(color=TYPE_COLORS[k], label=NAMES[k]) for k in (SCAR, BORDER)]
              + [plt.Line2D([], [], color="k", marker="o", ls="", label="очаг экстрасистолы")],
              loc="lower left", fontsize=8)
    sy, sx = np.nonzero(pvc)
    ax.plot(sx.mean() * hi.dx, sy.mean() * hi.dx, "ko", ms=6)
    vmax = np.nanmax(ri["act"][np.isin(hi.type, (VENT, BORDER))])
    for j, (h, r, ttl) in enumerate(((hn, rn, "Активация: норма"), (hi, ri, "Активация: инфаркт"))):
        a = fig.add_subplot(g[0, j + 1])
        f = np.where(np.isin(h.type, (VENT, BORDER, PURK, HIS)), r["act"], np.nan)
        draw_map(a, h, f, ttl, isolines=np.arange(160, 420, 10))
        a.images[-1].set_clim(160, vmax)
    ax2 = fig.add_subplot(g[1, :2])
    for name, r, ls in (("норма", rn, "--"), ("инфаркт", ri, "-")):
        w = r["t"] < 800
        for k, lead in enumerate(("I", "II")):
            ax2.plot(r["t"][w], r["leads"][lead][w] / scale - 1.7 * k,
                     color=LEAD_COLORS[lead], ls=ls, lw=1.3,
                     label=f"{lead}, {name}")
    ax2.set_title("Синусовый цикл: норма (пунктир) и инфаркт (сплошная)")
    ax2.legend(fontsize=8, ncol=2)
    ax2.set_xlabel("время, мс")
    ax2.set_yticks([])
    ax2.grid(True, color="#f4b6b6")
    ax3 = fig.add_subplot(g[1, 2])
    ax3.plot(ri["t"], ri["leads"]["II"] / scale, color=LEAD_COLORS["II"], lw=1)
    ax3.axvline(1450, color="k", ls=":")
    ax3.text(1470, ax3.get_ylim()[1] * 0.85, "экстра-\nсистола", fontsize=8)
    ax3.set_title("Отведение II: экстрасистола из\nпограничной зоны и компенсаторная пауза")
    ax3.set_xlabel("время, мс")
    ax3.grid(True, color="#f4b6b6")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "06_infarct.png"), dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# 4. Re-entry: спиральная волна (тахикардия) и её распад на фиброзе
# ---------------------------------------------------------------------------
def patchy_fibrosis(n, dx, frac, blob, seed=1):
    """Пятнистый фиброз: сглаженный гауссов шум, порог по доле frac."""
    rng = np.random.default_rng(seed)
    z = np.fft.fft2(rng.standard_normal((n, n)))
    kx = np.fft.fftfreq(n)[None, :]
    ky = np.fft.fftfreq(n)[:, None]
    z = np.real(np.fft.ifft2(z * np.exp(-(kx ** 2 + ky ** 2) * (np.pi * blob / dx) ** 2)))
    return z > np.quantile(z, 1 - frac)


def sheet(fib_frac, L=100.0, dx=0.5, D=5.0, k=10.0, t_end=4000.0):
    """Квадратный фрагмент миокарда, протокол S1-S2 (крестовой стимуляции).

    S1 - плоская волна от левого края; S2 - стимул в левой нижней четверти
    в момент, когда хвост S1 (зона восстановления) проходит середину.
    Разрыв фронта S2 о рефрактерный хвост S1 порождает спиральную волну.
    """
    n = int(L / dx)
    yy, xx = np.mgrid[0:n, 0:n] * dx
    fib = patchy_fibrosis(n, dx, fib_frac, 2.0) if fib_frac > 0 else np.zeros((n, n), bool)
    fib &= ~(xx < 4)      # у стимулирующего электрода ткань здорова
    Dm = np.where(fib, 0.0, D)
    tis = Tissue(Dm, dx, 0.01, k=k, method="explicit")
    # электроды вне ткани: "отведение" = разность потенциалов
    ecg = PseudoECG(tis, {"A": (L / 2, -L), "B": (L / 2, 2 * L)})
    s1 = tis.cells(xx < 3)
    s2c = tis.cells((xx < L / 2) & (yy > L / 2))
    probe = tis.cells((np.abs(xx - L / 2) < 2) & (np.abs(yy - L / 2) < 2) & ~fib)[0]
    stim = np.zeros(tis.idx.size)
    t_s2, excited = None, False
    ts, sig, frames, ft = [], [], [], []
    nstep = int(t_end / T_MS / tis.dt)
    probe_u = []
    for st in range(nstep):
        tm = tis.t * T_MS
        stim[:] = 0
        if tm < 10:
            stim[s1] = 1
        if tis.u[probe] > 0.5:
            excited = True
        if t_s2 is None and excited and tis.u[probe] < 0.3:
            t_s2 = tm
        if t_s2 is not None and t_s2 <= tm < t_s2 + 10:
            stim[s2c] = 1
        tis.step(stim)
        if st % 20 == 0:
            m = ecg.measure()
            ts.append(tm)
            sig.append(m["A"] - m["B"])
            probe_u.append(tis.u[probe])
        if st % 100 == 0:
            frames.append(tis.full().astype(np.float32))
            ft.append(tm)
    return dict(t=np.array(ts), ecg=np.array(sig), frames=np.array(frames),
                ft=np.array(ft), fib=fib, t_s2=t_s2, probe=np.array(probe_u),
                L=L, dx=dx)


def dominant_period(t, x, t_from):
    w = t > t_from
    y = x[w] - x[w].mean()
    f = np.fft.rfftfreq(y.size, d=(t[1] - t[0]))
    p = np.abs(np.fft.rfft(y)) ** 2
    p[f < 1 / 2000] = 0
    return 1 / f[np.argmax(p)], p, f


def count_activations(t, u, t_from):
    w = t > t_from
    up = (u[w][1:] > 0.5) & (u[w][:-1] <= 0.5)
    return np.diff(t[w][1:][up])


def scenario_reentry():
    log("\n=== 4. Re-entry во фрагменте миокарда (100 x 100 мм) ===")
    res = {}
    for key, frac in (("однородная ткань", 0.0), ("фиброз 25 %", 0.25)):
        t0 = time.time()
        s = sheet(frac)
        res[key] = s
        cl = count_activations(s["t"], s["probe"], 1500)
        per, _, _ = dominant_period(s["t"], s["ecg"], 1500)
        active = [np.mean(f[~s["fib"]] > 0.5) for f in s["frames"][-5:]]
        log(f"{key}: S2 в {s['t_s2']:.0f} мс; активность в конце: "
            f"{'есть' if max(active) > 0.01 else 'нет'}; "
            f"интервалы между возбуждениями в центре: "
            f"{np.mean(cl):.0f} ± {np.std(cl):.0f} мс (ЧСС {60000 / np.mean(cl):.0f}/мин); "
            f"доминирующий период ЭКГ {per:.0f} мс; счёт {time.time() - t0:.1f} с")

    fig = plt.figure(figsize=(15, 8))
    g = fig.add_gridspec(3, 6, height_ratios=[1, 1, 0.9])
    for row, (key, s) in enumerate(res.items()):
        idxs = [np.argmin(np.abs(s["ft"] - tt)) for tt in (300, s["t_s2"] + 60, 1200, 2000, 3000, 3900)]
        for c, i in enumerate(idxs):
            ax = fig.add_subplot(g[row, c])
            ax.imshow(np.where(s["fib"], np.nan, to_mv(s["frames"][i])), cmap="inferno",
                      vmin=-85, vmax=25, extent=[0, s["L"], s["L"], 0])
            ax.set_title(f"{s['ft'][i]:.0f} мс", fontsize=9)
            ax.set_xticks([]); ax.set_yticks([])
            if c == 0:
                ax.set_ylabel(key)
    ax = fig.add_subplot(g[2, :])
    for k, (key, s) in enumerate(res.items()):
        e = s["ecg"] / np.abs(s["ecg"]).max()
        ax.plot(s["t"], e - 2.3 * k, lw=1.1, color=("#d62728", "#1f3b73")[k], label=key)
    ax.axvline(res["однородная ткань"]["t_s2"], color="k", ls=":")
    ax.set_yticks([])
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xlabel("время, мс")
    ax.set_title("Псевдо-ЭКГ фрагмента: мономорфная тахикардия (стабильная спираль) и "
                 "нерегулярная активность при фиброзе (модель фибрилляции)")
    ax.grid(True, color="#f4b6b6")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "07_reentry.png"), dpi=110)
    plt.close(fig)

    # анимация спиральной волны
    for key, fname in (("однородная ткань", "spiral.gif"), ("фиброз 25 %", "fibrillation.gif")):
        s = res[key]
        fig, ax = plt.subplots(figsize=(4, 4))
        im = ax.imshow(np.where(s["fib"], np.nan, to_mv(s["frames"][0])), cmap="inferno",
                       vmin=-85, vmax=25)
        ax.axis("off")
        ttl = ax.set_title("")
        sel = np.arange(0, len(s["ft"]), 2)

        def upd(j, s=s, im=im, ttl=ttl, sel=sel):
            i = sel[j]
            im.set_data(np.where(s["fib"], np.nan, to_mv(s["frames"][i])))
            ttl.set_text(f"{key}, t = {s['ft'][i]:.0f} мс")
            return im,

        FuncAnimation(fig, upd, frames=len(sel)).save(
            os.path.join(OUT, fname), writer=PillowWriter(fps=15), dpi=60)
        plt.close(fig)


if __name__ == "__main__":
    which = sys.argv[1:] or ["normal", "avblock", "infarct", "reentry"]
    t_all = time.time()
    scale = scenario_normal() if "normal" in which else None
    if scale is None:
        r = run(Heart(), 800)
        scale = np.abs(r["leads"]["II"]).max()
    if "avblock" in which:
        scenario_avblock(scale)
    if "infarct" in which:
        scenario_infarct(scale)
    if "reentry" in which:
        scenario_reentry()
    log(f"\nОбщее время: {time.time() - t_all:.0f} с")
    with open(os.path.join(OUT, "metrics.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(metrics) + "\n")
