"""SEED-0001 exploratory outcome analysis (EXPLORATORY / UNDERPOWERED).

Implements `docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json` on the
frozen episode sets of `docs/research/seed0001/EPISODES_{SYMBOL}.csv`. The
feasibility verdict INCONCLUSIVE_SAMPLE / BELOW_HARD_FLOOR is unchanged, the
classification is fixed before outcomes as INCONCLUSIVE_DISCOVERY, and nothing
here is confirmatory evidence.

Outcome definitions (permit OUTCOME_DEFINITIONS):
- preregistered bracket: entry E = close of bar i+3, stop S = low_i, R = E - S;
  over 1m bars with open time in [T, T + cap): stop = low < S, target =
  high >= E + kR, same minute = stop; WIN target first, LOSS stop first or
  same minute, NEUTRAL timeout; Yk_cap = 1 on WIN;
- descriptive (fixed in the permit before opening): FWD_RET_h = C_h/E - 1,
  FWD_R_h = (C_h - E)/R with C_h the close of the minute opening at T+h-1m,
  MFE_R_h and MAE_R_h over the full window.

    python -m scripts.research.seed0001_exploratory_outcomes run
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from scripts.research import seed0001_feasibility as R
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
PERMIT_REL = "docs/research/SEED0001_EXPLORATORY_OUTCOME_PERMIT.json"
AUTHORIZATION_COMMIT = "df9e351fb3c9b3d59f2fd32cb135b9d03a9f3fc0"
RESULT_REL = "docs/research/SEED0001_EXPLORATORY_OUTCOME_RESULT.json"
OUTCOMES_DIR_REL = "docs/research/seed0001"
MINUTE_MS = 60_000
CAPS_HOURS = (48, 96)
KS = (1, 2)
ENDPOINTS = ("Y1_48H", "Y2_48H", "Y1_96H", "Y2_96H")
BOOTSTRAP_RESAMPLES = 4999
BOOTSTRAP_SEED = 20261004
EPOCH_PERMUTATIONS = 2000
EPOCH_SEED = 20261003
EPOCHS = ("2023H1", "2023H2", "2024H1", "2024H2")
ALPHA = 0.05
MIN_EFFECT = 0.10
ROUND_TRIP_COST = 0.0010
COVARIATES = ("RV24_LOG", "TOD_SIN", "TOD_COS", "DECLINE_ATR", "NETFLOW24", "RISK_ATR")
LABEL = "EXPLORATORY / UNDERPOWERED"


class OutcomeWindowError(RuntimeError):
    pass


# ----------------------------------------------------------------- outcomes

def window_slice(t: np.ndarray, start_ms: int, hours: int) -> slice | None:
    """Indices of the 1m bars with open time in [start, start + hours); None if any minute is missing."""
    end_ms = start_ms + hours * 3_600_000
    if end_ms > L.PROTECTED_START_MS:
        raise OutcomeWindowError("outcome window reaches the protected 2025 surface")
    a = int(np.searchsorted(t, start_ms))
    b = int(np.searchsorted(t, end_ms))
    if b - a != hours * 60 or a >= t.size or t[a] != start_ms or t[b - 1] != end_ms - MINUTE_MS:
        return None
    return slice(a, b)


def bracket(high: np.ndarray, low: np.ndarray, entry: float, stop: float, k: int) -> str:
    """WIN, LOSS or NEUTRAL for one window under the frozen bracket rule."""
    risk = entry - stop
    stop_hits = np.flatnonzero(low < stop)
    target_hits = np.flatnonzero(high >= entry + k * risk)
    s = int(stop_hits[0]) if stop_hits.size else None
    g = int(target_hits[0]) if target_hits.size else None
    if s is None and g is None:
        return "NEUTRAL"
    if g is not None and (s is None or g < s):
        return "WIN"
    return "LOSS"


def episode_outcomes(minutes: dict, ep: dict) -> dict:
    t, high, low, close = minutes["t"], minutes["high"], minutes["low"], minutes["close"]
    entry, stop = float(ep["ENTRY_REF_PRICE"]), float(ep["STOP_PRICE"])
    risk = entry - stop
    if not risk > 0:
        raise OutcomeWindowError(f"non-positive risk {ep['EPISODE_ID']}")
    out = {"EPISODE_ID": ep["EPISODE_ID"], "R": risk}
    for cap in CAPS_HOURS:
        sl = window_slice(t, int(ep["DECISION_TIME_MS"]), cap)
        for k in KS:
            name = f"Y{k}_{cap}H"
            if sl is None:
                out[f"{name}_WLN"], out[name] = "UNAVAILABLE", None
                continue
            wln = bracket(high[sl], low[sl], entry, stop, k)
            out[f"{name}_WLN"], out[name] = wln, int(wln == "WIN")
        if sl is None:
            for key in ("FWD_RET", "FWD_R", "MFE_R", "MAE_R"):
                out[f"{key}_{cap}H"] = None
            continue
        c_h = float(close[sl.stop - 1])
        out[f"FWD_RET_{cap}H"] = c_h / entry - 1.0
        out[f"FWD_R_{cap}H"] = (c_h - entry) / risk
        out[f"MFE_R_{cap}H"] = (float(high[sl].max()) - entry) / risk
        out[f"MAE_R_{cap}H"] = (entry - float(low[sl].min())) / risk
    return out


# --------------------------------------------------------------- statistics

def ols_cr1(X: np.ndarray, y: np.ndarray, clusters) -> dict:
    """OLS with CR1 cluster-robust variance: G/(G-1) * (n-1)/(n-k) small-sample factor."""
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    resid = y - X @ beta
    _, g = np.unique(np.asarray(clusters), return_inverse=True)
    n_g = int(g.max()) + 1
    scores = np.zeros((n_g, k))
    np.add.at(scores, g, X * resid[:, None])
    meat = scores.T @ scores
    factor = n_g / (n_g - 1) * (n - 1) / (n - k)
    return {"beta": beta, "V": factor * xtx_inv @ meat @ xtx_inv, "G": n_g, "n": n}


def contrast(fit: dict, c, *, one_sided_negative: bool = False) -> dict:
    c = np.asarray(c, dtype=float)
    est = float(c @ fit["beta"])
    se = float(math.sqrt(max(c @ fit["V"] @ c, 0.0)))
    df = fit["G"] - 1
    tstat = est / se if se > 0 else float("nan")
    p = float(2 * stats.t.sf(abs(tstat), df)) if se > 0 else float("nan")
    half = float(stats.t.ppf(0.975, df)) * se
    out = {"ESTIMATE": est, "SE_CR1": se, "T": tstat, "DF": df, "P_TWO_SIDED": p,
           "CI95_CR1_T": [est - half, est + half]}
    if one_sided_negative:
        out["P_ONE_SIDED_BELOW_ZERO"] = float(stats.t.cdf(tstat, df)) if se > 0 else float("nan")
    return out


def holm(p1: float, p2: float) -> dict:
    lo, hi = min(p1, p2), max(p1, p2)
    adj_lo = min(1.0, 2 * lo)
    adj_hi = max(adj_lo, hi)
    adj = (adj_lo, adj_hi) if p1 <= p2 else (adj_hi, adj_lo)
    return {"P1_HOLM": adj[0], "P2_HOLM": adj[1],
            "REJECT_BOTH": bool(lo <= ALPHA / 2 and hi <= ALPHA)}


def covariates(eps: list[dict]) -> np.ndarray:
    hour = np.array([int(e["TOD_HOUR_UTC"]) for e in eps], dtype=float)
    return np.column_stack([
        np.log(np.array([float(e["RV24"]) for e in eps])),
        np.sin(2 * np.pi * hour / 24.0), np.cos(2 * np.pi * hour / 24.0),
        np.array([float(e["DECLINE_ATR"]) for e in eps]),
        np.array([float(e["NETFLOW24"]) for e in eps]),
        np.array([float(e["RISK_ATR"]) for e in eps]),
    ])


def arm_dummies(arms) -> np.ndarray:
    arms = np.asarray(arms)
    return np.column_stack([arms == "A", arms == "B", arms == "C"]).astype(float)


def full_design(eps: list[dict], arms=None) -> np.ndarray:
    arms = [e["ARM"] for e in eps] if arms is None else arms
    return np.column_stack([np.ones(len(eps)), arm_dummies(arms), covariates(eps)])


P1 = np.r_[0.0, 1.0, -1.0, 0.0, np.zeros(len(COVARIATES))]
P2 = np.r_[0.0, 1.0, 0.0, -1.0, np.zeros(len(COVARIATES))]
P1_ARM = np.array([0.0, 1.0, -1.0, 0.0])
P2_ARM = np.array([0.0, 1.0, 0.0, -1.0])
AD_ARM = np.array([0.0, 1.0, 0.0, 0.0])


def adjusted_model(eps: list[dict], y: np.ndarray, clusters) -> dict:
    X = full_design(eps)
    fit = ols_cr1(X, y, clusters)
    p1, p2 = contrast(fit, P1), contrast(fit, P2)
    adj_rates = {arm: float(np.mean(full_design(eps, [arm] * len(eps)) @ fit["beta"])) for arm in "ABCD"}
    return {"P1_A_VS_B": p1, "P2_A_VS_C": p2, "HOLM": holm(p1["P_TWO_SIDED"], p2["P_TWO_SIDED"]),
            "ADJUSTED_RATES": adj_rates, "G": fit["G"], "N": fit["n"]}


def arm_only_model(arms, y: np.ndarray, clusters) -> dict:
    X = np.column_stack([np.ones(len(arms)), arm_dummies(arms)])
    fit = ols_cr1(X, y, clusters)
    rates = {}
    for arm, c in (("A", [1, 1, 0, 0]), ("B", [1, 0, 1, 0]), ("C", [1, 0, 0, 1]), ("D", [1, 0, 0, 0])):
        rates[arm] = contrast(fit, c)
    return {"RATES": rates, "A_VS_B": contrast(fit, P1_ARM), "A_VS_C": contrast(fit, P2_ARM),
            "A_VS_D": contrast(fit, AD_ARM), "G": fit["G"], "N": fit["n"]}


def cluster_bootstrap(eps: list[dict], y: np.ndarray, clusters, *, resamples: int = BOOTSTRAP_RESAMPLES,
                      seed: int = BOOTSTRAP_SEED) -> dict:
    """Pairs bootstrap over whole weekly clusters; percentile 95% CI for P1 and P2."""
    X = full_design(eps)
    arms = np.array([e["ARM"] for e in eps])
    keys, g = np.unique(np.asarray(clusters), return_inverse=True)
    members = [np.flatnonzero(g == j) for j in range(keys.size)]
    rng = np.random.default_rng(seed)
    draws, skipped = [], 0
    for _ in range(resamples):
        pick = rng.integers(0, keys.size, size=keys.size)
        idx = np.concatenate([members[j] for j in pick])
        if not all((arms[idx] == a).any() for a in "ABCD"):
            skipped += 1
            continue
        Xb, yb = X[idx], y[idx]
        if np.linalg.matrix_rank(Xb) < Xb.shape[1]:
            skipped += 1
            continue
        beta = np.linalg.solve(Xb.T @ Xb, Xb.T @ yb)
        draws.append((float(P1 @ beta), float(P2 @ beta)))
    d = np.array(draws)
    return {"RESAMPLES": resamples, "SEED": seed, "USED": int(d.shape[0]), "SKIPPED": skipped,
            "P1_CI95_PERCENTILE": [float(np.quantile(d[:, 0], 0.025)), float(np.quantile(d[:, 0], 0.975))],
            "P2_CI95_PERCENTILE": [float(np.quantile(d[:, 1], 0.025)), float(np.quantile(d[:, 1], 0.975))],
            "P1_SHARE_ABOVE_ZERO": float((d[:, 0] > 0).mean()), "P2_SHARE_ABOVE_ZERO": float((d[:, 1] > 0).mean())}


# ------------------------------------------------------------------- epochs

def _epoch_contrasts(arms, y, clusters, epochs) -> dict:
    out = {}
    for ep in EPOCHS:
        m = epochs == ep
        if not all((arms[m] == a).any() for a in "ABCD") or np.unique(clusters[m]).size < 3:
            out[ep] = None
            continue
        res = arm_only_model(arms[m], y[m], clusters[m])
        out[ep] = {"A_VS_B": res["A_VS_B"], "A_VS_C": res["A_VS_C"],
                   "N_BY_ARM": {a: int((arms[m] == a).sum()) for a in "ABCD"}, "G": res["G"]}
    return out


def _q_stat(per_epoch: dict, key: str) -> float | None:
    rows = [(v[key]["ESTIMATE"], v[key]["SE_CR1"]) for v in per_epoch.values() if v and v[key]["SE_CR1"] > 0]
    if len(rows) < 3:
        return None
    th = np.array([r[0] for r in rows])
    w = 1.0 / np.array([r[1] for r in rows]) ** 2
    pooled = float((w * th).sum() / w.sum())
    return float((w * (th - pooled) ** 2).sum())


def epoch_analysis(eps: list[dict], y: np.ndarray, *, draws: int = EPOCH_PERMUTATIONS, seed: int = EPOCH_SEED) -> dict:
    arms = np.array([e["ARM"] for e in eps])
    weeks = np.array([int(e["WEEK_BLOCK"]) for e in eps])
    epochs = np.array([e["EPOCH"] for e in eps])
    per = _epoch_contrasts(arms, y, weeks, epochs)
    pooled = arm_only_model(arms, y, weeks)
    out = {"ROLE": "descriptive robustness only; epoch gate NOT_ASSESSABLE in the feasibility pass", "BY_EPOCH": per}
    # Permutation units are (epoch, week) cells: a week that spans an epoch boundary is split there.
    units = sorted({(e, w) for e, w in zip(epochs.tolist(), weeks.tolist())})
    unit_index = {u: j for j, u in enumerate(units)}
    unit_of = np.array([unit_index[(e, w)] for e, w in zip(epochs.tolist(), weeks.tolist())])
    labels = np.array([u[0] for u in units])
    rng = np.random.default_rng(seed)
    for key, pooled_key in (("A_VS_B", "A_VS_B"), ("A_VS_C", "A_VS_C")):
        q_obs = _q_stat(per, key)
        sign = np.sign(pooled[pooled_key]["ESTIMATE"])
        opposite = []
        for ep, v in per.items():
            if v is None or v[key]["SE_CR1"] <= 0:
                continue
            est, se, df = v[key]["ESTIMATE"], v[key]["SE_CR1"], v[key]["DF"]
            if np.sign(est) == -sign:
                p_opp = float(stats.t.sf(abs(est) / se, df))
                if p_opp < 0.05:
                    opposite.append({"EPOCH": ep, "P_ONE_SIDED": p_opp})
        same = sum(1 for v in per.values() if v is not None and np.sign(v[key]["ESTIMATE"]) == sign)
        defined = sum(1 for v in per.values() if v is not None)
        p_het = None
        if q_obs is not None:
            exceed = 0
            for _ in range(draws):
                pseudo = rng.permutation(labels)[unit_of]
                q = _q_stat(_epoch_contrasts(arms, y, weeks, pseudo), key)
                exceed += q is not None and q >= q_obs
            p_het = (1 + exceed) / (1 + draws)
        out[key] = {"POOLED_ARM_ONLY": pooled[pooled_key], "Q": q_obs, "P_HETEROGENEITY": p_het,
                    "PERMUTATIONS": draws, "SEED": seed, "EPOCHS_DEFINED": defined,
                    "EPOCHS_SAME_SIGN_AS_POOLED": same, "SIGNIFICANTLY_OPPOSITE_EPOCHS": opposite}
    return out


# --------------------------------------------------------------------- I/O

def load_minutes(symbol: str) -> dict:
    manifest = json.loads((REPO / R.MANIFEST_REL).read_text())
    pinned = {(o["SYMBOL"], o["PERIOD"]): o["SHA256"] for o in manifest["OBJECTS"] if o["KIND"] == "KLINES_1M"}
    frames = []
    for ym in R.KLINE_MONTHS:
        path = R.DATA_ROOT / "raw/KLINES_1M" / symbol / f"{symbol}-1m-{ym}.zip"
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pinned[(symbol, ym)]:
            raise RuntimeError(f"KLINE_SHA256_MISMATCH:{symbol}:{ym}")
        df = pd.read_csv(io.BytesIO(R._read_zip_csv(path)), header=None, dtype=str)
        if not df.iloc[0, 0].isdigit():
            df = df.iloc[1:]
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    t = df[0].astype(np.int64).to_numpy()
    if np.any(np.diff(t) <= 0) or t[-1] >= L.PROTECTED_START_MS:
        raise RuntimeError("1m series unordered or inside the protected surface")
    return {"t": t, "high": df[2].astype(float).to_numpy(), "low": df[3].astype(float).to_numpy(),
            "close": df[4].astype(float).to_numpy()}


_INT = {"DECISION_TIME_MS", "WEEK_BLOCK", "COMPARISON_GAP_BARS", "MAX_INPUT_BAR_CLOSE_MS", "TOD_HOUR_UTC",
        "DIV_COUNT", "SUPPORT_TRAILING_PRESENT", "CHAIN_48H"}
_BOOL = {"RSI14_DIV", "RSI21_DIV", "RSI_FAMILY", "MACD_FAMILY", "CVD_FAMILY", "DIVERGENCE", "SUPPORT"}
_STR = {"DECISION_TIME_UTC", "DECISION_DATE_UTC", "EPOCH", "PIVOT_BAR_OPEN_UTC", "COMPARISON_PIVOT_OPEN_UTC", "ARM",
        "SYMBOL", "EPISODE_ID"}


def load_frozen_episodes(symbol: str, permit: dict) -> list[dict]:
    rel = f"docs/research/seed0001/EPISODES_{symbol}.csv"
    raw = (REPO / rel).read_bytes()
    if hashlib.sha256(raw).hexdigest() != permit["FROZEN_ARTIFACT_SHA256_BEFORE_OPENING"][rel]:
        raise RuntimeError(f"FROZEN_EPISODE_CSV_CHANGED:{symbol}")
    rows = list(csv.DictReader(io.StringIO(raw.decode())))
    eps = [{k: (int(v) if k in _INT else v == "True" if k in _BOOL else v if k in _STR else float(v))
            for k, v in r.items()} for r in rows]
    digest = hashlib.sha256("\n".join(L.episode_digest_rows(eps, symbol)).encode()).hexdigest()
    if digest != permit["FROZEN_EPISODE_DIGESTS"][symbol]:
        raise RuntimeError(f"FROZEN_EPISODE_DIGEST_MISMATCH:{symbol}")
    return eps


def _summary(values) -> dict:
    v = np.array([x for x in values if x is not None], dtype=float)
    if v.size == 0:
        return {"N": 0}
    return {"N": int(v.size), "MEAN": float(v.mean()), "MEDIAN": float(np.median(v)),
            "Q25": float(np.quantile(v, 0.25)), "Q75": float(np.quantile(v, 0.75))}


def symbol_analysis(symbol: str, permit: dict) -> tuple[dict, list[dict]]:
    eps = load_frozen_episodes(symbol, permit)
    minutes = load_minutes(symbol)
    outcomes = [episode_outcomes(minutes, e) for e in eps]
    arms = np.array([e["ARM"] for e in eps])
    weeks = np.array([e["WEEK_BLOCK"] for e in eps])
    chains = np.array([e["CHAIN_48H"] for e in eps])
    unavailable = {ep: sum(o[ep] is None for o in outcomes) for ep in ENDPOINTS}
    if any(unavailable.values()):
        raise RuntimeError(f"UNAVAILABLE_OUTCOMES:{symbol}:{unavailable}")
    Y = {ep: np.array([o[ep] for o in outcomes], dtype=float) for ep in ENDPOINTS}

    primary = adjusted_model(eps, Y["Y1_48H"], weeks)
    primary["BOOTSTRAP"] = cluster_bootstrap(eps, Y["Y1_48H"], weeks)
    p1, p2 = primary["P1_A_VS_B"]["ESTIMATE"], primary["P2_A_VS_C"]["ESTIMATE"]
    a_idx = arms == "A"
    breakeven = float(np.mean(0.5 + (ROUND_TRIP_COST / np.array([e["RISK_FRACTION"] for e in eps])[a_idx]) / 2))
    gates = {
        "STATISTICAL": bool(primary["HOLM"]["REJECT_BOTH"] and p1 > 0 and p2 > 0),
        "PRACTICAL": bool(p1 >= MIN_EFFECT and p2 >= MIN_EFFECT and primary["ADJUSTED_RATES"]["A"] >= breakeven),
        "A_BREAK_EVEN_RATE": breakeven,
        "ROLE": "reported mechanically for transparency; the classification is fixed as INCONCLUSIVE_DISCOVERY",
    }
    secondary = {
        "S1_Y2_48H": adjusted_model(eps, Y["Y2_48H"], weeks),
        "S2_Y1_96H": adjusted_model(eps, Y["Y1_96H"], weeks),
        "S3_Y2_96H": adjusted_model(eps, Y["Y2_96H"], weeks),
        "S4_Y1_48H_CHAIN_CLUSTERS": adjusted_model(eps, Y["Y1_48H"], chains),
    }
    raw = {ep: arm_only_model(arms, Y[ep], weeks) for ep in ENDPOINTS}
    counts = {ep: {a: {w: sum(1 for o, e in zip(outcomes, eps) if e["ARM"] == a and o[f"{ep}_WLN"] == w)
                       for w in ("WIN", "LOSS", "NEUTRAL")} for a in "ABCD"} for ep in ENDPOINTS}
    descriptive = {}
    for cap in CAPS_HOURS:
        for key in ("FWD_RET", "FWD_R", "MFE_R", "MAE_R"):
            name = f"{key}_{cap}H"
            vals = np.array([o[name] for o in outcomes], dtype=float)
            model = arm_only_model(arms, vals, weeks)
            descriptive[name] = {"BY_ARM": {a: _summary(vals[arms == a]) for a in "ABCD"},
                                 "A_MINUS_B_MEAN": model["A_VS_B"], "A_MINUS_C_MEAN": model["A_VS_C"]}
    epochs = epoch_analysis(eps, Y["Y1_48H"])
    by_epoch_counts = {ep: {a: {w: sum(1 for o, e in zip(outcomes, eps)
                                       if e["EPOCH"] == ep and e["ARM"] == a and o["Y1_48H_WLN"] == w)
                                for w in ("WIN", "LOSS", "NEUTRAL")} for a in "ABCD"} for ep in EPOCHS}
    epochs["Y1_48H_COUNTS_BY_EPOCH"] = by_epoch_counts
    result = {
        "SYMBOL": symbol, "LABEL": LABEL, "EPISODES": len(eps),
        "EPISODES_BY_ARM": {a: int((arms == a).sum()) for a in "ABCD"},
        "UNAVAILABLE": unavailable,
        "PRIMARY_Y1_48H": primary, "GATES_MECHANICAL": gates,
        "SECONDARY": secondary, "RAW_ARM_RATES": raw, "WIN_LOSS_NEUTRAL": counts,
        "DESCRIPTIVE_PATH": descriptive, "EPOCHS": epochs,
    }
    rows = [{**{k: e[k] for k in ("EPISODE_ID", "ARM", "EPOCH", "WEEK_BLOCK", "CHAIN_48H", "DECISION_TIME_UTC")}, **o}
            for e, o in zip(eps, outcomes)]
    return result, rows


def _git_head() -> str:
    return subprocess.check_output(["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True).strip()


def run() -> dict:
    permit_bytes = (REPO / PERMIT_REL).read_bytes()
    permit = json.loads(permit_bytes)
    for rel, digest in permit["FROZEN_ARTIFACT_SHA256_BEFORE_OPENING"].items():
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"FROZEN_ARTIFACT_CHANGED:{rel}")
    results = {}
    for symbol in R.SYMBOLS:
        res, rows = symbol_analysis(symbol, permit)
        results[symbol] = res
        out = REPO / OUTCOMES_DIR_REL / f"OUTCOMES_{symbol}.csv"
        with out.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
            w.writeheader()
            for r in rows:
                w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})
    report = {
        "RESULT": "SEED0001_EXPLORATORY_OUTCOME_RESULT_V1",
        "LABEL": LABEL,
        "CONFIRMATORY": False,
        "FEASIBILITY_VERDICT": permit["FEASIBILITY_VERDICT"],
        "CLASSIFICATION": permit["CLASSIFICATION_FIXED_BEFORE_OUTCOMES"],
        "PERMIT_PATH": PERMIT_REL,
        "PERMIT_SHA256": hashlib.sha256(permit_bytes).hexdigest(),
        "AUTHORIZATION_COMMIT": AUTHORIZATION_COMMIT,
        "EVALUATOR_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "GIT_HEAD_AT_RUN": _git_head(),
        "PYTHON": sys.version.split()[0], "NUMPY": np.__version__, "PANDAS": pd.__version__,
        "SYMBOLS": results,
        "ETH_ROLE": "robustness only; never pooled; cannot change anything about BTC",
        "PROTECTED_2025_2026_OPENED": False,
        "RERUN_AUTHORIZED": False,
    }
    (REPO / RESULT_REL).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def main(argv: list[str]) -> int:
    if argv[:1] == ["run"]:
        r = run()
        print(json.dumps({"RESULT": RESULT_REL, "GIT_HEAD_AT_RUN": r["GIT_HEAD_AT_RUN"]}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
