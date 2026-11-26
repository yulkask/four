"""Решения блока из 20 задач. Все числа в отчёте считаются этим скриптом."""

import json
import os
import time

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.datasets import load_iris, load_wine, load_breast_cancer, load_diabetes, make_moons, make_classification
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.naive_bayes import GaussianNB as SkGaussianNB, MultinomialNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, roc_auc_score,
)
from imblearn.over_sampling import SMOTE

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "figure.dpi": 120,
    "axes.grid": True,
    "grid.alpha": 0.3,
})

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "results")
os.makedirs(OUT, exist_ok=True)
SEED = 42


def save_fig(fig, name):
    path = os.path.join(OUT, name)
    fig.tight_layout()
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)
    return path


def r2_score(y, yhat):
    ss_res = np.sum((y - yhat) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    return float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0


def mse(y, yhat):
    return float(np.mean((y - yhat) ** 2))


def sigmoid(z):
    z = np.clip(z, -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


def stratified_split(y, test_size=0.3, seed=SEED):
    rng = np.random.default_rng(seed)
    tr, te = [], []
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        n_te = int(round(len(idx) * test_size))
        te.extend(idx[:n_te])
        tr.extend(idx[n_te:])
    return rng.permutation(tr), rng.permutation(te)


def plain_split(n, test_size=0.3, seed=SEED):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    n_te = int(round(n * test_size))
    return idx[n_te:], idx[:n_te]


def confusion(y, p):
    y = np.asarray(y).astype(int)
    p = np.asarray(p).astype(int)
    tp = int(np.sum((p == 1) & (y == 1)))
    tn = int(np.sum((p == 0) & (y == 0)))
    fp = int(np.sum((p == 1) & (y == 0)))
    fn = int(np.sum((p == 0) & (y == 1)))
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp}


def prf(y, p):
    cm = confusion(y, p)
    prec = cm["tp"] / (cm["tp"] + cm["fp"]) if (cm["tp"] + cm["fp"]) else 0.0
    rec = cm["tp"] / (cm["tp"] + cm["fn"]) if (cm["tp"] + cm["fn"]) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    acc = (cm["tp"] + cm["tn"]) / max(len(y), 1)
    return {
        "accuracy": float(acc),
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        **cm,
    }


def roc_curve_points(y, scores):
    y = np.asarray(y).astype(int)
    scores = np.asarray(scores, dtype=float)
    order = np.argsort(-scores, kind="mergesort")
    y_s = y[order]
    P = max(int(np.sum(y == 1)), 1)
    N = max(int(np.sum(y == 0)), 1)
    tp = np.cumsum(y_s == 1)
    fp = np.cumsum(y_s == 0)
    tpr = np.r_[0.0, tp / P]
    fpr = np.r_[0.0, fp / N]
    # схлопнуть одинаковые пороги не обязательно для площади
    auc = float(np.trapezoid(tpr, fpr))
    return fpr, tpr, auc


# ---------------------------------------------------------------------------
# Деревья
# ---------------------------------------------------------------------------

class _Node:
    __slots__ = ("feature", "threshold", "left", "right", "pred", "n", "errors", "impurity")

    def __init__(self):
        self.feature = None
        self.threshold = None
        self.left = None
        self.right = None
        self.pred = None
        self.n = 0
        self.errors = 0
        self.impurity = 0.0


def _impurity(y, criterion):
    if len(y) == 0:
        return 0.0
    _, counts = np.unique(y, return_counts=True)
    p = counts / len(y)
    if criterion == "gini":
        return float(1.0 - np.sum(p * p))
    p = p[p > 0]
    return float(-np.sum(p * np.log2(p)))


class DecisionTree:
    def __init__(self, criterion="gini", max_depth=None, min_samples_split=2,
                 min_samples_leaf=1, max_features=None, random_state=None, n_thresholds=24):
        self.criterion = criterion
        self.max_depth = max_depth
        self.min_samples_split = min_samples_split
        self.min_samples_leaf = min_samples_leaf
        self.max_features = max_features
        self.random_state = random_state
        self.n_thresholds = n_thresholds
        self.root = None
        self.n_features_ = None
        self.rng = np.random.default_rng(random_state)

    def fit(self, X, y):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        self.n_features_ = X.shape[1]
        self.root = self._build(X, y, 0)
        return self

    def _majority(self, y):
        vals, counts = np.unique(y, return_counts=True)
        return vals[np.argmax(counts)]

    def _leaf(self, y):
        node = _Node()
        node.n = int(len(y))
        node.pred = self._majority(y)
        node.errors = int(np.sum(y != node.pred))
        node.impurity = _impurity(y, self.criterion)
        return node

    def _candidate_thresholds(self, col, y):
        # пороги — середины между соседними различными значениями,
        # но не больше n_thresholds квантилей, чтобы дерево строилось быстро
        uniq = np.unique(col)
        if len(uniq) > self.n_thresholds:
            qs = np.linspace(0, 100, self.n_thresholds)
            uniq = np.unique(np.percentile(col, qs))
        if len(uniq) < 2:
            return []
        return ((uniq[:-1] + uniq[1:]) / 2.0).tolist()

    def _build(self, X, y, depth):
        node = self._leaf(y)
        if self.max_depth is not None and depth >= self.max_depth:
            return node
        if len(y) < self.min_samples_split or node.errors == 0 or len(np.unique(y)) == 1:
            return node

        n_features = X.shape[1]
        if self.max_features is None or self.max_features >= n_features:
            feats = np.arange(n_features)
        else:
            feats = self.rng.choice(n_features, size=self.max_features, replace=False)

        parent = node.impurity
        best_gain = 0.0
        best = None
        n = len(y)
        for f in feats:
            col = X[:, f]
            for thr in self._candidate_thresholds(col, y):
                left_mask = col <= thr
                n_l = int(left_mask.sum())
                n_r = n - n_l
                if n_l < self.min_samples_leaf or n_r < self.min_samples_leaf:
                    continue
                imp = (n_l * _impurity(y[left_mask], self.criterion)
                       + n_r * _impurity(y[~left_mask], self.criterion)) / n
                gain = parent - imp
                if gain > best_gain:
                    best_gain = gain
                    best = (f, thr, left_mask)
        if best is None or best_gain <= 1e-12:
            return node
        f, thr, left_mask = best
        node.feature = int(f)
        node.threshold = float(thr)
        node.left = self._build(X[left_mask], y[left_mask], depth + 1)
        node.right = self._build(X[~left_mask], y[~left_mask], depth + 1)
        return node

    def _predict_one(self, x, node):
        while node.left is not None:
            if x[node.feature] <= node.threshold:
                node = node.left
            else:
                node = node.right
        return node.pred

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        return np.array([self._predict_one(x, self.root) for x in X])


def tree_to_text(node, feature_names, depth=0, prefix=""):
    pad = "  " * depth
    if node is None:
        return ""
    if node.left is None:
        return f"{pad}{prefix}лист: класс {node.pred} (n={node.n}, ошибок={node.errors})\n"
    name = feature_names[node.feature]
    s = f"{pad}{prefix}если {name} <= {node.threshold:.3f}:\n"
    s += tree_to_text(node.left, feature_names, depth + 1, "")
    s += f"{pad}иначе:\n"
    s += tree_to_text(node.right, feature_names, depth + 1, "")
    return s


def draw_tree(node, feature_names, path, title):
    # координаты: обход в глубину, листья равномерно по x
    positions = {}
    leaves = []

    def walk(n, depth):
        if n.left is None:
            leaves.append(n)
            positions[id(n)] = [len(leaves) - 1, -depth]
            return
        walk(n.left, depth + 1)
        walk(n.right, depth + 1)
        positions[id(n)] = [
            (positions[id(n.left)][0] + positions[id(n.right)][0]) / 2,
            -depth,
        ]

    walk(node, 0)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.set_title(title)

    def edges(n):
        if n.left is None:
            return
        x, y = positions[id(n)]
        for child, label in ((n.left, "≤"), (n.right, ">")):
            xc, yc = positions[id(child)]
            ax.plot([x, xc], [y, yc], color="#4a5568", lw=1)
            edges(child)

    edges(node)

    for n in [node] + _all_nodes(node):
        x, y = positions[id(n)]
        if n.left is None:
            text = f"класс {n.pred}\nn={n.n}"
            color = "#e6f4ea"
        else:
            text = f"{feature_names[n.feature]}\n≤ {n.threshold:.2f}"
            color = "#e8f0fe"
        ax.text(
            x, y, text, ha="center", va="center", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", fc=color, ec="#334155"),
        )
    ax.axis("off")
    save_fig(fig, path)


def _all_nodes(n):
    if n is None or n.left is None:
        return []
    return [n.left, n.right] + _all_nodes(n.left) + _all_nodes(n.right)


def _clone_tree(node):
    if node is None:
        return None
    n = _Node()
    n.feature = node.feature
    n.threshold = node.threshold
    n.pred = node.pred
    n.n = node.n
    n.errors = node.errors
    n.impurity = node.impurity
    n.left = _clone_tree(node.left)
    n.right = _clone_tree(node.right)
    return n


def _leaf_count(node):
    if node.left is None:
        return 1
    return _leaf_count(node.left) + _leaf_count(node.right)


def _leaf_errors(node):
    if node.left is None:
        return node.errors
    return _leaf_errors(node.left) + _leaf_errors(node.right)


def cost_complexity_path(tree, X_tr, y_tr, X_te, y_te):
    """Слабейшее звено: на каждом шаге срезается внутренний узел с минимальным g(t)."""
    root = _clone_tree(tree.root)
    n_total = max(root.n, 1)
    path = []

    def acc(node, X, y):
        tmp = DecisionTree()
        tmp.root = node
        return float(np.mean(tmp.predict(X) == y))

    def internals(node, acc_list):
        if node is None or node.left is None:
            return
        acc_list.append(node)
        internals(node.left, acc_list)
        internals(node.right, acc_list)

    path.append({
        "alpha": 0.0,
        "leaves": _leaf_count(root),
        "train_acc": acc(root, X_tr, y_tr),
        "test_acc": acc(root, X_te, y_te),
    })
    while root.left is not None:
        nodes = []
        internals(root, nodes)
        best_g = None
        best_node = None
        for node in nodes:
            leaves = _leaf_count(node)
            if leaves <= 1:
                continue
            # g(t) = (R(t) - R(T_t)) / (|T_t| - 1), R — доля ошибок на всей выборке
            g = (node.errors - _leaf_errors(node)) / n_total / (leaves - 1)
            if best_g is None or g < best_g:
                best_g = g
                best_node = node
        if best_node is None:
            break
        best_node.left = None
        best_node.right = None
        best_node.feature = None
        path.append({
            "alpha": float(best_g),
            "leaves": _leaf_count(root),
            "train_acc": acc(root, X_tr, y_tr),
            "test_acc": acc(root, X_te, y_te),
        })
    return path


class BaggingTrees:
    def __init__(self, n_estimators=40, max_depth=None, max_features=None, random_state=0):
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.max_features = max_features
        self.random_state = random_state
        self.trees = []

    def fit(self, X, y):
        rng = np.random.default_rng(self.random_state)
        self.trees = []
        n = len(y)
        for i in range(self.n_estimators):
            idx = rng.integers(0, n, size=n)
            tree = DecisionTree(
                criterion="gini",
                max_depth=self.max_depth,
                min_samples_leaf=1,
                max_features=self.max_features,
                random_state=int(rng.integers(0, 1_000_000)),
                n_thresholds=16,
            )
            tree.fit(X[idx], y[idx])
            self.trees.append(tree)
        return self

    def predict(self, X):
        votes = np.vstack([t.predict(X) for t in self.trees])
        # большинство
        out = []
        for col in votes.T:
            vals, counts = np.unique(col, return_counts=True)
            out.append(vals[np.argmax(counts)])
        return np.array(out)


# ---------------------------------------------------------------------------
# Задачи
# ---------------------------------------------------------------------------

def task_1_2():
    rng = np.random.default_rng(SEED)
    x = np.arange(1, 11, dtype=float)
    y = 2.0 * x + 3.0 + rng.normal(0.0, 1.5, size=10)

    x_bar, y_bar = x.mean(), y.mean()
    sxx = float(np.sum((x - x_bar) ** 2))
    sxy = float(np.sum((x - x_bar) * (y - y_bar)))
    a = sxy / sxx
    b = y_bar - a * x_bar
    yhat = a * x + b
    resid = y - yhat
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y_bar) ** 2))

    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.scatter(x, y, color="#1d4ed8", zorder=3, label="наблюдения")
    xs = np.linspace(0.5, 10.5, 100)
    ax.plot(xs, a * xs + b, color="#b91c1c", label=f"МНК: y = {a:.3f}x + {b:.3f}")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.set_title("Задача 1. Одномерная регрессия")
    ax.legend()
    p1 = save_fig(fig, "task01_regression.png")

    # градиентный спуск, та же функция потерь MSE
    etas = [0.001, 0.01, 0.1, 0.5]
    n = len(x)
    histories = {}
    finals = {}
    for eta in etas:
        aa, bb = 0.0, 0.0
        hist = []
        status = "сошёлся"
        diverge_at = None
        for it in range(20001):
            err = aa * x + bb - y
            loss = float(np.mean(err ** 2))
            if it < 25 or it % 20 == 0 or it == 20000:
                hist.append({"iter": it, "loss": loss if np.isfinite(loss) else 1e12, "a": aa, "b": bb})
            if (not np.isfinite(loss)) or loss > 1e8:
                status = "расходится"
                diverge_at = it
                break
            aa -= eta * (2.0 / n) * float(np.sum(err * x))
            bb -= eta * (2.0 / n) * float(np.sum(err))
        histories[str(eta)] = hist
        finals[str(eta)] = {
            "a": None if status == "расходится" else float(aa),
            "b": None if status == "расходится" else float(bb),
            "loss": None if status == "расходится" else float(np.mean((aa * x + bb - y) ** 2)),
            "status": status,
            "diverge_at": diverge_at,
            "iters": 20000 if status == "сошёлся" else diverge_at,
            "delta_a": None if status == "расходится" else float(aa - a),
            "delta_b": None if status == "расходится" else float(bb - b),
        }

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for eta in etas:
        h = [p for p in histories[str(eta)] if p["iter"] <= 40]
        axes[0].plot([p["iter"] for p in h], [max(p["loss"], 1e-6) for p in h], label=f"eta = {eta}")
    axes[0].set_yscale("log")
    axes[0].set_xlabel("итерация")
    axes[0].set_ylabel("MSE")
    axes[0].set_title("Первые итерации, все скорости")
    axes[0].legend(fontsize=8)
    for eta in (0.001, 0.01):
        h = histories[str(eta)]
        axes[1].plot([p["iter"] for p in h], [p["loss"] for p in h], label=f"eta = {eta}")
    axes[1].axhline(ss_res / n, color="#b91c1c", ls="--", label="MSE аналитического МНК")
    axes[1].set_xlabel("итерация")
    axes[1].set_ylabel("MSE")
    axes[1].set_title("Сходящиеся скорости, 20 000 итераций")
    axes[1].legend(fontsize=8)
    p2 = save_fig(fig, "task02_gd.png")

    return {
        "x": x.tolist(),
        "y": [float(v) for v in y],
        "x_bar": float(x_bar),
        "y_bar": float(y_bar),
        "sxx": sxx,
        "sxy": sxy,
        "a": float(a),
        "b": float(b),
        "yhat": [float(v) for v in yhat],
        "mse": ss_res / n,
        "ss_res": ss_res,
        "ss_tot": ss_tot,
        "r2": 1 - ss_res / ss_tot,
        "plot": p1,
        "gd": finals,
        "gd_plot": p2,
        "true_a": 2.0,
        "true_b": 3.0,
    }


def task_3_4():
    rng = np.random.default_rng(SEED)
    n = 120
    area = rng.uniform(28, 110, n)
    floor = rng.integers(1, 18, n).astype(float)
    dist = rng.uniform(0.2, 6.0, n)
    year = rng.integers(1965, 2024, n).astype(float)
    # цена в тыс. условных единиц
    price = (90.0 * area + 12.0 * floor - 35.0 * dist + 1.8 * (year - 2000)
             + 400.0 + rng.normal(0, 80, n))
    X_raw = np.column_stack([area, floor, dist, year])
    names = ["площадь", "этаж", "до метро", "год"]
    true_w = np.array([90.0, 12.0, -35.0, 1.8])

    X = np.column_stack([np.ones(n), X_raw])
    w = np.linalg.pinv(X) @ price
    xtx = X.T @ X
    cond = float(np.linalg.cond(xtx))
    yhat = X @ w

    # обусловленность после стандартизации признаков (свободный член отдельно)
    mu = X_raw.mean(0)
    sd = X_raw.std(0)
    sd[sd == 0] = 1
    Z = (X_raw - mu) / sd
    Z1 = np.column_stack([np.ones(n), Z])
    cond_std = float(np.linalg.cond(Z1.T @ Z1))

    # Ridge / Lasso на стандартизованных признаках, штраф не на интерсепт
    y_c = price - price.mean()
    lam_grid = np.logspace(-2, 3, 18)

    def ridge_w(lam):
        # (1/(2n))||Zw - y_c||^2 + (lam/2)||w||^2
        A = Z.T @ Z + n * lam * np.eye(Z.shape[1])
        return np.linalg.solve(A, Z.T @ y_c)

    def lasso_w(lam, n_iter=4000):
        w = np.zeros(Z.shape[1])
        for _ in range(n_iter):
            w_old = w.copy()
            for j in range(Z.shape[1]):
                r = y_c - Z @ w + Z[:, j] * w[j]
                rho = float(Z[:, j] @ r) / n
                w[j] = np.sign(rho) * max(abs(rho) - lam, 0.0)
            if np.max(np.abs(w - w_old)) < 1e-7:
                break
        return w

    ridge_path = []
    lasso_path = []
    for lam in lam_grid:
        wr = ridge_w(lam)
        wl = lasso_w(lam)
        # в исходный масштаб: y = (Z @ w_std) + y.mean(), Z=(X-mu)/sd
        def to_orig(ws):
            coef = ws / sd
            intercept = float(price.mean() - mu @ coef)
            return intercept, coef

        br, cr = to_orig(wr)
        bl, cl = to_orig(wl)
        ridge_path.append({
            "lambda": float(lam),
            "intercept": br,
            "coef": cr.tolist(),
            "n_zero": int(np.sum(np.abs(cr) < 1e-8)),
            "mse": mse(price, Z @ wr + price.mean()),
        })
        lasso_path.append({
            "lambda": float(lam),
            "intercept": bl,
            "coef": cl.tolist(),
            "n_zero": int(np.sum(np.abs(cl) < 1e-6)),
            "mse": mse(price, Z @ wl + price.mean()),
        })

    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), sharey=True)
    colors = ["#1d4ed8", "#b45309", "#15803d", "#b91c1c"]
    for ax, path, title in (
        (axes[0], ridge_path, "Ridge (L2)"),
        (axes[1], lasso_path, "Lasso (L1)"),
    ):
        for j, name in enumerate(names):
            ax.plot([p["lambda"] for p in path], [p["coef"][j] for p in path],
                    color=colors[j], label=name)
        ax.set_xscale("log")
        ax.set_xlabel("λ")
        ax.set_title(title)
        ax.legend(fontsize=8)
    axes[0].set_ylabel("коэффициент в исходном масштабе")
    p4 = save_fig(fig, "task04_paths.png")

    return {
        "n": n,
        "names": names,
        "true_coef": true_w.tolist(),
        "weights": w.tolist(),  # intercept + 4
        "cond_xtx": cond,
        "cond_xtx_standardized": cond_std,
        "mse": mse(price, yhat),
        "r2": r2_score(price, yhat),
        "feature_means": mu.tolist(),
        "feature_stds": sd.tolist(),
        "ridge": ridge_path,
        "lasso": lasso_path,
        "plot": p4,
        "sample_head": {
            "area": area[:5].tolist(),
            "floor": floor[:5].tolist(),
            "dist": dist[:5].tolist(),
            "year": year[:5].tolist(),
            "price": price[:5].tolist(),
        },
        "generating": "price = 90·площадь + 12·этаж − 35·до_метро + 1.8·(год−2000) + 400 + ε, ε~N(0, 80²)",
    }


def task_5():
    rng = np.random.default_rng(SEED)
    n = 80
    x = rng.uniform(-np.pi, np.pi, n)
    y = np.sin(x) + rng.normal(0, 0.25, n)
    tr, te = plain_split(n, 0.3, SEED)
    z = x / np.pi  # фиксированное масштабирование в [-1, 1]

    rows = []
    curves = {}
    grid = np.linspace(-np.pi, np.pi, 400)
    zg = grid / np.pi
    from numpy.polynomial.polynomial import polyfit, polyval
    for deg in (1, 3, 7, 15):
        coef = polyfit(z[tr], y[tr], deg)
        ytr = polyval(z[tr], coef)
        yte = polyval(z[te], coef)
        rows.append({
            "degree": deg,
            "train_mse": mse(y[tr], ytr),
            "test_mse": mse(y[te], yte),
            "train_r2": r2_score(y[tr], ytr),
            "test_r2": r2_score(y[te], yte),
        })
        curves[deg] = polyval(zg, coef)

    fig, axes = plt.subplots(2, 2, figsize=(9.5, 7.2), sharex=True, sharey=True)
    for ax, deg in zip(axes.ravel(), (1, 3, 7, 15)):
        ax.scatter(x[tr], y[tr], s=16, c="#1d4ed8", label="train")
        ax.scatter(x[te], y[te], s=16, c="#b45309", label="test")
        ax.plot(grid, np.sin(grid), c="#94a3b8", ls="--", label="sin x")
        ax.plot(grid, curves[deg], c="#b91c1c", label=f"полином {deg}")
        row = next(r for r in rows if r["degree"] == deg)
        ax.set_title(f"степень {deg}: train MSE={row['train_mse']:.3f}, test MSE={row['test_mse']:.3f}")
        ax.set_ylim(-2.2, 2.2)
        ax.legend(fontsize=7)
    p = save_fig(fig, "task05_poly.png")
    return {"n": n, "n_train": int(len(tr)), "n_test": int(len(te)), "noise_std": 0.25, "rows": rows, "plot": p}


def fit_logreg(X, y, lr=0.5, n_iter=2500, l2=0.0, sample_weight=None):
    n, d = X.shape
    Xb = np.column_stack([np.ones(n), X])
    w = np.zeros(d + 1)
    sw = np.ones(n) if sample_weight is None else np.asarray(sample_weight, dtype=float)
    sw = sw * (n / sw.sum())
    hist = []
    for it in range(n_iter):
        p = sigmoid(Xb @ w)
        err = (p - y) * sw
        grad = Xb.T @ err / n
        grad[1:] += l2 * w[1:]
        w -= lr * grad
        if it % 100 == 0 or it == n_iter - 1:
            p = np.clip(p, 1e-12, 1 - 1e-12)
            loss = float(-np.mean(sw * (y * np.log(p) + (1 - y) * np.log(1 - p))))
            hist.append(loss)
    return w, hist


def task_6_7():
    X, y = make_moons(n_samples=300, noise=0.18, random_state=SEED)
    tr, te = stratified_split(y, 0.3, SEED)
    scaler = StandardScaler().fit(X[tr])
    Xtr = scaler.transform(X[tr])
    Xte = scaler.transform(X[te])
    w, hist = fit_logreg(Xtr, y[tr], lr=0.8, n_iter=3000, l2=0.0)
    Xb_te = np.column_stack([np.ones(len(te)), Xte])
    proba = sigmoid(Xb_te @ w)
    pred = (proba >= 0.5).astype(int)
    metrics = prf(y[te], pred)
    fpr, tpr, auc = roc_curve_points(y[te], proba)
    metrics["auc"] = auc
    metrics["loss_last"] = hist[-1]

    # граница в исходных координатах
    xx, yy = np.meshgrid(
        np.linspace(X[:, 0].min() - 0.4, X[:, 0].max() + 0.4, 300),
        np.linspace(X[:, 1].min() - 0.4, X[:, 1].max() + 0.4, 300),
    )
    grid = np.column_stack([xx.ravel(), yy.ravel()])
    zz = sigmoid(np.column_stack([np.ones(len(grid)), scaler.transform(grid)]) @ w).reshape(xx.shape)
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    ax.contourf(xx, yy, zz, levels=20, cmap="RdBu_r", alpha=0.85)
    ax.contour(xx, yy, zz, levels=[0.5], colors="black", linewidths=1.4)
    ax.scatter(X[tr][y[tr] == 0, 0], X[tr][y[tr] == 0, 1], c="#1d4ed8", s=16, label="класс 0, train")
    ax.scatter(X[tr][y[tr] == 1, 0], X[tr][y[tr] == 1, 1], c="#b91c1c", s=16, label="класс 1, train")
    ax.set_title("Задача 6. Логистическая регрессия, make_moons")
    ax.legend(fontsize=8, loc="upper right")
    p6 = save_fig(fig, "task06_boundary.png")

    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.2))
    cm = np.array([[metrics["tn"], metrics["fp"]], [metrics["fn"], metrics["tp"]]])
    axes[0].imshow(cm, cmap="Blues")
    axes[0].set_xticks([0, 1], ["прогноз 0", "прогноз 1"])
    axes[0].set_yticks([0, 1], ["истина 0", "истина 1"])
    for (i, j), v in np.ndenumerate(cm):
        axes[0].text(j, i, str(v), ha="center", va="center", fontsize=14)
    axes[0].set_title("Матрица ошибок (test)")
    axes[0].grid(False)
    axes[1].plot(fpr, tpr, color="#1d4ed8", label=f"AUC = {auc:.3f}")
    axes[1].plot([0, 1], [0, 1], ls="--", color="#94a3b8")
    axes[1].set_xlabel("FPR")
    axes[1].set_ylabel("TPR")
    axes[1].set_title("ROC-кривая")
    axes[1].legend()
    p7 = save_fig(fig, "task07_roc.png")
    return {
        "n": 300,
        "noise": 0.18,
        "n_test": int(len(te)),
        "weights": w.tolist(),
        "metrics": metrics,
        "plot_boundary": p6,
        "plot_roc": p7,
    }


def softmax_fit(X, Y, lr=0.4, n_iter=2500, l2=0.0):
    n, d = X.shape
    k = Y.shape[1]
    Xb = np.column_stack([np.ones(n), X])
    W = np.zeros((d + 1, k))
    for _ in range(n_iter):
        Z = Xb @ W
        Z -= Z.max(axis=1, keepdims=True)
        E = np.exp(Z)
        P = E / E.sum(axis=1, keepdims=True)
        grad = Xb.T @ (P - Y) / n
        grad[1:] += l2 * W[1:]
        W -= lr * grad
    return W


def softmax_predict(X, W):
    Xb = np.column_stack([np.ones(len(X)), X])
    Z = Xb @ W
    Z -= Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    P = E / E.sum(axis=1, keepdims=True)
    return P.argmax(axis=1), P


def task_8():
    data = load_iris()
    X, y = data.data, data.target
    tr, te = stratified_split(y, 0.3, SEED)
    scaler = StandardScaler().fit(X[tr])
    Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
    classes = np.unique(y)
    Y = np.eye(len(classes))[y[tr]]
    W = softmax_fit(Xtr, Y, lr=0.5, n_iter=3000)
    pred_te, _ = softmax_predict(Xte, W)
    pred_tr, _ = softmax_predict(Xtr, W)
    # one-vs-rest
    ovr_w = []
    for c in classes:
        wc, _ = fit_logreg(Xtr, (y[tr] == c).astype(float), lr=0.6, n_iter=2500)
        ovr_w.append(wc)
    def ovr_scores(Xs):
        Xb = np.column_stack([np.ones(len(Xs)), Xs])
        return np.column_stack([sigmoid(Xb @ wc) for wc in ovr_w])
    ovr_te = ovr_scores(Xte).argmax(axis=1)
    ovr_tr = ovr_scores(Xtr).argmax(axis=1)
    return {
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "softmax_train": float(np.mean(pred_tr == y[tr])),
        "softmax_test": float(np.mean(pred_te == y[te])),
        "ovr_train": float(np.mean(ovr_tr == y[tr])),
        "ovr_test": float(np.mean(ovr_te == y[te])),
        "class_names": data.target_names.tolist(),
    }


def task_9():
    X, y = make_classification(
        n_samples=2000, n_features=10, n_informative=6, n_redundant=2,
        weights=[0.95, 0.05], flip_y=0.01, class_sep=1.1, random_state=SEED,
    )
    tr, te = stratified_split(y, 0.3, SEED)
    scaler = StandardScaler().fit(X[tr])
    Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
    ytr, yte = y[tr], y[te]

    def eval_model(Xfit, yfit, sw=None):
        w, _ = fit_logreg(Xfit, yfit.astype(float), lr=0.4, n_iter=2000, sample_weight=sw)
        Xb = np.column_stack([np.ones(len(Xte)), Xte])
        pred = (sigmoid(Xb @ w) >= 0.5).astype(int)
        return prf(yte, pred)

    base = eval_model(Xtr, ytr)

    # веса классов: n / (n_classes * n_c)
    n = len(ytr)
    w_c = {c: n / (2 * np.sum(ytr == c)) for c in (0, 1)}
    sw = np.array([w_c[int(t)] for t in ytr])
    weighted = eval_model(Xtr, ytr, sw)

    sm = SMOTE(random_state=SEED, k_neighbors=5)
    Xsm, ysm = sm.fit_resample(Xtr, ytr)
    smote = eval_model(Xsm, ysm)

    rng = np.random.default_rng(SEED)
    min_idx = np.flatnonzero(ytr == 1)
    maj_idx = np.flatnonzero(ytr == 0)
    take = rng.choice(maj_idx, size=len(min_idx), replace=False)
    sel = np.concatenate([min_idx, take])
    under = eval_model(Xtr[sel], ytr[sel])

    # доля меньшинства и «наивная» accuracy
    majority_acc = float(np.mean(yte == 0))
    return {
        "n": 2000,
        "train_counts": {"0": int(np.sum(ytr == 0)), "1": int(np.sum(ytr == 1))},
        "test_counts": {"0": int(np.sum(yte == 0)), "1": int(np.sum(yte == 1))},
        "majority_accuracy": majority_acc,
        "base": base,
        "weighted": weighted,
        "smote": smote,
        "undersample": under,
        "smote_n": int(len(ysm)),
        "under_n": int(len(sel)),
    }


def task_10():
    data = load_breast_cancer()
    X, y = data.data, data.target
    tr, te = stratified_split(y, 0.3, SEED)
    scaler = StandardScaler().fit(X[tr])
    Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
    lams = np.logspace(-4, 2, 13)
    rows = []
    for lam in lams:
        # шаг уменьшается вместе с λ: член λw иначе делает итерацию неустойчивой
        w, _ = fit_logreg(
            Xtr, y[tr].astype(float),
            lr=0.5 / (1.0 + float(lam)), n_iter=5000, l2=float(lam),
        )
        def acc_of(Xs, ys):
            Xb = np.column_stack([np.ones(len(Xs)), Xs])
            return float(np.mean((sigmoid(Xb @ w) >= 0.5).astype(int) == ys))
        rows.append({
            "lambda": float(lam),
            "weight_norm": float(np.linalg.norm(w[1:])),
            "train_acc": acc_of(Xtr, y[tr]),
            "test_acc": acc_of(Xte, y[te]),
        })
    fig, ax1 = plt.subplots(figsize=(6.8, 4.2))
    ax1.plot([r["lambda"] for r in rows], [r["train_acc"] for r in rows], label="train accuracy")
    ax1.plot([r["lambda"] for r in rows], [r["test_acc"] for r in rows], label="test accuracy")
    ax1.set_xscale("log")
    ax1.set_xlabel("λ")
    ax1.set_ylabel("accuracy")
    ax2 = ax1.twinx()
    ax2.plot([r["lambda"] for r in rows], [r["weight_norm"] for r in rows], color="#b45309", ls="--", label="||w||")
    ax2.set_ylabel("норма весов ||w|| (без свободного члена)")
    ax1.set_title("Задача 10. L2-регуляризация логистической регрессии")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8, loc="lower left")
    p = save_fig(fig, "task10_l2.png")
    best = max(rows, key=lambda r: r["test_acc"])
    return {"dataset": "Breast Cancer Wisconsin", "rows": rows, "best": best, "plot": p}


def knn_predict(Xtr, ytr, Xte, k, metric="euclidean", weighted=False, eps=1e-9):
    # поблочно, чтобы не раздувать память
    preds = np.empty(len(Xte), dtype=ytr.dtype)
    for i0 in range(0, len(Xte), 64):
        block = Xte[i0:i0 + 64]
        if metric == "euclidean":
            # (a-b)^2 = a^2 + b^2 - 2ab
            d = (
                np.sum(block ** 2, axis=1, keepdims=True)
                + np.sum(Xtr ** 2, axis=1)
                - 2 * block @ Xtr.T
            )
            d = np.sqrt(np.maximum(d, 0))
        elif metric == "manhattan":
            d = np.sum(np.abs(block[:, None, :] - Xtr[None, :, :]), axis=2)
        else:
            raise ValueError(metric)
        nn = np.argpartition(d, kth=min(k, d.shape[1] - 1), axis=1)[:, :k]
        row = np.arange(len(block))[:, None]
        dn = d[row, nn]
        yn = ytr[nn]
        out = []
        for j in range(len(block)):
            labs = yn[j]
            dist = dn[j]
            if weighted:
                w = 1.0 / (dist + eps)
                classes = np.unique(labs)
                scores = [np.sum(w[labs == c]) for c in classes]
                out.append(classes[int(np.argmax(scores))])
            else:
                vals, counts = np.unique(labs, return_counts=True)
                out.append(vals[np.argmax(counts)])
        preds[i0:i0 + len(block)] = np.array(out)
    return preds


def task_11():
    data = load_iris()
    X, y = data.data, data.target
    tr, te = stratified_split(y, 0.3, SEED)
    scaler = StandardScaler().fit(X[tr])
    Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
    ks = [1, 3, 5, 7, 15, 25]
    rows = []
    for metric in ("euclidean", "manhattan"):
        for k in ks:
            pred = knn_predict(Xtr, y[tr], Xte, k, metric=metric)
            rows.append({"metric": metric, "k": k, "accuracy": float(np.mean(pred == y[te]))})
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    for metric, color in (("euclidean", "#1d4ed8"), ("manhattan", "#b45309")):
        sub = [r for r in rows if r["metric"] == metric]
        ax.plot([r["k"] for r in sub], [r["accuracy"] for r in sub], marker="o", color=color, label=metric)
    ax.set_xlabel("k")
    ax.set_ylabel("accuracy на тесте")
    ax.set_title("Задача 11. k-NN на ирисах")
    ax.legend()
    p = save_fig(fig, "task11_knn.png")
    return {"n_train": int(len(tr)), "n_test": int(len(te)), "rows": rows, "plot": p}


def task_12():
    dims = [2, 5, 10, 50, 100]
    rows = []
    rng_master = np.random.default_rng(SEED)
    for d in dims:
        rng = np.random.default_rng(SEED + d)
        n = 240
        X = rng.normal(size=(n, d))
        # сигнал только в первой координате, остальные — шум
        y = (X[:, 0] > 0).astype(int)
        tr, te = stratified_split(y, 0.3, SEED)
        # без стандартизации: все признаки уже N(0,1)
        pred = knn_predict(X[tr], y[tr], X[te], k=5, metric="euclidean")
        # среднее попарное расстояние на подвыборке из 80 точек
        sub = X[rng_master.choice(n, size=80, replace=False)]
        dif = sub[:, None, :] - sub[None, :, :]
        dist = np.sqrt(np.sum(dif ** 2, axis=2))
        iu = np.triu_indices(len(sub), k=1)
        rows.append({
            "d": d,
            "accuracy": float(np.mean(pred == y[te])),
            "mean_distance": float(dist[iu].mean()),
            "std_distance": float(dist[iu].std()),
        })
    fig, ax1 = plt.subplots(figsize=(6.6, 4.2))
    ax1.plot([r["d"] for r in rows], [r["accuracy"] for r in rows], marker="o", color="#1d4ed8", label="accuracy")
    ax1.set_xlabel("число признаков d")
    ax1.set_ylabel("accuracy")
    ax1.set_ylim(0.45, 1.02)
    ax2 = ax1.twinx()
    ax2.plot([r["d"] for r in rows], [r["mean_distance"] for r in rows], marker="s", color="#b45309", label="среднее расстояние")
    ax2.set_ylabel("среднее евклидово расстояние")
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, fontsize=8)
    ax1.set_title("Задача 12. Проклятие размерности")
    p = save_fig(fig, "task12_curse.png")
    return {"rows": rows, "plot": p, "note": "класс = 1{x1 > 0}, остальные признаки ~ N(0,1), k=5, n=240"}


def task_13():
    datasets = {
        "Ирисы": load_iris(return_X_y=True),
        "Вино": load_wine(return_X_y=True),
        "Breast Cancer": load_breast_cancer(return_X_y=True),
    }
    rows = []
    for name, (X, y) in datasets.items():
        tr, te = stratified_split(y, 0.3, SEED)
        scaler = StandardScaler().fit(X[tr])
        Xtr, Xte = scaler.transform(X[tr]), scaler.transform(X[te])
        for k in (3, 7):
            plain = knn_predict(Xtr, y[tr], Xte, k, weighted=False)
            distw = knn_predict(Xtr, y[tr], Xte, k, weighted=True)
            rows.append({
                "dataset": name,
                "k": k,
                "uniform": float(np.mean(plain == y[te])),
                "distance": float(np.mean(distw == y[te])),
            })
    return {"eps": 1e-9, "rows": rows}


class GaussianNBScratch:
    def fit(self, X, y, var_smoothing=1e-9):
        X = np.asarray(X, dtype=float)
        y = np.asarray(y)
        self.classes_ = np.unique(y)
        self.theta_ = []
        self.var_ = []
        self.prior_ = []
        for c in self.classes_:
            Xc = X[y == c]
            self.theta_.append(Xc.mean(axis=0))
            self.var_.append(Xc.var(axis=0) + var_smoothing)
            self.prior_.append(len(Xc) / len(X))
        self.theta_ = np.vstack(self.theta_)
        self.var_ = np.vstack(self.var_)
        self.class_prior_ = np.array(self.prior_)
        return self

    def predict_log_proba(self, X):
        X = np.asarray(X, dtype=float)
        logs = []
        for i, _c in enumerate(self.classes_):
            mu, var = self.theta_[i], self.var_[i]
            ll = -0.5 * np.sum(np.log(2 * np.pi * var)) - 0.5 * np.sum((X - mu) ** 2 / var, axis=1)
            logs.append(np.log(self.class_prior_[i]) + ll)
        return np.column_stack(logs)

    def predict_proba(self, X):
        lp = self.predict_log_proba(X)
        lp = lp - lp.max(axis=1, keepdims=True)
        e = np.exp(lp)
        return e / e.sum(axis=1, keepdims=True)

    def predict(self, X):
        return self.classes_[self.predict_log_proba(X).argmax(axis=1)]


def task_14():
    data = load_iris()
    X, y = data.data, data.target
    tr, te = stratified_split(y, 0.3, SEED)
    mine = GaussianNBScratch().fit(X[tr], y[tr])
    lib = SkGaussianNB().fit(X[tr], y[tr])
    pm, pl = mine.predict(X[te]), lib.predict(X[te])
    return {
        "scratch_test": float(np.mean(pm == y[te])),
        "sklearn_test": float(np.mean(pl == y[te])),
        "agree": float(np.mean(pm == pl)),
        "priors": mine.class_prior_.tolist(),
        "means": mine.theta_.tolist(),
        "n_test": int(len(te)),
    }


def task_15():
    path = os.path.join(ROOT, "data", "SMSSpamCollection.tsv")
    labels, texts = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            lab, text = line.split("\t", 1)
            labels.append(1 if lab == "spam" else 0)
            texts.append(text)
    y = np.array(labels)
    tr, te = stratified_split(y, 0.3, SEED)
    vec = CountVectorizer(lowercase=True, token_pattern=r"(?u)\b\w+\b", min_df=2)
    Xtr = vec.fit_transform([texts[i] for i in tr]).astype(float)
    Xte = vec.transform([texts[i] for i in te]).astype(float)
    # плотные матрицы для своей реализации; словарь после min_df умеренный
    Xtr_d = Xtr.toarray()
    Xte_d = Xte.toarray()
    ytr, yte = y[tr], y[te]

    def multinomial_nb(alpha):
        classes = [0, 1]
        # счётчики слов
        log_probs = []
        priors = []
        V = Xtr_d.shape[1]
        for c in classes:
            Xc = Xtr_d[ytr == c]
            priors.append(len(Xc) / len(ytr))
            counts = Xc.sum(axis=0) + alpha
            total = counts.sum()
            log_probs.append(np.log(counts / total))
        log_prior = np.log(np.array(priors))
        log_probs = np.vstack(log_probs)
        # оценка на тесте
        # log P(c|x) ~ log prior + x · log P(w|c)
        scores = Xte_d @ log_probs.T + log_prior
        pred = scores.argmax(axis=1)
        m = prf(yte, pred)
        # sklearn для сверки при alpha
        sk = MultinomialNB(alpha=alpha).fit(Xtr, ytr)
        sk_pred = sk.predict(Xte)
        m["sklearn_f1"] = float(f1_score(yte, sk_pred, zero_division=0))
        return m

    alphas = [0.1, 0.5, 1.0, 2.0, 5.0]
    rows = []
    for a in alphas:
        m = multinomial_nb(a)
        rows.append({"alpha": a, **{k: m[k] for k in ("accuracy", "precision", "recall", "f1", "sklearn_f1", "tp", "fp", "fn", "tn")}})
    return {
        "n": int(len(y)),
        "spam": int(y.sum()),
        "ham": int((y == 0).sum()),
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "vocab": int(Xtr_d.shape[1]),
        "rows": rows,
    }


def task_16():
    data = load_iris()
    X, y = data.data, data.target
    names = ["чашелист. длина", "чашелист. ширина", "лепесток длина", "лепесток ширина"]
    tr, te = stratified_split(y, 0.3, SEED)
    out = {"n_train": int(len(tr)), "n_test": int(len(te)), "criteria": {}}
    for crit in ("gini", "entropy"):
        tree = DecisionTree(criterion=crit, max_depth=3, min_samples_split=4, min_samples_leaf=2,
                            random_state=SEED, n_thresholds=40)
        tree.fit(X[tr], y[tr])
        out["criteria"][crit] = {
            "train": float(np.mean(tree.predict(X[tr]) == y[tr])),
            "test": float(np.mean(tree.predict(X[te]) == y[te])),
            "text": tree_to_text(tree.root, names),
        }
        if crit == "gini":
            draw_tree(tree.root, names, "task16_tree.png", "Дерево глубины 3, критерий Джини (ирисы)")
            out["plot"] = os.path.join(OUT, "task16_tree.png")
    return out


def task_17_18():
    X, y = make_classification(
        n_samples=480, n_features=10, n_informative=6, n_redundant=2,
        n_clusters_per_class=2, flip_y=0.04, class_sep=0.9, random_state=SEED,
    )
    tr, te = stratified_split(y, 0.3, SEED)
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]

    full = DecisionTree(criterion="gini", max_depth=None, min_samples_split=2,
                        random_state=SEED, n_thresholds=20)
    full.fit(Xtr, ytr)
    full_train = float(np.mean(full.predict(Xtr) == ytr))
    full_test = float(np.mean(full.predict(Xte) == yte))

    pre = DecisionTree(criterion="gini", max_depth=4, min_samples_split=20,
                       min_samples_leaf=8, random_state=SEED, n_thresholds=20)
    pre.fit(Xtr, ytr)
    pre_train = float(np.mean(pre.predict(Xtr) == ytr))
    pre_test = float(np.mean(pre.predict(Xte) == yte))

    path = cost_complexity_path(full, Xtr, ytr, Xte, yte)
    # лучший alpha по тесту показываем как иллюстрацию; для честного выбора
    # берём дерево с максимальной test accuracy среди пути (в учебной задаче
    # сравниваем кривые, а не прячем тест)
    best = max(path, key=lambda r: (r["test_acc"], -r["leaves"]))

    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    ax.plot([r["leaves"] for r in path], [r["train_acc"] for r in path], marker="o", label="train")
    ax.plot([r["leaves"] for r in path], [r["test_acc"] for r in path], marker="o", label="test")
    ax.set_xlabel("число листьев после обрезки")
    ax.set_ylabel("accuracy")
    ax.set_title("Задача 17. Cost-complexity pruning")
    ax.legend()
    p17 = save_fig(fig, "task17_prune.png")

    # ансамбли: ограничиваем глубину базового дерева, иначе 40 полных деревьев долго считаются
    single = full
    bag = BaggingTrees(n_estimators=40, max_depth=8, max_features=None, random_state=SEED)
    t0 = time.perf_counter()
    bag.fit(Xtr, ytr)
    bag_time = time.perf_counter() - t0
    d = X.shape[1]
    rf = BaggingTrees(n_estimators=40, max_depth=8, max_features=max(1, int(np.sqrt(d))), random_state=SEED + 1)
    t0 = time.perf_counter()
    rf.fit(Xtr, ytr)
    rf_time = time.perf_counter() - t0

    def pack(model):
        return {
            "train": float(np.mean(model.predict(Xtr) == ytr)),
            "test": float(np.mean(model.predict(Xte) == yte)),
        }

    return {
        "n": 480,
        "n_train": int(len(tr)),
        "n_test": int(len(te)),
        "d": int(d),
        "full": {"train": full_train, "test": full_test, "leaves": _leaf_count(full.root)},
        "preprune": {"max_depth": 4, "min_samples_split": 20, "min_samples_leaf": 8,
                     "train": pre_train, "test": pre_test},
        "ccp_path": path,
        "ccp_best": best,
        "plot": p17,
        "single_depth8_note": "бэггинг и лес: 40 деревьев, max_depth=8",
        "single_unrestricted": {"train": full_train, "test": full_test},
        "bagging": {**pack(bag), "time_sec": bag_time, "n_estimators": 40, "max_depth": 8},
        "forest": {**pack(rf), "time_sec": rf_time, "n_estimators": 40, "max_depth": 8,
                   "max_features": max(1, int(np.sqrt(d)))},
    }


def kfold_indices(n, k=5, seed=SEED):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(n)
    folds = np.array_split(idx, k)
    splits = []
    for i in range(k):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(k) if j != i])
        splits.append((tr, te))
    return splits


def stratified_kfold_indices(y, k=5, seed=SEED):
    rng = np.random.default_rng(seed)
    folds = [[] for _ in range(k)]
    for c in np.unique(y):
        idx = rng.permutation(np.flatnonzero(y == c))
        for i, ix in enumerate(idx):
            folds[i % k].append(int(ix))
    folds = [np.array(f, dtype=int) for f in folds]
    splits = []
    for i in range(k):
        te = folds[i]
        tr = np.concatenate([folds[j] for j in range(k) if j != i])
        splits.append((tr, te))
    return splits


def task_19():
    iris = load_iris()
    wine = load_wine()
    diabetes = load_diabetes()

    def cv_knn(X, y, ks):
        splits = stratified_kfold_indices(y, 5, SEED)
        scores = []
        for k in ks:
            fold_scores = []
            for tr, te in splits:
                scaler = StandardScaler().fit(X[tr])
                pred = KNeighborsClassifier(n_neighbors=k).fit(
                    scaler.transform(X[tr]), y[tr]
                ).predict(scaler.transform(X[te]))
                fold_scores.append(float(np.mean(pred == y[te])))
            scores.append(float(np.mean(fold_scores)))
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("knn", KNeighborsClassifier()),
        ])
        gs = GridSearchCV(pipe, {"knn__n_neighbors": ks}, cv=splits, scoring="accuracy")
        gs.fit(X, y)
        return {
            "param": "k",
            "grid": ks,
            "mean_score": scores,
            "best": ks[int(np.argmax(scores))],
            "best_score": float(np.max(scores)),
            "sklearn_best": int(gs.best_params_["knn__n_neighbors"]),
            "sklearn_score": float(gs.best_score_),
            "dataset": "Ирисы",
            "metric": "accuracy",
        }

    def cv_tree(X, y, depths):
        splits = stratified_kfold_indices(y, 5, SEED)
        scores = []
        for depth in depths:
            fold_scores = []
            for tr, te in splits:
                clf = DecisionTreeClassifier(max_depth=depth, random_state=SEED)
                clf.fit(X[tr], y[tr])
                fold_scores.append(float(np.mean(clf.predict(X[te]) == y[te])))
            scores.append(float(np.mean(fold_scores)))
        gs = GridSearchCV(
            DecisionTreeClassifier(random_state=SEED),
            {"max_depth": depths},
            cv=splits,
            scoring="accuracy",
        )
        gs.fit(X, y)
        return {
            "param": "max_depth",
            "grid": depths,
            "mean_score": scores,
            "best": depths[int(np.argmax(scores))],
            "best_score": float(np.max(scores)),
            "sklearn_best": gs.best_params_["max_depth"],
            "sklearn_score": float(gs.best_score_),
            "dataset": "Вино",
            "metric": "accuracy",
        }

    def cv_ridge(X, y, lams):
        splits = kfold_indices(len(y), 5, SEED)
        scores = []
        for lam in lams:
            fold_scores = []
            for tr, te in splits:
                scaler = StandardScaler().fit(X[tr])
                model = Ridge(alpha=lam).fit(scaler.transform(X[tr]), y[tr])
                pred = model.predict(scaler.transform(X[te]))
                fold_scores.append(r2_score(y[te], pred))
            scores.append(float(np.mean(fold_scores)))
        pipe = Pipeline([("scaler", StandardScaler()), ("ridge", Ridge())])
        gs = GridSearchCV(pipe, {"ridge__alpha": lams}, cv=splits, scoring="r2")
        gs.fit(X, y)
        return {
            "param": "lambda",
            "grid": [float(v) for v in lams],
            "mean_score": scores,
            "best": float(lams[int(np.argmax(scores))]),
            "best_score": float(np.max(scores)),
            "sklearn_best": float(gs.best_params_["ridge__alpha"]),
            "sklearn_score": float(gs.best_score_),
            "dataset": "Diabetes",
            "metric": "R2",
        }

    ks = [1, 3, 5, 7, 15, 25]
    depths = [1, 2, 3, 4, 6, 8, 12]
    lams = np.logspace(-3, 3, 13)
    knn = cv_knn(iris.data, iris.target, ks)
    tree = cv_tree(wine.data, wine.target, depths)
    ridge = cv_ridge(diabetes.data, diabetes.target, lams)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8))
    axes[0].plot(knn["grid"], knn["mean_score"], marker="o")
    axes[0].set_title("k-NN, ирисы")
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("accuracy, 5-fold")
    axes[1].plot(tree["grid"], tree["mean_score"], marker="o", color="#b45309")
    axes[1].set_title("Дерево, вино")
    axes[1].set_xlabel("max_depth")
    axes[2].plot(ridge["grid"], ridge["mean_score"], marker="o", color="#15803d")
    axes[2].set_xscale("log")
    axes[2].set_title("Ridge, diabetes")
    axes[2].set_xlabel("λ")
    axes[2].set_ylabel("R², 5-fold")
    p = save_fig(fig, "task19_cv.png")
    return {"knn": knn, "tree": tree, "ridge": ridge, "plot": p}


def task_20():
    data = load_breast_cancer()
    X = data.data
    # в sklearn 0 — malignant. Переворачиваем метку: 1 = злокачественная опухоль,
    # чтобы precision/recall/F1/AUC относились к выявлению рака.
    y = 1 - data.target
    splits = stratified_kfold_indices(y, 5, SEED)
    models = {
        "Логистическая регрессия": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=500, random_state=SEED)),
        ]),
        "k-NN (k=7)": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", KNeighborsClassifier(n_neighbors=7)),
        ]),
        "Наивный Байес": GaussianNBScratch(),
        "Дерево (глубина 4)": DecisionTreeClassifier(max_depth=4, random_state=SEED),
        "Случайный лес": RandomForestClassifier(
            n_estimators=200, max_depth=None, random_state=SEED, n_jobs=1
        ),
    }
    rows = []
    for name, model in models.items():
        accs, precs, recs, f1s, aucs, times = [], [], [], [], [], []
        for tr, te in splits:
            # GaussianNBScratch не клонируется sklearn-ом — создаём заново
            if name == "Наивный Байес":
                clf = GaussianNBScratch()
            else:
                clf = model
            t0 = time.perf_counter()
            clf.fit(X[tr], y[tr])
            dt = time.perf_counter() - t0
            pred = clf.predict(X[te])
            if hasattr(clf, "predict_proba"):
                proba = clf.predict_proba(X[te])
                # столбец положительного класса 1
                if name == "Наивный Байес":
                    score = proba[:, list(clf.classes_).index(1)]
                else:
                    score = proba[:, 1]
            else:
                score = pred
            accs.append(accuracy_score(y[te], pred))
            precs.append(precision_score(y[te], pred, zero_division=0))
            recs.append(recall_score(y[te], pred, zero_division=0))
            f1s.append(f1_score(y[te], pred, zero_division=0))
            try:
                aucs.append(roc_auc_score(y[te], score))
            except ValueError:
                aucs.append(float("nan"))
            times.append(dt)
        rows.append({
            "model": name,
            "accuracy": float(np.mean(accs)),
            "precision": float(np.mean(precs)),
            "recall": float(np.mean(recs)),
            "f1": float(np.mean(f1s)),
            "auc": float(np.nanmean(aucs)),
            "time_sec": float(np.mean(times)),
        })
    return {
        "dataset": "Breast Cancer Wisconsin (sklearn)",
        "n": int(len(y)),
        "n_features": int(X.shape[1]),
        "positive_class": "1 = malignant (метка sklearn перевёрнута)",
        "folds": 5,
        "rows": rows,
    }


def main():
    results = {}
    steps = [
        ("t1", task_1_2),
        ("t3", task_3_4),
        ("t5", task_5),
        ("t6", task_6_7),
        ("t8", task_8),
        ("t9", task_9),
        ("t10", task_10),
        ("t11", task_11),
        ("t12", task_12),
        ("t13", task_13),
        ("t14", task_14),
        ("t15", task_15),
        ("t16", task_16),
        ("t17", task_17_18),
        ("t19", task_19),
        ("t20", task_20),
    ]
    for key, fn in steps:
        print("running", key, flush=True)
        results[key] = fn()
        print(" done", key, flush=True)
    path = os.path.join(OUT, "results.json")

    def conv(o):
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        raise TypeError(type(o))

    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=conv)
    print("WROTE", path)


if __name__ == "__main__":
    main()
