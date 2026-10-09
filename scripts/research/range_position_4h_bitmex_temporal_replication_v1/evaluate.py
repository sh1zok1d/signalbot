"""One BitMEX read. Refuses to score until the design and the support census are frozen."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.formation_width_regime_v1.amendment_a1 import partial_spearman
from scripts.research.range_position_4h_incremental_replication_v1.grid import features
from scripts.research.range_position_4h_incremental_replication_v1.stats import (
    partial_rank,
    quintile_table,
    spearman,
)

from . import constants as K
from .report import write_markdown
from .sample import build_grid, classify, load_rows, rows_to_arrays, sha256
from .stats import assign_route

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_DESIGN.md"
DESIGN_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_DESIGN.json"
SUPPORT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_SUPPORT.json"
RESULT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1.md"
MANIFEST = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_EVALUATOR_MANIFEST.json"
PACKAGE = Path(__file__).resolve().parent


def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists() or MANIFEST.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_frozen() -> dict:
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        raise SystemExit("DESIGN_HASH_UNSET")
    if K.DESIGN_JSON_SHA256 == "PENDING_DESIGN_JSON_HASH":
        raise SystemExit("DESIGN_JSON_HASH_UNSET")
    if K.SUPPORT_SHA256 == "PENDING_SUPPORT_HASH":
        raise SystemExit("SUPPORT_HASH_UNSET")
    design = sha256(DESIGN_PATH)
    if design != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    design_json = sha256(DESIGN_JSON)
    if design_json != K.DESIGN_JSON_SHA256:
        raise SystemExit("DESIGN_JSON_HASH_MISMATCH")
    support_hash = sha256(SUPPORT_JSON)
    if support_hash != K.SUPPORT_SHA256:
        raise SystemExit("SUPPORT_HASH_MISMATCH")
    support = json.loads(SUPPORT_JSON.read_text(encoding="utf-8"))
    if support.get("relation_computed") is not False:
        raise SystemExit("SUPPORT_ALREADY_SCORED")
    if support.get("adequate") is not True:
        raise SystemExit("SUPPORT_INADEQUATE")
    return {"design": design, "design_json": design_json, "support": support_hash, "census": support}


def _jsonable(obj):
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        value = float(obj)
        return value if np.isfinite(value) else None
    return obj


def _code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(PACKAGE.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _interval(samples: np.ndarray) -> dict:
    finite = samples[np.isfinite(samples)]
    if finite.size == 0:
        return {"lo": None, "hi": None, "valid": 0, "draws": K.BOOT_DRAWS}
    return {
        "lo": float(np.quantile(finite, K.BOOT_LO)),
        "hi": float(np.quantile(finite, K.BOOT_HI)),
        "valid": int(finite.size),
        "draws": K.BOOT_DRAWS,
    }


def _bootstrap(rp, target, ret, rv, blocks) -> dict:
    rng = np.random.default_rng(K.BOOT_SEED)
    _uniq, inverse = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inverse == i) for i in range(int(inverse.max()) + 1)]
    n_weeks = len(groups)
    raws = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    prim = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    sec = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    for draw in range(K.BOOT_DRAWS):
        pick = rng.integers(0, n_weeks, size=n_weeks)
        idx = np.concatenate([groups[int(i)] for i in pick])
        raw = spearman(rp[idx], target[idx])
        primary = partial_rank(target[idx], rp[idx], [ret[idx], rv[idx]])
        secondary = partial_rank(target[idx], rp[idx], [ret[idx]])
        raws[draw] = np.nan if raw is None else raw
        prim[draw] = np.nan if primary["rho"] is None else primary["rho"]
        sec[draw] = np.nan if secondary["rho"] is None else secondary["rho"]
        if draw % 250 == 0:
            print(f"bootstrap {draw}", flush=True)
    return {"raw": _interval(raws), "primary": _interval(prim), "secondary": _interval(sec)}


def _by_year(rp, target, ret, rv, year) -> list[dict]:
    rows = []
    for value in sorted(set(int(v) for v in year)):
        mask = year == value
        raw = spearman(rp[mask], target[mask])
        primary = partial_rank(target[mask], rp[mask], [ret[mask], rv[mask]])
        rows.append({
            "year": int(value),
            "n": int(mask.sum()),
            "raw": raw,
            "primary": primary["rho"],
            "primary_degenerate": bool(primary["degenerate"]),
        })
    return rows


def _halves(rp, target, ret, rv, when) -> dict:
    med = float(np.median(when))
    out = {"median_t_ms": med, "median_t": _iso(int(med))}
    for name, mask in (("first", when <= med), ("second", when > med)):
        raw = spearman(rp[mask], target[mask])
        primary = partial_rank(target[mask], rp[mask], [ret[mask], rv[mask]])
        out[name] = {
            "n": int(mask.sum()),
            "raw": raw,
            "primary": primary["rho"],
            "primary_degenerate": bool(primary["degenerate"]),
        }
    return out


def _status(route: str) -> str:
    if route == K.ROUTE_SUPPORTED:
        return "CROSS_VENUE_AND_TEMPORALLY_REPLICATED_DIRECTIONAL_STATE"
    return "CROSS_VENUE_REPLICATED_DIRECTIONAL_STATE / TEMPORAL_GENERALIZATION_NOT_ESTABLISHED"


def run() -> dict:
    refuse_if_scored()
    frozen = assert_frozen()
    census = frozen["census"]
    opens, highs, lows, closes = rows_to_arrays(load_rows(ROOT / K.SERIES))
    grid = build_grid(opens, highs, lows, closes)
    masks = classify(grid)
    feat = features(grid["high"], grid["low"], grid["close"])
    finite = (
        np.isfinite(feat["rp"])
        & np.isfinite(feat["ret4"])
        & np.isfinite(feat["rv4"])
        & np.isfinite(feat["r1"])
    )
    if not np.all(finite[masks["eligible"]]):
        raise SystemExit("ELIGIBILITY_FEATURE_MISMATCH")
    idx = np.flatnonzero(masks["eligible"])
    if int(idx.size) != int(census["eligible"]):
        raise SystemExit("SUPPORT_N_MISMATCH")
    rp = feat["rp"][idx]
    ret = feat["ret4"][idx]
    rv = feat["rv4"][idx]
    target = feat["r1"][idx]
    close_ms = grid["close_at_decision"][idx]
    first_t = _iso(int(close_ms[0]))
    last_t = _iso(int(close_ms[-1]))
    if first_t != census["first_eligible_t"] or last_t != census["last_eligible_t"]:
        raise SystemExit("SUPPORT_ENDPOINT_MISMATCH")
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    blocks = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    year = ts.year.to_numpy(dtype=np.int64)
    if int(np.unique(blocks).size) != int(census["iso_weeks"]):
        raise SystemExit("SUPPORT_WEEK_MISMATCH")

    raw = spearman(rp, target)
    secondary = partial_rank(target, rp, [ret])
    canonical = partial_spearman(rp, target, ret)
    if secondary["degenerate"] or canonical["degenerate"]:
        raise SystemExit("CANONICAL_PARITY_DEGENERATE")
    if abs(float(secondary["rho"]) - float(canonical["rho"])) > 1e-8:
        raise SystemExit("CANONICAL_PARITY")
    primary = partial_rank(target, rp, [ret, rv])
    if raw is None or primary["rho"] is None or secondary["rho"] is None:
        raise SystemExit("ESTIMATE_MISSING")

    print(f"sample {idx.size} weeks {np.unique(blocks).size}", flush=True)
    boot = _bootstrap(rp, target, ret, rv, blocks)
    route = assign_route(raw, boot["raw"], primary["rho"], boot["primary"])
    result = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False,
        "historical_only": True,
        "current_probability": False,
        "target_hit_model": False,
        "trading_edge": False,
        "design_sha256": frozen["design"],
        "design_json_sha256": frozen["design_json"],
        "support_sha256": frozen["support"],
        "series_sha256": K.SERIES_SHA256,
        "evaluator_digest": _code_digest(),
        "series": K.SERIES,
        "price_transform": "last_trade_price_space_no_inverse",
        "d7_read": False,
        "holes": int(grid["holes"]),
        "occupied_bars": int(grid["occupied"]),
        "grid_slots": int(grid["slots"]),
        "phase_anchors": int(masks["phase"].sum()),
        "lost_to_gap": int(masks["gap"].sum()),
        "lost_to_lookback": int(masks["lookback"].sum()),
        "lost_to_future": int(masks["future"].sum()),
        "analysis_n": int(idx.size),
        "iso_weeks": int(np.unique(blocks).size),
        "first_t": first_t,
        "last_t": last_t,
        "years_present": sorted(set(int(v) for v in year)),
        "raw_spearman": raw,
        "secondary_partial_ret": secondary["rho"],
        "secondary_matches_canonical": True,
        "primary_partial": primary["rho"],
        "primary_degenerate": bool(primary["degenerate"]),
        "bootstrap": boot,
        "route": route,
        "scientific_status": _status(route),
        "quintiles": quintile_table(rp, target),
        "yearly": _by_year(rp, target, ret, rv, year),
        "halves": _halves(rp, target, ret, rv, close_ms.astype(np.float64)),
        "bootstrap_seed": K.BOOT_SEED,
        "bootstrap_draws": K.BOOT_DRAWS,
    }
    manifest = {
        "unit": K.UNIT,
        "design_sha256": frozen["design"],
        "design_json_sha256": frozen["design_json"],
        "support_sha256": frozen["support"],
        "series_sha256": K.SERIES_SHA256,
        "evaluator_digest": result["evaluator_digest"],
        "bootstrap_seed": K.BOOT_SEED,
        "bootstrap_draws": K.BOOT_DRAWS,
        "route": route,
        "features_imported_from": "scripts.research.range_position_4h_incremental_replication_v1.grid",
        "partial_rank_imported_from": "scripts.research.range_position_4h_incremental_replication_v1.stats",
    }
    RESULT_JSON.write_text(json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    MANIFEST.write_text(json.dumps(_jsonable(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(result, RESULT_MD)
    print(route, flush=True)
    return result


if __name__ == "__main__":
    run()
