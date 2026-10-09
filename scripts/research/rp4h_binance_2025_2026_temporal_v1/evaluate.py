"""Unit B: one Binance 2025-26 read with Unit A's exact estimands (shared code imported from Unit A).

    python -m scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate preflight   # manifest, guard, hashes, census
    python -m scripts.research.rp4h_binance_2025_2026_temporal_v1.evaluate run --go    # one shot, after the owner's go
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.rp4h_bitmex_temporal_v1 import constants as KA
from scripts.research.rp4h_bitmex_temporal_v1.evaluate import _bootstrap, _jsonable, _pieces, assign_route
from scripts.research.rp4h_bitmex_temporal_v1.grid import local_returns
from scripts.research.rp4h_bitmex_temporal_v1.parent import features, partial_rank, quintile_table, ref_partial_spearman, spearman

from . import constants as K
from .data import ROOT, anchor_mask, census, load_series, place
from .report import write_markdown

DESIGN_PATH = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1.md"
PACKAGES = (Path(__file__).resolve().parent, ROOT / "scripts" / "research" / "rp4h_bitmex_temporal_v1")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_design_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        raise SystemExit("DESIGN_HASH_UNSET")
    found = _sha256(DESIGN_PATH)
    if found != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return found


def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_census(c: dict) -> None:
    if not K.CENSUS_PINNED:
        raise SystemExit("CENSUS_NOT_PINNED")
    if (c["rows"], c["holes"], c["holes_sha256"]) != (K.EXPECTED_ROWS, K.EXPECTED_HOLES, K.EXPECTED_HOLES_SHA256):
        raise SystemExit("CENSUS_MISMATCH")


def _code_digest() -> str:
    digest = hashlib.sha256()
    for pkg in PACKAGES:
        for path in sorted(pkg.glob("*.py")):
            digest.update(f"{pkg.name}/{path.name}".encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def build_sample(series: dict) -> dict:
    grid = place(series)
    feat = features(grid["high"], grid["low"], grid["close"])
    loc = local_returns(grid["close"])
    future_open = grid["grid_open"] + KA.HORIZON * K.BAR_MS
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


def preflight() -> dict:
    series = load_series()
    return {"design_sha256": _sha256(DESIGN_PATH), "object_list_sha256": K.OBJECT_LIST_SHA256, **census(series)}


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    series = load_series()
    c = census(series)
    assert_census(c)
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
    if abs(float(sec1["rho"]) - float(canonical["rho"])) > KA.PARITY_TOL:
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
        "sibling_unit": K.SIBLING_UNIT, "parent_unit": K.PARENT_UNIT,
        "manifest": K.MANIFEST, "object_list_sha256": K.OBJECT_LIST_SHA256, "evaluator_digest": _code_digest(),
        "e1_window": "excluded by the pre-fixed object-level rule (beta.history_data PROTECTED_WINDOWS); never requested",
        "preflight_census": c, "grid": s["grid"], "phase_anchors": s["phase_anchors"],
        "analysis_n": int(s["rp"].size), "iso_weeks": int(np.unique(blocks).size),
        "first_t": ts[0].strftime("%Y-%m-%dT%H:%M:%SZ"), "last_t": ts[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "spot_read": False, "rejection_or_bars_since_read": False, "fees_computed": False,
        "raw_spearman": raw, "primary_partial": prim["rho"], "primary_degenerate": bool(prim["degenerate"]),
        "secondary_ret4_partial": sec1["rho"], "secondary_ret4_matches_canonical": True,
        "attenuation_by_ret": attenuation,
        "share_removed_by_ret": None if (attenuation is None or raw == 0.0) else float(attenuation / raw),
        "secondary_local_partial": sec2["rho"], "secondary_local_degenerate": bool(sec2["degenerate"]),
        "width_spearman_with_rp": width_assoc, "width_partial": width_partial["rho"],
        "bootstrap": boot, "bootstrap_seed": KA.BOOT_SEED, "bootstrap_draws": KA.BOOT_DRAWS,
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
