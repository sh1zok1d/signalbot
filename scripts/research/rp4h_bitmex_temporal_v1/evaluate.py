"""Unit A: one BitMEX read. Refuses unless the design hash, series hash and gap census match and no result exists.

    python -m scripts.research.rp4h_bitmex_temporal_v1.evaluate preflight   # hashes and gap census; no prices used
    python -m scripts.research.rp4h_bitmex_temporal_v1.evaluate run --go    # the one-shot read (after the owner's go)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import constants as K
from .grid import ROOT, anchor_mask, load_series, local_returns, place, preflight_census, sha256
from .parent import (_above_zero, _below_zero, _includes_zero, _interval, features, partial_rank, quintile_table,
                     ref_partial_spearman, spearman)
from .report import write_markdown

DESIGN_PATH = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1.md"
PACKAGE = Path(__file__).resolve().parent


def assert_design_frozen() -> str:
    found = sha256(DESIGN_PATH)
    if found != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return found


def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assign_route(raw, raw_ci: dict, primary, primary_ci: dict) -> tuple[str, list]:
    """The frozen order of the design. Secondaries, diagnostics and descriptions never enter."""
    if raw is None or primary is None or raw_ci["valid"] < K.MIN_VALID_DRAWS or primary_ci["valid"] < K.MIN_VALID_DRAWS:
        return K.ROUTE_UNAVAILABLE, []
    if raw < 0.0 and primary < 0.0 and _below_zero(primary_ci):
        return K.ROUTE_SUPPORTED, []
    if raw < 0.0 and _below_zero(raw_ci) and _includes_zero(primary_ci):
        return K.ROUTE_RAW_ONLY, []
    if raw < 0.0 and primary < 0.0:
        return K.ROUTE_COMPATIBLE, []
    flags = [K.FLAG_OPPOSES] if _above_zero(primary_ci) else []
    return K.ROUTE_NOT, flags


def _code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PACKAGE.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return value if np.isfinite(value) else None
    return obj


def build_sample(series: dict) -> dict:
    grid = place(series)
    feat = features(grid["high"], grid["low"], grid["close"])
    loc = local_returns(grid["close"])
    future_open = grid["grid_open"] + K.HORIZON * K.BAR_MS
    feat["r1"] = np.where(future_open < K.SURFACE_END_MS, feat["r1"], np.nan)
    keep = anchor_mask(grid["grid_open"])
    finite = (np.isfinite(feat["rp"]) & np.isfinite(feat["ret4"]) & np.isfinite(feat["rv4"])
              & np.isfinite(feat["width"]) & np.isfinite(feat["r1"]))
    idx = np.flatnonzero(keep & finite)
    out = {k: feat[k][idx] for k in ("rp", "ret4", "rv4", "width", "r1")}
    out["ret1h"], out["ret15"] = loc["ret1h"][idx], loc["ret15"][idx]
    if not (np.isfinite(out["ret1h"]).all() and np.isfinite(out["ret15"]).all()):
        raise SystemExit("LOCAL_CONTROLS_OUTSIDE_SAMPLE")
    out["close_ms"] = grid["grid_open"][idx] + K.BAR_MS
    out["phase_anchors"] = int(keep.sum())
    out["grid"] = {"slots": grid["slots"], "occupied": grid["occupied"], "holes": grid["holes"]}
    return out


def _bootstrap(s: dict, blocks: np.ndarray) -> dict:
    rng = np.random.default_rng(K.BOOT_SEED)
    _uniq, inverse = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inverse == i) for i in range(inverse.max() + 1)]
    n_weeks = len(groups)
    names = ("raw", "primary", "secondary_ret4", "secondary_local")
    draws = {k: np.empty(K.BOOT_DRAWS, dtype=np.float64) for k in names}
    for d in range(K.BOOT_DRAWS):
        pick = rng.integers(0, n_weeks, size=n_weeks)
        idx = np.concatenate([groups[i] for i in pick])
        rp, y = s["rp"][idx], s["r1"][idx]
        raw = spearman(rp, y)
        prim = partial_rank(y, rp, [s["ret4"][idx], s["rv4"][idx]])
        sec1 = partial_rank(y, rp, [s["ret4"][idx]])
        sec2 = partial_rank(y, rp, [s["ret4"][idx], s["rv4"][idx], s["ret1h"][idx], s["ret15"][idx]])
        draws["raw"][d] = np.nan if raw is None else raw
        for k, v in (("primary", prim), ("secondary_ret4", sec1), ("secondary_local", sec2)):
            draws[k][d] = np.nan if v["rho"] is None else v["rho"]
        if d % 250 == 0:
            print(f"bootstrap {d}", flush=True)
    return {k: _interval(v) for k, v in draws.items()}


def _pieces(s: dict, masks: list) -> list:
    rows = []
    for name, m in masks:
        raw = spearman(s["rp"][m], s["r1"][m])
        prim = partial_rank(s["r1"][m], s["rp"][m], [s["ret4"][m], s["rv4"][m]])
        rows.append({"piece": name, "n": int(m.sum()), "raw": raw, "primary": prim["rho"],
                     "primary_degenerate": bool(prim["degenerate"])})
    return rows


def preflight() -> dict:
    series = load_series()
    census = preflight_census(series)
    return {"design_sha256": assert_design_frozen(), "series_sha256": K.SERIES_SHA256, **census}


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    series = load_series()
    census = preflight_census(series)
    s = build_sample(series)
    ts = pd.to_datetime(s["close_ms"], unit="ms", utc=True)
    iso = ts.isocalendar()
    blocks = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    year = ts.year.to_numpy(dtype=np.int64)

    raw = spearman(s["rp"], s["r1"])
    sec1 = partial_rank(s["r1"], s["rp"], [s["ret4"]])
    canonical = ref_partial_spearman(s["rp"], s["r1"], s["ret4"])
    if sec1["degenerate"] or canonical["degenerate"]:
        raise SystemExit("CANONICAL_PARITY_DEGENERATE")
    if abs(float(sec1["rho"]) - float(canonical["rho"])) > K.PARITY_TOL:
        raise SystemExit("CANONICAL_PARITY")
    prim = partial_rank(s["r1"], s["rp"], [s["ret4"], s["rv4"]])
    sec2 = partial_rank(s["r1"], s["rp"], [s["ret4"], s["rv4"], s["ret1h"], s["ret15"]])
    width_assoc = spearman(s["rp"], s["width"])
    width_partial = partial_rank(s["r1"], s["rp"], [s["ret4"], s["rv4"], s["width"]])
    if raw is None or prim["rho"] is None:
        raise SystemExit("ESTIMATE_MISSING")

    print(f"sample {s['rp'].size} weeks {np.unique(blocks).size}", flush=True)
    boot = _bootstrap(s, blocks)
    route, flags = assign_route(raw, boot["raw"], prim["rho"], boot["primary"])
    attenuation = None if sec1["rho"] is None else float(raw - sec1["rho"])
    med = float(np.median(s["close_ms"]))
    result = {
        "unit": K.UNIT, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "parent_unit": K.PARENT_UNIT, "parent_design_sha256": K.PARENT_DESIGN_SHA256,
        "series": K.SERIES, "series_sha256": K.SERIES_SHA256, "evaluator_digest": _code_digest(),
        "preflight_census": census, "grid": s["grid"], "phase_anchors": s["phase_anchors"],
        "analysis_n": int(s["rp"].size), "iso_weeks": int(np.unique(blocks).size),
        "first_t": ts[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "last_t": ts[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "objects_read": [K.SERIES], "binance_2025_2026_read": False, "spot_read": False, "fees_computed": False,
        "raw_spearman": raw, "primary_partial": prim["rho"], "primary_degenerate": bool(prim["degenerate"]),
        "secondary_ret4_partial": sec1["rho"], "secondary_ret4_matches_canonical": True,
        "attenuation_by_ret": attenuation,
        "share_removed_by_ret": None if (attenuation is None or raw == 0.0) else float(attenuation / raw),
        "secondary_local_partial": sec2["rho"], "secondary_local_degenerate": bool(sec2["degenerate"]),
        "width_spearman_with_rp": width_assoc, "width_partial": width_partial["rho"],
        "bootstrap": boot, "bootstrap_seed": K.BOOT_SEED, "bootstrap_draws": K.BOOT_DRAWS,
        "route": route, "route_flags": flags,
        "quintiles": quintile_table(s["rp"], s["r1"]),
        "yearly": _pieces(s, [(str(int(y)), year == y) for y in sorted(set(year.tolist()))]),
        "halves": {"median_t_ms": med, "pieces": _pieces(s, [("first", s["close_ms"] <= med), ("second", s["close_ms"] > med)])},
    }
    result = _jsonable(result)
    RESULT_JSON.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(result, RESULT_MD)
    print(route, flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true", help="required for the one-shot read, after the owner's go")
    a = ap.parse_args()
    if a.step == "run" and not a.go:
        raise SystemExit("refusing: the one-shot read needs --go after the owner's go")
    out = preflight() if a.step == "preflight" else run()
    print(json.dumps(out, indent=2, sort_keys=True)[:6000])


if __name__ == "__main__":
    main()
