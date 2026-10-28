"""Общие утилиты: папка результатов, сохранение рисунков и метрик."""

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 10, "figure.dpi": 110})

SEED = 42


def save_fig(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def save_json(name, data):
    def conv(o):
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=conv)


def train_test_split_idx(n, test_size=0.3, seed=SEED, y=None):
    """Случайное (при заданном y — стратифицированное) разбиение индексов."""
    rng = np.random.default_rng(seed)
    if y is None:
        idx = rng.permutation(n)
        n_test = int(round(n * test_size))
        return idx[n_test:], idx[:n_test]
    tr, te = [], []
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        n_test = int(round(len(idx) * test_size))
        te.extend(idx[:n_test])
        tr.extend(idx[n_test:])
    return rng.permutation(tr), rng.permutation(te)


class Standardizer:
    """z-нормировка признаков по статистикам обучающей выборки."""

    def fit(self, X):
        self.mu = X.mean(axis=0)
        self.sd = X.std(axis=0)
        self.sd[self.sd == 0] = 1.0
        return self

    def transform(self, X):
        return (X - self.mu) / self.sd

    def fit_transform(self, X):
        return self.fit(X).transform(X)


def accuracy(y, p):
    return float(np.mean(y == p))
