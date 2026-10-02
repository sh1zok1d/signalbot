"""SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0: pure functions, no I/O.

Frozen design: `docs/research/SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0_DESIGN.json`.

Population: support episodes of the unchanged SEED-0001 detector
(`SUPPORT = True`, i.e. arms A and B). Every episode carries a swing low at
pivot bar i, a comparison pivot j with a higher low, and the decision time
T = close of bar i + 3.

Candidate selling-exhaustion states (no oscillator input):

- `SE_LEG`: relative to the prior downswing. The net taker-flow share over
  the second leg (j, i] is above that over the equal-length window ending at
  pivot j, AND open interest at the close of bar i is not above its value at
  the close of bar j.
- `SE_BASELINE`: relative to a local baseline. The net taker-flow share over
  the 24 bars ending at pivot bar i is above the median of the same 24-bar
  statistic over the local 720-bar baseline (windows ending at i-696..i-24),
  AND open interest at the close of bar i is not above its value 24h earlier.

Every input ends at or before the close of pivot bar i, which precedes T.
Window lengths reuse frozen SEED-0001 constants (`FLOW_BARS` = 24,
`WARMUP_BARS` = 720), and thresholds are the no-change points (0) or a
median. Nothing is tuned.

Continuous scores (feasibility only) are frozen before use:
- the mean of two components, each robust-z scaled per symbol (median,
  1.4826 MAD) and clipped to [-3, 3];
- the components are the flow component and the sign-flipped OI component
  of each variant.

The outcome-dependence calibration is state-blind. It receives outcomes and
cluster keys only, never a candidate state, so no E-versus-S outcome
contrast can be formed.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
from scipy import sparse, stats

from scripts.research import divergence_full_history_v0_lib as F
from scripts.research import seed0001_regular_divergence_lib as L

HOUR_MS = L.BAR_MS
DAY_MS = 86_400_000
FLOW_WINDOW_BARS = L.FLOW_BARS            # 24
BASELINE_SPAN_BARS = L.WARMUP_BARS        # 720
OI_LOOKBACK_HOURS = L.FLOW_BARS           # 24
CHAIN_HOURS = L.PRIMARY_CAP_HOURS         # 48: outcome windows overlap within a symbol
VARIANTS = ("SE_LEG", "SE_BASELINE")
STATE_INPUTS = ("LEG_FLOW_CHANGE", "LEG_OI_CHANGE", "APPROACH_FLOW_SHARE", "APPROACH_FLOW_BASELINE",
                "APPROACH_FLOW_EXCESS", "APPROACH_OI_CHANGE")
SCORE_COMPONENTS = {
    "SE_LEG": (("LEG_FLOW_CHANGE", 1.0), ("LEG_OI_CHANGE", -1.0)),
    "SE_BASELINE": (("APPROACH_FLOW_EXCESS", 1.0), ("APPROACH_OI_CHANGE", -1.0)),
}
MAD_SCALE = 1.4826
SCORE_CLIP = 3.0

ALPHA = 0.05
TARGET_POWER = 0.80
Z80 = float(stats.norm.ppf(1 - ALPHA / 2) + stats.norm.ppf(TARGET_POWER))
COMPARATOR_RATE = 0.50
REPORTED_EFFECTS = (0.03, 0.05, 0.075, 0.10)
DECISION_EFFECTS = (0.04, 0.05)
EFFECT_GRID = tuple(round(0.005 * k, 3) for k in range(2, 31))          # 0.010 .. 0.150
PROFILES = {
    "INDEPENDENT": {},
    "BASE": {"DATE": 0.25 / 0.75},              # latent ICC 0.25 per UTC date (V0/V1 BASE)
    "STRESS": {"DATE_X_STATE": 1.0},            # latent ICC 0.50 per (UTC date, state) (V0/V1 STRESS)
}
GATE_PROFILE = "STRESS"
REALISTIC_HORIZON_WEEKS = 104                   # the SEED-0001 prospective leg: 2026-10-05 .. 2028-10-05
MAX_PROJECTED_WEEKS = 520
MIN_STATE_EPISODES = 30
MIN_STATE_WEEK_CLUSTERS = 30


# ------------------------------------------------------------------ states

def _share(tb: np.ndarray, v: np.ndarray) -> float:
    s = float(np.sum(v))
    return float(np.sum(2.0 * tb - v) / s) if s > 0 else float("nan")


def _ratio_change(now: float, before: float) -> float:
    if not (math.isfinite(now) and math.isfinite(before)) or before <= 0:
        return float("nan")
    return now / before - 1.0


def state_inputs(bars: dict, oi: dict | None, ep: dict) -> dict:
    """Point-in-time state inputs; every bar and OI value ends at or before the close of pivot bar i."""
    grid = bars["open_time_ms"]
    i = int(np.searchsorted(grid, F.ms(ep["PIVOT_BAR_OPEN_UTC"])))
    j = int(np.searchsorted(grid, F.ms(ep["COMPARISON_PIVOT_OPEN_UTC"])))
    d = i + L.PIVOT_RIGHT
    if d >= grid.size or int(grid[d]) + HOUR_MS != int(ep["DECISION_TIME_MS"]):
        raise ValueError("episode does not align with the bar grid")
    if i - BASELINE_SPAN_BARS + 1 < 0:
        raise ValueError("baseline span precedes the data")
    vol, tb = bars["volume"], bars["taker_buy"]
    gap = i - j
    lo_prev = max(j - gap + 1, 0)
    leg_flow_change = _share(tb[j + 1:i + 1], vol[j + 1:i + 1]) - _share(tb[lo_prev:j + 1], vol[lo_prev:j + 1])

    w = FLOW_WINDOW_BARS
    approach = _share(tb[i - w + 1:i + 1], vol[i - w + 1:i + 1])
    a, b = i - BASELINE_SPAN_BARS + 1, i - w + 1                 # bars i-719 .. i-24
    net_w = np.lib.stride_tricks.sliding_window_view(2.0 * tb[a:b] - vol[a:b], w).sum(axis=1)
    vol_w = np.lib.stride_tricks.sliding_window_view(vol[a:b], w).sum(axis=1)
    ok = vol_w > 0
    baseline = float(np.median(net_w[ok] / vol_w[ok])) if ok.any() else float("nan")

    at_i = int(grid[i]) + HOUR_MS
    oi_i = F.oi_asof(oi, at_i)
    return {
        "LEG_FLOW_CHANGE": leg_flow_change,
        "LEG_OI_CHANGE": _ratio_change(oi_i, F.oi_asof(oi, int(grid[j]) + HOUR_MS)),
        "APPROACH_FLOW_SHARE": approach,
        "APPROACH_FLOW_BASELINE": baseline,
        "APPROACH_FLOW_EXCESS": approach - baseline,
        "APPROACH_OI_CHANGE": _ratio_change(oi_i, F.oi_asof(oi, at_i - OI_LOOKBACK_HOURS * HOUR_MS)),
    }


def state_flags(x: dict) -> dict:
    """1 = exhaustion state E, 0 = support without it (S), None = undefined (a missing input)."""
    def flag(flow: float, oi_change: float):
        if not (math.isfinite(flow) and math.isfinite(oi_change)):
            return None
        return int(flow > 0.0 and oi_change <= 0.0)
    return {"SE_LEG": flag(x["LEG_FLOW_CHANGE"], x["LEG_OI_CHANGE"]),
            "SE_BASELINE": flag(x["APPROACH_FLOW_EXCESS"], x["APPROACH_OI_CHANGE"])}


def robust_constants(rows: list[dict], variant: str) -> dict:
    """Per-symbol (median, 1.4826 * MAD) of each score component; feature values only, no outcome."""
    out = {}
    for sym in sorted({r["SYMBOL"] for r in rows}):
        out[sym] = {}
        for comp, _sign in SCORE_COMPONENTS[variant]:
            v = np.array([r[comp] for r in rows if r["SYMBOL"] == sym], dtype=float)
            v = v[np.isfinite(v)]
            med = float(np.median(v)) if v.size else float("nan")
            mad = float(np.median(np.abs(v - med))) * MAD_SCALE if v.size else float("nan")
            out[sym][comp] = {"MEDIAN": med, "SCALE": mad}
    return out


def score(row: dict, variant: str, constants: dict) -> float:
    parts = []
    for comp, sign in SCORE_COMPONENTS[variant]:
        c = constants[row["SYMBOL"]][comp]
        x = float(row[comp])
        if not (math.isfinite(x) and c["SCALE"] > 0):
            return float("nan")
        parts.append(sign * float(np.clip((x - c["MEDIAN"]) / c["SCALE"], -SCORE_CLIP, SCORE_CLIP)))
    return float(np.mean(parts))


# -------------------------------------------------------------- dependence

def date_key(ms: int) -> int:
    return int(ms) // DAY_MS


def symbol_chains(symbols, times_ms) -> list[str]:
    """Within-symbol chains of episodes whose 48h outcome windows overlap."""
    symbols = np.asarray(symbols)
    times = np.asarray(times_ms, dtype=np.int64)
    out = np.empty(times.size, dtype=object)
    for sym in np.unique(symbols):
        idx = np.flatnonzero(symbols == sym)
        ch = L.overlap_chains(times[idx], window_hours=CHAIN_HOURS)
        for k, c in zip(idx.tolist(), ch.tolist()):
            out[k] = f"{sym}:{c}"
    return out.tolist()


def _concentration(sel: list[dict]) -> dict:
    by_sym = Counter(r["SYMBOL"] for r in sel)
    by_epoch = Counter(r["EPOCH"] for r in sel)
    shares = np.array(list(by_sym.values()), dtype=float) / len(sel)
    return {"BY_SYMBOL": dict(sorted(by_sym.items())), "MAX_SYMBOL_SHARE": float(shares.max()),
            "SYMBOL_HHI": float((shares ** 2).sum()), "BY_EPOCH": dict(sorted(by_epoch.items())),
            "MAX_EPOCH_SHARE": float(max(by_epoch.values()) / len(sel))}


def _co_occurrence(sel: list[dict]) -> dict:
    """Share of episodes with an episode of another symbol, in the same state, within 0 / 6 / 24 h."""
    times = {}
    for r in sel:
        times.setdefault(r["SYMBOL"], []).append(r["DECISION_TIME_MS"])
    times = {k: np.sort(np.array(v, dtype=np.int64)) for k, v in times.items()}
    out = {}
    for h in (0, 6, 24):
        hits = 0
        for r in sel:
            for sym, arr in times.items():
                if sym == r["SYMBOL"]:
                    continue
                k = int(np.searchsorted(arr, r["DECISION_TIME_MS"] - h * HOUR_MS))
                if k < arr.size and arr[k] <= r["DECISION_TIME_MS"] + h * HOUR_MS:
                    hits += 1
                    break
        out[f"WITH_OTHER_SYMBOL_SAME_STATE_WITHIN_{h}H"] = hits / len(sel)
    return out


def state_layout_stats(rows: list[dict], state_key: str) -> dict:
    """Counts and structural dependence of one variant's E and S episodes (no outcome)."""
    out = {}
    for label, val in (("E", 1), ("S", 0)):
        sel = [r for r in rows if r[state_key] == val]
        if not sel:
            out[label] = {"EPISODES": 0}
            continue
        per_date = Counter(date_key(r["DECISION_TIME_MS"]) for r in sel)
        chains = symbol_chains([r["SYMBOL"] for r in sel], [r["DECISION_TIME_MS"] for r in sel])
        market = L.overlap_chains(np.array([r["DECISION_TIME_MS"] for r in sel], dtype=np.int64), window_hours=24)
        out[label] = {
            "EPISODES": len(sel),
            "DISTINCT_DECISION_TIMES": len({r["DECISION_TIME_MS"] for r in sel}),
            "DECISION_DATES": len(per_date),
            "WEEK_CLUSTERS": len({r["WEEK_BLOCK"] for r in sel}),
            "SYMBOL_48H_OVERLAP_CHAINS": len(set(chains)),
            "PANEL_24H_MARKET_CHAINS": len(set(market.tolist())),
            "MAX_EPISODES_PER_DATE": max(per_date.values()),
            **_concentration(sel),
            **_co_occurrence(sel),
        }
    n_e, n_s = out["E"]["EPISODES"], out["S"]["EPISODES"]
    out["PREVALENCE_E_AMONG_DEFINED_SUPPORT"] = n_e / (n_e + n_s) if n_e + n_s else None
    return out


# ------------------------------------------- state-blind outcome dependence

def _keys(*cols) -> np.ndarray:
    return np.unique(np.array(["|".join(map(str, t)) for t in zip(*cols)]), return_inverse=True)[1]


def _pairs_by_week(group: np.ndarray, week_idx: np.ndarray, y: np.ndarray, n_weeks: int) -> np.ndarray:
    """Per week: (sum y_a y_b, sum (y_a + y_b), pair count) over unordered pairs inside each group."""
    n_g = int(group.max()) + 1
    s1 = np.bincount(group, weights=y, minlength=n_g)
    s2 = np.bincount(group, weights=y * y, minlength=n_g)
    cnt = np.bincount(group, minlength=n_g).astype(float)
    g_week = np.zeros(n_g, dtype=np.int64)
    g_week[group] = week_idx
    yy = 0.5 * (s1 * s1 - s2)
    ys = (cnt - 1.0) * s1
    pc = 0.5 * cnt * (cnt - 1.0)
    out = np.zeros((n_weeks, 3))
    np.add.at(out, g_week, np.column_stack([yy, ys, pc]))
    return out


PAIR_CLASSES = ("WEEK_OTHER_DATE_OTHER_SYMBOL", "DATE_OTHER_SYMBOL", "SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK")


def outcome_pair_stats(y, symbols, times_ms, weeks) -> tuple[dict, np.ndarray]:
    """State-blind per-week pair statistics of a binary outcome for three within-week pair classes."""
    y = np.asarray(y, dtype=float)
    symbols = np.asarray(symbols)
    weeks = np.asarray(weeks)
    dates = np.array([date_key(t) for t in times_ms])
    chains = np.array(symbol_chains(symbols, times_ms))
    week_idx = np.unique(weeks, return_inverse=True)[1]
    n_w = int(week_idx.max()) + 1
    P = lambda *cols: _pairs_by_week(_keys(*cols), week_idx, y, n_w)  # noqa: E731
    w, dte = P(weeks), P(weeks, dates)
    w_s, d_s = P(weeks, symbols), P(weeks, dates, symbols)
    c_w, c_d = P(weeks, chains), P(weeks, dates, chains)
    per_week = {
        "WEEK_OTHER_DATE_OTHER_SYMBOL": w - dte - w_s + d_s,
        "DATE_OTHER_SYMBOL": dte - d_s,
        "SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK": c_w - c_d,
    }
    return per_week, week_idx


def phi_from_pairs(per_week: dict, y: np.ndarray, week_idx: np.ndarray, weights: np.ndarray | None = None) -> dict:
    """Pairwise phi per class; `weights` are week multiplicities (bootstrap)."""
    n_w = int(week_idx.max()) + 1
    wts = np.ones(n_w) if weights is None else np.asarray(weights, dtype=float)
    row_w = wts[week_idx]
    ybar = float(np.sum(row_w * y) / np.sum(row_w))
    v = ybar * (1.0 - ybar)
    out = {}
    for cls, arr in per_week.items():
        yy, ys, pc = (wts @ arr[:, 0]), (wts @ arr[:, 1]), (wts @ arr[:, 2])
        out[cls] = float((yy - ybar * ys + ybar * ybar * pc) / (pc * v)) if pc > 0 and v > 0 else float("nan")
        out[cls + "_PAIRS"] = float(pc)
    return out


def latent_profile(phi: dict) -> dict:
    """Probit variance components that reproduce the pair-class correlations at p ~ 0.5.

    rho = sin(pi * phi / 2) per class; week = rho_W; date = rho_D - rho_W;
    chain = rho_C - rho_W (each floored at 0); tau^2 = rho * V with V = 1 / (1 - sum rho).
    """
    rho = {k: math.sin(math.pi * phi[k] / 2.0) if math.isfinite(phi[k]) else 0.0 for k in PAIR_CLASSES}
    r_w = max(rho["WEEK_OTHER_DATE_OTHER_SYMBOL"], 0.0)
    r_d = max(rho["DATE_OTHER_SYMBOL"] - r_w, 0.0)
    r_c = max(rho["SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK"] - r_w, 0.0)
    total = r_w + r_d + r_c
    if total > 0.95:                       # keep V finite; proportional shrink
        r_w, r_d, r_c = (r * 0.95 / total for r in (r_w, r_d, r_c))
    v = 1.0 / (1.0 - (r_w + r_d + r_c))
    return {"WEEK": r_w * v, "DATE": r_d * v, "CHAIN": r_c * v,
            "LATENT_CORR": {"WEEK": r_w, "DATE": r_d, "CHAIN": r_c}}


def week_bootstrap_phi(per_week: dict, y: np.ndarray, week_idx: np.ndarray, *, resamples: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    n_w = int(week_idx.max()) + 1
    draws = {k: [] for k in PAIR_CLASSES}
    for _ in range(resamples):
        wts = np.bincount(rng.integers(0, n_w, n_w), minlength=n_w).astype(float)
        ph = phi_from_pairs(per_week, y, week_idx, wts)
        for k in PAIR_CLASSES:
            draws[k].append(ph[k])
    return {k: {"Q05": float(np.nanquantile(v, 0.05)), "Q95": float(np.nanquantile(v, 0.95))} for k, v in draws.items()}


# -------------------------------------------------------------- simulation

def layout_arrays(rows: list[dict], state_key: str, score_key: str | None = None) -> dict:
    sel = [r for r in rows if r[state_key] is not None and (score_key is None or math.isfinite(r[score_key]))]
    t = [r["DECISION_TIME_MS"] for r in sel]
    sym = [r["SYMBOL"] for r in sel]
    return {
        "SYMBOL": np.array(sym), "WEEK": np.array([r["WEEK_BLOCK"] for r in sel]),
        "DATE": np.array([date_key(x) for x in t]), "STATE": np.array([int(r[state_key]) for r in sel]),
        "CHAIN": np.array(symbol_chains(sym, t)),
        "SCORE": np.array([r[score_key] for r in sel], dtype=float) if score_key else None,
    }


def collapse_layout(lay: dict) -> dict:
    """One unit per (UTC date, state): same-day same-state episodes across symbols become one."""
    seen = {}
    for k in range(lay["STATE"].size):
        key = (int(lay["DATE"][k]), int(lay["STATE"][k]))
        if key not in seen:
            seen[key] = (int(lay["WEEK"][k]), int(lay["DATE"][k]), int(lay["STATE"][k]))
    units = list(seen.values())
    return {"SYMBOL": np.array(["PANEL"] * len(units)), "WEEK": np.array([u[0] for u in units]),
            "DATE": np.array([u[1] for u in units]), "STATE": np.array([u[2] for u in units]),
            "CHAIN": np.array([f"U{k}" for k in range(len(units))]), "SCORE": None}


def _groups(lay: dict, kind: str) -> np.ndarray:
    if kind == "DATE":
        return _keys(lay["DATE"])
    if kind == "DATE_X_STATE":
        return _keys(lay["DATE"], lay["STATE"])
    if kind == "WEEK":
        return _keys(lay["WEEK"])
    if kind == "CHAIN":
        return _keys(lay["CHAIN"])
    raise ValueError(kind)


def _design(lay: dict, x: np.ndarray) -> np.ndarray:
    syms = lay["SYMBOL"]
    present = sorted(set(syms.tolist()))
    cols = [np.ones(x.size), x] + [(syms == s).astype(float) for s in present[1:]]
    return np.column_stack(cols)


def simulate(lay: dict, *, p: np.ndarray, regressors: dict, profile: dict, reps: int, seed: int,
             batch: int = 500) -> dict:
    """Rejection rates of one-coefficient tests on synthetic binary outcomes (never real outcomes).

    Outcomes: y = 1[latent < Phi^-1(p) sqrt(V)] with probit shocks of the stated
    variances (marginal P(y=1) = p exactly). Each regressor is tested in its own
    OLS (regressor + symbol FE), CR1 by week, t(G - 1), two-sided 0.05 with a
    positive estimate required.
    """
    n = p.size
    g = _keys(lay["WEEK"])
    n_g = int(g.max()) + 1
    if n_g < 3:
        raise ValueError("fewer than 3 week clusters")
    member = sparse.csr_matrix((np.ones(n), (g, np.arange(n))), shape=(n_g, n))
    fits = {}
    for name, x in regressors.items():
        X = _design(lay, np.asarray(x, dtype=float))
        if np.linalg.matrix_rank(X) < X.shape[1]:
            raise ValueError(f"singular design for {name}")
        xtx_inv = np.linalg.inv(X.T @ X)
        k = X.shape[1]
        fits[name] = {"X": X, "proj": xtx_inv @ X.T, "w": X @ xtx_inv[:, 1],
                      "scale": n_g / (n_g - 1) * (n - 1) / (n - k)}
    comps = [(_groups(lay, kind), math.sqrt(var)) for kind, var in profile.items() if var > 0]
    v = 1.0 + sum(t * t for _, t in comps)
    loc = stats.norm.ppf(np.clip(p, 1e-9, 1 - 1e-9)) * math.sqrt(v)
    crit = float(stats.t.ppf(1 - ALPHA / 2, n_g - 1))
    rng = np.random.default_rng(seed)
    hits = {k: 0 for k in fits}
    ests = {k: [] for k in fits}
    done = 0
    while done < reps:
        m = min(batch, reps - done)
        latent = rng.standard_normal((n, m))
        for grp, tau in comps:
            latent += tau * rng.standard_normal((int(grp.max()) + 1, m))[grp]
        y = (latent < loc[:, None]).astype(float)
        for name, f in fits.items():
            beta = f["proj"] @ y
            resid = y - f["X"] @ beta
            scores = np.asarray(member @ (f["w"][:, None] * resid))
            se = np.sqrt(f["scale"] * (scores ** 2).sum(axis=0))
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.where(se > 0, beta[1] / se, 0.0)
            hits[name] += int((t > crit).sum())
            ests[name].extend(beta[1].tolist())
        done += m
    return {name: {"POWER": hits[name] / reps, "MEAN_ESTIMATE": float(np.mean(ests[name])),
                   "SD_ESTIMATE": float(np.std(ests[name], ddof=1))} for name in fits} | {
        "_META": {"N": int(n), "WEEK_CLUSTERS": n_g, "REPS": reps}}


def step_probabilities(state: np.ndarray, delta: float) -> np.ndarray:
    return COMPARATOR_RATE + delta * np.asarray(state, dtype=float)


def linear_probabilities(state: np.ndarray, score_std: np.ndarray, delta: float) -> tuple[np.ndarray, float]:
    """P(y=1) linear in the standardized score, scaled so the implied E - S rate gap equals delta."""
    gap = float(score_std[state == 1].mean() - score_std[state == 0].mean())
    beta = delta / gap
    raw = COMPARATOR_RATE + beta * score_std
    p = np.clip(raw, 0.01, 0.99)
    return p, float(np.mean(raw != p))


def standardize(x: np.ndarray) -> np.ndarray:
    return (x - x.mean()) / x.std(ddof=0)


# -------------------------------------------------------------- projection

def weeks_for_power(weeks_ref: float, sd_ref: float, mean_ref: float) -> float:
    """Weeks for 80% power under sqrt(weeks) scaling of the estimator's SD (normal approximation)."""
    if not (mean_ref > 0 and sd_ref > 0):
        return float("inf")
    return weeks_ref * (Z80 * sd_ref / mean_ref) ** 2


def prospective_rows(rows: list[dict], n_weeks: int) -> list[dict]:
    """Structural stand-in for n_weeks of a prospective stream: cycles the exposed weeks in order,
    relabelling weeks and shifting times so copies never share a cluster, a date or a chain."""
    by_week = {}
    for r in rows:
        by_week.setdefault(r["WEEK_BLOCK"], []).append(r)
    lo, hi = min(by_week), max(by_week)
    span = hi - lo + 1
    out = []
    for step in range(n_weeks):
        src = lo + step % span
        new_week = 1_000_000 + step
        shift = (new_week - src) * L.WEEK_MS
        for r in by_week.get(src, []):
            out.append({**r, "WEEK_BLOCK": new_week, "DECISION_TIME_MS": r["DECISION_TIME_MS"] + shift})
    return out


# ----------------------------------------------------------------- verdict

STATUS_PRIORITY = ["DEFINITION_INCOMPLETE", "DATA_BLOCKED", "PIT_BLOCKED", "INFERENCE_SUPPORT_INSUFFICIENT",
                   "INFORMATIONALLY_WEAK", "FEASIBLE_FOR_PREREGISTRATION"]


def verdict(per_variant: dict, *, data_ok: bool, pit_ok: bool) -> dict:
    """Frozen rule on the primary binary E - S.

    FEASIBLE_FOR_PREREGISTRATION if some variant reaches 80% power at 5 pp
    under STRESS within the realistic prospective horizon (104 weeks).
    INFORMATIONALLY_WEAK otherwise, with the reason
    FEASIBLE_ONLY_UNDER_WEAKER_DEPENDENCE when BASE or EMPIRICAL reaches it in
    that horizon, else NOT_TESTABLE_WITHIN_REALISTIC_HORIZON.
    """
    if not data_ok:
        return {"STATUS": "DATA_BLOCKED", "REASONS": ["DATA_BLOCKED"]}
    if not pit_ok:
        return {"STATUS": "PIT_BLOCKED", "REASONS": ["PIT_TRUNCATION_AUDIT_FAILED"]}
    supported = {v: r for v, r in per_variant.items() if r["SUPPORT_OK"]}
    if not supported:
        return {"STATUS": "INFERENCE_SUPPORT_INSUFFICIENT", "REASONS": ["NO_VARIANT_WITH_ENOUGH_E_EPISODES_AND_WEEKS"]}
    weeks = lambda r, prof: r["WEEKS_FOR_80"][prof]["0.05"]  # noqa: E731
    if any(weeks(r, GATE_PROFILE) <= REALISTIC_HORIZON_WEEKS for r in supported.values()):
        return {"STATUS": "FEASIBLE_FOR_PREREGISTRATION", "REASONS": ["STRESS_80_AT_5PP_WITHIN_104_WEEKS"]}
    if any(weeks(r, prof) <= REALISTIC_HORIZON_WEEKS for r in supported.values() for prof in ("BASE", "EMPIRICAL")):
        return {"STATUS": "INFORMATIONALLY_WEAK", "REASONS": ["FEASIBLE_ONLY_UNDER_WEAKER_DEPENDENCE"]}
    return {"STATUS": "INFORMATIONALLY_WEAK", "REASONS": ["NOT_TESTABLE_WITHIN_REALISTIC_HORIZON"]}
