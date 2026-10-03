"""DIVERGENCE_PANEL_FEASIBILITY_V0: outcome-blind panel feasibility for the divergence program.

Frozen design: `docs/research/DIVERGENCE_PANEL_FEASIBILITY_V0_DESIGN.json`.

Runs the unchanged SEED-0001 point-in-time detector on six Binance UM perps
(BTC, ETH, SOL, XRP, BNB, DOGE), decisions 2023-01-01..2024-12-28, and sizes
a future panel card whose primary estimand is the interaction
(A - B) - (C - D). It computes no outcome on any symbol and reads no byte
dated 2025 or later.

Dependence is the point of this unit. Episodes on different symbols at the
same time are not independent: the power profiles put a shared shock on
same-day episodes across symbols, the gate profile makes same-day same-arm
episodes strongly correlated across symbols, and a collapsed diagnostic
merges them into one unit. Inference planned for the card clusters by
panel-wide UTC week.

    python -m scripts.research.divergence_panel_feasibility_v0 acquire
    python -m scripts.research.divergence_panel_feasibility_v0 run
"""

from __future__ import annotations

import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import sparse, stats

from scripts.research import seed0001_feasibility as R
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
DESIGN_REL = "docs/research/DIVERGENCE_PANEL_FEASIBILITY_V0_DESIGN.json"
REPORT_REL = "docs/research/DIVERGENCE_PANEL_FEASIBILITY_V0_REPORT.json"
MANIFEST_REL = "docs/research_data/DIVERGENCE_PANEL_V0_BINANCE_UM/DATASET_MANIFEST.json"
PANEL = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT")
NEW_SYMBOLS = ("SOLUSDT", "XRPUSDT", "BNBUSDT", "DOGEUSDT")
ARMS = ("A", "B", "C", "D")
DAY_MS = 86_400_000

MIN_EFFECT = 0.15
DIAGNOSTIC_EFFECTS = (0.10, 0.20)
EFFECT_GRID = tuple(round(0.025 * k, 3) for k in range(1, 17))
TARGET_POWER = 0.80
ALPHA = 0.05
COMPARATOR_RATE = 0.50
POWER_REPS = 2000
POWER_SEED = 20261005
PROFILES = {
    "INDEPENDENT": {"SHOCK": None, "LATENT_ICC": 0.0, "ROLE": "diagnostic: episodes treated as independent"},
    "BASE": {"SHOCK": "DATE", "LATENT_ICC": 0.25, "ROLE": "one probit shock per UTC decision date shared by all symbols and arms"},
    "STRESS": {"SHOCK": "DATE_X_ARM", "LATENT_ICC": 0.50,
               "ROLE": "GATE: one shock per (UTC date, arm) shared across symbols; same-day same-arm episodes move together"},
}
COLLAPSED_PROFILE = {"SHOCK": "DATE", "LATENT_ICC": 0.25,
                     "ROLE": "diagnostic lower bound: same-day same-arm episodes merged into one unit across symbols"}
GATE_PROFILE = "STRESS"
MIN_A_WEEK_CLUSTERS = 30
MIN_C_WEEK_CLUSTERS = 30
MAX_SYMBOL_SHARE_OF_A = 0.50
MIN_BOOK_HOUR_COVERAGE = 0.95
SPEND_FIRST_DECISION_UTC = "2025-01-01T00:00:00Z"
SPEND_LAST_DECISION_UTC = "2026-08-11T00:00:00Z"
E1_HOLDOUT_UTC = ("2026-08-16T00:00:00Z", "2026-08-25T17:20:00Z")
STACK_FACTORS = (1, 2, 3, 4, 6, 8, 10)

STATUS_PRIORITY = ["DEFINITION_INCOMPLETE", "DATA_BLOCKED", "PIT_BLOCKED", "INFERENCE_SUPPORT_INSUFFICIENT",
                   "STRUCTURAL_INFERENCE_RISK", "INFORMATIONALLY_WEAK", "FEASIBLE_FOR_PREREGISTRATION"]


def ms(iso: str) -> int:
    return int(dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp() * 1000)


def spend_weeks() -> int:
    return L.week_block(ms(SPEND_LAST_DECISION_UTC)) - L.week_block(ms(SPEND_FIRST_DECISION_UTC)) + 1


def spend_window_respects_e1() -> bool:
    last_input = ms(SPEND_LAST_DECISION_UTC) + L.SENSITIVITY_CAP_HOURS * L.BAR_MS
    return last_input <= ms(E1_HOLDOUT_UTC[0]) - DAY_MS


# ---------------------------------------------------------------- dependence

def date_key(e: dict) -> int:
    return e["DECISION_TIME_MS"] // DAY_MS


def cross_symbol_overlap(eps: list[dict]) -> dict:
    """For A episodes: another-symbol episode at the same hour, within 6h and within 24h (any arm, same arm)."""
    times = defaultdict(list)
    for e in eps:
        times[(e["SYMBOL"], e["ARM"])].append(e["DECISION_TIME_MS"])
        times[(e["SYMBOL"], "*")].append(e["DECISION_TIME_MS"])
    for k in times:
        times[k] = np.sort(np.array(times[k], dtype=np.int64))

    def near(sym: str, arm: str, t: int, window_h: int) -> bool:
        for other in PANEL:
            if other == sym or (other, arm) not in times:
                continue
            arr = times[(other, arm)]
            j = int(np.searchsorted(arr, t - window_h * L.BAR_MS))
            if j < arr.size and arr[j] <= t + window_h * L.BAR_MS:
                return True
        return False

    out = {}
    a_eps = [e for e in eps if e["ARM"] == "A"]
    for label, arm in (("ANY_ARM", "*"), ("SAME_ARM", "A")):
        for h in (0, 6, 24):
            hits = sum(near(e["SYMBOL"], arm, e["DECISION_TIME_MS"], h) for e in a_eps)
            out[f"A_WITH_OTHER_SYMBOL_{label}_WITHIN_{h}H"] = {"COUNT": hits,
                                                               "SHARE": hits / len(a_eps) if a_eps else None}
    return out


def market_chains(times_ms, gap_hours: int) -> np.ndarray:
    return L.overlap_chains(np.asarray(times_ms, dtype=np.int64), window_hours=gap_hours)


def concentration(eps: list[dict], arm: str = "A") -> dict:
    sel = [e for e in eps if e["ARM"] == arm]
    if not sel:
        return {}
    by_sym = Counter(e["SYMBOL"] for e in sel)
    by_epoch = Counter(e["EPOCH"] for e in sel)
    shares = np.array(list(by_sym.values())) / len(sel)
    return {"BY_SYMBOL": dict(sorted(by_sym.items())), "BY_EPOCH": dict(sorted(by_epoch.items())),
            "MAX_SYMBOL_SHARE": float(shares.max()), "SYMBOL_HHI": float((shares ** 2).sum()),
            "MAX_EPOCH_SHARE": float(max(by_epoch.values()) / len(sel))}


def layout_stats(eps: list[dict]) -> dict:
    arms = [e["ARM"] for e in eps]
    out = {"NOMINAL_EPISODES": len(eps), "BY_ARM": {}}
    for arm in ARMS:
        sel = [e for e in eps if e["ARM"] == arm]
        out["BY_ARM"][arm] = {
            "EPISODES": len(sel),
            "DISTINCT_DECISION_TIMES": len({e["DECISION_TIME_MS"] for e in sel}),
            "DISTINCT_DATES": len({date_key(e) for e in sel}),
            "WEEK_CLUSTERS": len({e["WEEK_BLOCK"] for e in sel}),
            "MAX_EPISODES_PER_DATE": max(Counter(date_key(e) for e in sel).values()) if sel else 0,
        }
    out["DISTINCT_DECISION_TIMES"] = len({e["DECISION_TIME_MS"] for e in eps})
    out["DISTINCT_DATES"] = len({date_key(e) for e in eps})
    out["WEEK_CLUSTERS"] = len({e["WEEK_BLOCK"] for e in eps})
    for gap in (24, 48):
        ch = market_chains([e["DECISION_TIME_MS"] for e in eps], gap)
        sizes = Counter(int(c) for c in ch)
        out[f"PANEL_MARKET_CHAINS_{gap}H"] = {"COUNT": len(sizes), "MEAN_SIZE": len(eps) / len(sizes) if sizes else None,
                                              "MAX_SIZE": max(sizes.values()) if sizes else 0}
    a_times = [e["DECISION_TIME_MS"] for e in eps if e["ARM"] == "A"]
    if a_times:
        ch = market_chains(a_times, 24)
        out["A_MARKET_CHAINS_24H"] = len(set(ch.tolist()))
    out["ARM_COUNTS"] = dict(Counter(arms))
    return out


# --------------------------------------------------------------------- power

def design_matrix(arms, symbols) -> np.ndarray:
    arms, symbols = np.asarray(arms), np.asarray(symbols)
    cols = [np.ones(arms.size), arms == "A", arms == "B", arms == "C"]
    present = [s for s in PANEL if (symbols == s).any()]
    cols += [symbols == s for s in present[1:]]
    return np.column_stack(cols).astype(float)


def _index(keys) -> tuple[np.ndarray, int]:
    _, inv = np.unique(np.asarray(keys), return_inverse=True)
    return inv, int(inv.max()) + 1


def simulate(arms, symbols, weeks, dates, delta: float, profile: dict, *, reps: int = POWER_REPS,
             seed: int = POWER_SEED) -> dict:
    """Power of the primary interaction and of the A - B secondary under one dependence profile.

    Synthetic outcomes only: p = 0.5 in B, C, D and 0.5 + delta in A, so the
    interaction and A - B both equal delta. Shocks are probit-scale with the
    stated latent ICC; marginal rates are exact. Inference: OLS with symbol
    fixed effects, CR1 by panel-wide week, t(G - 1), two-sided alpha 0.05,
    a positive estimate required.
    """
    arms = np.asarray(arms)
    if any((arms == a).sum() < 2 for a in ARMS):
        return {"POWER_INTERACTION": 0.0, "POWER_A_MINUS_B": 0.0, "REASON": "AN_ARM_HAS_FEWER_THAN_2"}
    X = design_matrix(arms, symbols)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        return {"POWER_INTERACTION": 0.0, "POWER_A_MINUS_B": 0.0, "REASON": "SINGULAR_DESIGN"}
    g, n_g = _index(weeks)
    if n_g < 3:
        return {"POWER_INTERACTION": 0.0, "POWER_A_MINUS_B": 0.0, "REASON": "FEWER_THAN_3_CLUSTERS"}
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    proj = xtx_inv @ X.T
    c_int = np.zeros(k); c_int[1], c_int[2], c_int[3] = 1.0, -1.0, -1.0
    c_ab = np.zeros(k); c_ab[1], c_ab[2] = 1.0, -1.0
    w_int, w_ab = xtx_inv @ c_int, xtx_inv @ c_ab
    scale = n_g / (n_g - 1) * (n - 1) / (n - k)
    icc = profile["LATENT_ICC"]
    tau = math.sqrt(icc / (1.0 - icc)) if icc > 0 else 0.0
    if profile["SHOCK"] == "DATE":
        sg, n_s = _index(dates)
    elif profile["SHOCK"] == "DATE_X_ARM":
        sg, n_s = _index([f"{d}|{a}" for d, a in zip(np.asarray(dates).tolist(), arms.tolist())])
    else:
        sg, n_s = np.zeros(n, dtype=int), 1
    p = np.where(arms == "A", COMPARATOR_RATE + delta, COMPARATOR_RATE)
    loc = stats.norm.ppf(p) * math.sqrt(1.0 + tau * tau)
    crit = stats.t.ppf(1 - ALPHA / 2, n_g - 1)
    rng = np.random.default_rng(seed)
    member = sparse.csr_matrix((np.ones(n), (g, np.arange(n))), shape=(n_g, n))
    xw_int, xw_ab = X @ w_int, X @ w_ab
    hit_int, hit_ab, est_int = [], [], []
    done = 0
    while done < reps:
        m = min(250, reps - done)
        z = rng.standard_normal((n_s, m))[sg] if tau > 0 else 0.0
        y = (rng.standard_normal((n, m)) < loc[:, None] + tau * z).astype(float)
        beta = proj @ y
        resid = y - X @ beta
        for xw, c, hits, ests in ((xw_int, c_int, hit_int, est_int), (xw_ab, c_ab, hit_ab, None)):
            cluster_scores = member @ (xw[:, None] * resid)
            se = np.sqrt(scale * (cluster_scores ** 2).sum(axis=0))
            est = c @ beta
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.where(se > 0, est / se, 0.0)
            hits.extend((t > crit).tolist())
            if ests is not None:
                ests.extend(est.tolist())
        done += m
    return {"POWER_INTERACTION": float(np.mean(hit_int)), "POWER_A_MINUS_B": float(np.mean(hit_ab)),
            "SD_INTERACTION_ESTIMATE": float(np.std(est_int, ddof=1)), "REPS": reps, "WEEK_CLUSTERS": n_g, "N": n}


def collapse(eps: list[dict]) -> list[dict]:
    """One unit per (UTC date, arm): same-day same-arm episodes across symbols become one observation."""
    seen = {}
    for e in sorted(eps, key=lambda e: e["DECISION_TIME_MS"]):
        key = (date_key(e), e["ARM"])
        if key not in seen:
            seen[key] = {"ARM": e["ARM"], "SYMBOL": "PANEL", "WEEK_BLOCK": e["WEEK_BLOCK"], "DATE": date_key(e)}
    return list(seen.values())


def _cols(eps: list[dict]):
    return ([e["ARM"] for e in eps], [e["SYMBOL"] for e in eps], [e["WEEK_BLOCK"] for e in eps],
            [e["DATE"] if "DATE" in e else date_key(e) for e in eps])


def power_curve(eps: list[dict], profile: dict, *, seed_base: int, reps: int = POWER_REPS) -> dict:
    arms, syms, weeks, dates = _cols(eps)
    grid = {}
    sd = None
    for i, d in enumerate(EFFECT_GRID):
        r = simulate(arms, syms, weeks, dates, d, profile, reps=reps, seed=seed_base + i)
        grid[f"{d:.3f}"] = {"INTERACTION": r["POWER_INTERACTION"], "A_MINUS_B": r["POWER_A_MINUS_B"]}
        if sd is None and "SD_INTERACTION_ESTIMATE" in r:
            sd = r["SD_INTERACTION_ESTIMATE"]
    mde = next((d for d in EFFECT_GRID if grid[f"{d:.3f}"]["INTERACTION"] >= TARGET_POWER), None)
    mde_ab = next((d for d in EFFECT_GRID if grid[f"{d:.3f}"]["A_MINUS_B"] >= TARGET_POWER), None)
    return {"POWER_BY_EFFECT": grid, "MDE80_INTERACTION": mde, "MDE80_A_MINUS_B": mde_ab,
            "SD_INTERACTION_ESTIMATE_AT_SMALLEST_EFFECT": sd,
            "AT": {f"{d:.2f}": grid[f"{d:.3f}"] for d in (DIAGNOSTIC_EFFECTS[0], MIN_EFFECT, DIAGNOSTIC_EFFECTS[1])}}


def projected_layouts(eps: list[dict]) -> dict:
    """The first and the last spend-window-length runs of weeks of the 2023-2024 layout."""
    weeks = sorted({e["WEEK_BLOCK"] for e in eps})
    w = spend_weeks()
    lo, hi = weeks[0], weeks[-1]
    first = [e for e in eps if e["WEEK_BLOCK"] < lo + w]
    last = [e for e in eps if e["WEEK_BLOCK"] > hi - w]
    return {"FIRST_WEEKS": first, "LAST_WEEKS": last}


def stacked(eps: list[dict], k: int) -> list[dict]:
    out = []
    for j in range(k):
        for e in eps:
            out.append({**e, "WEEK_BLOCK": e["WEEK_BLOCK"] + 10_000 * j, "DECISION_TIME_MS": e["DECISION_TIME_MS"] + j * 10_000 * L.WEEK_MS})
    return out


def verdict(data_ok: bool, support: dict, max_symbol_share: float, gate_power: float) -> tuple[str, list[str]]:
    reasons = []
    flags = {s: False for s in STATUS_PRIORITY}
    if not data_ok:
        flags["DATA_BLOCKED"] = True
        reasons.append("a panel symbol misses a kline month or has book coverage below 95%")
    if support["MIN_A_WEEK_CLUSTERS"] < MIN_A_WEEK_CLUSTERS or support["MIN_C_WEEK_CLUSTERS"] < MIN_C_WEEK_CLUSTERS:
        flags["INFERENCE_SUPPORT_INSUFFICIENT"] = True
        reasons.append("a projected layout has fewer than 30 week clusters containing A or C")
    if max_symbol_share > MAX_SYMBOL_SHARE_OF_A:
        flags["STRUCTURAL_INFERENCE_RISK"] = True
        reasons.append("one symbol holds more than half of the A episodes")
    if gate_power < TARGET_POWER:
        flags["INFORMATIONALLY_WEAK"] = True
        reasons.append("STRESS power of the interaction at 0.15 is below 0.80 on a projected layout")
    if not any(flags.values()):
        flags["FEASIBLE_FOR_PREREGISTRATION"] = True
        reasons.append("no harder status matched")
    return next(s for s in STATUS_PRIORITY if flags[s]), reasons


# ----------------------------------------------------------------------- I/O

def acquire(workers: int = 8) -> dict:
    jobs = [("KLINES_1M", s, m, None) for s in NEW_SYMBOLS for m in R.KLINE_MONTHS]
    jobs += [("BOOKDEPTH", s, d, None) for s in NEW_SYMBOLS for d in R.book_days()]
    for kind, s, period, _ in jobs:
        R.assert_url_allowed(R.kline_url(s, period) if kind == "KLINES_1M" else R.book_url(s, period))
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(lambda j: R._acquire_one(*j), jobs))
    rows.sort(key=lambda r: (r["KIND"], r["SYMBOL"], r["PERIOD"]))
    body = {
        "DATASET_ID": "DIVERGENCE_PANEL_V0_BINANCE_UM",
        "DESIGN": DESIGN_REL,
        "MARKET": "USD_M_FUTURES",
        "NEW_INSTRUMENTS": list(NEW_SYMBOLS),
        "REUSED_INSTRUMENTS": {"BTCUSDT": R.MANIFEST_REL, "ETHUSDT": R.MANIFEST_REL},
        "KLINE_MONTHS": [R.KLINE_MONTHS[0], R.KLINE_MONTHS[-1]],
        "BOOKDEPTH_DAYS": [R.book_days()[0], R.book_days()[-1]],
        "VERIFIED_AGAINST": "published .CHECKSUM (no pinned inventory exists for these symbols)",
        "OBJECT_COUNTS": dict(Counter(f"{r['KIND']}|{r['SYMBOL']}|{r['STATUS']}" for r in rows)),
        "MISSING_IN_ARCHIVE": [f"{r['KIND']}|{r['SYMBOL']}|{r['PERIOD']}" for r in rows if r["STATUS"] != "VERIFIED"],
        "OBJECTS": [{k: r[k] for k in ("KIND", "SYMBOL", "PERIOD", "STATUS", "SHA256", "BYTES") if k in r} for r in rows],
        "PROTECTED_2025_BYTES_FETCHED": False,
        "PROTECTED_2026_BYTES_FETCHED": False,
    }
    body["CANONICAL_MANIFEST_DIGEST"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    out = REPO / MANIFEST_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(body, indent=1, sort_keys=True) + "\n")
    return body


def detect_symbol(symbol: str) -> tuple[list[dict], dict]:
    bars = R.load_bars(symbol)
    book, book_stats = R.load_book(symbol, bars["open_time_ms"])
    out = L.detect(bars, book, decision_start_ms=R.DECISION_START_MS, decision_last_ms=R.DECISION_LAST_MS)
    eps = out["EPISODES"]
    L.assert_outcome_blind(eps)
    audit = R.pit_audit(bars, book, eps)
    digest = hashlib.sha256("\n".join(L.episode_digest_rows(eps, symbol)).encode()).hexdigest()
    chains = L.overlap_chains([e["DECISION_TIME_MS"] for e in eps])
    for e in eps:
        e["SYMBOL"] = symbol
    manifest = R.MANIFEST_REL if symbol in ("BTCUSDT", "ETHUSDT") else MANIFEST_REL
    objects = [o for o in json.loads((REPO / manifest).read_text())["OBJECTS"]
               if o["SYMBOL"] == symbol and o["KIND"] == "KLINES_1M"]
    kline_missing = len(R.KLINE_MONTHS) - sum(o["STATUS"] == "VERIFIED" for o in objects)
    coverage = book_stats["HOURS_WITH_VALUE_FROM_2023"] / book_stats["HOURS_FROM_2023"]
    meta = {
        "FUNNEL": out["FUNNEL"], "BOOK": {k: v for k, v in book_stats.items()},
        "BOOK_HOUR_COVERAGE": coverage, "KLINE_MONTHS_MISSING": kline_missing,
        "INCOMPLETE_HOURS": int((~bars["complete"]).sum()), "PIT_TRUNCATION_AUDIT": audit,
        "EPISODE_DIGEST": digest,
        "WITHIN_SYMBOL_48H_CHAINS": {"COUNT": len(set(chains.tolist())),
                                     "MAX_SIZE": max(Counter(chains.tolist()).values()) if eps else 0},
        "DATA_OK": kline_missing == 0 and coverage >= MIN_BOOK_HOUR_COVERAGE,
    }
    return eps, meta


def run() -> dict:
    design_bytes = (REPO / DESIGN_REL).read_bytes()
    design = json.loads(design_bytes)
    for rel, digest in design["CODE_IDENTITY"].items():
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"CODE_IDENTITY_MISMATCH:{rel}")
    if not spend_window_respects_e1():
        raise RuntimeError("spend window would reach the E1 holdout")
    all_eps, per_symbol = [], {}
    for sym in PANEL:
        eps, meta = detect_symbol(sym)
        per_symbol[sym] = {**meta, "ARMS": {a: sum(e["ARM"] == a for e in eps) for a in ARMS},
                           "A_DISTINCT_DATES": len({date_key(e) for e in eps if e["ARM"] == "A"})}
        all_eps.extend(eps)
    frozen = json.loads((REPO / "docs/research/SEED0001_FEASIBILITY_REPORT.json").read_text())
    for sym in ("BTCUSDT", "ETHUSDT"):
        if per_symbol[sym]["EPISODE_DIGEST"] != frozen["SYMBOLS"][sym]["EPISODE_DIGEST"]:
            raise RuntimeError(f"SEED0001_EPISODES_NOT_REPRODUCED:{sym}")
    full = layout_stats(all_eps)
    overlap = cross_symbol_overlap(all_eps)
    conc = concentration(all_eps)
    power_full = {name: power_curve(all_eps, prof, seed_base=POWER_SEED + 100 * i)
                  for i, (name, prof) in enumerate(PROFILES.items())}
    power_full["COLLAPSED"] = power_curve(collapse(all_eps), COLLAPSED_PROFILE, seed_base=POWER_SEED + 900)
    projected, support, gate_powers = {}, {"MIN_A_WEEK_CLUSTERS": 10 ** 9, "MIN_C_WEEK_CLUSTERS": 10 ** 9}, []
    for j, (name, eps) in enumerate(projected_layouts(all_eps).items()):
        st = layout_stats(eps)
        pw = {pname: power_curve(eps, prof, seed_base=POWER_SEED + 2000 + 100 * (3 * j + i))
              for i, (pname, prof) in enumerate(PROFILES.items())}
        pw["COLLAPSED"] = power_curve(collapse(eps), COLLAPSED_PROFILE, seed_base=POWER_SEED + 2900 + j)
        projected[name] = {"LAYOUT": st, "POWER": pw}
        support["MIN_A_WEEK_CLUSTERS"] = min(support["MIN_A_WEEK_CLUSTERS"], st["BY_ARM"]["A"]["WEEK_CLUSTERS"])
        support["MIN_C_WEEK_CLUSTERS"] = min(support["MIN_C_WEEK_CLUSTERS"], st["BY_ARM"]["C"]["WEEK_CLUSTERS"])
        gate_powers.append(pw[GATE_PROFILE]["AT"][f"{MIN_EFFECT:.2f}"]["INTERACTION"])
    design_effect = {}
    base_sd = power_full["INDEPENDENT"]["SD_INTERACTION_ESTIMATE_AT_SMALLEST_EFFECT"]
    for name in ("BASE", "STRESS"):
        sd = power_full[name]["SD_INTERACTION_ESTIMATE_AT_SMALLEST_EFFECT"]
        de = (sd / base_sd) ** 2 if base_sd else None
        design_effect[name] = {"DESIGN_EFFECT_ON_INTERACTION_VARIANCE": de,
                               "EFFECTIVE_N_EQUIVALENT": len(all_eps) / de if de else None}
    days_disc = (R.DECISION_LAST_MS - (R.DECISION_START_MS + 20 * DAY_MS)) / DAY_MS
    required = {}
    for kf in STACK_FACTORS:
        r = simulate(*_cols(stacked(all_eps, kf)), MIN_EFFECT, PROFILES[GATE_PROFILE], reps=1000, seed=POWER_SEED + 5000 + kf)
        required[str(kf)] = {"YEARS_OF_PANEL_HISTORY": round(days_disc * kf / 365.25, 1),
                             "STRESS_POWER_INTERACTION_AT_0_15": r["POWER_INTERACTION"]}
    data_ok = all(m["DATA_OK"] for m in per_symbol.values())
    status, reasons = verdict(data_ok, support, conc["MAX_SYMBOL_SHARE"], min(gate_powers))
    days_spend = (ms(SPEND_LAST_DECISION_UTC) - ms(SPEND_FIRST_DECISION_UTC)) / DAY_MS + 1
    est = {sym: {a: round(m["ARMS"][a] * days_spend / days_disc, 1) for a in ARMS} for sym, m in per_symbol.items()}
    report = {
        "REPORT": "DIVERGENCE_PANEL_FEASIBILITY_V0",
        "DESIGN_PATH": DESIGN_REL, "DESIGN_SHA256": hashlib.sha256(design_bytes).hexdigest(),
        "PANEL": list(PANEL), "DETECTOR": "SEED0001_DETECTOR_V1 (unchanged)",
        "PER_SYMBOL": per_symbol, "PANEL_LAYOUT_2023_2024": full,
        "CROSS_SYMBOL_OVERLAP_A": overlap, "A_CONCENTRATION": conc,
        "POWER_2023_2024_LAYOUT": power_full, "DESIGN_EFFECT": design_effect,
        "SPEND_WINDOW": {"DECISIONS_UTC": [SPEND_FIRST_DECISION_UTC, SPEND_LAST_DECISION_UTC], "WEEKS": spend_weeks(),
                         "E1_HOLDOUT_UTC": list(E1_HOLDOUT_UTC), "RESPECTS_E1": spend_window_respects_e1(),
                         "ESTIMATED_EPISODES_BY_SYMBOL_RATE_SCALED": est,
                         "ESTIMATED_EPISODES_TOTAL": {a: round(sum(v[a] for v in est.values()), 1) for a in ARMS}},
        "PROJECTED_SPEND_LAYOUTS": projected, "INFERENCE_SUPPORT": support,
        "GATE": {"PROFILE": GATE_PROFILE, "EFFECT": MIN_EFFECT, "POWER_ON_PROJECTED_LAYOUTS": gate_powers,
                 "MIN_POWER": min(gate_powers), "TARGET": TARGET_POWER},
        "REQUIRED_HISTORY_STACKED_EXTRAPOLATION": required,
        "VERDICT": status, "VERDICT_REASONS": reasons,
        "OUTCOMES_COMPUTED": False, "PROTECTED_2025_2026_OPENED": False,
        "NEW_SYMBOL_OUTCOMES_OPENED": False,
        "RUNNER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (REPO / REPORT_REL).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def main(argv: list[str]) -> int:
    if argv[:1] == ["acquire"]:
        m = acquire()
        print(json.dumps({"OBJECT_COUNTS": m["OBJECT_COUNTS"], "MISSING": m["MISSING_IN_ARCHIVE"][:20]}, sort_keys=True))
        return 0
    if argv[:1] == ["run"]:
        r = run()
        print(json.dumps({"VERDICT": r["VERDICT"], "GATE": r["GATE"]}, sort_keys=True))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
