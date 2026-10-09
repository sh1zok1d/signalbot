"""OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1: one read of OCC_MEAN_4H on the canonical Binance 2025-26 surface.

    python -m scripts.research.occ_mean_4h_modern_temporal_v1.evaluate preflight   # outcome-blind
    python -m scripts.research.occ_mean_4h_modern_temporal_v1.evaluate run --go    # the one shot, after the owner's go

Imported, not copied: the canonical Binance 2025-26 surface of RP4H Unit B (manifest, object refusals, E1 guard,
E1-development cut, census pins, grid, anchors, sample), the OCC formula of the discovery (F2a), and the estimands,
week-block bootstrap, pieces, quintiles and identity audit of OCC_MEAN_4H_TEMPORAL_REPLICATION_V1.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.research.directional_state_search_v2.features import occupancy
from scripts.research.occ_mean_4h_temporal_v1 import constants as KO
from scripts.research.occ_mean_4h_temporal_v1.evaluate import (blocks_of, bootstrap, estimate, identity_audit, pieces,
                                                               quintiles)
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import constants as KB
from scripts.research.rp4h_binance_2025_2026_temporal_v1 import data as DB
from scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate import assert_census, build_sample
from scripts.research.rp4h_bitmex_temporal_v1.parent import _ols_residual, average_ranks_fast

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs/research/OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs/research/OCC_MEAN_4H_MODERN_TEMPORAL_REPLICATION_V1.md"
PACKAGES = (Path(__file__).resolve().parent, ROOT / "scripts/research/occ_mean_4h_temporal_v1",
            ROOT / "scripts/research/rp4h_binance_2025_2026_temporal_v1", ROOT / "scripts/research/rp4h_bitmex_temporal_v1",
            ROOT / "scripts/research/directional_state_search_v2")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digest() -> str:
    h = hashlib.sha256()
    for pkg in PACKAGES:
        for p in sorted(pkg.glob("*.py")):
            h.update(f"{pkg.name}/{p.name}".encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def occ_sample(series: dict) -> dict:
    """Unit B's sample plus OCC_MEAN_4H from the discovery function on the same dense grid."""
    s = build_sample(series)
    grid = DB.place(series)
    idx = ((s["close_ms"] - KB.BAR_MS - KB.SURFACE_START_MS) // KB.BAR_MS).astype(np.int64)
    o = occupancy({"high": grid["high"], "low": grid["low"], "close": grid["close"]}, idx)["OCC_MEAN_4H"]
    if not np.isfinite(o).all():
        raise SystemExit("OCC_NOT_FINITE_ON_SAMPLE")
    s.update({"occ": o, "idx": idx, "_grid": grid})
    return s


def support(s: dict) -> dict:
    blocks, year = blocks_of(s["close_ms"])
    med = float(np.median(s["close_ms"]))
    return {"n": int(s["occ"].size), "iso_weeks": int(np.unique(blocks).size),
            "by_year": {str(y): int((year == y).sum()) for y in sorted(set(year.tolist()))},
            "halves": {"first": int((s["close_ms"] <= med).sum()), "second": int((s["close_ms"] > med).sum()),
                       "median_t_ms": med},
            "phase_anchors": s["phase_anchors"], "grid": s["grid"]}


def preflight() -> dict:
    series = DB.load_series()
    census = DB.census(series)
    assert_census(census)
    s = occ_sample(series)
    return {"object_list_sha256": KB.OBJECT_LIST_SHA256, "census": census, "support": support(s),
            "identity": identity_audit(s), "design_sha256": _sha(DESIGN_PATH) if DESIGN_PATH.exists() else None}


def assign_route(points: dict, ci: dict) -> str:
    """Frozen order: INVALID, SUPPORTED, SIGN_OPPOSES, DIRECTION_COMPATIBLE_BUT_UNCERTAIN, NOT_REPLICATED (PRIMARY only)."""
    p, c = points.get(K.PRIMARY), ci.get(K.PRIMARY, {})
    if p is None or c.get("valid", 0) < KO.MIN_VALID_DRAWS or c.get("lo") is None:
        return K.ROUTE_INVALID
    if p > 0 and c["lo"] > 0:
        return K.ROUTE_SUPPORTED
    if c["hi"] < 0:
        return K.ROUTE_OPPOSES
    if p > 0:
        return K.ROUTE_COMPATIBLE
    return K.ROUTE_NOT


def heterogeneity(point: float, ci: dict) -> dict:
    """Descriptive, no route: modern PRIMARY minus BitMEX PRIMARY with SEs approximated from each 95 % percentile
    interval (width / 3.92), and the same for B0 against BitMEX and discovery."""
    se = lambda lo, hi: (hi - lo) / 3.92
    s_new = se(ci["lo"], ci["hi"])
    s_bmx = se(*K.BITMEX["b1_ci"])
    d = point - K.BITMEX["b1"]
    return {"modern_minus_bitmex_b1": d, "approx_se": float(np.hypot(s_new, s_bmx)),
            "approx_z": float(d / np.hypot(s_new, s_bmx))}


def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_design_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING":
        raise SystemExit("DESIGN_HASH_UNSET")
    if _sha(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return K.DESIGN_SHA256


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    series = DB.load_series()
    census = DB.census(series)
    assert_census(census)
    s = occ_sample(series)
    sup = support(s)
    if K.EXPECTED_N is None or (sup["n"], sup["iso_weeks"]) != (K.EXPECTED_N, K.EXPECTED_WEEKS):
        raise SystemExit("SUPPORT_MISMATCH")
    ida = identity_audit(s)
    if ida["r2_rank_occ_on_B1"] is None:
        raise SystemExit("REDUNDANT_BY_CONSTRUCTION")
    blocks, year = blocks_of(s["close_ms"])
    points = {name: estimate(s, None, ctrl) for name, ctrl in KO.ESTIMANDS}
    print(f"sample {sup['n']} weeks {sup['iso_weeks']}", flush=True)
    ci = bootstrap(s, blocks)
    route = assign_route(points, ci)
    rx = average_ranks_fast(s["occ"])
    rz = np.column_stack([average_ranks_fast(s[c]) for c in dict(KO.ESTIMANDS)[K.PRIMARY]])
    resid = _ols_residual(rx, rz)
    med = sup["halves"]["median_t_ms"]
    het = {"b1": heterogeneity(points[K.PRIMARY], ci[K.PRIMARY])} if points[K.PRIMARY] is not None else None
    result = {
        "unit": K.UNIT, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "evaluator_digest": code_digest(), "manifest": KB.MANIFEST, "object_list_sha256": KB.OBJECT_LIST_SHA256,
        "census": census, "support": sup, "identity_audit": ida,
        "estimands": {name: list(ctrl) for name, ctrl in KO.ESTIMANDS}, "primary": K.PRIMARY,
        "bootstrap": {"draws": KO.BOOT_DRAWS, "seed": KO.BOOT_SEED, "min_valid": KO.MIN_VALID_DRAWS},
        "points": points, "intervals": ci, "route": route, "status_after_route": K.STATUS[route],
        "years": pieces(s, [(str(y), year == y) for y in sorted(set(year.tolist()))]),
        "halves": {"median_t_ms": med, "pieces": pieces(s, [("first", s["close_ms"] <= med), ("second", s["close_ms"] > med)])},
        "quintiles_occ": quintiles(s["occ"], s["r1"]),
        "quintiles_occ_residual_on_b1": None if resid is None else quintiles(resid, s["r1"]),
        "p_up_all": float(np.mean(s["r1"] > 0)), "mean_bp_all": float(s["r1"].mean() * 1e4),
        "median_bp_all": float(np.median(s["r1"]) * 1e4),
        "comparison_quoted": {"discovery": K.DISCOVERY, "bitmex": K.BITMEX}, "heterogeneity": het,
        "e1_window": "never requested (product guard; object level)",
        "e1_development_slice": "[2026-08-02, 2026-08-16) never requested (Unit B canonical exclusion)",
        "not_read": ["CORE / Binance 2020-24 (no B1 recomputation)", "spot", "BitMEX", "OCC variants", "other windows",
                     "other horizons", "interactions", "OI", "E1", "PnL"],
    }
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown
    write_markdown(result, RESULT_MD)
    print(route, flush=True)
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=("preflight", "run"))
    ap.add_argument("--go", action="store_true")
    a = ap.parse_args()
    if a.step == "preflight":
        print(json.dumps(preflight(), indent=1, sort_keys=True))
        return
    if not a.go:
        raise SystemExit("refusing: the one-shot read needs --go after the owner's go")
    run()


if __name__ == "__main__":
    main()
