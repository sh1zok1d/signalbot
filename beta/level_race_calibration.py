"""Level race calibration, monitors and display state (ОПГ-2 track F3; pure, no database).

Implements `docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md` for the forecast layer of
`docs/FORECAST_LAYER_DECISION_V1.md` §5–§7:

- the three race outcomes are carried as two binary heads: RESOLVE (a barrier is reached within 4h)
  and BREAK_GIVEN_RESOLVE (the BREAK barrier is the first one, among resolved events);
- each head gets a two-parameter Bayesian logistic recalibration p' = expit(a + b·logit p), fitted by
  Laplace approximation on outcomes resolved before the batch cutoff only, with a Gaussian prior worth
  `N_EQUIV_PRIOR` events;
- the drift monitors (an anytime-valid change-point mixture e-process on the published probabilities,
  the rolling intercept, the rolling paired log loss against B0, the size of the required correction);
- the display state machine HIST / L3_HISTORY_BACKED / L3_LIVE / FALLBACK / OFF.

Every number here is a design constant fixed before any real outcome is read; the simulation that
chose them runs on synthetic data only (`scripts/research/level_race_calibration_sim.py`).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping, Optional, Sequence

import numpy as np

LR_CAL_VERSION = "LEVEL_RACE_CAL_V1"
LR_STATE_VERSION = "LEVEL_RACE_STATE_V1"
OUTCOMES = ("BREAK", "REJECT", "NEITHER")
HEADS = ("RESOLVE", "BREAK_GIVEN_RESOLVE")
P_CLIP = 1e-4

# ---- calibrator (design §3) ---------------------------------------------------------------------
N_EQUIV_PRIOR = 150             # the held-out fit enters the live calibrator worth 150 events
BASE_PRIOR_EQUIV = 150          # the held-out walk-forward starts from the identity map worth 150 events
WEEKLY_BATCHES = 12             # weekly cutoffs for the first 12 weeks, then every 4 weeks
LATER_BATCH_WEEKS = 4
ISOTONIC_MIN_EVENTS = 300       # no non-parametric calibrator below this; V1 has none at all
LARGE_SHIFT_PP = 10.0           # a required correction beyond this is a drift signal, not a fix

# ---- held-out gate (design §2) ------------------------------------------------------------------
HOLDOUT_CITL_PP = 5.0           # |intercept| of the walk-forward published probabilities, each head
HOLDOUT_CURVE_PP = 7.5         # max |fitted recalibration curve − identity| over the 10–90 % range, each head
HOLDOUT_RAW_CITL_PP = 10.0      # raw model: a larger miscalibration is a drift signal, not a calibration
HOLDOUT_MIN_WEEKS = 20

# ---- live (design §4) ---------------------------------------------------------------------------
LIVE_FLOOR = 150                # resolved live events per class for L3_LIVE
LIVE_CITL_PP = 7.5              # |intercept| of the live published probabilities, each head
LIVE_CURVE_PP = 10.0

# ---- drift (design §5) --------------------------------------------------------------------------
E_THRESHOLD = 10.0
E_DELTAS = (-0.6, -0.3, 0.0, 0.3, 0.6)   # logit intercept shifts per head; (0, 0) excluded
E_KEY = "p_pub"                 # the e-process tests the published probabilities ("p_ref" tested: see design §5.1)
E_BLOCK = 25                    # change points every 25 events, weight 1 / ((j + 1)(j + 2))
ROLL_N = 100                    # rolling window of the intercept and paired log-loss monitors
ROLL_CITL_BAND_PP = 5.0         # rolling intercept whose week-clustered ROLL_Z interval lies wholly outside ±5 pp
ROLL_LL_MIN_WEEKS = 8
ROLL_Z = 2.576                  # the rolling monitors use 99 % week-clustered intervals (looked at every batch)
RETURN_MIN_EVENTS = 50
RETURN_CITL_PP = 10.0
MAX_FALLBACKS = 2               # the second FALLBACK of a model version is final for that version

# ---- challengers (design §6) --------------------------------------------------------------------
CHALLENGER_MIN_PAIRED = 150
CHALLENGER_LOOK_EVERY = 150     # promotion is looked at only at 150, 300, 450, 600 paired events
CHALLENGER_MAX_PAIRED = 600     # retired unpromoted after the fourth look
CHALLENGER_MAX_CONCURRENT = 2
Z95 = 1.959964


# ---- probabilities --------------------------------------------------------------------------------
def _clip(p):
    return np.clip(np.asarray(p, dtype=float), P_CLIP, 1 - P_CLIP)


def logit(p):
    p = _clip(p)
    return np.log(p) - np.log1p(-p)


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def heads_from_probs(p3) -> tuple:
    """(P(BREAK), P(REJECT), P(NEITHER)) → (P(resolve), P(BREAK | resolve)), arrays allowed."""
    p3 = np.asarray(p3, dtype=float)
    pb, pr, pn = p3[..., 0], p3[..., 1], p3[..., 2]
    res = pb + pr
    with np.errstate(invalid="ignore", divide="ignore"):
        cond = np.where(res > 0, pb / np.where(res > 0, res, 1.0), 0.5)
    return _clip(1.0 - pn), _clip(cond)


def probs_from_heads(p_res, p_cond) -> np.ndarray:
    p_res, p_cond = np.asarray(p_res, dtype=float), np.asarray(p_cond, dtype=float)
    return np.stack([p_res * p_cond, p_res * (1 - p_cond), 1 - p_res], axis=-1)


def head_targets(outcome: str) -> tuple:
    """(y_resolve, y_break_given_resolve or None)."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    if outcome == "NEITHER":
        return 0, None
    return 1, int(outcome == "BREAK")


def head_arrays(records: Sequence[Mapping[str, Any]], key: str) -> dict:
    """Per head: (probabilities, targets, week ids) of the resolved records, probabilities from `key`."""
    p3 = np.array([r[key] for r in records], dtype=float).reshape(-1, 3)
    pa, pc = heads_from_probs(p3) if len(records) else (np.zeros(0), np.zeros(0))
    ya = np.array([head_targets(r["outcome"])[0] for r in records], dtype=float)
    wk = np.array([int(r["week"]) for r in records], dtype=int)
    res = ya == 1
    yb = np.array([1.0 if r["outcome"] == "BREAK" else 0.0 for r in records], dtype=float)
    return {"RESOLVE": (pa, ya, wk), "BREAK_GIVEN_RESOLVE": (pc[res], yb[res], wk[res])}


# ---- logistic fits ---------------------------------------------------------------------------------
def _design(lg):
    return np.column_stack([np.ones_like(lg), lg])


def _center(prior: Mapping[str, Any]) -> float:
    return float(prior.get("center", 0.0))


def unit_information(raw_logits) -> np.ndarray:
    """Mean per-event Fisher information of (a, b) at the identity map on a design of raw logits.
    It uses the raw probabilities only, never an outcome."""
    lg = np.asarray(raw_logits, dtype=float)
    if lg.size == 0:
        return np.eye(2) * 0.25
    X = _design(lg)
    w = expit(lg) * (1 - expit(lg))
    return (X * w[:, None]).T @ X / lg.size


def prior_worth(mean, raw_logits, n_equiv: float, *, center: Optional[float] = None) -> dict:
    """A Gaussian prior on (a, b) at `mean` whose precision equals n_equiv events of the design.
    The map is p' = expit(c + a + b·(logit p − c)) with c the design's mean raw logit (fixed per head),
    so (0, 1) is the identity and a is the shift at the design centre."""
    mean = np.asarray(mean, dtype=float)
    lg = np.asarray(raw_logits, dtype=float)
    c = float(lg.mean()) if center is None and lg.size else float(center or 0.0)
    X = _design(lg - c) if lg.size else np.array([[1.0, 0.0]])
    q = expit(c + X @ mean)
    w = q * (1 - q)
    info = (X * w[:, None]).T @ X / max(len(X), 1) + np.eye(2) * 1e-6
    cov = np.linalg.inv(info * n_equiv)
    return {"mean": mean.tolist(), "cov": cov.tolist(), "center": c}


def fit_logistic(raw_logits, y, prior: Mapping[str, Any], *, iters: int = 50) -> dict:
    """MAP of p' = expit(c + a + b·(raw_logit − c)) under a Gaussian prior; Laplace covariance."""
    lg, y = np.asarray(raw_logits, dtype=float), np.asarray(y, dtype=float)
    m0 = np.asarray(prior["mean"], dtype=float)
    P0 = np.linalg.inv(np.asarray(prior["cov"], dtype=float))
    c = _center(prior)
    X = _design(lg - c)
    th = m0.copy()
    for _ in range(iters):
        q = expit(c + X @ th)
        g = X.T @ (y - q) - P0 @ (th - m0)
        H = (X * (q * (1 - q))[:, None]).T @ X + P0
        step = np.linalg.lstsq(H, g, rcond=None)[0]
        th = th + step
        if float(np.max(np.abs(step))) < 1e-10:
            break
    q = expit(c + X @ th)
    H = (X * (q * (1 - q))[:, None]).T @ X + P0
    return {"mean": th.tolist(), "cov": np.linalg.pinv(H).tolist(), "n": int(lg.size), "center": c}


# ---- the calibrator --------------------------------------------------------------------------------
@dataclass(frozen=True)
class Calibrator:
    claim_class: str
    cutoff_ms: int
    heads: Mapping[str, Mapping[str, Any]]     # head -> {"mean": [a, b], "cov": 2x2, "n": live events}
    priors: Mapping[str, Mapping[str, Any]]    # head -> prior {"mean", "cov"}
    version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=float).encode()).hexdigest()


def make_calibrator(claim_class: str, cutoff_ms: int, heads: Mapping, priors: Mapping) -> Calibrator:
    body = {"v": LR_CAL_VERSION, "class": claim_class, "cutoff_ms": int(cutoff_ms),
            "heads": {h: {"mean": [round(x, 12) for x in heads[h]["mean"]], "n": heads[h]["n"]} for h in HEADS},
            "priors": {h: {"mean": [round(x, 12) for x in priors[h]["mean"]]} for h in HEADS}}
    return Calibrator(claim_class, int(cutoff_ms), heads, priors, f"{LR_CAL_VERSION}:{_digest(body)[:16]}")


def identity_priors(raw_logits_by_head: Mapping[str, Sequence[float]], n_equiv: float = BASE_PRIOR_EQUIV) -> dict:
    return {h: prior_worth([0.0, 1.0], raw_logits_by_head.get(h, ()), n_equiv) for h in HEADS}


def fit_calibrator(claim_class: str, records: Sequence[Mapping[str, Any]], priors: Mapping[str, Mapping[str, Any]],
                   *, cutoff_ms: int) -> Calibrator:
    """Refit every head from its prior on the records whose outcome resolved strictly before the cutoff.
    A record needs `p_raw` (BREAK, REJECT, NEITHER), `outcome`, `week` and `resolved_ms`."""
    done = [r for r in records if r.get("outcome") in OUTCOMES and int(r["resolved_ms"]) < int(cutoff_ms)]
    arrs = head_arrays(done, "p_raw")
    heads = {}
    for h in HEADS:
        p, y, _ = arrs[h]
        heads[h] = fit_logistic(logit(p), y, priors[h]) if len(p) else \
            {"mean": list(priors[h]["mean"]), "cov": [list(r) for r in priors[h]["cov"]], "n": 0,
             "center": _center(priors[h])}
    return make_calibrator(claim_class, cutoff_ms, heads, priors)


def live_priors(holdout_cal: Calibrator, raw_logits_by_head: Mapping[str, Sequence[float]],
                n_equiv: float = N_EQUIV_PRIOR) -> dict:
    """The held-out fit as the live prior (same centre), its precision reset to n_equiv events of the
    held-out design."""
    return {h: prior_worth(holdout_cal.heads[h]["mean"], raw_logits_by_head.get(h, ()), n_equiv,
                           center=holdout_cal.heads[h].get("center", 0.0)) for h in HEADS}


def _map(head: Mapping[str, Any], lg):
    a, b = head["mean"]
    c = float(head.get("center", 0.0))
    return expit(c + a + b * (np.asarray(lg, dtype=float) - c))


def apply_calibrator(cal: Optional[Calibrator], p3_raw) -> np.ndarray:
    """Published (BREAK, REJECT, NEITHER) from raw; None is the identity."""
    p3_raw = np.asarray(p3_raw, dtype=float)
    if cal is None:
        return probs_from_heads(*heads_from_probs(p3_raw))
    pa, pc = heads_from_probs(p3_raw)
    return probs_from_heads(_map(cal.heads["RESOLVE"], logit(pa)), _map(cal.heads["BREAK_GIVEN_RESOLVE"], logit(pc)))


def correction(cal: Calibrator, head: str, raw_logits) -> dict:
    """The size of the map on a design: mean |p' − p| in pp, and the slope b (reported, not gated: the
    slope of a head with little spread is poorly identified)."""
    lg = np.asarray(raw_logits, dtype=float)
    hd = cal.heads[head]
    if not lg.size:
        lg = np.array([float(hd.get("center", 0.0))])
    shift = float(np.mean(np.abs(_map(hd, lg) - expit(lg)))) * 100
    return {"shift_pp": round(shift, 3), "slope": round(float(hd["mean"][1]), 4)}


def large_correction(cal: Calibrator, raw_logits_by_head: Mapping[str, Sequence[float]]) -> bool:
    for h in HEADS:
        c = correction(cal, h, raw_logits_by_head.get(h, ()))
        if c["shift_pp"] > LARGE_SHIFT_PP:
            return True
    return False


def batch_cutoffs(start_ms: int, end_ms: int) -> list:
    """Cutoffs after start: weekly for WEEKLY_BATCHES weeks, then every LATER_BATCH_WEEKS weeks."""
    wk = 7 * 86_400_000
    out, t, k = [], int(start_ms), 0
    while True:
        t += wk if k < WEEKLY_BATCHES else LATER_BATCH_WEEKS * wk
        k += 1
        if t > end_ms:
            return out
        out.append(t)


# ---- statistics ----------------------------------------------------------------------------------
def clustered_mean(z, clusters, *, zq: float = Z95, iid_var=None) -> dict:
    """Mean of z with a cluster-robust normal interval (95 % by default; None below 5 clusters). The
    standard error never goes below the independent-events one (the sample variance, or `iid_var`
    per event when given): with few clusters the cluster-robust estimate can be far too small."""
    z, g = np.asarray(z, dtype=float), np.asarray(clusters)
    n = z.size
    if n == 0:
        return {"est": None, "lo": None, "hi": None, "n": 0, "clusters": 0}
    m = float(z.mean())
    keys, inv = np.unique(g, return_inverse=True)
    G = keys.size
    out = {"est": m, "lo": None, "hi": None, "n": int(n), "clusters": int(G)}
    if G >= 5:
        s = np.bincount(inv, weights=z - m, minlength=G)
        se = math.sqrt(float(np.sum(s ** 2)) * G / (G - 1)) / n
        v1 = float(np.mean(iid_var)) if iid_var is not None else float(z.var(ddof=1)) if n > 1 else 0.0
        se = max(se, math.sqrt(v1 / n))
        out.update(lo=m - zq * se, hi=m + zq * se)
    return out


def citl(p, y, weeks, *, zq: float = Z95) -> dict:
    """Calibration in the large, in pp: mean(y − p) with a week-clustered interval."""
    p = np.asarray(p, float)
    r = clustered_mean(np.asarray(y, float) - p, weeks, zq=zq, iid_var=p * (1 - p) if p.size else None)
    return {k: (None if v is None else (v * 100 if k in ("est", "lo", "hi") else v)) for k, v in r.items()}


def cal_slope(p, y, weeks) -> dict:
    """Calibration slope: logistic y ~ c + a + b·(logit p − c), with a week-clustered sandwich interval of b,
    and the largest gap (pp) between the fitted curve and the identity at the 10/25/50/75/90 % quantiles."""
    p, y, g = np.asarray(p, float), np.asarray(y, float), np.asarray(weeks)
    if p.size < 10 or np.unique(y).size < 2:
        return {"est": None, "lo": None, "hi": None, "n": int(p.size), "intercept": None, "curve_dev_pp": None}
    c = float(logit(p).mean())
    fit = fit_logistic(logit(p), y, {"mean": [0.0, 1.0], "cov": [[1e4, 0.0], [0.0, 1e4]], "center": c})
    th = np.asarray(fit["mean"])
    X = _design(logit(p) - c)
    q = expit(c + X @ th)
    H = (X * (q * (1 - q))[:, None]).T @ X
    keys, inv = np.unique(g, return_inverse=True)
    S = np.zeros((keys.size, 2))
    np.add.at(S, inv, X * (y - q)[:, None])
    G = keys.size
    qs = np.quantile(logit(p), (0.1, 0.25, 0.5, 0.75, 0.9))
    dev = float(np.max(np.abs(expit(c + th[0] + th[1] * (qs - c)) - expit(qs)))) * 100
    out = {"est": float(th[1]), "lo": None, "hi": None, "n": int(p.size), "intercept": float(th[0]),
           "curve_dev_pp": dev}
    if G >= 5:
        Hi = np.linalg.pinv(H)
        V = Hi @ (S.T @ S) @ Hi * G / (G - 1)
        se = math.sqrt(max(float(V[1, 1]), float(Hi[1, 1]), 0.0))
        if math.isfinite(se) and math.isfinite(float(th[1])):
            out.update(lo=float(th[1]) - Z95 * se, hi=float(th[1]) + Z95 * se)
    return out


def log_loss3(p3, outcomes) -> np.ndarray:
    p3 = _clip(p3)
    idx = np.array([OUTCOMES.index(o) for o in outcomes], dtype=int)
    return -np.log(p3[np.arange(len(idx)), idx])


def paired_log_loss(records: Sequence[Mapping[str, Any]], a: str, b: str, *, zq: float = Z95) -> dict:
    """Mean log loss of b minus a (positive: a better), week-clustered interval."""
    if not records:
        return clustered_mean([], [])
    o = [r["outcome"] for r in records]
    d = log_loss3(np.array([r[b] for r in records]), o) - log_loss3(np.array([r[a] for r in records]), o)
    return clustered_mean(d, [int(r["week"]) for r in records], zq=zq)


# ---- e-process (design §5.1) --------------------------------------------------------------------
def _grid() -> list:
    return [(da, db) for da in E_DELTAS for db in E_DELTAS if (da, db) != (0.0, 0.0)]


def e_increments_arrays(pa, pc, ya, yb) -> np.ndarray:
    """Per event and per grid alternative: the log likelihood ratio of the intercept-shifted alternative
    against the published head probabilities (head B counts only when the event resolved, ya = 1)."""
    grid = np.array(_grid())
    pa, pc = _clip(pa), _clip(pc)
    ya, yb = np.asarray(ya, dtype=float)[:, None], np.asarray(yb, dtype=float)[:, None]
    la, lc = logit(pa)[:, None], logit(pc)[:, None]

    def llr(lp, y, d):
        q = _clip(expit(lp + d))
        p = _clip(expit(lp))
        return y * (np.log(q) - np.log(p)) + (1 - y) * (np.log1p(-q) - np.log1p(-p))

    return llr(la, ya, grid[None, :, 0]) + ya * llr(lc, yb, grid[None, :, 1])


def e_increments(records: Sequence[Mapping[str, Any]], key: str = "p_pub") -> np.ndarray:
    """e_increments_arrays on records (in order) with probabilities under `key`."""
    if not records:
        return np.zeros((0, len(_grid())))
    pa, pc = heads_from_probs(np.array([r[key] for r in records], dtype=float))
    ya = np.array([head_targets(r["outcome"])[0] for r in records], dtype=float)
    yb = np.array([1.0 if r["outcome"] == "BREAK" else 0.0 for r in records], dtype=float)
    return e_increments_arrays(pa, pc, ya, yb)


def e_path(inc: np.ndarray) -> np.ndarray:
    """E_t after each record: Σ_j π_j M_j(t) with change points s_j = j·E_BLOCK, π_j = 1/((j+1)(j+2)),
    M_j the mean over the grid of the likelihood ratios from s_j; blocks not yet started count as 1.
    Under conditional calibration E is a test martingale, so P(sup E ≥ 10) ≤ 0.1 (Ville)."""
    T = inc.shape[0]
    if T == 0:
        return np.zeros(0)
    S = np.vstack([np.zeros((1, inc.shape[1])), np.cumsum(inc, axis=0)])        # S[t] after t records
    J = (T - 1) // E_BLOCK + 1
    out = np.zeros(T)
    for j in range(J):
        s = j * E_BLOCK
        pi = 1.0 / ((j + 1) * (j + 2))
        seg = S[s + 1:] - S[s]
        m = np.max(seg, axis=1, keepdims=True)
        mj = np.exp(m[:, 0]) * np.mean(np.exp(seg - m), axis=1)
        out[s:] += pi * mj
    jt = np.arange(T) // E_BLOCK + 1                                             # blocks started by record t
    return out + 1.0 / (jt + 1)                                                  # Σ_{j≥jt} π_j, not yet started


def e_value(records: Sequence[Mapping[str, Any]], key: str = "p_pub") -> float:
    path = e_path(e_increments(records, key))
    return float(path[-1]) if path.size else 1.0


# ---- input drift (design §5.4; reported, never a state change) ---------------------------------
INPUT_BLOCK_WEEKS = 8
INPUT_RANGE = (0.025, 0.975)


def _block_stats(rows: Sequence[Mapping[str, Any]], weeks: Sequence[int]) -> dict:
    wk = set(int(w) for w in weeks)
    sel = [r for r in rows if int(r["week"]) in wk]
    return {"median_sigma": float(np.median([r["sigma"] for r in sel])) if sel else None,
            "mean_b0_break": float(np.mean([r["p_b0"][0] for r in sel])) if sel else None,
            "rate": len(sel) / max(len(wk), 1)}


def input_drift(reference: Sequence[Mapping[str, Any]], recent: Sequence[Mapping[str, Any]], *,
                ref_weeks: Sequence[int], recent_weeks: Sequence[int]) -> list:
    """Warnings for the last INPUT_BLOCK_WEEKS weeks against the held-out 8-week blocks: median PIT σ,
    mean B0 BREAK probability (position) and events per week outside the blocks' 2.5–97.5 % range.
    Rows carry `week`, `sigma` and `p_b0`; every issued event counts, resolved or not."""
    rw = sorted(set(int(w) for w in ref_weeks))
    blocks = [rw[i:i + INPUT_BLOCK_WEEKS] for i in range(0, len(rw) - INPUT_BLOCK_WEEKS + 1, INPUT_BLOCK_WEEKS)]
    if len(blocks) < 5:
        return []
    ref = [_block_stats(reference, b) for b in blocks]
    cur = _block_stats(recent, recent_weeks)
    out = []
    for k in ("median_sigma", "mean_b0_break", "rate"):
        vals = [x[k] for x in ref if x[k] is not None]
        if cur[k] is None or len(vals) < 5:
            continue
        lo, hi = np.quantile(vals, INPUT_RANGE)
        if cur[k] < lo or cur[k] > hi:
            out.append(f"{k}:{cur[k]:.4g} outside [{lo:.4g}, {hi:.4g}]")
    return out


# ---- monitor snapshot ------------------------------------------------------------------------------
@dataclass(frozen=True)
class Monitors:
    n_live: int                       # resolved live records of the class (whole version)
    n_epoch: int                      # resolved records since the current epoch began
    e_value: float                    # e-process of the current epoch
    e_max: float
    roll_citl: Mapping[str, Any]      # head -> citl over the last ROLL_N records
    live_citl: Mapping[str, Any]      # head -> citl over all live records
    live_slope: Mapping[str, Any]     # head -> slope over all live records
    epoch_citl: Mapping[str, Any]     # head -> citl since the epoch began
    roll_ll_vs_b0: Mapping[str, Any]  # paired log loss, B0 minus published, last ROLL_N
    epoch_ll_vs_b0: Mapping[str, Any]
    large_correction: bool
    input_warnings: tuple = ()

    def to_dict(self) -> dict:
        return asdict(self)


def monitors(live: Sequence[Mapping[str, Any]], *, epoch_start: int = 0, cal: Optional[Calibrator] = None,
             raw_logits_by_head: Optional[Mapping[str, Sequence[float]]] = None,
             input_warnings: Sequence[str] = ()) -> Monitors:
    """Monitor statistics from the resolved live records of one class, in issue order. Records carry
    p_pub (published, shown or not), p_ref (raw under the frozen held-out calibrator; the e-process
    uses it so that the batched calibrator cannot absorb a drift before it is detected; p_pub when
    absent), p_b0, outcome and week. `epoch_start` indexes the record where
    the current epoch began (the version start or the last state change into or out of FALLBACK)."""
    ep = list(live[epoch_start:])
    key = E_KEY if ep and E_KEY in ep[0] else "p_pub"
    path = e_path(e_increments(ep, key))
    roll = list(live[-ROLL_N:])
    ha, hr, he = head_arrays(live, "p_pub"), head_arrays(roll, "p_pub"), head_arrays(ep, "p_pub")
    return Monitors(
        n_live=len(live), n_epoch=len(ep),
        e_value=float(path[-1]) if path.size else 1.0, e_max=float(path.max()) if path.size else 1.0,
        roll_citl={h: citl(*hr[h], zq=ROLL_Z) for h in HEADS}, live_citl={h: citl(*ha[h]) for h in HEADS},
        live_slope={h: cal_slope(*ha[h]) for h in HEADS}, epoch_citl={h: citl(*he[h]) for h in HEADS},
        roll_ll_vs_b0=paired_log_loss(roll, "p_pub", "p_b0", zq=ROLL_Z), epoch_ll_vs_b0=paired_log_loss(ep, "p_pub", "p_b0"),
        large_correction=bool(cal is not None and large_correction(cal, raw_logits_by_head or {})),
        input_warnings=tuple(input_warnings))


# ---- held-out gate (design §2) -------------------------------------------------------------------
def holdout_gate(records: Sequence[Mapping[str, Any]]) -> dict:
    """The one-shot held-out check of one class. Records carry p_raw, p_pub (walk-forward published:
    the calibrator at each record fitted only on held-out outcomes resolved before it), p_b0, outcome
    and week. Passed when, for each head, the walk-forward published |intercept| ≤ 5 pp and its fitted
    recalibration curve stays within 7.5 pp of the identity, the raw |intercept| ≤ 10 pp, and at least
    20 weeks are present."""
    pub, raw = head_arrays(records, "p_pub"), head_arrays(records, "p_raw")
    heads, ok = {}, len({int(r["week"]) for r in records}) >= HOLDOUT_MIN_WEEKS
    for h in HEADS:
        c, s, cr = citl(*pub[h]), cal_slope(*pub[h]), citl(*raw[h])
        hp = (c["est"] is not None and abs(c["est"]) <= HOLDOUT_CITL_PP and s["curve_dev_pp"] is not None
              and s["curve_dev_pp"] <= HOLDOUT_CURVE_PP and abs(cr["est"]) <= HOLDOUT_RAW_CITL_PP)
        heads[h] = {"citl": c, "slope": s, "raw_citl": cr, "passed": bool(hp)}
        ok = ok and hp
    return {"passed": bool(ok), "n": len(records), "weeks": len({int(r["week"]) for r in records}),
            "heads": heads, "ll_vs_b0": paired_log_loss(records, "p_pub", "p_b0")}


BEATS_B0_Z = 1.644854           # M1 is published when gain − BEATS_B0_Z·SE > 0 (one-sided 95 %)


def beats_b0(gate_m1: Mapping[str, Any]) -> bool:
    """M1 is published only when the week-clustered lower bound of its log-loss gain over B0 is above 0;
    otherwise the calibrated B0 is published and no level effect is claimed (FORECAST_LAYER §6)."""
    ll = gate_m1.get("ll_vs_b0") or {}
    if ll.get("lo") is None:
        return False
    se = (ll["est"] - ll["lo"]) / Z95
    return ll["est"] - BEATS_B0_Z * se > 0


# ---- state machine (design §7) -------------------------------------------------------------------
STATES = ("HIST", "L3_HISTORY_BACKED", "L3_LIVE", "FALLBACK", "OFF")


@dataclass(frozen=True)
class Health:
    data_fresh: bool = True
    parity_ok: bool = True
    journal_ok: bool = True
    coverage_ok: bool = True

    def ok(self) -> bool:
        return self.data_fresh and self.parity_ok and self.journal_ok and self.coverage_ok

    def faults(self) -> tuple:
        return tuple(k for k, v in asdict(self).items() if not v)


@dataclass(frozen=True)
class StateRecord:
    state: str
    since_ms: int
    epoch_start: int = 0              # index of the first resolved live record of the current epoch
    fallbacks: int = 0
    before_off: Optional[str] = None
    reason: str = "start"
    model_version: str = ""
    version: str = LR_STATE_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def initial_state(*, holdout_passed: bool, model_version: str, now_ms: int) -> StateRecord:
    return StateRecord("L3_HISTORY_BACKED" if holdout_passed else "HIST", int(now_ms),
                       reason="holdout_passed" if holdout_passed else "holdout_not_passed",
                       model_version=model_version)


def drift_reasons(m: Monitors) -> list:
    out = []
    if m.e_value >= E_THRESHOLD:
        out.append("e_process")
    for h in HEADS:
        c = m.roll_citl[h]
        if c["n"] >= ROLL_N // 2 and c["lo"] is not None and (c["lo"] > ROLL_CITL_BAND_PP or c["hi"] < -ROLL_CITL_BAND_PP):
            out.append(f"rolling_intercept:{h}")
    ll = m.roll_ll_vs_b0
    if ll.get("clusters", 0) >= ROLL_LL_MIN_WEEKS and ll.get("hi") is not None and ll["hi"] < 0:
        out.append("worse_than_b0")
    if m.large_correction:
        out.append("large_correction")
    return out


def live_ok(m: Monitors) -> bool:
    for h in HEADS:
        c, s = m.live_citl[h], m.live_slope[h]
        if c["est"] is None or abs(c["est"]) > LIVE_CITL_PP:
            return False
        if s["curve_dev_pp"] is None or s["curve_dev_pp"] > LIVE_CURVE_PP:
            return False
    return True


def recovered(m: Monitors) -> bool:
    if m.n_epoch < RETURN_MIN_EVENTS or m.e_value >= 1.0:
        return False
    for h in HEADS:
        c = m.epoch_citl[h]
        if c["est"] is None or abs(c["est"]) > RETURN_CITL_PP:
            return False
    ll = m.epoch_ll_vs_b0
    return not (ll.get("hi") is not None and ll["hi"] < 0)


def next_state(prev: StateRecord, *, health: Health, mon: Optional[Monitors], now_ms: int) -> StateRecord:
    """One deterministic step. Health is checked at every call (OFF at once); the model rules are
    evaluated when `mon` is given (at each batch cutoff). `mon.epoch_start` follows `prev.epoch_start`."""
    if not health.ok():
        if prev.state == "OFF":
            return prev
        return replace(prev, state="OFF", since_ms=now_ms, before_off=prev.state,
                       reason="health:" + ",".join(health.faults()))
    if prev.state == "OFF":
        return replace(prev, state=prev.before_off or "HIST", since_ms=now_ms, before_off=None, reason="health_ok")
    if mon is None or prev.state == "HIST":
        return prev
    if prev.state in ("L3_HISTORY_BACKED", "L3_LIVE"):
        why = drift_reasons(mon)
        if why:
            return replace(prev, state="FALLBACK", since_ms=now_ms, epoch_start=mon.n_live,
                           fallbacks=prev.fallbacks + 1, reason="drift:" + ",".join(why))
        if prev.state == "L3_HISTORY_BACKED" and mon.n_live >= LIVE_FLOOR and live_ok(mon):
            return replace(prev, state="L3_LIVE", since_ms=now_ms, reason="live_floor_reached")
        return prev
    if prev.state == "FALLBACK":
        if prev.fallbacks >= MAX_FALLBACKS or not recovered(mon) or drift_reasons(mon):
            return prev
        to = "L3_LIVE" if mon.n_live >= LIVE_FLOOR and live_ok(mon) else "L3_HISTORY_BACKED"
        return replace(prev, state=to, since_ms=now_ms, epoch_start=mon.n_live, reason="recovered")
    return prev


# ---- challengers (design §6) -------------------------------------------------------------------
def challenger_look(paired: Sequence[Mapping[str, Any]]) -> Optional[dict]:
    """At a look (150, 300, 450, 600 paired resolved events) the promotion verdict for a challenger whose
    records carry p_pub (champion, published) and p_chal (challenger, its own walk-forward calibration).
    Promoted when the week-clustered 95 % interval of the log-loss gain is above 0 and the challenger's
    calibration is within the live tolerance. None between looks."""
    n = len(paired)
    if n < CHALLENGER_MIN_PAIRED or n % CHALLENGER_LOOK_EVERY or n > CHALLENGER_MAX_PAIRED:
        return None
    gain = paired_log_loss(paired, "p_chal", "p_pub")
    ch = head_arrays(paired, "p_chal")
    cal_ok = all(citl(*ch[h])["est"] is not None and abs(citl(*ch[h])["est"]) <= LIVE_CITL_PP for h in HEADS)
    promoted = gain.get("lo") is not None and gain["lo"] > 0 and cal_ok
    return {"n": n, "gain": gain, "calibration_ok": cal_ok, "promoted": bool(promoted),
            "retired": bool(not promoted and n >= CHALLENGER_MAX_PAIRED)}


# ---- the display contract for F2 (design §9) -----------------------------------------------------
WORDING = {"HIST": "lr_hist_l2", "L3_HISTORY_BACKED": "lr_b_holdout", "L3_LIVE": "lr_b_live",
           "FALLBACK": "lr_fallback_b0", "OFF": "lr_off"}


def display_contract(st: StateRecord, *, published_model: str, calibrator_version: Optional[str],
                     holdout_line: Optional[Mapping[str, Any]], live_line: Optional[Mapping[str, Any]]) -> dict:
    """What the display layer (F2) reads for one class: the state, the template id, which probabilities
    to print and which accuracy line. `published_model` is "M1" or "B0" (the held-out choice);
    FALLBACK always prints the B0 / generic-race probabilities, OFF prints no number."""
    probs = {"HIST": None, "OFF": None, "FALLBACK": "B0_GENERIC"}.get(st.state, published_model)
    return {"version": LR_STATE_VERSION, "state": st.state, "since_ms": st.since_ms, "reason": st.reason,
            "template": WORDING[st.state], "probabilities": probs,
            "level_effect_claimed": bool(probs == "M1"),
            "calibrator_version": calibrator_version if probs in ("M1", "B0") else None,
            "accuracy_line": {"L3_HISTORY_BACKED": "holdout", "L3_LIVE": "live"}.get(st.state),
            "holdout_line": holdout_line if st.state in ("L3_HISTORY_BACKED", "L3_LIVE") else None,
            "live_line": live_line if st.state in ("L3_HISTORY_BACKED", "L3_LIVE") else None}
