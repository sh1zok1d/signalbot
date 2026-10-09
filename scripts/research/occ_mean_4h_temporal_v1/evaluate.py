"""OCC_MEAN_4H_TEMPORAL_REPLICATION_V1: one BitMEX 2016-19 read of the discovery object F2a.

    python -m scripts.research.occ_mean_4h_temporal_v1.evaluate preflight   # outcome-blind
    python -m scripts.research.occ_mean_4h_temporal_v1.evaluate run --go    # the one shot, after the owner's go

Shared code is imported, not copied: the BitMEX canonical loader, census, grid, anchors, sample and local returns
(Unit A, scripts/research/rp4h_bitmex_temporal_v1), the OCC formula (discovery, directional_state_search_v2.features
.occupancy) and the rank machinery (RP4H parent code).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.directional_state_search_v2.features import occupancy
from scripts.research.rp4h_bitmex_temporal_v1 import constants as KA
from scripts.research.rp4h_bitmex_temporal_v1.evaluate import build_sample
from scripts.research.rp4h_bitmex_temporal_v1.grid import load_series, place, preflight_census
from scripts.research.rp4h_bitmex_temporal_v1.parent import _ols_residual, average_ranks_fast, partial_rank, spearman

from . import constants as K

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs/research/OCC_MEAN_4H_TEMPORAL_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs/research/OCC_MEAN_4H_TEMPORAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs/research/OCC_MEAN_4H_TEMPORAL_REPLICATION_V1.md"
PACKAGES = (Path(__file__).resolve().parent, ROOT / "scripts/research/rp4h_bitmex_temporal_v1",
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


# ------------------------------------------------------------------ sample
def occ_sample(series: dict) -> dict:
    """Unit A's sample (RP4H, RET_4H, RV_4H, width, R_1H finite; RET_1H, RET_15M inside it) plus OCC_MEAN_4H from the
    discovery function on the same dense grid. Refuses if OCC is not finite on the whole sample."""
    s = build_sample(series)
    grid = place(series)
    idx = ((s["close_ms"] - KA.BAR_MS - grid["grid_open"][0]) // KA.BAR_MS).astype(np.int64)
    bars = {"high": grid["high"], "low": grid["low"], "close": grid["close"]}
    o = occupancy(bars, idx)["OCC_MEAN_4H"]
    if not np.isfinite(o).all():
        raise SystemExit("OCC_NOT_FINITE_ON_SAMPLE")
    s["occ"] = o
    s["idx"] = idx
    s["_grid"] = grid
    return s


def blocks_of(close_ms: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    return iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64), ts.year.to_numpy(dtype=np.int64)


def identity_audit(s: dict) -> dict:
    """Outcome-blind. OCC - RP4H = -(close_i - SMA47)/(H - L), SMA47 = mean of the 47 prior closes, H/L the RP4H box.
    Reports the algebra residual and how much of rank(OCC) the controls determine (R^2 of OLS on their ranks)."""
    g, idx = s["_grid"], s["idx"]
    w = np.arange(-47, 0)
    sma = g["close"][idx[:, None] + w[None, :]].mean(axis=1)
    hi = g["high"][idx[:, None] + np.arange(-47, 1)[None, :]].max(axis=1)
    lo = g["low"][idx[:, None] + np.arange(-47, 1)[None, :]].min(axis=1)
    d = (g["close"][idx] - sma) / (hi - lo)
    algebra = float(np.max(np.abs((s["occ"] - s["rp"]) + d)))
    ro = average_ranks_fast(s["occ"])
    out = {"max_abs_algebra_residual": algebra}
    for name, ctrl in (("B0", ("rp", "ret4", "rv4")), ("B1", ("rp", "ret4", "rv4", "ret1h", "ret15"))):
        rz = np.column_stack([average_ranks_fast(s[c]) for c in ctrl])
        res = _ols_residual(ro, rz)
        out[f"r2_rank_occ_on_{name}"] = None if res is None else float(1.0 - res.var() / ro.var())
        lin = np.column_stack([s[c] for c in ctrl])
        res2 = _ols_residual(s["occ"], lin)
        out[f"r2_occ_on_{name}_values"] = None if res2 is None else float(1.0 - res2.var() / s["occ"].var())
    out["spearman_occ_rp4h"] = spearman(s["occ"], s["rp"])
    out["spearman_occ_minus_rp_vs_close_minus_sma"] = spearman(s["occ"] - s["rp"], -d)
    return out


def support(s: dict) -> dict:
    blocks, year = blocks_of(s["close_ms"])
    return {"n": int(s["occ"].size), "iso_weeks": int(np.unique(blocks).size),
            "by_year": {str(y): int((year == y).sum()) for y in sorted(set(year.tolist()))},
            "first_t": pd.Timestamp(int(s["close_ms"][0]), unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_t": pd.Timestamp(int(s["close_ms"][-1]), unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase_anchors": s["phase_anchors"], "grid": s["grid"]}


def preflight() -> dict:
    series = load_series()
    census = preflight_census(series)
    s = occ_sample(series)
    return {"series_sha256": KA.SERIES_SHA256, "census": census, "support": support(s), "identity": identity_audit(s),
            "design_sha256": _sha(DESIGN_PATH) if DESIGN_PATH.exists() else None}


# ------------------------------------------------------------------ estimands and the one shot
def estimate(s: dict, idx: np.ndarray | None, controls: tuple) -> float | None:
    x, y = (s["occ"], s["r1"]) if idx is None else (s["occ"][idx], s["r1"][idx])
    if not controls:
        return spearman(x, y)
    cols = [s[c] if idx is None else s[c][idx] for c in controls]
    return partial_rank(y, x, cols)["rho"]


def bootstrap(s: dict, blocks: np.ndarray) -> dict:
    """Canonical RP4H contract: ISO-week blocks resampled with replacement, every estimand and its ranks recomputed
    per draw, B and seed frozen, percentile 2.5/97.5, at least MIN_VALID_DRAWS valid draws."""
    rng = np.random.default_rng(K.BOOT_SEED)
    _u, inv = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inv == i) for i in range(inv.max() + 1)]
    w = len(groups)
    draws = {name: np.full(K.BOOT_DRAWS, np.nan) for name, _ in K.ESTIMANDS}
    for d in range(K.BOOT_DRAWS):
        pick = rng.integers(0, w, size=w)
        ix = np.concatenate([groups[i] for i in pick])
        for name, ctrl in K.ESTIMANDS:
            v = estimate(s, ix, ctrl)
            draws[name][d] = np.nan if v is None else v
        if d % 250 == 0:
            print(f"bootstrap {d}", flush=True)
    out = {}
    for name, v in draws.items():
        f = v[np.isfinite(v)]
        out[name] = {"lo": float(np.quantile(f, K.BOOT_LO)) if f.size else None,
                     "hi": float(np.quantile(f, K.BOOT_HI)) if f.size else None,
                     "valid": int(f.size), "draws": K.BOOT_DRAWS}
    return out


def assign_route(points: dict, ci: dict) -> tuple[str, list]:
    """Frozen order. Only PRIMARY (B1) routes to SUPPORTED; B0 decides between LOCAL_PATH and NOT."""
    p, pc = points[K.PRIMARY], ci[K.PRIMARY]
    b, bc = points["b0"], ci["b0"]
    if p is None or b is None or pc["valid"] < K.MIN_VALID_DRAWS or bc["valid"] < K.MIN_VALID_DRAWS:
        return K.ROUTE_INVALID, []
    sgn = K.DISCOVERY_SIGN
    flags = []
    if sgn * p > 0 and (pc["lo"] > 0 if sgn > 0 else pc["hi"] < 0):
        return K.ROUTE_SUPPORTED, flags
    b0_replicates = sgn * b > 0 and (bc["lo"] > 0 if sgn > 0 else bc["hi"] < 0)
    if (pc["hi"] < 0 if sgn > 0 else pc["lo"] > 0):
        flags.append(K.FLAG_PRIMARY_OPPOSES)
    if b0_replicates:
        return K.ROUTE_LOCAL_PATH, flags
    return K.ROUTE_NOT, flags


def pieces(s: dict, masks: list) -> list:
    rows = []
    for name, m in masks:
        ix = np.flatnonzero(m)
        rows.append({"piece": name, "n": int(ix.size), **{e: estimate(s, ix, c) for e, c in K.ESTIMANDS}})
    return rows


def quintiles(x: np.ndarray, y: np.ndarray) -> dict:
    edges = np.quantile(x, [0.2, 0.4, 0.6, 0.8])
    if not (edges[0] < edges[1] < edges[2] < edges[3]):
        return {"degenerate": True, "edges": [float(v) for v in edges], "bins": None}
    b = np.digitize(x, edges, right=False)
    return {"degenerate": False, "edges": [float(v) for v in edges],
            "bins": [{"bin": k + 1, "n": int((b == k).sum()), "p_up": float(np.mean(y[b == k] > 0)),
                      "mean_bp": float(y[b == k].mean() * 1e4), "median_bp": float(np.median(y[b == k]) * 1e4)}
                     for k in range(5)]}


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
    series = load_series()
    census = preflight_census(series)
    s = occ_sample(series)
    sup = support(s)
    if K.EXPECTED_N is None or (sup["n"], sup["iso_weeks"]) != (K.EXPECTED_N, K.EXPECTED_WEEKS):
        raise SystemExit("SUPPORT_MISMATCH")
    ida = identity_audit(s)
    if ida["r2_rank_occ_on_B1"] is None:
        raise SystemExit("REDUNDANT_BY_CONSTRUCTION")
    blocks, year = blocks_of(s["close_ms"])
    points = {name: estimate(s, None, ctrl) for name, ctrl in K.ESTIMANDS}
    print(f"sample {sup['n']} weeks {sup['iso_weeks']}", flush=True)
    ci = bootstrap(s, blocks)
    route, flags = assign_route(points, ci)
    rx = average_ranks_fast(s["occ"])
    rz = np.column_stack([average_ranks_fast(s[c]) for c in dict(K.ESTIMANDS)[K.PRIMARY]])
    resid = _ols_residual(rx, rz)
    med = float(np.median(s["close_ms"]))
    result = {
        "unit": K.UNIT, "evidence_class": K.EVIDENCE_CLASS, "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False, "design_sha256": design, "design_commit": K.DESIGN_COMMIT,
        "evaluator_digest": code_digest(), "series": KA.SERIES, "series_sha256": KA.SERIES_SHA256, "census": census,
        "support": sup, "identity_audit": ida, "estimands": {name: list(ctrl) for name, ctrl in K.ESTIMANDS}, "primary": K.PRIMARY,
        "points": points, "intervals": ci, "route": route, "route_flags": flags,
        "years": pieces(s, [(str(y), year == y) for y in sorted(set(year.tolist()))]),
        "halves": {"median_t_ms": med, "pieces": pieces(s, [("first", s["close_ms"] <= med), ("second", s["close_ms"] > med)])},
        "quintiles_occ": quintiles(s["occ"], s["r1"]),
        "quintiles_occ_residual_on_b1": None if resid is None else quintiles(resid, s["r1"]),
        "p_up_all": float(np.mean(s["r1"] > 0)), "mean_bp_all": float(s["r1"].mean() * 1e4),
        "median_bp_all": float(np.median(s["r1"]) * 1e4),
        "discovery": {"unit": K.DISCOVERY_UNIT, "object": K.DISCOVERY_OBJECT, "result_sha256": K.DISCOVERY_RESULT_SHA256,
                      "b0_point": K.DISCOVERY_B0_POINT, "b0_ci": list(K.DISCOVERY_B0_CI),
                      "local_path_controlled_point": "not computed (discovery surface untouched by owner instruction)"},
        "not_read": ["spot", "Binance 2025/2026", "CORE", "OCC variants", "other horizons", "interactions", "OI", "E1"],
    }
    RESULT_JSON.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    from .report import write_markdown
    write_markdown(result, RESULT_MD)
    print(route, flags, flush=True)
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
