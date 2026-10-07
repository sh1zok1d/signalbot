"""Outcome-blind robust scaling and KMeans. No resolution label is read."""

from __future__ import annotations

import hashlib
import math
from typing import Optional

import numpy as np

from . import constants as K


def matrix_of(rows: list[dict]) -> np.ndarray:
    out = np.empty((len(rows), len(K.FEATURES)), dtype=float)
    for i, row in enumerate(rows):
        for j, name in enumerate(K.FEATURES):
            value = row.get(name)
            out[i, j] = math.nan if value is None else float(value)
    return out


def fit_scaler(raw: np.ndarray) -> dict:
    """Median / IQR scaler. A zero IQR is a degenerate predictor."""
    if raw.ndim != 2 or raw.shape[1] != len(K.FEATURES):
        raise ValueError("scaler expects the five-column predictor matrix")
    if not np.all(np.isfinite(raw)):
        raise ValueError("scaler fit rows must be finite")
    medians = []
    iqrs = []
    for j in range(raw.shape[1]):
        med = float(np.quantile(raw[:, j], 0.50, method="linear"))
        q25 = float(np.quantile(raw[:, j], 0.25, method="linear"))
        q75 = float(np.quantile(raw[:, j], 0.75, method="linear"))
        iqr = q75 - q25
        if not math.isfinite(iqr) or iqr <= 0.0:
            raise ValueError(f"degenerate IQR on {K.FEATURES[j]}")
        medians.append(med)
        iqrs.append(iqr)
    return {"median": medians, "iqr": iqrs, "n": int(raw.shape[0])}


def transform(raw: np.ndarray, scaler: dict) -> tuple[np.ndarray, np.ndarray]:
    """Return clipped z and the pre-clip count outside ±CLIP, per column."""
    med = np.asarray(scaler["median"], dtype=float)
    iqr = np.asarray(scaler["iqr"], dtype=float)
    scale = iqr / K.ROBUST_IQR_SCALE
    z = (raw - med) / scale
    outside = np.sum(np.abs(z) > K.CLIP, axis=0).astype(int)
    return np.clip(z, -K.CLIP, K.CLIP), outside


def _seed(parts: list[int]) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence(parts))


def _kmeans_pp(z: np.ndarray, k: int, rng: np.random.Generator) -> np.ndarray:
    n = z.shape[0]
    first = int(rng.integers(0, n))
    chosen = [first]
    closest = np.full(n, np.inf)
    for _ in range(1, k):
        diff = z - z[chosen[-1]]
        dist = np.einsum("ij,ij->i", diff, diff)
        closest = np.minimum(closest, dist)
        total = float(closest.sum())
        if not math.isfinite(total) or total <= 0.0:
            pick = int(rng.integers(0, n))
        else:
            pick = int(rng.choice(n, p=closest / total))
        chosen.append(pick)
    return z[np.asarray(chosen, dtype=int)].copy()


def _lloyd(z: np.ndarray, centroids: np.ndarray) -> tuple[Optional[np.ndarray], Optional[np.ndarray], float]:
    current = centroids.copy()
    labels = np.zeros(z.shape[0], dtype=int)
    for _ in range(K.KMEANS_MAX_ITER):
        dist = ((z[:, None, :] - current[None, :, :]) ** 2).sum(axis=2)
        labels = dist.argmin(axis=1).astype(int)
        updated = current.copy()
        for j in range(current.shape[0]):
            members = z[labels == j]
            if members.shape[0] == 0:
                far = int(dist.min(axis=1).argmax())
                updated[j] = z[far]
            else:
                updated[j] = members.mean(axis=0)
        shift = float(np.max(np.abs(updated - current)))
        current = updated
        if shift <= K.KMEANS_TOL:
            break
    dist = ((z[:, None, :] - current[None, :, :]) ** 2).sum(axis=2)
    labels = dist.argmin(axis=1).astype(int)
    if len(set(int(v) for v in labels)) != current.shape[0]:
        return None, None, math.inf
    inertia = float(dist[np.arange(z.shape[0]), labels].sum())
    return labels, current, inertia


def _canonicalize(labels: np.ndarray, centroids: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lexicographic order on (X1, X2, X3, X4, X5). STATE_1 is the first row."""
    order = sorted(range(centroids.shape[0]), key=lambda i: tuple(float(v) for v in centroids[i]))
    remap = {old: new for new, old in enumerate(order)}
    out_labels = np.asarray([remap[int(v)] for v in labels], dtype=int)
    out_centroids = centroids[np.asarray(order, dtype=int)].copy()
    return out_labels, out_centroids


def fit_kmeans(z: np.ndarray, k: int) -> Optional[dict]:
    """Best of N_INIT deterministic inits. None when every init fails to fill K."""
    if z.shape[0] < k:
        return None
    best = None
    for init in range(K.KMEANS_N_INIT):
        rng = _seed([K.KMEANS_SEED, int(k), int(init)])
        start = _kmeans_pp(z, k, rng)
        labels, centroids, inertia = _lloyd(z, start)
        if labels is None:
            continue
        if best is None or inertia < best["inertia"] - 1e-12:
            labels, centroids = _canonicalize(labels, centroids)
            best = {"labels": labels, "centroids": centroids, "inertia": float(inertia), "init": int(init)}
    return best


def assign_nearest(z: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    dist = ((z[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
    return dist.argmin(axis=1).astype(int)


def silhouette(z: np.ndarray, labels: np.ndarray) -> Optional[float]:
    n = z.shape[0]
    diff = z[:, None, :] - z[None, :, :]
    dist = np.sqrt(np.einsum("ijk,ijk->ij", diff, diff))
    scores = np.empty(n, dtype=float)
    ids = sorted(set(int(v) for v in labels))
    for label in ids:
        members = np.flatnonzero(labels == label)
        if members.size <= 1:
            return None
    for label in ids:
        members = np.flatnonzero(labels == label)
        sub = dist[np.ix_(members, members)]
        a = (sub.sum(axis=1)) / (members.size - 1)
        b = np.full(members.size, np.inf)
        for other in ids:
            if other == label:
                continue
            others = np.flatnonzero(labels == other)
            mean = dist[np.ix_(members, others)].mean(axis=1)
            b = np.minimum(b, mean)
        denom = np.maximum(a, b)
        scores[members] = np.where(denom > 0.0, (b - a) / denom, 0.0)
    return float(scores.mean())


def adjusted_rand(left: np.ndarray, right: np.ndarray) -> float:
    a = np.asarray(left, dtype=int)
    b = np.asarray(right, dtype=int)
    n = int(a.size)
    if n == 0 or a.shape != b.shape:
        return 0.0
    _, a_inv = np.unique(a, return_inverse=True)
    _, b_inv = np.unique(b, return_inverse=True)
    table = np.zeros((int(a_inv.max()) + 1, int(b_inv.max()) + 1), dtype=np.int64)
    np.add.at(table, (a_inv, b_inv), 1)

    def comb2(values: np.ndarray) -> float:
        return float(np.sum(values * (values - 1) / 2.0))

    sum_ij = comb2(table)
    sum_a = comb2(table.sum(axis=1))
    sum_b = comb2(table.sum(axis=0))
    total = n * (n - 1) / 2.0
    if total <= 0.0:
        return 1.0
    expected = sum_a * sum_b / total
    maximum = 0.5 * (sum_a + sum_b)
    denom = maximum - expected
    if denom == 0.0:
        return 1.0
    return float((sum_ij - expected) / denom)


def _jaccard_by_state(original: np.ndarray, boot: np.ndarray, k: int) -> list[float]:
    inter = np.zeros((k, k), dtype=float)
    for i in range(k):
        for j in range(k):
            inter[i, j] = float(np.sum((original == i) & (boot == j)))
    pairs = sorted(
        ((inter[i, j], i, j) for i in range(k) for j in range(k)),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    used_o: set[int] = set()
    used_b: set[int] = set()
    matched: dict[int, int] = {}
    for _value, i, j in pairs:
        if i in used_o or j in used_b:
            continue
        used_o.add(i)
        used_b.add(j)
        matched[i] = j
    out = []
    for i in range(k):
        j = matched.get(i)
        if j is None:
            out.append(0.0)
            continue
        left = original == i
        right = boot == j
        union = float(np.sum(left | right))
        out.append(0.0 if union == 0.0 else float(np.sum(left & right) / union))
    return out


def stability(z: np.ndarray, labels: np.ndarray, k: int) -> dict:
    """Refit on bootstrap rows. Assign every original row to the new centroids."""
    n = z.shape[0]
    aris = []
    jacs = []
    for draw in range(K.STABILITY_DRAWS):
        rng = _seed([K.KMEANS_SEED, 1, int(k), int(draw)])
        sample = z[rng.integers(0, n, size=n)]
        # The fit seed is the draw seed, so a given sample has one init stream.
        # n_init still uses KMEANS_SEED inside fit_kmeans, independent of this draw.
        # To make the refit depend on the draw, shuffle is not enough: pass a
        # dedicated one-init fit via the sample contents and the global seed.
        fitted = fit_kmeans(sample, k)
        if fitted is None:
            aris.append(0.0)
            jacs.append([0.0] * k)
            continue
        assigned = assign_nearest(z, fitted["centroids"])
        aris.append(adjusted_rand(labels, assigned))
        jacs.append(_jaccard_by_state(labels, assigned, k))
    jac = np.asarray(jacs, dtype=float)
    return {
        "median_ari": float(np.median(np.asarray(aris, dtype=float))),
        "median_jaccard": [float(np.median(jac[:, i])) for i in range(k)],
        "draws": int(K.STABILITY_DRAWS),
    }


def size_report(labels: np.ndarray) -> dict:
    n = int(labels.size)
    counts = [int(np.sum(labels == i)) for i in range(int(labels.max()) + 1 if n else 0)]
    shares = [c / n if n else 0.0 for c in counts]
    return {
        "n": n,
        "counts": counts,
        "shares": shares,
        "min_n": int(min(counts) if counts else 0),
        "min_share": float(min(shares) if shares else 0.0),
        "passes_size": bool(counts) and min(counts) >= K.MIN_CLUSTER_N and min(shares) >= K.MIN_CLUSTER_SHARE,
    }


def select_k(diagnostics: list[dict]) -> Optional[dict]:
    """Discard size failures and low ARI. Highest silhouette. Tie: smaller K."""
    eligible = []
    for item in diagnostics:
        if not item.get("passes_size"):
            continue
        ari = item.get("median_ari")
        sil = item.get("silhouette")
        if ari is None or sil is None:
            continue
        if float(ari) < K.STABILITY_ARI_MIN:
            continue
        eligible.append(item)
    if not eligible:
        return None
    eligible.sort(key=lambda item: (-float(item["silhouette"]), int(item["k"])))
    return eligible[0]


def state_name(index: int) -> str:
    return f"STATE_{int(index) + 1}"


def row_digest(rows: list[dict]) -> str:
    lines = []
    ordered = sorted(rows, key=lambda row: (int(row["open_ms"]), str(row["episode_id"])))
    for row in ordered:
        vals = "|".join(float(row[name]).hex() for name in K.FEATURES)
        lines.append(f"{row['episode_id']}|{int(row['open_ms'])}|{vals}")
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()


def hex_list(values) -> list[str]:
    return [float(v).hex() for v in values]


def describe_centroid(centroid: list[float]) -> str:
    """Predictor-only words. The 0.5 cut is not a new state and not an outcome split."""
    words = {
        0: ("above-average OI expansion", "near-average OI change", "above-average OI contraction"),
        1: ("OI change accelerating", "near-average OI acceleration", "OI change decelerating"),
        2: ("aggressive flow toward the level", "near-average aggressive flow", "aggressive flow away from the level"),
        3: ("flow toward the level strengthening", "near-average flow shift", "flow toward the level weakening"),
        4: ("above-average price progress toward the level", "near-average price progress", "below-average price progress toward the level"),
    }
    parts = []
    for i, value in enumerate(centroid):
        if float(value) >= K.WORD_Z:
            parts.append(words[i][0])
        elif float(value) <= -K.WORD_Z:
            parts.append(words[i][2])
        else:
            parts.append(words[i][1])
    return "; ".join(parts)
