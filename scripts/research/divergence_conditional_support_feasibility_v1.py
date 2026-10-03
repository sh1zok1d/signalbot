"""DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1: outcome-blind feasibility for A - B.

Frozen design: `docs/research/DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_DESIGN.json`.

New research question (not a reinterpretation of V0, whose verdict
INFORMATIONALLY_WEAK stands): conditional on a support state, does regular
bullish divergence add practically meaningful value? Primary estimand A - B
(A = support + divergence, B = support only), minimum effect 0.15. The V0
interaction (A - B) - (C - D) is kept as a secondary mechanistic estimand.

Uses the same six-symbol panel, the unchanged SEED-0001 detector and the V0
dependence profiles. It computes no outcome and reads no byte dated 2025 or
later. The protected spend window and any prospective continuation are
represented only by structural stand-ins built from the 2023-2024 layout.

    python -m scripts.research.divergence_conditional_support_feasibility_v1 run
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy import sparse, stats

from scripts.research import divergence_panel_feasibility_v0 as V0
from scripts.research import seed0001_regular_divergence_lib as L

REPO = Path(__file__).resolve().parents[2]
DESIGN_REL = "docs/research/DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_DESIGN.json"
REPORT_REL = "docs/research/DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1_REPORT.json"
ARMS = ("A", "B", "C", "D")
MIN_EFFECT = 0.15
REPORTED_EFFECTS = (0.10, 0.15, 0.20)
EFFECT_GRID = V0.EFFECT_GRID
TARGET_POWER = 0.80
ALPHA = 0.05
CURVE_REPS = 2000
GATE_REPS = 10_000
SEED = 20261006
PROFILES = dict(V0.PROFILES)
COLLAPSED_PROFILE = dict(V0.COLLAPSED_PROFILE)
GATE_PROFILE = "STRESS"
MIN_A_WEEK_CLUSTERS = 30
MIN_B_WEEK_CLUSTERS = 30
MAX_SYMBOL_SHARE_OF_A = 0.50
PROSPECTIVE_START_UTC = "2026-10-05T00:00:00Z"
PROSPECTIVE_READS_NOT_BEFORE_UTC = "2026-08-27T00:00:00Z"
PROSPECTIVE_GRID_STEP_WEEKS = 4
PROSPECTIVE_MAX_WEEKS = 156
SCREEN_REPS = 4000
DEADLINE_FACTOR = 2.0
STATUS_PRIORITY = V0.STATUS_PRIORITY


# ------------------------------------------------------------- simulation

def simulate(arms, symbols, weeks, dates, delta: float, profile: dict, *, reps: int, seed: int) -> dict:
    """Power of A - B (primary) and (A - B) - (C - D) (secondary); synthetic outcomes only.

    Same planning alternative, shocks and inference as V0: p = 0.5 in B, C, D
    and 0.5 + delta in A; OLS with symbol fixed effects; CR1 by panel-wide
    UTC week; t(G - 1); two-sided 0.05 with a positive estimate required.
    """
    arms = np.asarray(arms)
    if any((arms == a).sum() < 2 for a in ARMS):
        return {"POWER_A_MINUS_B": 0.0, "POWER_INTERACTION": 0.0, "REASON": "AN_ARM_HAS_FEWER_THAN_2"}
    X = V0.design_matrix(arms, symbols)
    if np.linalg.matrix_rank(X) < X.shape[1]:
        return {"POWER_A_MINUS_B": 0.0, "POWER_INTERACTION": 0.0, "REASON": "SINGULAR_DESIGN"}
    g, n_g = V0._index(weeks)
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    proj = xtx_inv @ X.T
    c_ab = np.zeros(k); c_ab[1], c_ab[2] = 1.0, -1.0
    c_int = np.zeros(k); c_int[1], c_int[2], c_int[3] = 1.0, -1.0, -1.0
    xw = {"AB": X @ (xtx_inv @ c_ab), "INT": X @ (xtx_inv @ c_int)}
    cvec = {"AB": c_ab, "INT": c_int}
    scale = n_g / (n_g - 1) * (n - 1) / (n - k)
    icc = profile["LATENT_ICC"]
    tau = math.sqrt(icc / (1.0 - icc)) if icc > 0 else 0.0
    if profile["SHOCK"] == "DATE":
        sg, n_s = V0._index(dates)
    elif profile["SHOCK"] == "DATE_X_ARM":
        sg, n_s = V0._index([f"{d}|{a}" for d, a in zip(np.asarray(dates).tolist(), arms.tolist())])
    else:
        sg, n_s = np.zeros(n, dtype=int), 1
    p = np.where(arms == "A", 0.5 + delta, 0.5)
    loc = stats.norm.ppf(p) * math.sqrt(1.0 + tau * tau)
    crit = stats.t.ppf(1 - ALPHA / 2, n_g - 1)
    member = sparse.csr_matrix((np.ones(n), (g, np.arange(n))), shape=(n_g, n))
    rng = np.random.default_rng(seed)
    hits = {"AB": 0, "INT": 0}
    ests = {"AB": [], "INT": []}
    done = 0
    while done < reps:
        m = min(500, reps - done)
        z = rng.standard_normal((n_s, m))[sg] if tau > 0 else 0.0
        y = (rng.standard_normal((n, m)) < loc[:, None] + tau * z).astype(float)
        beta = proj @ y
        resid = y - X @ beta
        for key in ("AB", "INT"):
            se = np.sqrt(scale * ((member @ (xw[key][:, None] * resid)) ** 2).sum(axis=0))
            est = cvec[key] @ beta
            with np.errstate(divide="ignore", invalid="ignore"):
                t = np.where(se > 0, est / se, 0.0)
            hits[key] += int((t > crit).sum())
            ests[key].extend(est.tolist())
        done += m
    return {"POWER_A_MINUS_B": hits["AB"] / reps, "POWER_INTERACTION": hits["INT"] / reps,
            "SD_A_MINUS_B": float(np.std(ests["AB"], ddof=1)), "SD_INTERACTION": float(np.std(ests["INT"], ddof=1)),
            "REPS": reps, "WEEK_CLUSTERS": n_g, "N": n}


def cols(eps):
    return V0._cols(eps)


def power_table(eps: list[dict], seed_base: int) -> dict:
    out = {}
    layouts = {name: (eps, prof) for name, prof in PROFILES.items()}
    layouts["COLLAPSED"] = (V0.collapse(eps), COLLAPSED_PROFILE)
    for i, (name, (lay, prof)) in enumerate(layouts.items()):
        grid = {}
        for j, d in enumerate(EFFECT_GRID):
            r = simulate(*cols(lay), d, prof, reps=CURVE_REPS, seed=seed_base + 100 * i + j)
            grid[f"{d:.3f}"] = {"A_MINUS_B": r["POWER_A_MINUS_B"], "INTERACTION": r["POWER_INTERACTION"]}
        out[name] = {
            "AT": {f"{d:.2f}": grid[f"{d:.3f}"] for d in REPORTED_EFFECTS},
            "MDE80_A_MINUS_B": next((d for d in EFFECT_GRID if grid[f"{d:.3f}"]["A_MINUS_B"] >= TARGET_POWER), None),
            "MDE80_INTERACTION": next((d for d in EFFECT_GRID if grid[f"{d:.3f}"]["INTERACTION"] >= TARGET_POWER), None),
            "POWER_BY_EFFECT": grid,
        }
    return out


def gate_power(eps: list[dict], seed: int, reps: int = GATE_REPS) -> dict:
    r = simulate(*cols(eps), MIN_EFFECT, PROFILES[GATE_PROFILE], reps=reps, seed=seed)
    mc_se = math.sqrt(r["POWER_A_MINUS_B"] * (1 - r["POWER_A_MINUS_B"]) / reps)
    return {"POWER_A_MINUS_B": r["POWER_A_MINUS_B"], "MC_SE": mc_se, "REPS": reps,
            "POWER_INTERACTION": r["POWER_INTERACTION"], "PASS": r["POWER_A_MINUS_B"] >= TARGET_POWER}


def design_effect(eps: list[dict], seed: int) -> dict:
    ind = simulate(*cols(eps), 0.0, PROFILES["INDEPENDENT"], reps=CURVE_REPS, seed=seed)
    out = {}
    for name in ("BASE", "STRESS"):
        r = simulate(*cols(eps), 0.0, PROFILES[name], reps=CURVE_REPS, seed=seed + 1)
        de = (r["SD_A_MINUS_B"] / ind["SD_A_MINUS_B"]) ** 2
        n_ab = sum(e["ARM"] in ("A", "B") for e in eps)
        out[name] = {"DESIGN_EFFECT_A_MINUS_B": de, "A_PLUS_B_EFFECTIVE_N": n_ab / de}
    return out


# ------------------------------------------------------------ layouts

def layout_counts(eps: list[dict]) -> dict:
    a = [e for e in eps if e["ARM"] == "A"]
    b = [e for e in eps if e["ARM"] == "B"]
    by_sym = Counter(e["SYMBOL"] for e in a)
    by_epoch = Counter(e["EPOCH"] for e in a if "EPOCH" in e)
    return {
        "A_EPISODES": len(a), "B_EPISODES": len(b),
        "A_DECISION_DATES": len({V0.date_key(e) for e in a}),
        "A_WEEK_CLUSTERS": len({e["WEEK_BLOCK"] for e in a}),
        "B_WEEK_CLUSTERS": len({e["WEEK_BLOCK"] for e in b}),
        "WEEK_CLUSTERS": len({e["WEEK_BLOCK"] for e in eps}),
        "A_BY_SYMBOL": dict(sorted(by_sym.items())),
        "A_MAX_SYMBOL_SHARE": max(by_sym.values()) / len(a) if a else None,
        "A_BY_EPOCH": dict(sorted(by_epoch.items())),
        "A_MAX_EPOCH_SHARE": max(by_epoch.values()) / len(a) if by_epoch else None,
    }


def week_span(eps: list[dict]) -> tuple[int, int]:
    weeks = [e["WEEK_BLOCK"] for e in eps]
    return min(weeks), max(weeks)


def continuation(eps: list[dict], start_week: int, n_weeks: int, *, exclude_symbols=()) -> list[dict]:
    """Structural stand-in for n_weeks of prospective panel stream.

    Cycles through the weeks of the 2023-2024 layout starting at start_week and
    re-labels each copy with new week ids and shifted timestamps, so the copies
    never share a cluster or a shock with the historical stand-in.
    """
    lo, hi = week_span(eps)
    span = hi - lo + 1
    by_week = {}
    for e in eps:
        by_week.setdefault(e["WEEK_BLOCK"], []).append(e)
    out = []
    for step in range(n_weeks):
        src = lo + (start_week - lo + step) % span
        new_week = 1_000_000 + step
        shift = (new_week - src) * L.WEEK_MS
        for e in by_week.get(src, []):
            if e["SYMBOL"] in exclude_symbols:
                continue
            out.append({**e, "WEEK_BLOCK": new_week, "DECISION_TIME_MS": e["DECISION_TIME_MS"] + shift,
                        "EPOCH": "PROSPECTIVE"})
    return out


def combined_search(proxy: list[dict], source: list[dict], start_week: int, seed: int, *,
                    exclude_symbols=()) -> dict:
    """Smallest prospective continuation (in weeks) that reaches STRESS power 0.80 for A - B at 0.15.

    Screened on a 4-week grid with 4000 replicates; the first screened pass must
    be confirmed with 10000 replicates, otherwise the search continues.
    """
    screen = {}
    found = None
    for w in range(0, PROSPECTIVE_MAX_WEEKS + 1, PROSPECTIVE_GRID_STEP_WEEKS):
        pros = continuation(source, start_week, w, exclude_symbols=exclude_symbols)
        lay = proxy + pros
        r = simulate(*cols(lay), MIN_EFFECT, PROFILES[GATE_PROFILE], reps=SCREEN_REPS, seed=seed + w)
        screen[str(w)] = r["POWER_A_MINUS_B"]
        if r["POWER_A_MINUS_B"] >= TARGET_POWER:
            confirm = gate_power(lay, seed=seed + 10_000 + w)
            if confirm["PASS"]:
                found = {"PROSPECTIVE_WEEKS": w, "CONFIRMED_POWER": confirm,
                         "TOTAL": layout_counts(lay), "PROSPECTIVE_PART": layout_counts(pros) if pros else None}
                break
    return {"SCREEN_POWER_BY_WEEKS": screen, "FIRST_PASS": found}


def stopping_rule(results: list[dict]) -> dict | None:
    """Thresholds from the more demanding proxy: cumulative A episodes, A-week clusters, deadline."""
    found = [r["FIRST_PASS"] for r in results]
    if any(f is None for f in found):
        return None
    weeks = max(f["PROSPECTIVE_WEEKS"] for f in found)
    n_a = max(f["TOTAL"]["A_EPISODES"] for f in found)
    g_a = max(f["TOTAL"]["A_WEEK_CLUSTERS"] for f in found)
    start = V0.ms(PROSPECTIVE_START_UTC)
    deadline_weeks = int(math.ceil(DEADLINE_FACTOR * max(weeks, 1)))
    return {
        "EXPECTED_PROSPECTIVE_WEEKS": weeks,
        "EXPECTED_STOP_DATE_UTC": L.iso_utc(start + weeks * L.WEEK_MS),
        "STOP_WHEN": f"cumulative (historical window + prospective) A episodes >= {n_a} AND cumulative A week clusters >= {g_a}",
        "CUMULATIVE_A_EPISODES": n_a, "CUMULATIVE_A_WEEK_CLUSTERS": g_a,
        "DEADLINE_UTC": L.iso_utc(start + deadline_weeks * L.WEEK_MS),
        "AT_DEADLINE_BELOW_THRESHOLDS": "INCONCLUSIVE; no extension (a new preregistration on later data)",
        "MONITORING": "counts only (episodes, arms, week clusters); no outcome before the stop",
    }


# ---------------------------------------------------------------- run

def run() -> dict:
    design_bytes = (REPO / DESIGN_REL).read_bytes()
    design = json.loads(design_bytes)
    for rel, digest in design["CODE_IDENTITY"].items():
        if hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"CODE_IDENTITY_MISMATCH:{rel}")
    if not V0.spend_window_respects_e1():
        raise RuntimeError("spend window would reach the E1 holdout")
    if V0.ms(PROSPECTIVE_READS_NOT_BEFORE_UTC) <= V0.ms(V0.E1_HOLDOUT_UTC[1]):
        raise RuntimeError("prospective reads would reach the E1 holdout")
    v0 = json.loads((REPO / V0.REPORT_REL).read_text())
    all_eps, per_symbol = [], {}
    for sym in V0.PANEL:
        eps, meta = V0.detect_symbol(sym)
        if meta["EPISODE_DIGEST"] != v0["PER_SYMBOL"][sym]["EPISODE_DIGEST"]:
            raise RuntimeError(f"V0_EPISODES_NOT_REPRODUCED:{sym}")
        per_symbol[sym] = {"EPISODE_DIGEST": meta["EPISODE_DIGEST"], "DATA_OK": meta["DATA_OK"]}
        all_eps.extend(eps)
    proxies = V0.projected_layouts(all_eps)
    lo, hi = week_span(all_eps)
    starts = {"FIRST_WEEKS": lo + V0.spend_weeks(), "LAST_WEEKS": lo}
    historical, combined, combined_ex_btc = {}, [], []
    for j, (name, eps) in enumerate(proxies.items()):
        historical[name] = {
            "COUNTS": layout_counts(eps),
            "POWER": power_table(eps, seed_base=SEED + 1000 * j),
            "GATE": gate_power(eps, seed=SEED + 50_000 + j),
            "DESIGN_EFFECT": design_effect(eps, seed=SEED + 60_000 + j),
        }
        res = combined_search(eps, all_eps, starts[name], seed=SEED + 100_000 * (j + 1))
        res["PROXY"] = name
        combined.append(res)
        res_x = combined_search(eps, all_eps, starts[name], seed=SEED + 500_000 * (j + 1),
                                exclude_symbols=("BTCUSDT",))
        res_x["PROXY"] = name
        combined_ex_btc.append(res_x)
    full = {"COUNTS": layout_counts(all_eps), "POWER": power_table(all_eps, seed_base=SEED + 9000)}
    support_ok = all(h["COUNTS"]["A_WEEK_CLUSTERS"] >= MIN_A_WEEK_CLUSTERS and
                     h["COUNTS"]["B_WEEK_CLUSTERS"] >= MIN_B_WEEK_CLUSTERS for h in historical.values())
    conc_ok = all(h["COUNTS"]["A_MAX_SYMBOL_SHARE"] <= MAX_SYMBOL_SHARE_OF_A for h in historical.values())
    data_ok = all(m["DATA_OK"] for m in per_symbol.values())
    hist_pass = all(h["GATE"]["PASS"] for h in historical.values())
    hist_status = ("DATA_BLOCKED" if not data_ok else "INFERENCE_SUPPORT_INSUFFICIENT" if not support_ok
                   else "STRUCTURAL_INFERENCE_RISK" if not conc_ok
                   else "FEASIBLE_FOR_PREREGISTRATION" if hist_pass else "INFORMATIONALLY_WEAK")
    rule = stopping_rule(combined)
    rule_ex = stopping_rule(combined_ex_btc)
    comb_status = (hist_status if hist_status in ("DATA_BLOCKED", "INFERENCE_SUPPORT_INSUFFICIENT", "STRUCTURAL_INFERENCE_RISK")
                   else "FEASIBLE_FOR_PREREGISTRATION" if rule is not None else "INFORMATIONALLY_WEAK")
    report = {
        "REPORT": "DIVERGENCE_CONDITIONAL_SUPPORT_FEASIBILITY_V1",
        "DESIGN_PATH": DESIGN_REL, "DESIGN_SHA256": hashlib.sha256(design_bytes).hexdigest(),
        "V0_VERDICT_UNCHANGED": v0["VERDICT"],
        "PRIMARY_ESTIMAND": "A - B", "SECONDARY_ESTIMAND": "(A - B) - (C - D)", "MIN_EFFECT": MIN_EFFECT,
        "PER_SYMBOL": per_symbol, "FULL_2023_2024_LAYOUT_REFERENCE": full,
        "HISTORICAL_WINDOW_PROXIES": historical,
        "HISTORICAL_ONLY_VERDICT": hist_status,
        "COMBINED_DESIGN": {"PROSPECTIVE_START_UTC": PROSPECTIVE_START_UTC,
                            "PROSPECTIVE_READS_NOT_BEFORE_UTC": PROSPECTIVE_READS_NOT_BEFORE_UTC,
                            "ALL_SIX_SYMBOLS": {"SEARCH": combined, "STOPPING_RULE": rule},
                            "PROSPECTIVE_WITHOUT_BTC": {"SEARCH": combined_ex_btc, "STOPPING_RULE": rule_ex}},
        "COMBINED_DESIGN_VERDICT": comb_status,
        "SPEND_WINDOW_ESTIMATE_RATE_SCALED": v0["SPEND_WINDOW"]["ESTIMATED_EPISODES_TOTAL"],
        "OUTCOMES_COMPUTED": False, "PROTECTED_2025_2026_OPENED": False, "SEED0003_CREATED": False,
        "RUNNER_SHA256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (REPO / REPORT_REL).write_text(json.dumps(report, indent=1, sort_keys=True) + "\n")
    return report


def main(argv: list[str]) -> int:
    if argv[:1] == ["run"]:
        r = run()
        print(json.dumps({"HISTORICAL_ONLY": r["HISTORICAL_ONLY_VERDICT"], "COMBINED": r["COMBINED_DESIGN_VERDICT"]}))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
