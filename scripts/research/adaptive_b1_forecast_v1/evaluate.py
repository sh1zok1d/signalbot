"""ADAPTIVE_B1_FORECAST_V1: retrospective walk-forward probabilistic forecast of the next-hour sign from the B1 states.

    python -m scripts.research.adaptive_b1_forecast_v1.evaluate preflight   # outcome-blind: support, schedule, fold
                                                                            # manifest, synthetic power check
    python -m scripts.research.adaptive_b1_forecast_v1.evaluate run --go    # the one evaluation, after the owner's go
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from . import constants as K
from . import metrics as MT
from . import walkforward as WF
from .surfaces import load_all

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/ADAPTIVE_B1_FORECAST_V1_DESIGN.md"
MANIFEST_PATH = ROOT / "docs/research/ADAPTIVE_B1_FORECAST_V1_FOLD_MANIFEST.json"
RESULT_JSON = ROOT / "docs/research/ADAPTIVE_B1_FORECAST_V1.json"
RESULT_MD = ROOT / "docs/research/ADAPTIVE_B1_FORECAST_V1.md"
PACKAGES = [Path(__file__).resolve().parent] + [ROOT / "scripts/research" / p for p in (
    "rp4h_trend_regime_v1", "rp4h_bitmex_temporal_v1", "rp4h_binance_2025_2026_temporal_v1", "directional_state_search_v2")]
PRIMARY_PAIRS = [("STATIC", "CLIM"), ("ADAPTIVE", "STATIC")]


def models() -> tuple:
    return ("CLIM", "STATIC", *[f"FIXED_{m}" for m in K.MEMORIES_WEEKS], "ADAPTIVE")


def all_pairs() -> list:
    return PRIMARY_PAIRS + [("ADAPTIVE", "CLIM")] + [(f"FIXED_{m}", "STATIC") for m in K.MEMORIES_WEEKS]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def code_digest() -> str:
    h = hashlib.sha256()
    for pkg in PACKAGES:
        for p in sorted(pkg.glob("*.py")):
            h.update(f"{pkg.name}/{p.name}".encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def route(brier: dict, ll: dict, names: dict) -> str:
    """Frozen: SUPPORTED needs delta Brier < 0 with the whole interval < 0 and a negative log-loss point."""
    if brier["valid"] < K.MIN_VALID_DRAWS:
        return K.ROUTE_INVALID
    if brier["lo"] > 0:
        return names["WORSE"]
    if brier["point"] < 0 and brier["hi"] < 0 and ll["point"] < 0:
        return names["SUPPORTED"]
    if brier["point"] < 0:
        return names["UNCERTAIN"]
    return names["NONE"]


def evaluate_predictions(rows: dict, sched: dict, y: np.ndarray, log_coefs: bool = True) -> dict:
    grid = WF.predict_grid(rows, sched, y, log_coefs=log_coefs)
    sel = WF.select(rows, sched, grid, y)
    preds = dict(grid["preds"])
    preds["ADAPTIVE"] = sel["ADAPTIVE"]
    om = WF.outer_mask(rows, sched)
    for k in models():
        if not np.isfinite(preds[k][om]).all():
            raise SystemExit(f"OUTER_PREDICTION_MISSING_{k}")
    yo, wk = y[om], MT.weeks_of(rows["close_ms"][om])
    bl = {k: MT.brier(preds[k][om], yo) for k in models()}
    ll = {k: MT.logloss(preds[k][om], yo) for k in models()}
    db, dl = MT.boot_diffs(bl, all_pairs(), wk), MT.boot_diffs(ll, all_pairs(), wk)
    return {"grid": grid, "sel": sel, "preds": preds, "om": om, "brier_d": db, "logloss_d": dl,
            "mean_brier": {k: float(v.mean()) for k, v in bl.items()}, "mean_logloss": {k: float(v.mean()) for k, v in ll.items()},
            "routes": {"P1_static_vs_climatology": route(db["STATIC-CLIM"], dl["STATIC-CLIM"], K.P1),
                       "P2_adaptive_vs_static": route(db["ADAPTIVE-STATIC"], dl["ADAPTIVE-STATIC"], K.P2)}}


# ------------------------------------------------------------------ synthetic power check (no market outcome)
def synthetic_y(rows: dict, beta_on: float, beta_off: float, seed: int) -> np.ndarray:
    """R_syn(T) = (sum of the 12 next per-bar N(0,1) innovations)/sqrt(12) + beta(T) * g(T), g = -standardized RP4H.
    The innovations live on each era's own 5m grid, so overlapping anchors share noise exactly like real 1h targets.
    beta(T) = beta_on in even 52-week periods from the first anchor, beta_off in odd ones."""
    rng = np.random.default_rng(seed)
    r = np.empty(rows["rp"].size)
    for era in range(len(K.ERAS)):
        m = rows["era"] == era
        if not m.any():
            continue
        bars = rows["bar"][m]
        e = rng.standard_normal(int(bars.max()) + 14)
        cs = np.concatenate([[0.0], np.cumsum(e)])
        r[m] = (cs[bars + 13] - cs[bars + 1]) / np.sqrt(12.0)
    g = -(rows["rp"] - rows["rp"].mean()) / rows["rp"].std()
    period = ((rows["close_ms"] - rows["close_ms"][0]) // (K.SYN_SWITCH_WEEKS * K.WEEK_MS)) % 2
    beta = np.where(period == 0, beta_on, beta_off)
    return ((r + beta * g) > 0).astype(np.float64)


def power_check(rows: dict, sched: dict) -> list:
    out = []
    for k, (name, b_on, b_off) in enumerate(K.SYN_SCENARIOS):
        ys = synthetic_y(rows, b_on, b_off, K.SYN_SEED + k)
        ev = evaluate_predictions(rows, sched, ys, log_coefs=False)
        sel = ev["sel"]["log"]
        share = {str(m): float(np.mean([b["selected_memory_weeks"] == m for b in sel])) for m in K.MEMORIES_WEEKS}
        out.append({"scenario": name, "beta_on": b_on, "beta_off": b_off, "routes": ev["routes"],
                    "brier_static_minus_clim": ev["brier_d"]["STATIC-CLIM"],
                    "brier_adaptive_minus_static": ev["brier_d"]["ADAPTIVE-STATIC"],
                    "brier_fixed_minus_static": {f"FIXED_{m}": ev["brier_d"][f"FIXED_{m}-STATIC"] for m in K.MEMORIES_WEEKS},
                    "selection_share": share})
        print(name, ev["routes"], flush=True)
    return out


def fold_manifest(rows: dict, sched: dict) -> dict:
    c = rows["close_ms"]
    blk = sched["block_ms"]
    folds = []
    for S in sched["outer_starts"]:
        n = int(((c >= S) & (c < S + blk)).sum())
        folds.append({"outer_start_ms": int(S), "outer_end_ms": int(S + blk), "train_end_ms_exclusive_target": int(S),
                      "inner_interval_ms": [int(S - K.INNER_BLOCKS * blk), int(S)],
                      "memories_weeks": list(K.MEMORIES_WEEKS), "n_outer_rows": n})
    return {"unit": K.UNIT, "first_outer_ms": int(sched["first_outer_ms"]), "block_days": K.BLOCK_DAYS,
            "n_grid_blocks": int(sched["grid_starts"].size), "n_outer_blocks": int(sched["outer_starts"].size), "folds": folds}


def support(rows: dict, sched: dict) -> dict:
    om = WF.outer_mask(rows, sched)
    yrs = (rows["close_ms"] // 1000).astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
    return {"rows": int(rows["rp"].size), "rows_by_era": {K.ERAS[e]: int((rows["era"] == e).sum()) for e in range(3)},
            "outer_rows": int(om.sum()), "outer_rows_by_diag_era": {lab: int((om & (yrs >= a) & (yrs <= b)).sum())
                                                                     for lab, a, b in K.DIAG_ERAS},
            "first_outer_ms": int(sched["first_outer_ms"]), "n_outer_blocks": int(sched["outer_starts"].size),
            "census": rows["_census"]}


def preflight(with_power: bool = True) -> dict:
    rows = load_all()
    sched = WF.schedule(rows["close_ms"])
    man = fold_manifest(rows, sched)
    MANIFEST_PATH.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    out = {"support": support(rows, sched), "fold_manifest_sha256": _sha(MANIFEST_PATH),
           "design_sha256": _sha(DESIGN_PATH) if DESIGN_PATH.exists() else None}
    if with_power:
        out["synthetic_power"] = power_check(rows, sched)
    return out


# ------------------------------------------------------------------ the one evaluation
def refuse_if_scored():
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING":
        raise SystemExit("DESIGN_HASH_UNSET")
    if _sha(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return K.DESIGN_SHA256


def selector_summary(log: list) -> dict:
    mems = [b["selected_memory_weeks"] for b in log]
    runs, cur = [], 1
    for a, b in zip(mems, mems[1:]):
        if a == b:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    years = {}
    for b in log:
        y = str(np.datetime64(b["outer_start_ms"], "ms").astype("datetime64[Y]"))
        years.setdefault(y, []).append(b["selected_memory_weeks"])
    return {"share": {str(m): float(np.mean([x == m for x in mems])) for m in K.MEMORIES_WEEKS},
            "switches": int(sum(1 for a, b in zip(mems, mems[1:]) if a != b)), "mean_run_length": float(np.mean(runs)),
            "by_year": {y: {str(m): v.count(m) for m in K.MEMORIES_WEEKS} for y, v in years.items()}}


def run() -> dict:
    refuse_if_scored()
    design = assert_frozen()
    rows = load_all()
    sched = WF.schedule(rows["close_ms"])
    if (rows["rp"].size, int(sched["outer_starts"].size), int(sched["first_outer_ms"])) != (
            K.EXPECTED_ROWS, K.EXPECTED_OUTER_BLOCKS, K.EXPECTED_FIRST_OUTER_MS):
        raise SystemExit("SUPPORT_MISMATCH")
    if json.loads(MANIFEST_PATH.read_text()) != json.loads(json.dumps(fold_manifest(rows, sched))):
        raise SystemExit("FOLD_MANIFEST_MISMATCH")
    y = rows["y"]
    ev = evaluate_predictions(rows, sched, y)
    om, preds = ev["om"], ev["preds"]
    yo = y[om]
    secondary = {k: {"auroc": MT.auroc(preds[k][om], yo), "calibration": MT.calibration(preds[k][om], yo),
                     "reliability": MT.reliability(preds[k][om], yo)} for k in models()}
    yrs = (rows["close_ms"] // 1000).astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
    per_era = {}
    for lab, a, b in K.DIAG_ERAS:
        m = om & (yrs >= a) & (yrs <= b)
        if not m.any():
            continue
        wk = MT.weeks_of(rows["close_ms"][m])
        bl = {k: MT.brier(preds[k][m], y[m]) for k in models()}
        ll = {k: MT.logloss(preds[k][m], y[m]) for k in models()}
        per_era[lab] = {"n": int(m.sum()), "brier": MT.boot_diffs(bl, PRIMARY_PAIRS + [("ADAPTIVE", "CLIM")], wk),
                        "logloss": MT.boot_diffs(ll, PRIMARY_PAIRS, wk), "p_up": float(y[m].mean())}
    result = {
        "unit": K.UNIT, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "evaluator_digest": code_digest(), "fold_manifest_sha256": _sha(MANIFEST_PATH), "support": support(rows, sched),
        "mean_brier": ev["mean_brier"], "mean_logloss": ev["mean_logloss"], "brier_differences": ev["brier_d"],
        "logloss_differences": ev["logloss_d"], "routes": ev["routes"], "secondary": secondary, "per_era": per_era,
        "selector": {"summary": selector_summary(ev["sel"]["log"]), "blocks": ev["sel"]["log"]},
        "outer_p_up": float(yo.mean()),
        "not_read": ["other features", "OCC", "spot", "other horizons", "PnL", "fees"],
    }
    result = json.loads(json.dumps(result, default=lambda o: o.tolist() if hasattr(o, "tolist") else float(o)))
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown
    write_markdown(result, RESULT_MD)
    print(ev["routes"], flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--no-power", action="store_true")
    a = ap.parse_args()
    if a.step == "preflight":
        print(json.dumps(preflight(with_power=not a.no_power), indent=1, sort_keys=True, default=str))
        return
    if not a.go:
        raise SystemExit("refusing: the one evaluation needs --go after the owner's go")
    run()


if __name__ == "__main__":
    main()
