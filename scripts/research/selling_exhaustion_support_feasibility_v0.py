"""SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0 runner: feasibility only.

Frozen design: `docs/research/SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0_DESIGN.json`.

Reads only the already-exposed six-symbol surface (decisions 2023-01-01 ..
2026-08-11; every read ends before the E1-safe horizon 2026-08-15) through the
verified loaders of DIVERGENCE_FULL_HISTORY_RESEARCH_V0.

What is computed:
- support episodes of the unchanged SEED-0001 detector;
- the frozen candidate states and scores;
- counts and structural dependence;
- a state-blind outcome-dependence calibration;
- synthetic-outcome power for E - S;
- a binary-versus-continuous comparison;
- prospective projections.

No E-versus-S outcome contrast is computed: real outcomes enter only the
state-blind calibration, as a vector with cluster keys. No candidate state is
ever passed to it.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path

import numpy as np

from scripts.research import divergence_full_history_v0 as FH
from scripts.research import divergence_full_history_v0_lib as F
from scripts.research import divergence_panel_feasibility_v0 as V0
from scripts.research import seed0001_regular_divergence_lib as L
from scripts.research import selling_exhaustion_support_feasibility_v0_lib as S

REPO = Path(__file__).resolve().parents[2]
DESIGN_REL = "docs/research/SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0_DESIGN.json"
RESULT_REL = "docs/research/SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0.json"
PANEL = FH.PANEL
FIRST_DECISION_MS = F.DISCOVERY_FIRST_DECISION_MS
LAST_DECISION_MS = F.VALIDATION_LAST_DECISION_MS
PIT_AUDIT_PER_SYMBOL = 30
NULL_REPS = 4000
CURVE_REPS = 2000
COMPARE_REPS = 2000
CONFIRM_REPS = 4000
BOOTSTRAP_RESAMPLES = 999
SEED = 20261008
PLANNING_START_UTC = "2026-10-12T00:00:00Z"
COMPARE_EFFECTS = (0.03, 0.04, 0.05, 0.075, 0.10)
COMPARE_PROFILES = ("INDEPENDENT", "BASE", "STRESS", "EMPIRICAL")
POWER_PROFILES = ("INDEPENDENT", "BASE", "STRESS", "EMPIRICAL", "EMPIRICAL_UPPER", "COLLAPSED")
CONFIRM_PROFILES = ("INDEPENDENT", "BASE", "STRESS", "EMPIRICAL", "EMPIRICAL_UPPER")
WEEKS_PER_YEAR = 365.25 / 7.0


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_bindings() -> str:
    design_path = REPO / DESIGN_REL
    dsg = json.loads(design_path.read_text())
    for rel, digest in dsg["CODE_IDENTITY"].items():
        if _sha(REPO / rel) != digest:
            raise RuntimeError(f"CODE_IDENTITY_MISMATCH:{rel}")
    for rel, digest in dsg["FROZEN_ARTIFACTS"].items():
        if _sha(REPO / rel) != digest:
            raise RuntimeError(f"FROZEN_ARTIFACT_CHANGED:{rel}")
    return _sha(design_path)


# ------------------------------------------------------------------ symbols

def _same(a: dict, b: dict) -> bool:
    for k in S.STATE_INPUTS:
        x, y = a[k], b[k]
        if not ((math.isnan(x) and math.isnan(y)) or x == y):
            return False
    return True


def pit_audit(bars: dict, oi: dict, support: list[dict]) -> dict:
    """Recompute state inputs on bars and OI truncated at T for a deterministic sample."""
    if not support:
        return {"CHECKED": 0, "IDENTICAL": 0}
    step = max(1, len(support) // PIT_AUDIT_PER_SYMBOL)
    same = 0
    sample = support[::step][:PIT_AUDIT_PER_SYMBOL]
    for ep in sample:
        t = ep["DECISION_TIME_MS"]
        keep = bars["open_time_ms"] + L.BAR_MS <= t
        tb = {k: v[keep] for k, v in bars.items() if isinstance(v, np.ndarray)}
        ko = oi["available_ms"] <= t
        toi = {"available_ms": oi["available_ms"][ko], "value": oi["value"][ko]}
        same += _same(S.state_inputs(tb, toi, ep), S.state_inputs(bars, oi, ep))
    return {"CHECKED": len(sample), "IDENTICAL": same}


def state_blind_outcomes(minutes: dict, support: list[dict], symbol: str) -> list[dict]:
    """+1R-before--1R-within-48h outcomes of support episodes inside the frozen full-history slices only.

    These outcomes were already opened by DIVERGENCE_FULL_HISTORY_RESEARCH_V0. The
    records carry no candidate state.
    """
    out = []
    for ep in support:
        if F.slice_of(ep["DECISION_TIME_MS"]) is None:
            continue
        y = F.episode_outcomes(minutes, ep)["Y1_48H"]
        if y is None:
            continue
        out.append({"Y": int(y), "SYMBOL": symbol, "DECISION_TIME_MS": ep["DECISION_TIME_MS"],
                    "WEEK_BLOCK": ep["WEEK_BLOCK"]})
    return out


def symbol_pass(symbol: str, pins: dict, v0_digest: str, validation_ids: set) -> tuple[list, list, dict]:
    minutes = FH.load_minutes(symbol, pins)
    bars = L.hourly_bars(minutes["t"], minutes["open"], minutes["high"], minutes["low"], minutes["close"],
                         minutes["volume"], minutes["taker_buy"])
    book, book_meta = FH.load_book(symbol, bars["open_time_ms"])
    with FH.e1_safe_detector_guard():
        det = L.detect(bars, book, decision_start_ms=FIRST_DECISION_MS, decision_last_ms=LAST_DECISION_MS)
        L.assert_outcome_blind(det["EPISODES"])
    eps = det["EPISODES"]
    disc = [e for e in eps if F.slice_of(e["DECISION_TIME_MS"]) == "DISCOVERY"]
    digest = hashlib.sha256("\n".join(L.episode_digest_rows(disc, symbol)).encode()).hexdigest()
    if digest != v0_digest:
        raise RuntimeError(f"DISCOVERY_EPISODES_NOT_REPRODUCED:{symbol}")
    val = {f"{symbol}-{e['DECISION_TIME_UTC']}" for e in eps if F.slice_of(e["DECISION_TIME_MS"]) == "VALIDATION"}
    if val != validation_ids:
        raise RuntimeError(f"VALIDATION_EPISODES_NOT_REPRODUCED:{symbol}")
    oi, oi_meta = FH.load_oi(symbol, pins)
    support = [e for e in eps if e["SUPPORT"]]
    rows = []
    for ep in support:
        x = S.state_inputs(bars, oi, ep)
        rows.append({
            "SYMBOL": symbol, "EPISODE_ID": f"{symbol}-{ep['DECISION_TIME_UTC']}",
            "DECISION_TIME_MS": ep["DECISION_TIME_MS"], "WEEK_BLOCK": ep["WEEK_BLOCK"], "EPOCH": ep["EPOCH"],
            "SLICE": F.slice_of(ep["DECISION_TIME_MS"]) or "BETWEEN_SLICES", "ARM": ep["ARM"],
            "DIVERGENCE": bool(ep["DIVERGENCE"]), "RSI_FAMILY": bool(ep["RSI_FAMILY"]),
            "MACD_FAMILY": bool(ep["MACD_FAMILY"]), "CVD_FAMILY": bool(ep["CVD_FAMILY"]),
            **x, **S.state_flags(x),
        })
    meta = {"EPISODES_ALL_ARMS": len(eps), "SUPPORT_EPISODES": len(support), "DISCOVERY_DIGEST_REPRODUCED": True,
            "VALIDATION_IDS_REPRODUCED": True, "PIT_AUDIT": pit_audit(bars, oi, support),
            "BOOK_DAYS_MISSING": book_meta["DAYS_MISSING"], "OI_DAYS_MISSING": len(oi_meta["DAYS_MISSING"]),
            "FUNNEL": det["FUNNEL"]}
    return rows, state_blind_outcomes(minutes, support, symbol), meta


# --------------------------------------------------------------- analysis

def finite_or_none(obj):
    """JSON-safe copy: non-finite floats become None (e.g. a projection that never reaches 80%)."""
    if isinstance(obj, dict):
        return {k: finite_or_none(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [finite_or_none(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return float(obj) if math.isfinite(obj) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def _round(d: float) -> str:
    return f"{d:.3f}"


def yields(rows: list[dict], variant: str, weeks_ref: int) -> dict:
    sel = [r for r in rows if r[variant] is not None]
    e = [r for r in sel if r[variant] == 1]
    per_week = Counter(r["WEEK_BLOCK"] for r in e)
    return {"E_PER_WEEK": len(e) / weeks_ref, "S_PER_WEEK": (len(sel) - len(e)) / weeks_ref,
            "SHARE_OF_WEEKS_WITH_E": len(per_week) / weeks_ref,
            "E_PER_YEAR": len(e) / weeks_ref * WEEKS_PER_YEAR,
            "S_PER_YEAR": (len(sel) - len(e)) / weeks_ref * WEEKS_PER_YEAR,
            "E_WEEK_CLUSTERS_PER_YEAR": len(per_week) / weeks_ref * WEEKS_PER_YEAR}


def descriptive_crosstabs(rows: list[dict]) -> dict:
    out = {}
    both = [r for r in rows if r["SE_LEG"] is not None and r["SE_BASELINE"] is not None]
    tab = Counter((r["SE_LEG"], r["SE_BASELINE"]) for r in both)
    e_leg = {r["EPISODE_ID"] for r in both if r["SE_LEG"] == 1}
    e_base = {r["EPISODE_ID"] for r in both if r["SE_BASELINE"] == 1}
    out["VARIANT_OVERLAP"] = {"LEG1_BASE1": tab[(1, 1)], "LEG1_BASE0": tab[(1, 0)], "LEG0_BASE1": tab[(0, 1)],
                              "LEG0_BASE0": tab[(0, 0)],
                              "JACCARD_E": len(e_leg & e_base) / len(e_leg | e_base) if e_leg | e_base else None}
    for v in S.VARIANTS:
        sel = [r for r in rows if r[v] is not None]
        out[v] = {}
        for label, val in (("E", 1), ("S", 0)):
            grp = [r for r in sel if r[v] == val]
            out[v][label] = {f"{k}_SHARE": sum(r[k] for r in grp) / len(grp) if grp else None
                             for k in ("DIVERGENCE", "RSI_FAMILY", "MACD_FAMILY", "CVD_FAMILY")}
    return out


def outcome_dependence(blind: list[dict]) -> dict:
    y = np.array([b["Y"] for b in blind], dtype=float)
    per_week, wi = S.outcome_pair_stats(y, [b["SYMBOL"] for b in blind], [b["DECISION_TIME_MS"] for b in blind],
                                        [b["WEEK_BLOCK"] for b in blind])
    phi = S.phi_from_pairs(per_week, y, wi)
    boot = S.week_bootstrap_phi(per_week, y, wi, resamples=BOOTSTRAP_RESAMPLES, seed=SEED + 1)
    emp = S.latent_profile(phi)
    upper = S.latent_profile({k: boot[k]["Q95"] for k in S.PAIR_CLASSES})
    implied = {
        "BASE": {"DATE_OTHER_SYMBOL": 2 / math.pi * math.asin(0.25), "WEEK_OTHER_DATE_OTHER_SYMBOL": 0.0,
                 "SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK": 0.0},
        "STRESS": {"DATE_OTHER_SYMBOL_SAME_STATE": 2 / math.pi * math.asin(0.50), "DATE_OTHER_SYMBOL_OTHER_STATE": 0.0,
                   "WEEK_OTHER_DATE_OTHER_SYMBOL": 0.0, "SYMBOL_CHAIN_OTHER_DATE_SAME_WEEK": 0.0},
    }
    return {"N": int(y.size), "WEEK_CLUSTERS": int(wi.max()) + 1, "SUPPORT_POPULATION_Y1_48H_RATE": float(y.mean()),
            "PHI": phi, "PHI_WEEK_BOOTSTRAP": boot, "EMPIRICAL_PROFILE": emp, "EMPIRICAL_UPPER_PROFILE": upper,
            "PHI_IMPLIED_BY_ASSUMED_PROFILES": implied,
            "STATE_BLIND": True}


def _profile(name: str, profiles: dict) -> dict:
    return profiles["BASE"] if name == "COLLAPSED" else profiles[name]


def power_block(lay: dict, profiles: dict, weeks_ref: int, seed: int) -> dict:
    out = {}
    for pi, name in enumerate(POWER_PROFILES):
        lay_p = S.collapse_layout(lay) if name == "COLLAPSED" else lay
        prof = _profile(name, profiles)
        x = lay_p["STATE"].astype(float)
        base_seed = seed + 1000 * pi
        null = S.simulate(lay_p, p=S.step_probabilities(lay_p["STATE"], 0.0), regressors={"E_MINUS_S": x},
                          profile=prof, reps=NULL_REPS, seed=base_seed)
        grid = {}
        for k, d in enumerate(S.EFFECT_GRID):
            r = S.simulate(lay_p, p=S.step_probabilities(lay_p["STATE"], d), regressors={"E_MINUS_S": x},
                           profile=prof, reps=CURVE_REPS, seed=base_seed + 1 + k)["E_MINUS_S"]
            grid[_round(d)] = {"POWER": r["POWER"], "MEAN_ESTIMATE": r["MEAN_ESTIMATE"], "SD_ESTIMATE": r["SD_ESTIMATE"]}
        mde = next((d for d in S.EFFECT_GRID if grid[_round(d)]["POWER"] >= S.TARGET_POWER), None)
        weeks80 = {f"{d:.2f}": S.weeks_for_power(weeks_ref, grid[_round(d)]["SD_ESTIMATE"],
                                                  grid[_round(d)]["MEAN_ESTIMATE"]) for d in S.DECISION_EFFECTS}
        out[name] = {
            "UNITS": int(x.size), "E_UNITS": int(x.sum()), "WEEK_CLUSTERS": null["_META"]["WEEK_CLUSTERS"],
            "NULL_REJECTION_RATE": null["E_MINUS_S"]["POWER"], "NULL_SD": null["E_MINUS_S"]["SD_ESTIMATE"],
            "AT": {f"{d:.3f}": grid[_round(d)]["POWER"] for d in S.REPORTED_EFFECTS},
            "MDE80_GRID": mde, "MDE80_ANALYTIC": S.Z80 * null["E_MINUS_S"]["SD_ESTIMATE"],
            "WEEKS_FOR_80": weeks80, "POWER_BY_EFFECT": grid,
        }
    ind_sd = out["INDEPENDENT"]["NULL_SD"]
    for name in POWER_PROFILES:
        de = (out[name]["NULL_SD"] / ind_sd) ** 2
        out[name]["DESIGN_EFFECT_VS_INDEPENDENT"] = de
        out[name]["EFFECTIVE_UNITS"] = out["INDEPENDENT"]["UNITS"] / de
    return out


def binary_vs_continuous(lay: dict, profiles: dict, weeks_ref: int, seed: int) -> dict:
    z = S.standardize(lay["SCORE"])
    xb = lay["STATE"].astype(float)
    out = {"N": int(xb.size), "POINT_BISERIAL_STATE_SCORE": float(np.corrcoef(xb, z)[0, 1]),
           "SCORE_MEAN_GAP_E_MINUS_S_SD": float(z[xb == 1].mean() - z[xb == 0].mean()), "PROFILES": {}}
    regs = {"BINARY": xb, "CONTINUOUS": z}
    for pi, name in enumerate(COMPARE_PROFILES):
        prof = profiles[name]
        s0 = seed + 1000 * pi
        null = S.simulate(lay, p=S.step_probabilities(lay["STATE"], 0.0), regressors=regs, profile=prof,
                          reps=NULL_REPS, seed=s0)
        res = {"NULL_REJECTION": {k: null[k]["POWER"] for k in regs}, "STEP": {}, "LINEAR": {}}
        for k, d in enumerate(COMPARE_EFFECTS):
            step = S.simulate(lay, p=S.step_probabilities(lay["STATE"], d), regressors=regs, profile=prof,
                              reps=COMPARE_REPS, seed=s0 + 10 + k)
            p_lin, clipped = S.linear_probabilities(lay["STATE"], z, d)
            lin = S.simulate(lay, p=p_lin, regressors=regs, profile=prof, reps=COMPARE_REPS, seed=s0 + 100 + k)
            for dgp, r in (("STEP", step), ("LINEAR", lin)):
                res[dgp][f"{d:.3f}"] = {
                    t: {"POWER": r[t]["POWER"],
                        "WEEKS_FOR_80": S.weeks_for_power(weeks_ref, r[t]["SD_ESTIMATE"], r[t]["MEAN_ESTIMATE"])}
                    for t in regs}
            res["LINEAR"][f"{d:.3f}"]["CLIPPED_SHARE"] = clipped
        out["PROFILES"][name] = res
    return out


def confirm_projection(rows_v: list[dict], variant: str, profiles: dict, power: dict, seed: int) -> dict:
    out = {}
    start = F.ms(PLANNING_START_UTC)
    for pi, name in enumerate(CONFIRM_PROFILES):
        out[name] = {}
        for k, d in enumerate(S.DECISION_EFFECTS):
            w80 = power[name]["WEEKS_FOR_80"][f"{d:.2f}"]
            if not math.isfinite(w80) or w80 > S.MAX_PROJECTED_WEEKS:
                out[name][f"{d:.2f}"] = {"WEEKS_FOR_80_ANALYTIC": w80, "CONFIRMED": None,
                                         "NOTE": f"beyond {S.MAX_PROJECTED_WEEKS} weeks; not simulated"}
                continue
            w = max(4, int(math.ceil(w80 / 4.0)) * 4)
            pros = S.prospective_rows(rows_v, w)
            lay = S.layout_arrays(pros, variant)
            r = S.simulate(lay, p=S.step_probabilities(lay["STATE"], d), regressors={"E_MINUS_S": lay["STATE"].astype(float)},
                           profile=profiles[name], reps=CONFIRM_REPS, seed=seed + 100 * pi + k)["E_MINUS_S"]
            out[name][f"{d:.2f}"] = {
                "WEEKS_FOR_80_ANALYTIC": w80, "SIMULATED_WEEKS": w, "SIMULATED_POWER": r["POWER"],
                "PROSPECTIVE_E": int(lay["STATE"].sum()), "PROSPECTIVE_S": int((lay["STATE"] == 0).sum()),
                "END_DATE_IF_STARTED_AT_PLANNING_START": L.iso_utc(start + w * L.WEEK_MS)}
    return out


def run() -> dict:
    if (REPO / RESULT_REL).exists():
        raise RuntimeError("RESULT_ALREADY_WRITTEN: this feasibility unit runs once")
    design_sha = verify_bindings()
    pins = FH._pinned()
    v0 = json.loads((REPO / V0.REPORT_REL).read_text())
    v0_digests = {s: v0["PER_SYMBOL"][s]["EPISODE_DIGEST"] for s in PANEL}
    validation_ids = {s: set() for s in PANEL}
    with open(REPO / FH.VALIDATION_EPISODES_REL, newline="") as fh:
        for rec in csv.DictReader(fh):
            validation_ids[rec["SYMBOL"]].add(rec["EPISODE_ID"])
    rows, blind, meta = [], [], {}
    for sym in PANEL:
        r, b, m = symbol_pass(sym, pins, v0_digests[sym], validation_ids[sym])
        rows += r
        blind += b
        meta[sym] = m
        print(f"{sym}: support {m['SUPPORT_EPISODES']} pit {m['PIT_AUDIT']}", flush=True)
    pit_ok = all(m["PIT_AUDIT"]["CHECKED"] == m["PIT_AUDIT"]["IDENTICAL"] for m in meta.values())

    constants = {}
    for v in S.VARIANTS:
        constants[v] = S.robust_constants([r for r in rows if r[v] is not None], v)
        for r in rows:
            r[f"SCORE_{v}"] = S.score(r, v, constants[v]) if r[v] is not None else float("nan")

    weeks = [r["WEEK_BLOCK"] for r in rows]
    weeks_ref = max(weeks) - min(weeks) + 1
    dep = outcome_dependence(blind)
    profiles = dict(S.PROFILES)
    profiles["EMPIRICAL"] = {k: dep["EMPIRICAL_PROFILE"][k] for k in ("WEEK", "DATE", "CHAIN")}
    profiles["EMPIRICAL_UPPER"] = {k: dep["EMPIRICAL_UPPER_PROFILE"][k] for k in ("WEEK", "DATE", "CHAIN")}

    per_variant = {}
    for vi, v in enumerate(S.VARIANTS):
        rows_v = [r for r in rows if r[v] is not None]
        lay = S.layout_arrays(rows, v)
        layout = S.state_layout_stats(rows_v, v)
        support_ok = (layout["E"]["EPISODES"] >= S.MIN_STATE_EPISODES
                      and layout["E"]["WEEK_CLUSTERS"] >= S.MIN_STATE_WEEK_CLUSTERS)
        power = power_block(lay, profiles, weeks_ref, SEED + 100_000 * (vi + 1))
        print(f"{v}: power done", flush=True)
        comp = binary_vs_continuous(S.layout_arrays(rows, v, f"SCORE_{v}"), profiles, weeks_ref,
                                    SEED + 100_000 * (vi + 1) + 50_000)
        print(f"{v}: comparison done", flush=True)
        per_variant[v] = {
            "UNDEFINED_STATE_EPISODES": sum(r[v] is None for r in rows),
            "LAYOUT": layout, "YIELDS": yields(rows, v, weeks_ref), "SUPPORT_OK": support_ok,
            "POWER": power,
            "WEEKS_FOR_80": {name: power[name]["WEEKS_FOR_80"] for name in POWER_PROFILES},
            "PROSPECTIVE_CONFIRMATION": confirm_projection(rows_v, v, profiles, power, SEED + 100_000 * (vi + 1) + 90_000),
            "BINARY_VS_CONTINUOUS": comp,
            "SCORE_CONSTANTS": constants[v],
        }
    status = S.verdict(per_variant, data_ok=True, pit_ok=pit_ok)
    continuous = {
        v: {name: per_variant[v]["BINARY_VS_CONTINUOUS"]["PROFILES"][name]["LINEAR"]["0.050"]["CONTINUOUS"]["WEEKS_FOR_80"]
            for name in COMPARE_PROFILES}
        for v in S.VARIANTS}
    support_rows = len(rows)
    result = {
        "UNIT": "SELLING_EXHAUSTION_SUPPORT_FEASIBILITY_V0",
        "STAGE": "FEASIBILITY_ONLY",
        "DESIGN_SHA256": design_sha,
        "RUNNER_SHA256": _sha(Path(__file__)),
        "LIB_SHA256": _sha(REPO / "scripts/research/selling_exhaustion_support_feasibility_v0_lib.py"),
        "SURFACE": {"DECISIONS_UTC": [L.iso_utc(FIRST_DECISION_MS), L.iso_utc(LAST_DECISION_MS)],
                    "READ_HORIZON_EXCLUSIVE_UTC": L.iso_utc(F.READ_HORIZON_MS),
                    "STATUS": "PREVIOUSLY EXPOSED (discovery for this hypothesis); never pristine validation",
                    "WEEKS_SPANNED": weeks_ref},
        "E1_INTERVAL_TOUCHED": False,
        "E_MINUS_S_OUTCOME_CONTRAST_COMPUTED": False,
        "SEED_CREATED": False,
        "PROSPECTIVE_ACTIVATED": False,
        "SUPPORT_EPISODES": support_rows,
        "SUPPORT_EPISODES_BY_SLICE": dict(Counter(r["SLICE"] for r in rows)),
        "PER_SYMBOL": meta,
        "PIT_AUDIT_OK": pit_ok,
        "DESCRIPTIVE_CROSSTABS": descriptive_crosstabs(rows),
        "OUTCOME_DEPENDENCE_STATE_BLIND": dep,
        "PROFILES_USED": profiles,
        "PER_VARIANT": per_variant,
        "VERDICT_BINARY_PRIMARY": status,
        "CONTINUOUS_OPTION_WEEKS_FOR_80_AT_5PP_LINEAR_DGP": continuous,
        "PLANNING_START_UTC": PLANNING_START_UTC,
        "REALISTIC_HORIZON_WEEKS": S.REALISTIC_HORIZON_WEEKS,
        "GENERATED_UTC": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    result = finite_or_none(result)
    (REPO / RESULT_REL).write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    return result


def main(argv: list[str]) -> int:
    if argv[1:] != ["run"]:
        print("usage: python -m scripts.research.selling_exhaustion_support_feasibility_v0 run")
        return 2
    res = run()
    print(json.dumps(res["VERDICT_BINARY_PRIMARY"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
