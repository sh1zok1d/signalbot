"""Vectorized outcome-free evaluator for the V2 synthetic adequacy study.

Every fit is the one-step Newton solution of the (weighted, ridge) logistic likelihood from the intercept-only start,
computed from segment sums, for many synthetic outcome replications at once. At these signal sizes (|eta| << 1) it
matches full Newton-IRLS to ~1e-4 relative in the coefficients; `validate.py` measures the difference against exact
IRLS (with the +-5 clip, which binds on ~0.06 % of rows) and against the exact V1 preflight. Market outcomes are never
an input: the engine only sees synthetic Y matrices.

Systems (all on the V1 schedule; venues never mixed):
  CLIM, B1, STATIC_OCC4             expanding window, as in V1
  V2 candidates (structure, memory, lambda_occ)
    JOINT  : one ridge logistic on B1 (lambda 1) + OCC_1H..12H (lambda_occ), fitted on the memory window
    OFFSET : the expanding B1 fit as an offset + a ridge logistic overlay on OCC_1H..12H (lambda_occ, no intercept)
             fitted on the memory window
    memory : TRAIL_52 / TRAIL_104 (up to M weeks), EWMA_26 (half-life 26 weeks), EXPANDING (reference)
  V1 hard selector (24 candidates, nested inner Brier over 24 weeks), for comparison only
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from scripts.research.adaptive_b1_forecast_v1 import metrics as MT
from scripts.research.adaptive_occupancy_v1 import constants as K1
from scripts.research.adaptive_occupancy_v1 import walkforward as WF1

LOOKBACKS = K1.LOOKBACK_HOURS
B1_IDX = np.arange(5)
OCC_IDX = {h: 5 + i for i, h in enumerate(LOOKBACKS)}
OCC_ALL = np.array([OCC_IDX[h] for h in LOOKBACKS])
P_CLIP = 1e-6
TIE_TOL = K1.TIE_TOL


def raw_matrix(rows: dict) -> np.ndarray:
    """[RP4H-0.5, RET_4H/RV, RET_1H/RV, RET_15M/RV, log RV, OCC_1H-0.5 ... OCC_12H-0.5] (V1 design columns)."""
    rv = rows["rv4"]
    cols = [rows["rp"] - 0.5, rows["ret4"] / rv, rows["ret1h"] / rv, rows["ret15"] / rv, np.log(rv)]
    cols += [rows[f"OCC_{h}H"] - 0.5 for h in LOOKBACKS]
    return np.column_stack(cols)


@dataclass(frozen=True)
class Spec:
    name: str
    structure: str                 # STD | OFFSET | CLIM
    cols: tuple                    # raw column indices (STD: all slopes; OFFSET: overlay columns)
    lam: tuple                     # ridge per slope
    memory: str                    # EXPANDING | TRAIL | EWMA
    weeks: int = 0                 # TRAIL window or EWMA half-life (weeks)
    v1_full_window: bool = False   # V1 rule: a trailing candidate exists only with a full window


def b1_spec() -> Spec:
    return Spec("B1", "STD", tuple(B1_IDX), (1.0,) * 5, "EXPANDING")


def static_spec() -> Spec:
    return Spec("STATIC_OCC4", "STD", tuple(B1_IDX) + (OCC_IDX[4],), (1.0,) * 6, "EXPANDING")


def v2_spec(structure: str, memory: str, weeks: int, lam_occ: float) -> Spec:
    tag = f"{memory}_{weeks}" if memory != "EXPANDING" else "EXPANDING"
    name = f"V2|{structure}|{tag}|{lam_occ:g}"
    if structure == "JOINT":
        return Spec(name, "STD", tuple(B1_IDX) + tuple(OCC_ALL), (1.0,) * 5 + (lam_occ,) * 7, memory, weeks)
    return Spec(name, "OFFSET", tuple(OCC_ALL), (lam_occ,) * 7, memory, weeks)


def v1_specs() -> list:
    out = []
    for mem in K1.MEMORIES_WEEKS:
        for cfg in K1.CONFIGS:
            cols = tuple(B1_IDX) + (() if cfg == K1.NO_OCC else (OCC_IDX[int(cfg.split("_")[1][:-1])],))
            out.append(Spec(f"V1|{mem}|{cfg}", "STD", cols, (1.0,) * len(cols), "TRAIL", mem, True))
    return out


# ------------------------------------------------------------------ geometry (outcome-free)
@dataclass
class Geometry:
    rows: dict
    X: np.ndarray
    sched: dict
    t: np.ndarray
    venue_range: dict
    week_ids: np.ndarray            # sorted unique ISO weeks of the outer rows (bootstrap order)
    row_week: np.ndarray            # per row: index into week_ids (-1 outside the outer set)
    outer: np.ndarray               # outer-row mask
    bounds: np.ndarray              # segment boundaries (row indices)
    t_ref: float
    ewma_weeks: int
    cum: dict = field(default_factory=dict)

    def idx_le(self, v: int, t: int) -> int:
        a, b = self.venue_range[v]
        return int(np.clip(np.searchsorted(self.t, t, "right"), a, b))

    def idx_lt(self, v: int, t: int) -> int:
        a, b = self.venue_range[v]
        return int(np.clip(np.searchsorted(self.t, t, "left"), a, b))

    def train_range(self, v: int, s: int, spec: Spec) -> tuple:
        a, _ = self.venue_range[v]
        end = self.idx_le(v, s - K1.HOUR_MS)
        if spec.memory == "TRAIL":
            return self.idx_lt(v, s - spec.weeks * K1.WEEK_MS), end
        return a, end

    def seg(self, i: int) -> int:
        k = int(np.searchsorted(self.bounds, i))
        if k >= self.bounds.size or self.bounds[k] != i:
            raise SystemExit(f"NOT_A_SEGMENT_BOUNDARY_{i}")
        return k


def build_geometry(rows: dict, ewma_weeks: int, memories=None) -> Geometry:
    memories = tuple(sorted(set(K1.MEMORIES_WEEKS) | {52, 104})) if memories is None else memories
    X = raw_matrix(rows)
    t = rows["close_ms"].astype(np.int64)
    sched = WF1.schedule(rows)
    vr = {}
    for v in sched:
        ix = np.flatnonzero(rows["venue"] == v)
        vr[v] = (int(ix[0]), int(ix[-1]) + 1)
        if ix.size != vr[v][1] - vr[v][0]:
            raise SystemExit("VENUE_NOT_CONTIGUOUS")
    outer = WF1.outer_mask(rows, sched)
    wk = MT.weeks_of(t)
    week_ids = np.unique(wk[outer])
    row_week = np.full(t.size, -1, dtype=np.int64)
    row_week[outer] = np.searchsorted(week_ids, wk[outer])
    g = Geometry(rows, X, sched, t, vr, week_ids, row_week, outer, np.array([0]), float(t[0]), ewma_weeks)
    b = {0, t.size}
    for v, sv in sched.items():
        b.update(vr[v])
        for s in sv["grid_starts"]:
            s = int(s)
            b.add(g.idx_le(v, s - K1.HOUR_MS))
            for m in memories:
                b.add(g.idx_lt(v, s - m * K1.WEEK_MS))
    g.bounds = np.array(sorted(b), dtype=np.int64)
    w = ewma_raw_weights(g)
    ones = np.ones(t.size)
    for tag, ww in (("u", ones), ("w", w)):
        xw = X * ww[:, None]
        g.cum[f"n_{tag}"] = _cum_segments(g.bounds, ww[:, None])[:, 0]
        g.cum[f"x_{tag}"] = _cum_segments(g.bounds, xw)
        g.cum[f"xx_{tag}"] = _cum_xx(g.bounds, X, ww)
    return g


def ewma_raw_weights(g: Geometry) -> np.ndarray:
    return np.exp2((g.t - g.t_ref) / (g.ewma_weeks * K1.WEEK_MS))


def _cum_segments(bounds: np.ndarray, a: np.ndarray) -> np.ndarray:
    seg = np.add.reduceat(a, bounds[:-1], axis=0) if bounds.size > 1 else np.zeros((0,) + a.shape[1:])
    seg[np.diff(bounds) == 0] = 0.0
    return np.concatenate([np.zeros((1,) + a.shape[1:]), np.cumsum(seg, axis=0)], axis=0)


def _cum_xx(bounds: np.ndarray, X: np.ndarray, w: np.ndarray) -> np.ndarray:
    k = X.shape[1]
    out = np.zeros((bounds.size, k, k))
    acc = np.zeros((k, k))
    for i in range(bounds.size - 1):
        a, b = bounds[i], bounds[i + 1]
        if b > a:
            xa = X[a:b]
            acc = acc + (xa * w[a:b, None]).T @ xa
        out[i + 1] = acc
    return out


def outcome_cums(g: Geometry, Y: np.ndarray) -> dict:
    """Segment-cumulative sums of y and x*y (plain and EWMA-weighted) for every replication column of Y."""
    w = ewma_raw_weights(g)
    out = {}
    nb = g.bounds.size
    for tag, ww in (("u", None), ("w", w)):
        sy = np.zeros((nb, Y.shape[1]))
        sxy = np.zeros((nb, g.X.shape[1], Y.shape[1]))
        accy = np.zeros(Y.shape[1])
        accxy = np.zeros((g.X.shape[1], Y.shape[1]))
        for i in range(nb - 1):
            a, b = g.bounds[i], g.bounds[i + 1]
            if b > a:
                ya = Y[a:b]
                if ww is None:
                    accy = accy + ya.sum(axis=0)
                    accxy = accxy + g.X[a:b].T @ ya
                else:
                    accy = accy + ww[a:b] @ ya
                    accxy = accxy + (g.X[a:b] * ww[a:b, None]).T @ ya
            sy[i + 1] = accy
            sxy[i + 1] = accxy
        out[f"y_{tag}"] = sy
        out[f"xy_{tag}"] = sxy
    return out


def _range_sums(g: Geometry, oc: dict, a: int, b: int, weighted: bool, s: int):
    ia, ib = g.seg(a), g.seg(b)
    tag = "w" if weighted else "u"
    f = np.exp2(-(s - g.t_ref) / (g.ewma_weeks * K1.WEEK_MS)) if weighted else 1.0
    n = f * (g.cum[f"n_{tag}"][ib] - g.cum[f"n_{tag}"][ia])
    sx = f * (g.cum[f"x_{tag}"][ib] - g.cum[f"x_{tag}"][ia])
    sxx = f * (g.cum[f"xx_{tag}"][ib] - g.cum[f"xx_{tag}"][ia])
    sy = f * (oc[f"y_{tag}"][ib] - oc[f"y_{tag}"][ia])
    sxy = f * (oc[f"xy_{tag}"][ib] - oc[f"xy_{tag}"][ia])
    return n, sx, sxx, sy, sxy


def _logit(p):
    p = np.clip(p, P_CLIP, 1 - P_CLIP)
    return np.log(p / (1 - p))


def fit_std(g: Geometry, oc: dict, v: int, s: int, spec: Spec) -> dict:
    a, b = g.train_range(v, s, spec)
    n, sx, sxx, sy, sxy = _range_sums(g, oc, a, b, spec.memory == "EWMA", s)
    c = np.array(spec.cols)
    mu = sx[c] / n
    cov = sxx[np.ix_(c, c)] / n - np.outer(mu, mu)
    sd = np.sqrt(np.clip(np.diag(cov), 0, None))
    sd = np.where(sd > 0, sd, 1.0)
    A = n * cov / np.outer(sd, sd)
    ybar = sy / n
    gr = (sxy[c] - mu[:, None] * sy[None, :]) / sd[:, None]
    vv = ybar * (1 - ybar)
    H = vv[:, None, None] * A[None] + np.diag(np.array(spec.lam))[None]
    beta = np.linalg.solve(H, gr.T[..., None])[..., 0].T
    return {"mu": mu, "sd": sd, "b0": _logit(ybar), "beta": beta, "cols": c, "ybar": ybar, "n": n, "range": (a, b)}


def fit_offset(g: Geometry, oc: dict, v: int, s: int, spec: Spec, base: dict) -> dict:
    """Overlay on the OCC columns with the B1 fit `base` (expanding, at s) as offset; no intercept."""
    a, b = g.train_range(v, s, spec)
    n, sx, sxx, sy, sxy = _range_sums(g, oc, a, b, spec.memory == "EWMA", s)
    c = np.array(spec.cols)
    c1 = base["cols"]
    mu = sx[c] / n
    cov = sxx[np.ix_(c, c)] / n - np.outer(mu, mu)
    sd = np.sqrt(np.clip(np.diag(cov), 0, None))
    sd = np.where(sd > 0, sd, 1.0)
    A = n * cov / np.outer(sd, sd)
    term_y = (sxy[c] - mu[:, None] * sy[None, :]) / sd[:, None]
    cross = (sxx[np.ix_(c, c1)] - np.outer(mu, sx[c1])) / sd[:, None]           # sum w z_o x_1^T
    u_term = (cross / base["sd"][None, :]) @ base["beta"]                         # sum w z_o u
    p0 = 1 / (1 + np.exp(-base["b0"]))
    v1 = p0 * (1 - p0)
    gr = term_y - v1[None, :] * u_term
    H = v1[:, None, None] * A[None] + np.diag(np.array(spec.lam))[None]
    gamma = np.linalg.solve(H, gr.T[..., None])[..., 0].T
    return {"mu": mu, "sd": sd, "gamma": gamma, "cols": c, "base": base, "range": (a, b)}


CLIP_Z = 5.0


def eta_std(g: Geometry, fit: dict, ix: np.ndarray) -> np.ndarray:
    z = np.clip((g.X[np.ix_(ix, fit["cols"])] - fit["mu"]) / fit["sd"], -CLIP_Z, CLIP_Z)
    return fit["b0"][None, :] + z @ fit["beta"]


def eta_offset(g: Geometry, fit: dict, ix: np.ndarray) -> np.ndarray:
    z = np.clip((g.X[np.ix_(ix, fit["cols"])] - fit["mu"]) / fit["sd"], -CLIP_Z, CLIP_Z)
    return eta_std(g, fit["base"], ix) + z @ fit["gamma"]


def _sig(e):
    return 1 / (1 + np.exp(-e))


def losses(p: np.ndarray, y: np.ndarray):
    pc = np.clip(p, P_CLIP, 1 - P_CLIP)
    return (p - y) ** 2, -(y * np.log(pc) + (1 - y) * np.log(1 - pc))


# ------------------------------------------------------------------ evaluation of one replication batch
@dataclass
class Acc:
    """Per-model accumulators over the outer rows: week sums of Brier and log loss; sums for the calibration sign."""
    W: int
    R: int
    brier: dict = field(default_factory=dict)
    logloss: dict = field(default_factory=dict)
    cal: dict = field(default_factory=dict)       # name -> [sum l, sum l^2, sum l*y, sum y, n]
    cw: dict = field(default_factory=dict)        # name -> week sums of 2 (p - p_B1)(y - p_B1)

    def _ensure(self, name: str):
        if name not in self.brier:
            self.brier[name] = np.zeros((self.W, self.R))
            self.logloss[name] = np.zeros((self.W, self.R))
            self.cal[name] = np.zeros((5, self.R))

    def add(self, name: str, wm: tuple, p: np.ndarray, y: np.ndarray):
        """wm = (week indices u, compact indicator W1 of shape (len(u), n))."""
        u, W1 = wm
        b, l = losses(p, y)
        self._ensure(name)
        self.brier[name][u] += W1 @ b
        self.logloss[name][u] += W1 @ l
        self.cal[name] += cal_sums(p, y)

    def add_cw(self, name: str, wm: tuple, p: np.ndarray, p0: np.ndarray, y: np.ndarray):
        u, W1 = wm
        if name not in self.cw:
            self.cw[name] = np.zeros((self.W, self.R))
        self.cw[name][u] += W1 @ (2 * (p - p0) * (y - p0))


def cal_sums(p: np.ndarray, y: np.ndarray) -> np.ndarray:
    lp = _logit(p)
    return np.stack([lp.sum(0), (lp * lp).sum(0), (lp * y).sum(0), y.sum(0), np.full(p.shape[1], float(p.shape[0]))])


def _week_matrix(g: Geometry, ix: np.ndarray) -> tuple:
    wk = g.row_week[ix]
    if np.any(wk < 0):
        raise SystemExit("NOT_AN_OUTER_ROW")
    u, inv = np.unique(wk, return_inverse=True)
    W1 = np.zeros((u.size, ix.size))
    W1[inv, np.arange(ix.size)] = 1.0
    return u, W1


def evaluate_batch(g: Geometry, Y: np.ndarray, v2: list, with_v1: bool) -> dict:
    """Y: (n_rows, R) synthetic outcomes in {0, 1}. Returns the per-model accumulators over the outer rows and the
    V1 selector log. Every model for block S is fitted on rows realized by S only."""
    Y = np.asarray(Y, dtype=np.float64)
    R = Y.shape[1]
    oc = outcome_cums(g, Y)
    acc = Acc(g.week_ids.size, R)
    blk = WF1.block_ms()
    sb, ss = b1_spec(), static_spec()
    v1 = v1_specs() if with_v1 else []
    v1_block = {}                  # (v, s) -> per-candidate head/tail sums and week sums
    for v, sv in g.sched.items():
        first = sv["first_ms"]
        outer_set = set(int(s) for s in sv["outer_starts"])
        starts = [int(s) for s in sv["grid_starts"]] if with_v1 else sorted(outer_set)
        for s in starts:
            lo, hi = g.idx_lt(v, s), g.idx_lt(v, s + blk)
            ix = np.arange(lo, hi)
            if ix.size == 0:
                continue
            y = Y[ix]
            is_outer = s in outer_set
            if is_outer:
                wm = _week_matrix(g, ix)
                fb = fit_std(g, oc, v, s, sb)
                pb = _sig(eta_std(g, fb, ix))
                acc.add("B1", wm, pb, y)
                acc.add("CLIM", wm, np.broadcast_to(fb["ybar"], y.shape).copy(), y)
                fs = fit_std(g, oc, v, s, ss)
                acc.add("STATIC_OCC4", wm, _sig(eta_std(g, fs, ix)), y)
                for sp in v2:
                    if sp.structure == "STD":
                        p = _sig(eta_std(g, fit_std(g, oc, v, s, sp), ix))
                    else:
                        p = _sig(eta_offset(g, fit_offset(g, oc, v, s, sp, fb), ix))
                    acc.add(sp.name, wm, p, y)
                    acc.add_cw(sp.name, wm, p, pb, y)
            if with_v1:
                head = g.t[ix] + K1.HOUR_MS <= s + blk
                rec = {"head_b": [], "head_l": [], "tail_b": [], "tail_l": [], "n_head": int(head.sum()),
                       "n_tail": int((~head).sum()), "exists": [], "wk_b": [], "wk_l": [], "cal": []}
                wmo = _week_matrix(g, ix) if is_outer else None
                for sp in v1:
                    ok = s - sp.weeks * K1.WEEK_MS >= first
                    rec["exists"].append(ok)
                    if not ok:
                        for k in ("head_b", "head_l", "tail_b", "tail_l"):
                            rec[k].append(np.full(R, np.nan))
                        if is_outer:
                            rec["wk_b"].append(None)
                            rec["wk_l"].append(None)
                            rec["cal"].append(None)
                        continue
                    p = _sig(eta_std(g, fit_std(g, oc, v, s, sp), ix))
                    b, l = losses(p, y)
                    rec["head_b"].append(b[head].sum(0))
                    rec["head_l"].append(l[head].sum(0))
                    rec["tail_b"].append(b[~head].sum(0))
                    rec["tail_l"].append(l[~head].sum(0))
                    if is_outer:
                        rec["wk_b"].append(wmo[1] @ b)
                        rec["wk_l"].append(wmo[1] @ l)
                        rec["cal"].append(cal_sums(p, y))
                if is_outer:
                    rec["wk_u"] = wmo[0]
                v1_block[(v, s)] = rec
    log = select_v1(g, v1_block, acc, R) if with_v1 else None
    return {"acc": acc, "v1_log": log}


def _order(spec: Spec):
    cfg = spec.name.split("|")[2]
    return (0 if cfg == K1.NO_OCC else 1, -spec.weeks,
            -1 if cfg == K1.NO_OCC else K1.LOOKBACK_HOURS.index(int(cfg.split("_")[1][:-1])))


def select_v1(g: Geometry, blocks: dict, acc: Acc, R: int) -> dict:
    """The V1 hard selector, exactly as frozen: lowest pooled inner Brier over the 6 blocks before S (rows realized by
    S), ties -> log loss -> NO_OCC, longer memory, shorter lookback; eligible memories as in V1."""
    v1 = v1_specs()
    order = sorted(range(len(v1)), key=lambda i: _order(v1[i]))
    blk = WF1.block_ms()
    chosen = []
    for v, sv in g.sched.items():
        for S in (int(s) for s in sv["outer_starts"]):
            if (v, S) not in blocks:
                continue
            elig_mem = WF1.eligible_memories(S, sv["first_ms"])
            cand = [i for i in order if v1[i].weeks in elig_mem]
            sb = np.zeros((len(cand), R))
            sl = np.zeros((len(cand), R))
            n = 0
            for j in range(1, K1.INNER_BLOCKS + 1):
                key = (v, S - j * blk)
                if key not in blocks:
                    continue
                rec = blocks[key]
                hb = np.array([rec["head_b"][i] for i in cand])
                hl = np.array([rec["head_l"][i] for i in cand])
                if j == 1:
                    sb += hb
                    sl += hl
                    n += rec["n_head"]
                else:
                    sb += hb + np.array([rec["tail_b"][i] for i in cand])
                    sl += hl + np.array([rec["tail_l"][i] for i in cand])
                    n += rec["n_head"] + rec["n_tail"]
            if not np.isfinite(sb).all():
                raise SystemExit("V1_INNER_MISSING")
            mb, ml = sb / n, sl / n
            best = mb.min(axis=0)
            m1 = mb <= best + TIE_TOL
            l2 = np.where(m1, ml, np.inf)
            m2 = m1 & (l2 <= l2.min(axis=0) + TIE_TOL)
            pick = np.argmax(m2, axis=0)
            rec = blocks[(v, S)]
            wb = np.stack([rec["wk_b"][i] for i in cand])
            wl = np.stack([rec["wk_l"][i] for i in cand])
            wc = np.stack([rec["cal"][i] for i in cand])
            r = np.arange(R)
            acc._ensure("V1")
            u = rec["wk_u"]
            acc.brier["V1"][u] += wb[pick, :, r].T
            acc.logloss["V1"][u] += wl[pick, :, r].T
            acc.cal["V1"] += wc[pick, :, r].T
            chosen.append({"venue": v, "S": S, "configs": [v1[cand[k]].name for k in pick]})
    return {"blocks": chosen}


# ------------------------------------------------------------------ bootstrap and routes
def boot_counts(W: int, draws: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = rng.integers(0, W, size=(draws, W))
    C = np.zeros((draws, W))
    for b in range(draws):
        C[b] = np.bincount(d[b], minlength=W)
    return C


def boot_pair(C: np.ndarray, cnt: np.ndarray, Sa: np.ndarray, Sb: np.ndarray, lo_q=0.025, hi_q=0.975) -> dict:
    D = Sa - Sb
    den = C @ cnt
    d = (C @ D) / den[:, None]
    return {"point": D.sum(0) / cnt.sum(), "lo": np.quantile(d, lo_q, axis=0), "hi": np.quantile(d, hi_q, axis=0),
            "valid": np.isfinite(d).sum(0)}


def cal_sign(c: np.ndarray) -> np.ndarray:
    """Sign of the logistic recalibration slope (y on logit p): the sign of the score at slope 0, Cov(logit p, y)."""
    sl, sll, sly, sy, n = c
    return sly - sl * sy / n


def summarize(acc: Acc, C: np.ndarray, cnt: np.ndarray, model: str, base: str = "B1") -> dict:
    db = boot_pair(C, cnt, acc.brier[model], acc.brier[base])
    dl = boot_pair(C, cnt, acc.logloss[model], acc.logloss[base])
    slope_pos = cal_sign(acc.cal[model]) >= 0
    support = (db["valid"] >= 1900) & (db["point"] < 0) & (db["hi"] < 0) & (dl["point"] < 0) & slope_pos
    worse = db["lo"] > 0
    out = {"d_brier": db["point"], "lo": db["lo"], "hi": db["hi"], "d_logloss": dl["point"],
           "support": support, "beat": db["point"] < 0, "worse": worse}
    if model in acc.cw:
        cw = boot_pair(C, cnt, acc.cw[model], np.zeros_like(acc.cw[model]))
        out.update({"cw": cw["point"], "cw_lo": cw["lo"], "cw_hi": cw["hi"],
                    "support_cw": (cw["lo"] > 0) & (cw["point"] > 0)})
    return out


def week_counts(g: Geometry) -> np.ndarray:
    return np.bincount(g.row_week[g.outer], minlength=g.week_ids.size).astype(float)
