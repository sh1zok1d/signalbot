"""ADAPTIVE_OCCUPANCY_TIMESCALE_V1: a past-only occupancy-timescale selection algorithm, evaluated out of sample.

    python -m scripts.research.adaptive_occupancy_v1.evaluate preflight   # outcome-blind: census, fold and selector
                                                                          # manifests, design JSON, synthetic power
    python -m scripts.research.adaptive_occupancy_v1.evaluate run --go    # the one evaluation, after the owner's go
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from scripts.research.adaptive_b1_forecast_v1 import constants as KB
from scripts.research.adaptive_b1_forecast_v1 import metrics as MT

from . import constants as K
from . import walkforward as WF
from .surfaces import load_all

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1_DESIGN.md"
DESIGN_JSON = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1_DESIGN.json"
FOLD_MANIFEST = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1_FOLD_MANIFEST.json"
SELECTOR_MANIFEST = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1_SELECTOR_MANIFEST.json"
JOURNAL_DIR = ROOT / "docs/research/adaptive_occupancy_timescale_v1_execution"
RESULT_JSON = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1.json"
RESULT_MD = ROOT / "docs/research/ADAPTIVE_OCCUPANCY_TIMESCALE_V1.md"
PACKAGES = [Path(__file__).resolve().parent] + [ROOT / "scripts/research" / p for p in (
    "adaptive_b1_forecast_v1", "rp4h_trend_regime_v1", "rp4h_bitmex_temporal_v1", "rp4h_binance_2025_2026_temporal_v1",
    "directional_state_search_v2")]
MODELS = ("CLIM", "B1", "STATIC_OCC4", "ADAPTIVE", "MM_NO_OCC")
PRIMARY = [("ADAPTIVE", "B1"), ("ADAPTIVE", "STATIC_OCC4")]
DIAG = [("STATIC_OCC4", "B1"), ("B1", "CLIM"), ("ADAPTIVE", "CLIM"), ("ADAPTIVE", "MM_NO_OCC")]
PIN_KEYS = ("DESIGN_SHA256", "DESIGN_COMMIT", "EXPECTED_ROWS", "EXPECTED_OUTER_BLOCKS", "FOLD_MANIFEST_SHA256",
            "SELECTOR_MANIFEST_SHA256", "DESIGN_JSON_SHA256", "EXPECTED_FEATURE_SHA256", "EVALUATOR_DIGEST")
SHARED = ("RIDGE", "CLIP_Z", "IRLS_MAX_ITER", "IRLS_TOL", "P_CLIP", "BOOT_DRAWS", "BOOT_LO", "BOOT_HI", "RELIABILITY_BINS")
FEATURE_COLS = ("close_ms", "era", "venue", "bar", "rp", "ret4", "rv4", "ret1h", "ret15") + tuple(
    f"OCC_{h}H" for h in K.LOOKBACK_HOURS)


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _dump(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, default=lambda o: o.tolist() if hasattr(o, "tolist") else str(o)) + "\n"


def code_digest() -> str:
    """All imported research code except this unit's and ADAPTIVE_B1's constants modules (pins live there; the
    shared values are asserted by assert_shared and every design constant is in the pinned design JSON)."""
    h = hashlib.sha256()
    for pkg in PACKAGES:
        for p in sorted(pkg.glob("*.py")):
            if p.name == "constants.py" and pkg.name in ("adaptive_occupancy_v1", "adaptive_b1_forecast_v1"):
                continue
            h.update(f"{pkg.name}/{p.name}".encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def assert_shared() -> None:
    for k in SHARED:
        if getattr(KB, k) != getattr(K, k):
            raise SystemExit(f"IMPORTED_CONSTANT_CHANGED_{k}")


def feature_digest(rows: dict) -> str:
    """Outcome-free digest: timestamps, venue/era, bar index and every feature; never R_1H or Y."""
    h = hashlib.sha256()
    for k in FEATURE_COLS:
        h.update(k.encode())
        h.update(np.ascontiguousarray(rows[k]).astype("<f8" if rows[k].dtype.kind == "f" else "<i8").tobytes())
    return h.hexdigest()


# ------------------------------------------------------------------ manifests (outcome-free)
def fold_manifest(rows: dict, sched: dict) -> dict:
    c, blk = rows["close_ms"], WF.block_ms()
    folds = []
    for v, sv in sched.items():
        inv = rows["venue"] == v
        for S in sv["outer_starts"]:
            S = int(S)
            folds.append({"venue": K.VENUES[v], "outer_start_ms": S, "outer_end_ms": S + blk, "train_end_ms": S,
                          "inner_interval_ms": [S - K.INNER_BLOCKS * blk, S],
                          "eligible_memories": WF.eligible_memories(S, sv["first_ms"]),
                          "n_outer_rows": int((inv & (c >= S) & (c < S + blk)).sum())})
    return {"unit": K.UNIT, "block_days": K.BLOCK_DAYS, "inner_blocks": K.INNER_BLOCKS,
            "venues": {K.VENUES[v]: {"first_anchor_ms": sv["first_ms"], "first_outer_ms": sv["first_outer_ms"],
                                      "n_grid_blocks": int(sv["grid_starts"].size), "n_outer_blocks": int(sv["outer_starts"].size)}
                       for v, sv in sched.items()}, "folds": folds}


def selector_manifest() -> dict:
    cands = [{"memory_weeks": m, "config": c} for m in K.MEMORIES_WEEKS for c in K.CONFIGS]
    return {"unit": K.UNIT, "candidates": cands, "n_candidates": len(cands), "objective": "pooled inner Brier",
            "tie_break": ["log loss within TIE_TOL", "NO_OCC first", "longer memory", "shorter lookback"],
            "tie_tol": K.TIE_TOL, "inner_blocks": K.INNER_BLOCKS, "block_days": K.BLOCK_DAYS,
            "memory_eligibility": "S - inner window - M weeks >= the venue's first anchor",
            "frozen_for_block": True, "outer_outcomes_used": False}


def design_json() -> dict:
    keys = [k for k in dir(K) if k.isupper() and not k.startswith("_") and k not in PIN_KEYS]
    return {"unit": K.UNIT, "constants": {k: getattr(K, k) for k in sorted(keys)},
            "model": "ridge logistic (Newton-IRLS, L2 1.0 on standardized slopes, not the intercept; 50 iterations; "
                     "tol 1e-10; standardization and clip +-5 fitted on training rows) imported from adaptive_b1_forecast_v1.model",
            "features_b1": ["RP4H - 0.5", "RET_4H / RV_4H", "RET_1H / RV_4H", "RET_15M / RV_4H", "log RV_4H"],
            "occ_feature": "OCC_L - 0.5 (one lookback per model)", "target": "Y = 1{R_1H > 0}",
            "venue_policy": "two venues (BitMEX; Binance USD-M 2020-26); no window or target crosses a series boundary; "
                            "training never mixes venues; Binance 2025-26 trains on Binance 2020-24 plus earlier 2025-26 rows"}


def support(rows: dict, sched: dict) -> dict:
    om = WF.outer_mask(rows, sched)
    yrs = (rows["close_ms"] // 1000).astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970
    return {"rows": int(rows["r1"].size), "rows_by_era": {K.ERAS[e]: int((rows["era"] == e).sum()) for e in range(3)},
            "outer_rows": int(om.sum()), "coverage_outer_share": float(om.mean()),
            "outer_rows_by_diag_era": {lab: int((om & (yrs >= a) & (yrs <= b)).sum()) for lab, a, b in K.DIAG_ERAS},
            "outer_blocks": {K.VENUES[v]: int(sv["outer_starts"].size) for v, sv in sched.items()},
            "first_outer": {K.VENUES[v]: int(sv["first_outer_ms"]) for v, sv in sched.items()},
            "census": rows["_census"]}


# ------------------------------------------------------------------ evaluation core
def route(db: dict, dl: dict, cal_slope: float) -> str:
    if db["valid"] < K.MIN_VALID_DRAWS:
        return K.ROUTE_INVALID
    if db["lo"] > 0:
        return K.ROUTE_WORSE
    if db["point"] < 0 and db["hi"] < 0 and dl["point"] < 0 and cal_slope >= 0:
        return K.ROUTE_SUPPORTED
    if db["point"] < 0:
        return K.ROUTE_UNCERTAIN
    return K.ROUTE_NONE


def evaluate_predictions(rows: dict, sched: dict, y: np.ndarray, log_models: bool = True) -> dict:
    grid = WF.predict_grid(rows, sched, y, log_models=log_models)
    sel = WF.select(rows, sched, grid, y)
    preds = {k: grid["preds"][k] for k in ("CLIM", "B1", "STATIC_OCC4")}
    preds.update({"ADAPTIVE": sel["ADAPTIVE"], "MM_NO_OCC": sel["MM_NO_OCC"]})
    om = WF.outer_mask(rows, sched)
    for k in MODELS:
        if not np.isfinite(preds[k][om]).all():
            raise SystemExit(f"OUTER_PREDICTION_MISSING_{k}")
    yo, wk = y[om], MT.weeks_of(rows["close_ms"][om])
    bl = {k: MT.brier(preds[k][om], yo) for k in MODELS}
    ll = {k: MT.logloss(preds[k][om], yo) for k in MODELS}
    db = MT.boot_diffs(bl, PRIMARY + DIAG, wk, seed=K.BOOT_SEED)
    dl = MT.boot_diffs(ll, PRIMARY + DIAG, wk, seed=K.BOOT_SEED)
    cal = MT.calibration(preds["ADAPTIVE"][om], yo)
    return {"grid": grid, "sel": sel, "preds": preds, "om": om, "brier_d": db, "logloss_d": dl, "adaptive_calibration": cal,
            "mean_brier": {k: float(v.mean()) for k, v in bl.items()}, "mean_logloss": {k: float(v.mean()) for k, v in ll.items()},
            "route": route(db["ADAPTIVE-B1"], dl["ADAPTIVE-B1"], cal["slope"])}


def selection_share(log: list) -> dict:
    return {cfg: float(np.mean([b["selected_config"] == cfg for b in log])) for cfg in K.CONFIGS}


# ------------------------------------------------------------------ synthetic power check (no market outcome)
def synthetic_y(rows: dict, cfg_on, cfg_off, seed: int) -> np.ndarray:
    """R_syn = (sum of the next 12 per-bar N(0,1) innovations on each series' own grid)/sqrt(12) + beta * g(T), with
    g = the standardized OCC config active in T's 52-week period (cfg_on in even periods, cfg_off in odd ones)."""
    rng = np.random.default_rng(seed)
    r = np.empty(rows["r1"].size)
    for era in range(3):
        m = rows["era"] == era
        bars = rows["bar"][m]
        e = rng.standard_normal(int(bars.max()) + 14)
        cs = np.concatenate([[0.0], np.cumsum(e)])
        r[m] = (cs[bars + 13] - cs[bars + 1]) / np.sqrt(12.0)
    if cfg_on is None:
        return (r > 0).astype(np.float64)
    period = ((rows["close_ms"] - rows["close_ms"][0]) // (K.SYN_SWITCH_WEEKS * K.WEEK_MS)) % 2
    z = lambda cfg: (rows[cfg] - rows[cfg].mean()) / rows[cfg].std()
    g = np.where(period == 0, z(cfg_on), z(cfg_off))
    return ((r + K.SYN_BETA * g) > 0).astype(np.float64)


def power_check(rows: dict, sched: dict) -> list:
    out = []
    for k, (name, on, off) in enumerate(K.SYN_SCENARIOS):
        ev = evaluate_predictions(rows, sched, synthetic_y(rows, on, off, K.SYN_SEED + k), log_models=False)
        out.append({"scenario": name, "route": ev["route"], "adaptive_minus_b1": ev["brier_d"]["ADAPTIVE-B1"],
                    "adaptive_minus_static_occ4": ev["brier_d"]["ADAPTIVE-STATIC_OCC4"],
                    "static_occ4_minus_b1": ev["brier_d"]["STATIC_OCC4-B1"],
                    "adaptive_minus_mm_no_occ": ev["brier_d"]["ADAPTIVE-MM_NO_OCC"],
                    "selection_share": selection_share(ev["sel"]["log"]),
                    "memory_share": {str(m): float(np.mean([b["selected_memory_weeks"] == m for b in ev["sel"]["log"]]))
                                     for m in K.MEMORIES_WEEKS}})
        print(name, ev["route"], flush=True)
    return out


def preflight(with_power: bool = True) -> dict:
    rows = load_all()
    sched = WF.schedule(rows)
    FOLD_MANIFEST.write_text(_dump(fold_manifest(rows, sched)), encoding="utf-8")
    SELECTOR_MANIFEST.write_text(_dump(selector_manifest()), encoding="utf-8")
    DESIGN_JSON.write_text(_dump(design_json()), encoding="utf-8")
    assert_shared()
    out = {"support": support(rows, sched), "fold_manifest_sha256": _sha(FOLD_MANIFEST),
           "selector_manifest_sha256": _sha(SELECTOR_MANIFEST), "design_json_sha256": _sha(DESIGN_JSON),
           "feature_sha256": feature_digest(rows), "evaluator_digest": code_digest(),
           "design_sha256": _sha(DESIGN_PATH) if DESIGN_PATH.exists() else None}
    if with_power:
        out["synthetic_power"] = power_check(rows, sched)
    return out


# ------------------------------------------------------------------ the one evaluation
def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists() or (JOURNAL_DIR / "ATTEMPT.json").exists():
        raise SystemExit("REFUSING_RERUN")


def assert_frozen() -> None:
    if K.DESIGN_SHA256 == "PENDING" or K.DESIGN_COMMIT == "PENDING" or any(
            getattr(K, k) is None for k in PIN_KEYS):
        raise SystemExit("PINS_UNSET")
    if _sha(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    for path, pin in ((FOLD_MANIFEST, K.FOLD_MANIFEST_SHA256), (SELECTOR_MANIFEST, K.SELECTOR_MANIFEST_SHA256),
                      (DESIGN_JSON, K.DESIGN_JSON_SHA256)):
        if _sha(path) != pin:
            raise SystemExit(f"PIN_MISMATCH_{path.name}")
    if code_digest() != K.EVALUATOR_DIGEST:
        raise SystemExit("EVALUATOR_DIGEST_MISMATCH")
    assert_shared()


def assert_support(rows: dict, sched: dict) -> None:
    """Outcome-free checks against the pins; nothing here reads R_1H or Y."""
    if rows["r1"].size != K.EXPECTED_ROWS:
        raise SystemExit("ROWS_MISMATCH")
    if sum(int(sv["outer_starts"].size) for sv in sched.values()) != K.EXPECTED_OUTER_BLOCKS:
        raise SystemExit("OUTER_BLOCKS_MISMATCH")
    if feature_digest(rows) != K.EXPECTED_FEATURE_SHA256:
        raise SystemExit("FEATURE_DIGEST_MISMATCH")
    for path, obj in ((FOLD_MANIFEST, fold_manifest(rows, sched)), (SELECTOR_MANIFEST, selector_manifest()),
                      (DESIGN_JSON, design_json())):
        if json.loads(path.read_text()) != json.loads(_dump(obj)):
            raise SystemExit(f"MANIFEST_REBUILD_MISMATCH_{path.name}")


def _head() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only
        return "UNKNOWN"


def write_attempt() -> dict:
    """The one-shot journal: written before any outcome is read; its presence refuses every later run."""
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"unit": K.UNIT, "started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "head": _head(), "design_sha256": K.DESIGN_SHA256, "design_commit": K.DESIGN_COMMIT,
           "evaluator_digest": K.EVALUATOR_DIGEST, "feature_sha256": K.EXPECTED_FEATURE_SHA256,
           "fold_manifest_sha256": K.FOLD_MANIFEST_SHA256, "selector_manifest_sha256": K.SELECTOR_MANIFEST_SHA256,
           "status": "STARTED_OUTCOMES_NOT_YET_READ"}
    with open(JOURNAL_DIR / "ATTEMPT.json", "x", encoding="utf-8") as f:
        f.write(_dump(rec))
    return rec


def persistence(log: list, key: str, values) -> dict:
    """Selection persistence per venue: share, switches and mean run length of the selected `key`."""
    out = {}
    for venue in sorted({b["venue"] for b in log}):
        seq = [b[key] for b in log if b["venue"] == venue]
        runs, cur = [], 1
        for a, b in zip(seq, seq[1:]):
            if a == b:
                cur += 1
            else:
                runs.append(cur)
                cur = 1
        runs.append(cur)
        out[venue] = {"share": {str(v): float(np.mean([x == v for x in seq])) for v in values},
                      "switches": int(sum(1 for a, b in zip(seq, seq[1:]) if a != b)),
                      "mean_run_length": float(np.mean(runs)), "n_blocks": len(seq)}
    return out


def _years(close_ms: np.ndarray) -> np.ndarray:
    return (close_ms // 1000).astype("datetime64[s]").astype("datetime64[Y]").astype(int) + 1970


def secondary(preds: dict, om: np.ndarray, y: np.ndarray) -> dict:
    yo = y[om]
    out = {}
    for k in MODELS:
        p = preds[k][om]
        out[k] = {"auroc": MT.auroc(p, yo), "calibration": MT.calibration(p, yo), "reliability": MT.reliability(p, yo),
                  "probability": {"mean": float(p.mean()), "sd": float(p.std()),
                                  "quantiles": {q: float(np.quantile(p, float(q))) for q in
                                                ("0.01", "0.05", "0.25", "0.5", "0.75", "0.95", "0.99")},
                                  "share_outside_0.45_0.55": float(np.mean((p < 0.45) | (p > 0.55)))}}
    return out


def per_era(rows: dict, preds: dict, om: np.ndarray, y: np.ndarray) -> dict:
    yrs = _years(rows["close_ms"])
    out = {}
    for lab, a, b in K.DIAG_ERAS:
        m = om & (yrs >= a) & (yrs <= b)
        if not m.any():
            out[lab] = {"n": 0}
            continue
        wk = MT.weeks_of(rows["close_ms"][m])
        bl = {k: MT.brier(preds[k][m], y[m]) for k in MODELS}
        ll = {k: MT.logloss(preds[k][m], y[m]) for k in MODELS}
        pairs = PRIMARY + [("STATIC_OCC4", "B1"), ("ADAPTIVE", "MM_NO_OCC")]
        out[lab] = {"n": int(m.sum()), "weeks": int(np.unique(wk).size), "p_up": float(y[m].mean()),
                    "brier": MT.boot_diffs(bl, pairs, wk, seed=K.BOOT_SEED),
                    "logloss": MT.boot_diffs(ll, PRIMARY, wk, seed=K.BOOT_SEED)}
    return out


def adaptation_vs_static(d: dict) -> str:
    """Frozen qualifier (not a route): ADAPTIVE vs STATIC_OCC4 on Brier."""
    if d["hi"] < 0:
        return "ADAPTIVE_BETTER_THAN_STATIC_OCC4"
    if d["lo"] > 0:
        return "ADAPTIVE_WORSE_THAN_STATIC_OCC4"
    return "ADAPTIVE_NOT_DISTINGUISHED_FROM_STATIC_OCC4"


def run() -> dict:
    refuse_if_scored()
    assert_frozen()
    rows = load_all()
    sched = WF.schedule(rows)
    assert_support(rows, sched)
    attempt = write_attempt()
    y = rows["y"]
    ev = evaluate_predictions(rows, sched, y)
    om, preds, log = ev["om"], ev["preds"], ev["sel"]["log"]
    c = rows["close_ms"]
    for b in log:
        m = (rows["venue"] == {v: k for k, v in K.VENUES.items()}[b["venue"]]) & (c >= b["outer_start_ms"]) & (
            c < b["outer_end_ms"])
        b["outer_brier"] = float(np.mean(MT.brier(preds["ADAPTIVE"][m], y[m])))
        b["outer_logloss"] = float(np.mean(MT.logloss(preds["ADAPTIVE"][m], y[m])))
        b["outer_brier_b1"] = float(np.mean(MT.brier(preds["B1"][m], y[m])))
    result = {
        "unit": K.UNIT, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": K.DESIGN_SHA256, "design_commit": K.DESIGN_COMMIT,
        "evaluator_digest": code_digest(), "feature_sha256": K.EXPECTED_FEATURE_SHA256,
        "fold_manifest_sha256": K.FOLD_MANIFEST_SHA256, "selector_manifest_sha256": K.SELECTOR_MANIFEST_SHA256,
        "attempt": attempt, "support": support(rows, sched), "outer_p_up": float(y[om].mean()),
        "mean_brier": ev["mean_brier"], "mean_logloss": ev["mean_logloss"],
        "brier_differences": ev["brier_d"], "logloss_differences": ev["logloss_d"],
        "route": ev["route"], "adaptation_vs_static": adaptation_vs_static(ev["brier_d"]["ADAPTIVE-STATIC_OCC4"]),
        "adaptive_calibration": ev["adaptive_calibration"], "secondary": secondary(preds, om, y),
        "per_era": per_era(rows, preds, om, y),
        "selector": {"config_persistence": persistence(log, "selected_config", K.CONFIGS),
                     "memory_persistence": persistence(log, "selected_memory_weeks", K.MEMORIES_WEEKS),
                     "blocks": log},
        "not_read": ["PnL", "fees", "Sharpe", "entries", "spot", "other horizons", "other features",
                     "lookbacks or memories outside the frozen set", "E1-RUN-001 holdout and E1-development slice"],
    }
    result = json.loads(_dump(result))
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown
    write_markdown(result, RESULT_MD)
    with open(JOURNAL_DIR / "COMPLETED.json", "x", encoding="utf-8") as f:
        f.write(_dump({"unit": K.UNIT, "route": ev["route"], "result_json_sha256": _sha(RESULT_JSON),
                       "result_md_sha256": _sha(RESULT_MD),
                       "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}))
    print(ev["route"], flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--no-power", action="store_true")
    ap.add_argument("--out", type=Path, default=None, help="preflight: also write the JSON summary here")
    a = ap.parse_args()
    if a.step == "preflight":
        out = _dump(preflight(with_power=not a.no_power))
        if a.out is not None:
            a.out.write_text(out, encoding="utf-8")
        print(out)
        return
    if not a.go:
        raise SystemExit("refusing: the one evaluation needs --go after the owner's go")
    run()


if __name__ == "__main__":
    main()
