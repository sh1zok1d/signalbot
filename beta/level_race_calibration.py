"""Level race calibration, gates, monitors and display state (ОПГ-2 track F3; pure, no database).

Implements the [F3] parts of `docs/research/LEVEL_RACE_FORECAST_V1_DESIGN.md` §7, §8a, §11b (F1) with the
numbers of `docs/research/LEVEL_RACE_CALIBRATION_MONITORING_V1_DESIGN.md`:

- the three race outcomes as two heads: R (a barrier within 4h; 1 − P(NEITHER)) and B (BREAK | resolved;
  UP | resolved on the generic stream);
- per head a Bayesian logistic recalibration logit p' = a_class + b·logit p with class intercepts
  GENERIC / LEVEL_T0 / LEVEL_T15 and a shared slope, MAP + Laplace, refit on outcomes resolved strictly
  before each batch cutoff (weekly, then every 4 weeks), versioned;
- the held-out gates G0–G3, the live floor, the drift monitors D0–D3 and the return rule;
- the display state machine HIST / L3_HISTORY_BACKED / L3_LIVE / FALLBACK / OFF with the mode switch
  HIST_ONLY / MODEL (FORECAST_LAYER §6a) and the FALLBACK-only-if-it-passes-G2 rule (§11b).

Every number here is a design constant fixed before any real outcome is read; the study that chose
them runs on synthetic data only (`scripts/research/level_race_calibration_sim.py`).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping, Optional, Sequence

import numpy as np

LR_CAL_VERSION = "LEVEL_RACE_CAL_V1"
LR_STATE_VERSION = "LEVEL_RACE_STATE_V1"
OUTCOMES = ("BREAK", "REJECT", "NEITHER")       # generic stream: UP_FIRST, DOWN_FIRST, NEITHER in this order
HEADS = ("R", "B")
CAL_CLASSES = ("GENERIC", "LEVEL_T0", "LEVEL_T15")
P_CLIP = 1e-4
Z95 = 1.959964

# ---- calibrator [F3] ----------------------------------------------------------------------------
PRIOR_M_A, PRIOR_S_A = 0.0, 0.5         # a_GENERIC ~ N(0, 0.5²)
PRIOR_M_B, PRIOR_S_B = 1.0, 0.25        # b ~ N(1, 0.25²)
PRIOR_S_LEVEL = 1.0                     # a_LEVEL − a_GENERIC ~ N(0, s²) default (dev-informed, design §3.2)
PRIOR_S_LEVEL_BY_CASE = {"A": 0.5, "B": 1.0}   # level rows feed M1 raw (A) or G1@event raw (B)
PRIOR_S_SLOPE_LEVEL = 0.25              # b_LEVEL − b_GENERIC ~ N(0, 0.25²); 0 = one shared slope (design §3.3)
SHARED_SLOPE_TIE = 1e-4                 # the SD used for "0" (a numerically tied slope)
N_EQUIV_PRIOR = 150                     # live prior: the held-out posterior worth 150 events per class
GENERIC_ROW_WEIGHT = 1 / 16             # 4 overlapping hourly anchors × 4 pairs share one 4h path
WEEKLY_BATCHES = 12
LATER_BATCH_WEEKS = 4
ISOTONIC_MIN_EVENTS = 300               # no non-parametric map below this; V1 has none

# ---- gates [F3] ---------------------------------------------------------------------------------
G0_MIN_EVENTS = 200
G1_MAX_LL_EXCESS = 0.02                 # nats: upper 95 % end of LL_published − LL_B0 (F1 planning 0.01; design §2)
G2_CITL_PP = 5.0                        # per outcome |CITL| ≤ 5 pp …
G2_CI_PP = 10.0                         # … and its 95 % interval inside ±10 pp
G3_SLOPE_BAND = (0.8, 1.25)             # per head, the slope's 95 % interval overlaps this band
LIVE_FLOOR = 150

# ---- drift [F3] ---------------------------------------------------------------------------------
D0_STALE_MINUTES = 10
D1_LAMBDAS = (-0.5, -0.25, 0.25, 0.5)
D1_OUTCOME_THRESHOLD = 30.0             # per outcome; three outcomes share the ≤ 0.1 Ville budget (design §5.1)
ROLL_N = 150                            # F1 planning 100 (design §5.2)
D2_PP = 10.0
D2_Z = 3.0                              # 99.7 % interval, iid floor (F1 planning 95 %; design §5.2)
D3_Z = 3.0
D3_MIN_WEEKS = 8
RETURN_MIN_EVENTS = 50
RETURN_E_MAX = 1.0                      # epoch e-value below 1 to return (F1 draft: ≤ 10; design §5.4)
MAX_DRIFT_EXITS = 2                     # the second drift exit of a version is final for it

# ---- generic-stream drift monitor [F3] (design §5.6) -------------------------------------------
GEN_THRESHOLD = 30.0                    # per outcome, change-point mixture e-process on p_ref with the margin
GEN_BLOCK = 40                          # change points every 40 independent windows (≈ 1 week)
GEN_RETURN_MIN = 50                     # the frozen return rule, applied to the generic stream first
GEN_ROLL_WEEKS = 0                      # rolling rule OFF (tested, rejected: design §5.6); 6 = the tested variant …
GEN_ROLL_PP = 5.0                       # … per outcome |CITL vs p_ref| beyond margin + 5 pp …
GEN_ROLL_Z = 3.0                        # … with its week-clustered 99.7 % interval (iid floor) beyond the margin
GEN_ALARM_TARGET = "HIST"               # architect 2026-10-08: never FALLBACK (FALLBACK is the generic model)
LEVEL_DRIFT_TARGET = "FALLBACK"         # level-stream drift: FALLBACK while it passes G2, else HIST

# ---- challengers [F3] ---------------------------------------------------------------------------
CHALLENGER_MIN_PAIRED = 150
CHALLENGER_LOOK_EVERY = 150
CHALLENGER_MAX_PAIRED = 600
CHALLENGER_MAX_CONCURRENT = 2

MODES = ("HIST_ONLY", "MODEL")
STATES = ("HIST", "L3_HISTORY_BACKED", "L3_LIVE", "FALLBACK", "OFF")


# ---- probabilities --------------------------------------------------------------------------------
def _clip(p):
    return np.clip(np.asarray(p, dtype=float), P_CLIP, 1 - P_CLIP)


def logit(p):
    p = _clip(p)
    return np.log(p) - np.log1p(-p)


def expit(x):
    return 1.0 / (1.0 + np.exp(-np.clip(np.asarray(x, dtype=float), -50, 50)))


def heads_from_probs(p3) -> tuple:
    """(P(BREAK), P(REJECT), P(NEITHER)) → (P(resolve), P(BREAK | resolve))."""
    p3 = np.asarray(p3, dtype=float)
    res = p3[..., 0] + p3[..., 1]
    cond = np.where(res > 0, p3[..., 0] / np.where(res > 0, res, 1.0), 0.5)
    return _clip(1.0 - p3[..., 2]), _clip(cond)


def probs_from_heads(p_res, p_cond) -> np.ndarray:
    p_res, p_cond = np.asarray(p_res, dtype=float), np.asarray(p_cond, dtype=float)
    return np.stack([p_res * p_cond, p_res * (1 - p_cond), 1 - p_res], axis=-1)


def head_targets(outcome: str) -> tuple:
    """(y_R, y_B or None)."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    if outcome == "NEITHER":
        return 0, None
    return 1, int(outcome == "BREAK")


def head_arrays(records: Sequence[Mapping[str, Any]], key: str) -> dict:
    """Per head: (probabilities, targets, week ids) under `key`; head B on resolved records only."""
    if not records:
        e = (np.zeros(0), np.zeros(0), np.zeros(0, int))
        return {"R": e, "B": e}
    p3 = np.array([r[key] for r in records], dtype=float).reshape(-1, 3)
    pa, pc = heads_from_probs(p3)
    ya = np.array([0.0 if r["outcome"] == "NEITHER" else 1.0 for r in records])
    yb = np.array([1.0 if r["outcome"] == "BREAK" else 0.0 for r in records])
    wk = np.array([int(r["week"]) for r in records], dtype=int)
    res = ya == 1
    return {"R": (pa, ya, wk), "B": (pc[res], yb[res], wk[res])}


def outcome_arrays(records: Sequence[Mapping[str, Any]], key: str) -> dict:
    """Per outcome (one against the rest): (probabilities, targets, week ids)."""
    p3 = np.array([r[key] for r in records], dtype=float).reshape(-1, 3)
    wk = np.array([int(r["week"]) for r in records], dtype=int)
    return {o: (p3[:, k], np.array([1.0 if r["outcome"] == o else 0.0 for r in records]), wk)
            for k, o in enumerate(OUTCOMES)}


# ---- hierarchical calibrator (design §3) ------------------------------------------------------------
def prior_for_cases(case_t0: str, case_t15: str, s_slope_level: Optional[float] = None) -> dict:
    """The held-out identity prior per head once the §11b case of each landmark is known (it is decided
    on raw outputs, before the prequential pass): s_level from PRIOR_S_LEVEL_BY_CASE per class."""
    s = (PRIOR_S_LEVEL_BY_CASE[case_t0], PRIOR_S_LEVEL_BY_CASE[case_t15])
    return {h: identity_prior(s, s_slope_level) for h in HEADS}


N_PARAMS = 5                            # θ = (a_GENERIC, a_LEVEL_T0, a_LEVEL_T15, b_GENERIC, b_LEVEL)


def identity_prior(s_level=None, s_slope_level: Optional[float] = None) -> dict:
    """Gaussian prior on θ = (a_G, a_T0, a_T15, b_G, b_L): a_G ~ N(m_a, s_a²), b_G ~ N(m_b, s_b²),
    a_level − a_G ~ N(0, s_level²) independently per level class (`s_level` a number or a pair
    (s_T0, s_T15)), b_L − b_G ~ N(0, s_slope_level²) (both level classes share b_L; 0 ties it to b_G)."""
    s_level = PRIOR_S_LEVEL if s_level is None else s_level
    s0, s15 = (s_level, s_level) if np.isscalar(s_level) else tuple(s_level)
    s_sl = PRIOR_S_SLOPE_LEVEL if s_slope_level is None else s_slope_level
    va, vb, vs = PRIOR_S_A ** 2, PRIOR_S_B ** 2, max(s_sl, SHARED_SLOPE_TIE) ** 2
    cov = np.zeros((N_PARAMS, N_PARAMS))
    cov[:3, :3] = va
    cov[1, 1] += s0 ** 2
    cov[2, 2] += s15 ** 2
    cov[3:, 3:] = vb
    cov[4, 4] += vs
    return {"mean": [PRIOR_M_A, PRIOR_M_A, PRIOR_M_A, PRIOR_M_B, PRIOR_M_B], "cov": cov.tolist()}


def _design(lg, cls_idx) -> np.ndarray:
    cls_idx = np.asarray(cls_idx, dtype=int)
    X = np.zeros((len(lg), N_PARAMS))
    X[np.arange(len(lg)), cls_idx] = 1.0
    X[:, 3] = np.where(cls_idx == 0, lg, 0.0)
    X[:, 4] = np.where(cls_idx == 0, 0.0, lg)
    return X


def fit_head(raw_p, y, cls, prior: Mapping[str, Any], *, weights=None, iters: int = 100) -> dict:
    """MAP of logit p' = a_class + b_(GENERIC or LEVEL)·logit p under the Gaussian prior; Laplace covariance;
    weighted rows."""
    raw_p, y = np.asarray(raw_p, dtype=float), np.asarray(y, dtype=float)
    idx = np.array([CAL_CLASSES.index(c) for c in cls], dtype=int)
    w = np.ones(len(y)) if weights is None else np.asarray(weights, dtype=float)
    m0 = np.asarray(prior["mean"], dtype=float)
    P0 = np.linalg.inv(np.asarray(prior["cov"], dtype=float))
    X = _design(logit(raw_p), idx)
    th = m0.copy()
    for _ in range(iters):
        q = expit(X @ th)
        g = X.T @ (w * (y - q)) - P0 @ (th - m0)
        H = (X * (w * q * (1 - q))[:, None]).T @ X + P0
        step = np.linalg.solve(H, g)
        th = th + step
        if float(np.max(np.abs(step))) < 1e-10:
            break
    q = expit(X @ th)
    H = (X * (w * q * (1 - q))[:, None]).T @ X + P0
    n = {c: int(np.sum(idx == k)) for k, c in enumerate(CAL_CLASSES)}
    return {"mean": th.tolist(), "cov": np.linalg.inv(H).tolist(), "n": n}


@dataclass(frozen=True)
class Calibrator:
    cutoff_ms: int
    heads: Mapping[str, Mapping[str, Any]]      # head -> {"mean": θ, "cov": 4×4, "n": per class}
    priors: Mapping[str, Mapping[str, Any]]     # head -> prior
    version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=float).encode()).hexdigest()


def make_calibrator(cutoff_ms: int, heads: Mapping, priors: Mapping) -> Calibrator:
    body = {"v": LR_CAL_VERSION, "cutoff_ms": int(cutoff_ms),
            "heads": {h: {"mean": [round(x, 12) for x in heads[h]["mean"]], "n": heads[h]["n"]} for h in HEADS},
            "priors": {h: {"mean": [round(x, 12) for x in priors[h]["mean"]],
                           "cov": [[round(x, 12) for x in r] for r in priors[h]["cov"]]} for h in HEADS}}
    return Calibrator(int(cutoff_ms), heads, priors, f"{LR_CAL_VERSION}:{_digest(body)[:16]}")


def prior_calibrator(priors: Mapping[str, Mapping[str, Any]], cutoff_ms: int = 0) -> Calibrator:
    return make_calibrator(cutoff_ms, {h: {"mean": list(priors[h]["mean"]), "cov": priors[h]["cov"],
                                           "n": {c: 0 for c in CAL_CLASSES}} for h in HEADS}, priors)


def _row_weight(r: Mapping[str, Any]) -> float:
    return float(r.get("weight", GENERIC_ROW_WEIGHT if r["cal_class"] == "GENERIC" else 1.0))


def fit_calibrator(records: Sequence[Mapping[str, Any]], priors: Mapping[str, Mapping[str, Any]], *,
                   cutoff_ms: int) -> Calibrator:
    """Refit both heads from their priors on the records resolved strictly before `cutoff_ms`. A record
    carries `cal_class` (GENERIC / LEVEL_T0 / LEVEL_T15), `p_raw` (three outcomes), `outcome`,
    `resolved_ms` and optionally `weight` (default GENERIC_ROW_WEIGHT for GENERIC rows, else 1)."""
    done = [r for r in records if r.get("outcome") in OUTCOMES and int(r["resolved_ms"]) < int(cutoff_ms)]
    if not done:
        return prior_calibrator(priors, cutoff_ms)
    p3 = np.array([r["p_raw"] for r in done], dtype=float)
    pa, pc = heads_from_probs(p3)
    ya = np.array([0.0 if r["outcome"] == "NEITHER" else 1.0 for r in done])
    yb = np.array([1.0 if r["outcome"] == "BREAK" else 0.0 for r in done])
    cls = [r["cal_class"] for r in done]
    w = np.array([_row_weight(r) for r in done])
    res = ya == 1
    heads = {"R": fit_head(pa, ya, cls, priors["R"], weights=w)}
    if res.any():
        heads["B"] = fit_head(pc[res], yb[res], [c for c, k in zip(cls, res) if k], priors["B"], weights=w[res])
    else:
        heads["B"] = {"mean": list(priors["B"]["mean"]), "cov": priors["B"]["cov"], "n": {c: 0 for c in CAL_CLASSES}}
    return make_calibrator(cutoff_ms, heads, priors)


def _head_map(head: Mapping[str, Any], cal_class: str, raw_p) -> np.ndarray:
    th = head["mean"]
    k = CAL_CLASSES.index(cal_class)
    return expit(th[k] + th[3 if k == 0 else 4] * logit(raw_p))


def apply_calibrator(cal: Optional[Calibrator], p3_raw, cal_class: str) -> np.ndarray:
    """Published three outcomes from raw ones with the intercept of `cal_class` (case B and the
    fallback model pass "GENERIC"); None is the identity."""
    p3_raw = np.asarray(p3_raw, dtype=float)
    pa, pc = heads_from_probs(p3_raw)
    if cal is None:
        return probs_from_heads(pa, pc)
    return probs_from_heads(_head_map(cal.heads["R"], cal_class, pa), _head_map(cal.heads["B"], cal_class, pc))


def class_information(records: Sequence[Mapping[str, Any]], head: str, theta) -> dict:
    """Mean per-event Fisher information of θ for each class's rows at θ (raw probabilities only)."""
    out = {}
    th = np.asarray(theta, dtype=float)
    for c in CAL_CLASSES:
        rows = [r for r in records if r["cal_class"] == c and (head == "R" or r["outcome"] in ("BREAK", "REJECT"))]
        if not rows:
            continue
        pa, pc = heads_from_probs(np.array([r["p_raw"] for r in rows], dtype=float))
        p = pa if head == "R" else pc
        X = _design(logit(p), [CAL_CLASSES.index(c)] * len(p))
        q = expit(X @ th)
        out[c] = (X * (q * (1 - q))[:, None]).T @ X / len(p)
    return out


def live_prior(holdout_cal: Calibrator, holdout_records: Sequence[Mapping[str, Any]],
               n_equiv: float = N_EQUIV_PRIOR) -> dict:
    """The held-out posterior as the live prior: its mean, and a precision of n_equiv events of each
    class's held-out design (FORECAST_LAYER §5: 100–200), plus 0.1 % of the identity prior's precision
    so that a parameter no class informs stays proper. Outcomes enter only through the mean."""
    out = {}
    floor = np.linalg.inv(np.asarray(identity_prior()["cov"]))
    for h in HEADS:
        th = holdout_cal.heads[h]["mean"]
        info = class_information(holdout_records, h, th)
        P = sum((n_equiv * I for I in info.values()), np.zeros((N_PARAMS, N_PARAMS))) + 1e-3 * floor
        out[h] = {"mean": list(th), "cov": np.linalg.inv(P).tolist()}
    return out


def calibrator_at(t_ms: int, versions: Sequence[Calibrator], prior: Optional[Calibrator] = None) -> Optional[Calibrator]:
    """The calibrator that applies to a forecast issued at t_ms: the version with the latest cutoff
    ≤ t_ms (a cutoff-c version is fitted on outcomes resolved before c, so it is usable from c on);
    `prior` (or None) before the first cutoff. The held-out pass and live both call this."""
    best = prior
    for v in versions:
        if v.cutoff_ms <= int(t_ms) and (best is None or best is prior or v.cutoff_ms > best.cutoff_ms):
            best = v
    return best


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


# ---- statistics ------------------------------------------------------------------------------------
def clustered_mean(z, clusters, *, zq: float = Z95, iid_var=None) -> dict:
    """Mean of z with a cluster-robust normal interval (None below 5 clusters). The standard error
    never goes below the independent-events one (the sample variance, or `iid_var` per row)."""
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
        v1 = float(np.mean(iid_var)) if iid_var is not None else (float(z.var(ddof=1)) if n > 1 else 0.0)
        se = max(se, math.sqrt(v1 / n))
        out.update(lo=m - zq * se, hi=m + zq * se)
    return out


def citl(p, y, weeks, *, zq: float = Z95) -> dict:
    """Calibration in the large in pp: mean(y − p) with a week-clustered interval (iid floor)."""
    p = np.asarray(p, float)
    r = clustered_mean(np.asarray(y, float) - p, weeks, zq=zq, iid_var=p * (1 - p) if p.size else None)
    return {k: (v * 100 if k in ("est", "lo", "hi") and v is not None else v) for k, v in r.items()}


def cal_slope(p, y, weeks) -> dict:
    """Recalibration logit P(y) = a + b·logit p (F1 §6), with a week-clustered sandwich interval of b."""
    p, y, g = np.asarray(p, float), np.asarray(y, float), np.asarray(weeks)
    out = {"est": None, "lo": None, "hi": None, "n": int(p.size), "a": None}
    if p.size < 10 or np.unique(y).size < 2:
        return out
    X = np.column_stack([np.ones(p.size), logit(p)])
    th = np.array([0.0, 1.0])
    for _ in range(100):
        q = expit(X @ th)
        H = (X * (q * (1 - q))[:, None]).T @ X + np.eye(2) * 1e-6
        step = np.linalg.lstsq(H, X.T @ (y - q), rcond=None)[0]
        th = th + step
        if float(np.max(np.abs(step))) < 1e-10 or not np.all(np.isfinite(th)):
            break
    if not np.all(np.isfinite(th)):
        return out
    q = expit(X @ th)
    H = (X * (q * (1 - q))[:, None]).T @ X
    keys, inv = np.unique(g, return_inverse=True)
    S = np.zeros((keys.size, 2))
    np.add.at(S, inv, X * (y - q)[:, None])
    G = keys.size
    out.update(est=float(th[1]), a=float(th[0]))
    if G >= 5:
        Hi = np.linalg.pinv(H)
        V = Hi @ (S.T @ S) @ Hi * G / (G - 1)
        se = math.sqrt(max(float(V[1, 1]), float(Hi[1, 1]), 0.0))
        if math.isfinite(se):
            out.update(lo=float(th[1]) - Z95 * se, hi=float(th[1]) + Z95 * se)
    return out


def log_loss3(p3, outcomes) -> np.ndarray:
    p3 = _clip(p3)
    idx = np.array([OUTCOMES.index(o) for o in outcomes], dtype=int)
    return -np.log(p3[np.arange(len(idx)), idx])


def paired_log_loss(records: Sequence[Mapping[str, Any]], a: str, b: str, *, zq: float = Z95) -> dict:
    """Mean of LL(b) − LL(a) (positive: a better), week-clustered interval."""
    if not records:
        return clustered_mean([], [])
    o = [r["outcome"] for r in records]
    d = log_loss3(np.array([r[b] for r in records]), o) - log_loss3(np.array([r[a] for r in records]), o)
    return clustered_mean(d, [int(r["week"]) for r in records], zq=zq)


# ---- held-out gates G0–G3 (design §2) ----------------------------------------------------------------
def _g2_pass(c: Mapping[str, Any]) -> bool:
    return c["lo"] is not None and abs(c["est"]) <= G2_CITL_PP and c["lo"] >= -G2_CI_PP and c["hi"] <= G2_CI_PP


def gates(records: Sequence[Mapping[str, Any]], key: str = "p_pub", *, b0_key: str = "p_b0") -> dict:
    """G0–G3 of one class on `key` (the prequential published probabilities on the held-out read, or a
    live window). G1 compares with raw B0; G2 per outcome; G3 per head."""
    out = {"n": len(records), "G0": {"n": len(records), "pass": len(records) >= G0_MIN_EVENTS}}
    if not records:
        out.update(G1={"pass": False}, G2={"pass": False}, G3={"pass": False}, passed=False)
        return out
    gain = paired_log_loss(records, key, b0_key)            # LL(B0) − LL(key)
    excess_hi = None if gain["lo"] is None else -gain["lo"]
    out["G1"] = {"ll_excess_est": None if gain["est"] is None else -gain["est"], "ll_excess_hi": excess_hi,
                 "pass": excess_hi is not None and excess_hi <= G1_MAX_LL_EXCESS}
    oa, g2 = outcome_arrays(records, key), {}
    for o in OUTCOMES:
        c = citl(*oa[o])
        g2[o] = {**c, "pass": _g2_pass(c)}
    out["G2"] = {"outcomes": g2, "pass": all(v["pass"] for v in g2.values())}
    ha, g3 = head_arrays(records, key), {}
    for h in HEADS:
        s = cal_slope(*ha[h])
        g3[h] = {**s, "pass": s["lo"] is not None and s["hi"] >= G3_SLOPE_BAND[0] and s["lo"] <= G3_SLOPE_BAND[1]}
    out["G3"] = {"heads": g3, "pass": all(v["pass"] for v in g3.values())}
    out["passed"] = bool(out["G0"]["pass"] and out["G1"]["pass"] and out["G2"]["pass"] and out["G3"]["pass"])
    return out


def g2_only(records: Sequence[Mapping[str, Any]], key: str) -> bool:
    if not records:
        return False
    oa = outcome_arrays(records, key)
    return all(_g2_pass(citl(*oa[o])) for o in OUTCOMES)


def beats(records: Sequence[Mapping[str, Any]], model: str, base: str) -> bool:
    """§11b publication rule: the raw model's log-loss gain over a raw base has a week-clustered 95 %
    interval above 0."""
    d = paired_log_loss(records, model, base)
    return d["lo"] is not None and d["lo"] > 0


# ---- D1: betting e-process (design §5.1) ------------------------------------------------------------
def d1_paths(records: Sequence[Mapping[str, Any]], key: str, margin: Optional[Mapping[str, float]] = None) -> np.ndarray:
    """Per outcome (columns BREAK, REJECT, NEITHER) the path of E_t = mean over λ ∈ D1_LAMBDAS of
    Π (1 + λ (y_i − p_i)), from the first record given (the epoch start).

    With `margin` (per outcome, probability units) the null is |E[y − p]| ≤ m instead of 0: the λ > 0
    bets use y − p − m and the λ < 0 bets y − p + m, which keeps every factor's mean ≤ 1 under that
    null. This is the variant for a frozen reference map (p_ref) whose own held-out estimation error
    is m (design §5.1)."""
    if not records:
        return np.ones((0, 3))
    p3 = _clip(np.array([r[key] for r in records], dtype=float))
    y3 = np.array([[1.0 if r["outcome"] == o else 0.0 for o in OUTCOMES] for r in records])
    lam = np.array(D1_LAMBDAS)[None, None, :]
    z = (y3 - p3)[:, :, None]
    if margin:
        m = np.array([float(margin.get(o, 0.0)) for o in OUTCOMES])[None, :, None]
        z = z - np.sign(lam) * m
    logs = np.cumsum(np.log1p(lam * z), axis=0)
    return np.mean(np.exp(logs), axis=2)


def d1_value(records: Sequence[Mapping[str, Any]], key: str) -> dict:
    path = d1_paths(records, key)
    if not path.size:
        return {"e": {o: 1.0 for o in OUTCOMES}, "e_max": {o: 1.0 for o in OUTCOMES}}
    return {"e": {o: float(path[-1, k]) for k, o in enumerate(OUTCOMES)},
            "e_max": {o: float(path[:, k].max()) for k, o in enumerate(OUTCOMES)}}


def d1_triggered(d1: Mapping[str, Any]) -> bool:
    return any(v > D1_OUTCOME_THRESHOLD for v in d1["e"].values())


# ---- generic-stream monitor (design §5.6) -------------------------------------------------------------
def generic_monitor_rows(records: Sequence[Mapping[str, Any]]) -> list:
    """The independent rows of the generic stream: the (1, 1) price pair at anchors on the 4h UTC grid
    (one per independent window). Records carry `pair` and `t_ms`; synthetic rows without `pair` are
    taken as already independent."""
    out = []
    for r in records:
        if r.get("pair", (1, 1)) not in ((1, 1), [1, 1]):
            continue
        if "pair" in r and int(r["t_ms"]) % (4 * 3_600_000):
            continue
        out.append(r)
    return out


def changepoint_paths(records: Sequence[Mapping[str, Any]], key: str, margin: Optional[Mapping[str, float]] = None,
                      block: int = GEN_BLOCK) -> np.ndarray:
    """Per outcome the change-point mixture of D1 betting e-processes: Σ_j π_j M_j(t), M_j started at
    record j·block, π_j = 1/((j+1)(j+2)); starts not yet reached count as 1. A test martingale under
    the null of d1_paths, so P(sup ≥ c) ≤ 1/c per outcome, while a late drift is not buried under the
    evidence of a long calm period."""
    T = len(records)
    if not T:
        return np.ones((0, 3))
    p3 = _clip(np.array([r[key] for r in records], dtype=float))
    y3 = np.array([[1.0 if r["outcome"] == o else 0.0 for o in OUTCOMES] for r in records])
    lam = np.array(D1_LAMBDAS)[None, None, :]
    z = (y3 - p3)[:, :, None]
    if margin:
        z = z - np.sign(lam) * np.array([float(margin.get(o, 0.0)) for o in OUTCOMES])[None, :, None]
    inc = np.log1p(lam * z)                                         # T × 3 × λ
    S = np.concatenate([np.zeros((1, 3, inc.shape[2])), np.cumsum(inc, axis=0)])
    out = np.zeros((T, 3))
    for j in range((T - 1) // block + 1):
        s0 = j * block
        out[s0:] += np.mean(np.exp(S[s0 + 1:] - S[s0]), axis=2) / ((j + 1) * (j + 2))
    started = np.arange(T) // block + 1
    return out + (1.0 / (started + 1))[:, None]


def generic_rolling_alarm(rows: Sequence[Mapping[str, Any]], key: str, margin: Optional[Mapping[str, float]], *,
                          now_ms: int) -> bool:
    """Rolling rule over the rows issued in the last GEN_ROLL_WEEKS weeks before now: some outcome's
    CITL exceeds its margin + GEN_ROLL_PP and its GEN_ROLL_Z week-clustered interval lies wholly beyond
    the margin. Off when GEN_ROLL_WEEKS = 0."""
    if GEN_ROLL_WEEKS <= 0:
        return False
    lo_t = int(now_ms) - GEN_ROLL_WEEKS * 7 * 86_400_000
    win = [r for r in rows if int(r["t_ms"]) >= lo_t]
    if len({int(r["week"]) for r in win}) < 5:
        return False
    oa = outcome_arrays(win, key)
    for o in OUTCOMES:
        m = 100 * float((margin or {}).get(o, 0.0))
        c = citl(*oa[o], zq=GEN_ROLL_Z)
        if c["lo"] is None:
            continue
        if (c["est"] > m + GEN_ROLL_PP and c["lo"] > m) or (c["est"] < -m - GEN_ROLL_PP and c["hi"] < -m):
            return True
    return False


@dataclass(frozen=True)
class GenericState:
    alarm: bool = False
    since_ms: int = 0
    epoch_start: int = 0                  # index into the generic monitor rows where the alarm began
    reason: str = "start"


def next_generic_state(prev: GenericState, rows: Sequence[Mapping[str, Any]], *, key: str = "p_ref",
                       margin: Optional[Mapping[str, float]] = None, now_ms: int) -> GenericState:
    """Alarm when any outcome's change-point e-process exceeds GEN_THRESHOLD; clear when, since the
    alarm, ≥ GEN_RETURN_MIN rows have resolved and every outcome's plain e-process (from the alarm) is
    below RETURN_E_MAX — the frozen return rule, applied to the generic stream."""
    if not prev.alarm:
        path = changepoint_paths(rows, key, margin)
        if path.size and float(path[-1].max()) > GEN_THRESHOLD:
            return GenericState(True, int(now_ms), len(rows), "generic_drift:e")
        if generic_rolling_alarm(rows, key, margin, now_ms=now_ms):
            return GenericState(True, int(now_ms), len(rows), "generic_drift:rolling")
        return prev
    ep = list(rows[prev.epoch_start:])
    if len(ep) >= GEN_RETURN_MIN:
        e = d1_paths(ep, key, margin=margin)[-1]
        if float(e.max()) < RETURN_E_MAX:
            return GenericState(False, int(now_ms), len(rows), "generic_recovered")
    return prev


# ---- monitors ------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Monitors:
    key: str                              # the probabilities monitored
    n_live: int                           # resolved live records of the class (this version)
    n_epoch: int                          # resolved records since the epoch began
    d1: Mapping[str, Any]                 # epoch e-values per outcome
    d2: Mapping[str, Any]                 # per outcome CITL over the last ROLL_N (D2_Z interval)
    d3: Optional[Mapping[str, Any]]       # LL(key) − LL(fallback) over the last ROLL_N; None without fallback
    epoch_citl: Mapping[str, Any]         # per outcome CITL since the epoch began
    live_gates: Mapping[str, Any]         # G2 / G3 on the whole live record (for L3_LIVE)
    fallback_g2_recent: Optional[bool]    # the fallback passes G2 on the last ROLL_N (None: fewer records)

    def to_dict(self) -> dict:
        return asdict(self)


def monitors(live: Sequence[Mapping[str, Any]], *, key: str = "p_pub", epoch_start: int = 0,
             fallback_key: Optional[str] = "p_fb") -> Monitors:
    """Statistics of the resolved live records of one class in issue order (published or not)."""
    ep, roll = list(live[epoch_start:]), list(live[-ROLL_N:])
    has_fb = bool(fallback_key and roll and fallback_key in roll[0])
    d3 = None
    if has_fb and fallback_key != key:
        g = paired_log_loss(roll, key, fallback_key, zq=D3_Z)          # LL(fb) − LL(key)
        d3 = {"est": None if g["est"] is None else -g["est"], "lo": None if g["hi"] is None else -g["hi"],
              "hi": None if g["lo"] is None else -g["lo"], "n": g["n"], "clusters": g["clusters"]}
    ro, eo = outcome_arrays(roll, key), outcome_arrays(ep, key)
    lg = gates(live, key) if live else {"G2": {"pass": False}, "G3": {"pass": False}}
    return Monitors(key=key, n_live=len(live), n_epoch=len(ep), d1=d1_value(ep, key),
                    d2={o: citl(*ro[o], zq=D2_Z) for o in OUTCOMES}, d3=d3,
                    epoch_citl={o: citl(*eo[o]) for o in OUTCOMES},
                    live_gates={"G2": lg["G2"]["pass"], "G3": lg["G3"]["pass"]},
                    fallback_g2_recent=(g2_only(roll, fallback_key) if has_fb and len(roll) >= ROLL_N else None))


def drift_reasons(m: Monitors) -> list:
    out = []
    if d1_triggered(m.d1):
        out.append("D1")
    for o, c in m.d2.items():
        if c["n"] >= ROLL_N // 2 and c["est"] is not None and abs(c["est"]) > D2_PP and c["lo"] is not None \
                and (c["lo"] > 0 or c["hi"] < 0):
            out.append(f"D2:{o}")
    if m.d3 is not None and m.d3.get("clusters", 0) >= D3_MIN_WEEKS and m.d3.get("lo") is not None and m.d3["lo"] > 0:
        out.append("D3")
    return out


def recovered(m: Monitors) -> bool:
    """Return rule: ≥ RETURN_MIN_EVENTS resolved since the epoch, every outcome's epoch |CITL| ≤ D2_PP,
    every epoch e-value below RETURN_E_MAX and no drift reason."""
    if m.n_epoch < RETURN_MIN_EVENTS or any(v >= RETURN_E_MAX for v in m.d1["e"].values()):
        return False
    if any(c["est"] is None or abs(c["est"]) > D2_PP for c in m.epoch_citl.values()):
        return False
    return not drift_reasons(m)


# ---- state machine (design §7) -------------------------------------------------------------------
@dataclass(frozen=True)
class Health:
    data_fresh: bool = True            # D0: last closed bar at issue ≤ D0_STALE_MINUTES old
    parity_ok: bool = True             # D0: live detector = research constructor
    journal_ok: bool = True
    coverage_ok: bool = True

    def ok(self) -> bool:
        return self.data_fresh and self.parity_ok and self.journal_ok and self.coverage_ok

    def faults(self) -> tuple:
        return tuple(k for k, v in asdict(self).items() if not v)


@dataclass(frozen=True)
class Setup:
    """Fixed per model version and class after the held-out read (and the mode setting)."""
    mode: str = "HIST_ONLY"            # HIST_ONLY / MODEL (FORECAST_LAYER §6a; one setting)
    case: str = "B"                    # A: champion published (§11b); B: the fallback model published
    holdout_passed: bool = False       # G0–G3 of the published model on the held-out read
    fallback_g2_holdout: bool = False  # the fallback model passes G2 on this class on the held-out read
    model_version: str = ""


@dataclass(frozen=True)
class StateRecord:
    state: str
    since_ms: int
    epoch_start: int = 0               # index of the first resolved live record of the current epoch
    drift_exits: int = 0
    before_off: Optional[str] = None
    off_reason: Optional[str] = None   # the D0 fault while OFF; `reason` keeps the reason of the state before
    reason: str = "start"
    model_version: str = ""
    version: str = LR_STATE_VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def initial_state(setup: Setup, *, now_ms: int) -> StateRecord:
    if setup.mode != "MODEL":
        return StateRecord("HIST", int(now_ms), reason="mode_hist_only", model_version=setup.model_version)
    if setup.case == "A" and setup.holdout_passed:
        return StateRecord("L3_HISTORY_BACKED", int(now_ms), reason="holdout_passed", model_version=setup.model_version)
    if setup.fallback_g2_holdout:
        return StateRecord("FALLBACK", int(now_ms), reason="holdout_passed" if setup.case == "B" else "holdout_not_passed",
                           model_version=setup.model_version)
    return StateRecord("HIST", int(now_ms), reason="holdout_not_passed", model_version=setup.model_version)


def fallback_available(setup: Setup, mon_fb: Optional[Monitors]) -> bool:
    """FALLBACK is published for a class only while the fallback model passes G2 on it: on the held-out
    read, and on the last ROLL_N live records once there are that many. In case B it is the only model
    state: case B never enters an L3 state (its number would be its own «обычно», §6b)."""
    if not setup.fallback_g2_holdout:
        return False
    recent = mon_fb.fallback_g2_recent if mon_fb is not None else None
    return True if recent is None else bool(recent)


def next_state(prev: StateRecord, setup: Setup, *, health: Health, mon: Optional[Monitors] = None,
               mon_fb: Optional[Monitors] = None, generic_alarm: bool = False, now_ms: int) -> StateRecord:
    """One deterministic step. D0 health at every call (OFF at once); the model rules when `mon` is
    given (at batch cutoffs). `mon` monitors the published model of the case (champion in A, fallback
    model in B), with its epoch from `prev.epoch_start`; `mon_fb` monitors the fallback model on the
    class (case A) from the same epoch. `generic_alarm` is the current GenericState.alarm: it sends an
    L3 state or FALLBACK to GEN_ALARM_TARGET (a drift exit), and a class left that way returns only
    after the alarm has cleared and then by the class's own return rule."""
    if not health.ok():
        if prev.state == "OFF":
            return prev
        return replace(prev, state="OFF", since_ms=now_ms, before_off=prev.state,
                       off_reason="D0:" + ",".join(health.faults()))
    if setup.mode != "MODEL":
        if prev.state == "HIST" and prev.reason == "mode_hist_only":
            return prev
        return StateRecord("HIST", now_ms, reason="mode_hist_only", model_version=setup.model_version)
    if prev.state == "OFF":
        return replace(prev, state=prev.before_off or "HIST", since_ms=now_ms, before_off=None, off_reason=None)
    if prev.reason == "mode_hist_only":
        return initial_state(setup, now_ms=now_ms)
    if generic_alarm:
        if prev.state in ("L3_HISTORY_BACKED", "L3_LIVE", "FALLBACK"):
            return replace(prev, state=GEN_ALARM_TARGET, since_ms=now_ms,
                           epoch_start=mon.n_live if mon is not None else prev.epoch_start,
                           drift_exits=prev.drift_exits + 1, reason="generic_drift")
        return prev
    if mon is None:
        return prev
    if prev.state in ("L3_HISTORY_BACKED", "L3_LIVE"):
        why = drift_reasons(mon)
        if why:
            to = LEVEL_DRIFT_TARGET if LEVEL_DRIFT_TARGET == "FALLBACK" and fallback_available(setup, mon_fb) else "HIST"
            return replace(prev, state=to, since_ms=now_ms, epoch_start=mon.n_live, drift_exits=prev.drift_exits + 1,
                           reason="drift:" + ",".join(why))
        if prev.state == "L3_HISTORY_BACKED" and mon.n_live >= LIVE_FLOOR and mon.live_gates["G2"] and mon.live_gates["G3"]:
            return replace(prev, state="L3_LIVE", since_ms=now_ms, reason="live_floor_reached")
        return prev
    if setup.case == "B":
        mon_fb = mon_fb if mon_fb is not None else mon
    if prev.state == "FALLBACK" and mon_fb is not None:
        fb_why = [w for w in drift_reasons(mon_fb) if w != "D3"]
        if fb_why or not fallback_available(setup, mon_fb):
            return replace(prev, state="HIST", since_ms=now_ms, epoch_start=mon_fb.n_live,
                           drift_exits=prev.drift_exits + (setup.case == "B"),
                           reason="fallback_drift:" + ",".join(fb_why or ["G2"]))
    returnable = prev.state in ("FALLBACK", "HIST") and prev.reason.startswith(("drift", "fallback_drift", "generic_drift"))
    if returnable and setup.case == "B":
        if prev.state == "HIST" and prev.drift_exits < MAX_DRIFT_EXITS and mon_fb is not None \
                and recovered(mon_fb) and fallback_available(setup, mon_fb):
            return replace(prev, state="FALLBACK", since_ms=now_ms, epoch_start=mon_fb.n_live, reason="recovered")
        return prev
    if returnable and setup.holdout_passed and prev.drift_exits < MAX_DRIFT_EXITS and recovered(mon):
        live = mon.n_live >= LIVE_FLOOR and mon.live_gates["G2"] and mon.live_gates["G3"]
        return replace(prev, state="L3_LIVE" if live else "L3_HISTORY_BACKED", since_ms=now_ms,
                       epoch_start=mon.n_live, reason="recovered")
    return prev


# ---- challengers (design §6) ---------------------------------------------------------------------
def challenger_look(paired: Sequence[Mapping[str, Any]]) -> Optional[dict]:
    """At 150, 300, 450, 600 paired resolved live events: promoted when the week-clustered 95 % interval
    of the log-loss gain of `p_chal` over the published champion `p_pub` lies above 0 and the
    challenger passes G2 and G3 on the paired record. None between looks."""
    n = len(paired)
    if n < CHALLENGER_MIN_PAIRED or n % CHALLENGER_LOOK_EVERY or n > CHALLENGER_MAX_PAIRED:
        return None
    gain = paired_log_loss(paired, "p_chal", "p_pub")
    g = gates(paired, "p_chal")
    cal_ok = bool(g["G2"]["pass"] and g["G3"]["pass"])
    promoted = gain["lo"] is not None and gain["lo"] > 0 and cal_ok
    return {"n": n, "gain": gain, "calibration_ok": cal_ok, "promoted": bool(promoted),
            "retired": bool(not promoted and n >= CHALLENGER_MAX_PAIRED)}


# ---- epochs cut by dated layer events (FORECAST_LAYER §6a) ----------------------------------------
def split_by_events(records: Sequence[Mapping[str, Any]], event_ms: Sequence[int]) -> list:
    """Records split at each dated layer event: [(start_ms, end_ms, records), …]; the monitors and the
    report never mix records across a cut."""
    cuts = sorted(int(x) for x in event_ms)
    bounds = [-(1 << 62)] + cuts + [1 << 62]
    return [(lo, hi, [r for r in records if lo <= int(r["t_ms"]) < hi]) for lo, hi in zip(bounds[:-1], bounds[1:])]


# ---- input drift (reported, never a state change) ------------------------------------------------
INPUT_BLOCK_WEEKS = 8
INPUT_RANGE = (0.025, 0.975)


def _block_stats(rows, weeks) -> dict:
    wk = set(int(w) for w in weeks)
    sel = [r for r in rows if int(r["week"]) in wk]
    return {"median_sigma": float(np.median([r["sigma"] for r in sel])) if sel else None,
            "mean_b0_break": float(np.mean([r["p_b0"][0] for r in sel])) if sel else None,
            "rate": len(sel) / max(len(wk), 1)}


def input_drift(reference, recent, *, ref_weeks, recent_weeks) -> list:
    """Warnings for the recent block against the held-out 8-week blocks' 2.5–97.5 % range: median PIT σ,
    mean B0 BREAK probability (position) and events per week."""
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


# ---- display contract for F2 (design §9) -------------------------------------------------------------
TEMPLATES = {"L3_HISTORY_BACKED": ("LR_L3H_V1", "LR_PUSH_L3H_V1"), "L3_LIVE": ("LR_L3L_V1", "LR_PUSH_L3L_V1"),
             "FALLBACK": ("LR_FB_V1", "LR_PUSH_FB_V1"), "OFF": ("LR_OFF_V1", "LR_PUSH_OFF_V1"), "HIST": ("HIST", "HIST")}


ACCURACY_SOURCE = {"L3_HISTORY_BACKED": "holdout", "L3_LIVE": "live", "FALLBACK": "generic"}


def display_contract(st: StateRecord, setup: Setup, *, calibrator_version: Optional[str],
                     accuracy: Optional[Mapping[str, Any]] = None) -> dict:
    """What F2 reads per class: state, template ids (full, push), which probabilities to print
    ("CHAMPION" with its class intercept, "FALLBACK" = G1@event with the GENERIC intercept, None),
    «обычно» and the accuracy line. A model state with a number always carries its accuracy line:
    `accuracy[source]` must be a {"predicted", "realized", "n"} block for the state's source (held-out
    for L3_HISTORY_BACKED, live for L3_LIVE, the generic class for FALLBACK), else ValueError — no
    number without its tracked accuracy (PRODUCT_DECISION_V2 §3). HIST keeps F1 §0 templates and table."""
    probs = None
    if st.state in ("L3_HISTORY_BACKED", "L3_LIVE"):
        probs = "CHAMPION"                                  # L3 states exist only in case A
    elif st.state == "FALLBACK":
        probs = "FALLBACK"
    line = None
    if probs is not None:
        src = ACCURACY_SOURCE[st.state]
        line = (accuracy or {}).get(src)
        if not line or any(line.get(k) is None for k in ("predicted", "realized", "n")):
            raise ValueError(f"{st.state}: a number needs its {src} accuracy line")
        line = {"source": src, **{k: line[k] for k in ("predicted", "realized", "n")}}
    full, push = TEMPLATES[st.state]
    return {"version": LR_STATE_VERSION, "mode": setup.mode, "case": setup.case, "state": st.state,
            "since_ms": st.since_ms, "reason": st.reason, "template": full, "push_template": push,
            "probabilities": probs, "calibrator_version": calibrator_version if probs else None,
            # «обычно»: G1@event beside the champion in L3; none in FALLBACK (its number is the generic
            # model itself, shown with its calibration line, §6 / §11b); HIST keeps its F1 §0 cell mean
            "usual": {"CHAMPION": "G1_AT_EVENT_RAW", "FALLBACK": None}.get(probs, "HIST_CELL" if st.state == "HIST" else None),
            "level_effect_claimed": False,                       # never in user text (F1 §11b)
            "accuracy_line": line,
            # in L3_HISTORY_BACKED the live segment reads «live: копится (N = …)» until L3_LIVE
            "live_accruing_n": (accuracy or {}).get("live_n") if st.state == "L3_HISTORY_BACKED" else None}
