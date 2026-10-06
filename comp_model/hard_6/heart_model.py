"""
Модель распространения электрического импульса по ткани сердца.

Монодоменная модель реакции-диффузии с кинетикой Алиева-Панфилова
(Aliev R.R., Panfilov A.V., Chaos, Solitons & Fractals 7(3), 1996):

    du/dt = div(D grad u) + k*u*(u - a)*(1 - u) - u*v + I_stim
    dv/dt = eps(u, v) * (-v - k*u*(u - a - 1)),
    eps(u, v) = eps0 + mu1*v / (u + mu2)

u - безразмерный трансмембранный потенциал (V[мВ] = 100*u - 80),
v - переменная восстановления (медленные токи K+).
Безразмерное время переводится в мс множителем T_MS = 12.9.

Пространственная дискретизация - метод конечных объёмов на квадратной
сетке: поток между соседними клетками D_f*(u_j - u_i)/dx, где D_f -
гармоническое среднее. Если одна из клеток не проводит (D = 0), поток
равен нулю - это условие непротекания на границе ткани, полостей и рубца.
Считаются только клетки ткани (разреженная матрица L).

Интегрирование по времени:
  * "explicit" - явный метод Эйлера, устойчив при dt <= dx^2 / (4 D_max);
  * "imex"     - полунеявная схема: диффузия неявно, реакция явно
                 (I - dt L) u^{n+1} = u^n + dt (f(u^n, v^n) + I_stim),
                 безусловно устойчива по диффузии, что важно для быстрой
                 проводящей системы (D у волокон Пуркинье в 20 раз больше).

Псевдо-ЭКГ (дипольное приближение, бесконечная однородная среда):
    phi(x0) = -integral D grad(u) . grad(1/r) dA,   r = |x - x0|
"""

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

T_MS = 12.9  # 1 безразмерная единица времени = 12.9 мс


def to_mv(u):
    return 100.0 * u - 80.0


class AlievPanfilov:
    """Параметры клеточной кинетики."""

    def __init__(self, k=8.0, a=0.15, eps0=0.002, mu1=0.2, mu2=0.3):
        self.k, self.a = k, a
        self.eps0, self.mu1, self.mu2 = eps0, mu1, mu2

    def rhs(self, u, v, k=None, a=None):
        k = self.k if k is None else k
        a = self.a if a is None else a
        fu = k * u * (u - a) * (1.0 - u) - u * v
        eps = self.eps0 + self.mu1 * v / (u + self.mu2)
        fv = eps * (-v - k * u * (u - a - 1.0))
        return fu, fv


def _hmean(a, b):
    s = a + b
    return np.where(s > 0, 2 * a * b / np.where(s > 0, s, 1), 0.0)


class Tissue:
    """Двумерная ткань с неоднородной проводимостью D.

    D      - массив (ny, nx) коэффициентов диффузии; D > 0 - ткань
    k      - скаляр или поле параметра k (длительность ПД)
    a      - скаляр или поле порога возбуждения a
    method - "imex" или "explicit"
    """

    def __init__(self, D, dx, dt, model=None, k=None, a=None, method="imex"):
        self.D = np.asarray(D, dtype=float)
        self.shape = self.D.shape
        self.mask = self.D > 0
        self.dx, self.dt, self.method = dx, dt, method
        self.model = model or AlievPanfilov()

        ny, nx = self.shape
        self.idx = np.flatnonzero(self.mask)           # клетки ткани
        n = self.idx.size
        pos = -np.ones(ny * nx, dtype=int)
        pos[self.idx] = np.arange(n)
        self.pos = pos

        # грани между соседними клетками ткани: (i, j, D_f)
        Dx = _hmean(self.D[:, 1:], self.D[:, :-1])
        Dy = _hmean(self.D[1:, :], self.D[:-1, :])
        flat = np.arange(ny * nx).reshape(ny, nx)
        fi = np.concatenate([flat[:, :-1].ravel(), flat[:-1, :].ravel()])
        fj = np.concatenate([flat[:, 1:].ravel(), flat[1:, :].ravel()])
        fd = np.concatenate([Dx.ravel(), Dy.ravel()])
        # направление грани: 0 - по x, 1 - по y; центр грани
        fdir = np.concatenate([np.zeros(Dx.size, int), np.ones(Dy.size, int)])
        keep = fd > 0
        self.faces = (pos[fi[keep]], pos[fj[keep]], fd[keep], fdir[keep])
        fi_, fj_, fd_ = pos[fi[keep]], pos[fj[keep]], fd[keep]

        # L u = div(D grad u), матрица n x n
        w = fd_ / dx ** 2
        rows = np.concatenate([fi_, fj_, fi_, fj_])
        cols = np.concatenate([fj_, fi_, fi_, fj_])
        vals = np.concatenate([w, w, -w, -w])
        self.L = sp.csr_matrix((vals, (rows, cols)), shape=(n, n))

        if method == "explicit":
            dt_max = dx * dx / (4 * self.D.max())
            if dt > dt_max:
                raise ValueError(f"dt={dt} нарушает устойчивость: dt <= {dt_max:.5f}")
        elif method == "imex":
            A = sp.identity(n, format="csc") - dt * self.L.tocsc()
            self._lu = spla.splu(A.tocsc())
        else:
            raise ValueError(method)

        kk = self.model.k if k is None else k
        self.k = np.broadcast_to(np.asarray(kk, float), self.shape).ravel()[self.idx].copy()
        aa = self.model.a if a is None else a
        self.a = np.broadcast_to(np.asarray(aa, float), self.shape).ravel()[self.idx].copy()
        self.u = np.zeros(n)
        self.v = np.zeros(n)
        self.t = 0.0

    def cells(self, mask):
        """Номера клеток ткани, попадающих в маску (ny, nx)."""
        p = self.pos[np.flatnonzero(mask)]
        return p[p >= 0]

    def full(self, vec=None, fill=np.nan):
        """Вектор по клеткам ткани -> массив (ny, nx)."""
        vec = self.u if vec is None else vec
        out = np.full(self.shape[0] * self.shape[1], fill, dtype=float)
        out[self.idx] = vec
        return out.reshape(self.shape)

    def step(self, stim=None):
        fu, fv = self.model.rhs(self.u, self.v, self.k, self.a)
        if stim is not None:
            fu = fu + stim
        if self.method == "explicit":
            self.u = self.u + self.dt * (self.L @ self.u + fu)
        else:
            self.u = self._lu.solve(self.u + self.dt * fu)
        self.v = self.v + self.dt * fv
        self.t += self.dt


class PseudoECG:
    """Потенциалы электродов, расположенных вне ткани.

    Градиент u берётся на гранях между клетками ткани с теми же весами D_f,
    что и в уравнении диффузии: через границу ткани ток не течёт, поэтому
    однородно возбуждённая ткань (плато ПД) не даёт ложного сигнала.
    Так как phi линейно зависит от u, для каждого электрода заранее
    строится вектор c: phi = c . u.

    weight - поле (ny, nx) "толщины" ткани поперёк среза (2.5D поправка):
             тонкие стенки предсердий дают меньший вклад, чем миокард ЛЖ.
    """

    def __init__(self, tissue, electrodes, weight=None):
        ny, nx = tissue.shape
        dx = tissue.dx
        fi, fj, fd, fdir = tissue.faces
        yi, xi = np.divmod(tissue.idx, nx)
        # центр грани (в единицах длины)
        cx = (xi[fi] + xi[fj]) / 2 * dx
        cy = (yi[fi] + yi[fj]) / 2 * dx
        if weight is None:
            wf = np.ones_like(fd)
        else:
            wv = np.asarray(weight, float).ravel()[tissue.idx]
            wf = (wv[fi] + wv[fj]) / 2
        self.names = list(electrodes)
        self.c = []
        n = tissue.idx.size
        for name in self.names:
            ex, ey = electrodes[name]
            rx, ry = cx - ex, cy - ey
            r3 = (rx * rx + ry * ry) ** 1.5
            g = np.where(fdir == 0, -rx, -ry) / r3     # d(1/r)/dx или d/dy
            # вклад грани: -D_f * (u_j - u_i)/dx * g * dx^2
            w = -fd * g * dx * wf
            c = np.zeros(n)
            np.add.at(c, fj, w)
            np.add.at(c, fi, -w)
            self.c.append(c)
        self.C = np.array(self.c)
        self.tissue = tissue

    def measure(self):
        vals = self.C @ self.tissue.u
        return dict(zip(self.names, vals))


def einthoven(phi):
    """Стандартные отведения по Эйнтховену из потенциалов RA, LA, LL."""
    return {
        "I": phi["LA"] - phi["RA"],
        "II": phi["LL"] - phi["RA"],
        "III": phi["LL"] - phi["LA"],
    }
