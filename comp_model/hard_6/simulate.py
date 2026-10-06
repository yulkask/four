"""Запуск модели на геометрии сердца: ритм, ЭКГ, карты активации, кадры."""

import numpy as np

from heart_model import Tissue, PseudoECG, einthoven, T_MS


def run(heart, t_end_ms, bpm=75.0, dt=0.004, method="imex", extra_stim=(),
        record_ms=2.0, snap_ms=10.0, stim_amp=1.0, stim_dur_ms=12.0,
        sinus=True, extra_amp=3.0, progress=False):
    """Моделирование.

    extra_stim - список (t_ms, mask): дополнительные стимулы
                 (экстрасистолы, протокол S1-S2).
    Возвращает словарь с ЭКГ, картами активации и кадрами u.
    """
    tis = Tissue(heart.D, heart.dx, dt, k=heart.k, a=heart.a, method=method)
    ecg = PseudoECG(tis, heart.electrodes(), weight=heart.w_ecg)

    period = 60000.0 / bpm / T_MS
    dur = stim_dur_ms / T_MS
    sa = tis.cells(heart.sa)
    stims = [(t / T_MS, tis.cells(m)) for t, m in extra_stim]

    n_steps = int(round(t_end_ms / T_MS / dt))
    rec_every = max(1, int(round(record_ms / T_MS / dt)))
    snap_every = max(1, int(round(snap_ms / T_MS / dt)))

    n = tis.idx.size
    act = np.full(n, np.nan)          # время первой активации, мс
    rep = np.full(n, np.nan)          # время первой реполяризации, мс
    act_last = np.full(n, np.nan)     # время последней активации, мс
    rep_last = np.full(n, np.nan)     # время последней реполяризации, мс
    n_act = np.zeros(n, dtype=int)    # число возбуждений клетки
    above = np.zeros(n, dtype=bool)

    times, snaps, snap_t = [], [], []
    leads = {"I": [], "II": [], "III": []}
    stim = np.zeros(n)

    for step in range(n_steps):
        t = tis.t
        stim[:] = 0.0
        if sinus and (t % period) < dur:
            stim[sa] = stim_amp
        for t0, cells in stims:
            if t0 <= t < t0 + dur:
                stim[cells] = extra_amp   # эктопический очаг: сильный стимул
        tis.step(stim)

        # регистрация фронта: пересечение u = 0.5 снизу вверх
        now = tis.u > 0.5
        new = now & ~above
        tm = tis.t * T_MS
        if new.any():
            act[new & np.isnan(act)] = tm
            act_last[new] = tm
            n_act[new] += 1
        down = above & ~now
        if down.any():
            rep[down & np.isnan(rep)] = tm
            rep_last[down] = tm
        above = now

        if step % rec_every == 0:
            lv = einthoven(ecg.measure())
            times.append(tis.t * T_MS)
            for key in leads:
                leads[key].append(lv[key])
        if step % snap_every == 0:
            snaps.append(tis.full().astype(np.float32))
            snap_t.append(tis.t * T_MS)
        if progress and step % max(1, n_steps // 10) == 0:
            print(f"  {100 * step / n_steps:5.1f}%  t = {tis.t * T_MS:7.1f} мс", flush=True)

    return {
        "t": np.array(times),
        "leads": {k: np.array(v) for k, v in leads.items()},
        "act": tis.full(act),
        "rep": tis.full(rep),
        "apd": tis.full(rep - act),
        "act_last": tis.full(act_last),
        "rep_last": tis.full(rep_last),
        "n_act": tis.full(n_act.astype(float), fill=0).astype(int),
        "snaps": np.array(snaps), "snap_t": np.array(snap_t),
        "heart": heart,
    }
