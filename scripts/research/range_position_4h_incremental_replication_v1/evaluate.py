"""One Bybit read. Refuses to open the series until the design hash matches."""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.formation_width_regime_v1.amendment_a1 import partial_spearman

from . import constants as K
from .grid import anchor_mask, features, place
from .report import write_markdown
from .stats import _interval, assign_route, partial_rank, quintile_table, spearman

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1_DESIGN.md"
RESULT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1.json"
RESULT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_INCREMENTAL_REPLICATION_V1.md"
PACKAGE = Path(__file__).resolve().parent


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def refuse_if_scored() -> None:
    if RESULT_JSON.exists() or RESULT_MD.exists():
        raise SystemExit("REFUSING_RERUN")


def assert_design_frozen() -> str:
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        raise SystemExit("DESIGN_HASH_UNSET")
    found = _sha256(DESIGN_PATH)
    if found != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    return found


def _load_series(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if _sha256(path) != K.SERIES_SHA256:
        raise SystemExit("SERIES_HASH_MISMATCH")
    opens: list[int] = []
    highs: list[float] = []
    lows: list[float] = []
    closes: list[float] = []
    with gzip.open(path, "rt") as handle:
        header = handle.readline().strip()
        if header != "open_ms,open,high,low,close":
            raise SystemExit("SERIES_HEADER")
        for line in handle:
            parts = line.strip().split(",")
            if len(parts) != 5:
                raise SystemExit("SERIES_ROW")
            opened = int(parts[0])
            if opened >= K.SURFACE_END_MS:
                raise SystemExit("SERIES_CROSSES_2025")
            opens.append(opened)
            highs.append(float(parts[2]))
            lows.append(float(parts[3]))
            closes.append(float(parts[4]))
    return (
        np.asarray(opens, dtype=np.int64),
        np.asarray(highs, dtype=np.float64),
        np.asarray(lows, dtype=np.float64),
        np.asarray(closes, dtype=np.float64),
    )


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


def _bootstrap(rp, target, ret, rv, blocks) -> dict:
    rng = np.random.default_rng(K.BOOT_SEED)
    _uniq, inverse = np.unique(blocks, return_inverse=True)
    groups = [np.flatnonzero(inverse == i) for i in range(inverse.max() + 1)]
    n_weeks = len(groups)
    raws = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    prim = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    sec = np.empty(K.BOOT_DRAWS, dtype=np.float64)
    for draw in range(K.BOOT_DRAWS):
        pick = rng.integers(0, n_weeks, size=n_weeks)
        idx = np.concatenate([groups[i] for i in pick])
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
        m = year == value
        raw = spearman(rp[m], target[m])
        primary = partial_rank(target[m], rp[m], [ret[m], rv[m]])
        rows.append({
            "year": int(value),
            "n": int(m.sum()),
            "raw": raw,
            "primary": primary["rho"],
            "primary_degenerate": bool(primary["degenerate"]),
        })
    return rows


def _halves(rp, target, ret, rv, when) -> dict:
    med = float(np.median(when))
    out = {"median_t_ms": med}
    for name, mask in ("first", when <= med), ("second", when > med):
        raw = spearman(rp[mask], target[mask])
        primary = partial_rank(target[mask], rp[mask], [ret[mask], rv[mask]])
        out[name] = {
            "n": int(mask.sum()),
            "raw": raw,
            "primary": primary["rho"],
            "primary_degenerate": bool(primary["degenerate"]),
        }
    return out


def run() -> dict:
    refuse_if_scored()
    design = assert_design_frozen()
    path = ROOT / K.SERIES
    opens, highs, lows, closes = _load_series(path)
    grid = place(opens, highs, lows, closes)
    feat = features(grid["high"], grid["low"], grid["close"])
    future_open = grid["grid_open"] + K.HORIZON * K.BAR_MS
    feat["r1"] = np.where(future_open < K.SURFACE_END_MS, feat["r1"], np.nan)
    keep = anchor_mask(grid["grid_open"])
    phase_n = int(keep.sum())
    finite = (
        np.isfinite(feat["rp"])
        & np.isfinite(feat["ret4"])
        & np.isfinite(feat["rv4"])
        & np.isfinite(feat["width"])
        & np.isfinite(feat["r1"])
    )
    sample = keep & finite
    idx = np.flatnonzero(sample)
    rp = feat["rp"][idx]
    ret = feat["ret4"][idx]
    rv = feat["rv4"][idx]
    width = feat["width"][idx]
    target = feat["r1"][idx]
    close_ms = grid["grid_open"][idx] + K.BAR_MS
    ts = pd.to_datetime(close_ms, unit="ms", utc=True)
    iso = ts.isocalendar()
    blocks = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    year = ts.year.to_numpy(dtype=np.int64)

    raw = spearman(rp, target)
    secondary = partial_rank(target, rp, [ret])
    canonical = partial_spearman(rp, target, ret)
    if secondary["degenerate"] or canonical["degenerate"]:
        raise SystemExit("CANONICAL_PARITY_DEGENERATE")
    if abs(float(secondary["rho"]) - float(canonical["rho"])) > 1e-8:
        raise SystemExit("CANONICAL_PARITY")
    primary = partial_rank(target, rp, [ret, rv])
    width_assoc = spearman(rp, width)
    width_partial = partial_rank(target, rp, [ret, rv, width])
    if raw is None or primary["rho"] is None or secondary["rho"] is None:
        raise SystemExit("ESTIMATE_MISSING")

    print(f"sample {idx.size} weeks {np.unique(blocks).size}", flush=True)
    boot = _bootstrap(rp, target, ret, rv, blocks)
    route = assign_route(raw, boot["raw"], primary["rho"], boot["primary"])
    attenuation = float(raw - secondary["rho"])
    share = None if raw == 0.0 else float(attenuation / raw)
    result = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "product_integration_candidate": False,
        "design_sha256": design,
        "series_sha256": K.SERIES_SHA256,
        "evaluator_digest": _code_digest(),
        "surface": K.SURFACE,
        "series": K.SERIES,
        "objects_2025_2026_used": False,
        "binance_outcomes_used": False,
        "rejection_features_read": False,
        "fees_computed": False,
        "holes": grid["holes"],
        "occupied_bars": grid["occupied"],
        "grid_slots": grid["slots"],
        "first_open": int(grid["grid_open"][0]),
        "last_open": int(grid["grid_open"][-1]),
        "phase_anchors": phase_n,
        "analysis_n": int(idx.size),
        "iso_weeks": int(np.unique(blocks).size),
        "first_t": ts[0].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_t": ts[-1].strftime("%Y-%m-%dT%H:%M:%SZ"),
        "years_present": sorted(set(int(v) for v in year)),
        "raw_spearman": raw,
        "secondary_partial_ret": secondary["rho"],
        "secondary_matches_canonical": True,
        "primary_partial": primary["rho"],
        "primary_degenerate": bool(primary["degenerate"]),
        "attenuation_by_ret": attenuation,
        "share_removed_by_ret": share,
        "width_spearman_with_rp": width_assoc,
        "width_partial": width_partial["rho"],
        "width_partial_degenerate": bool(width_partial["degenerate"]),
        "bootstrap": boot,
        "route": route,
        "quintiles": quintile_table(rp, target),
        "yearly": _by_year(rp, target, ret, rv, year),
        "halves": _halves(rp, target, ret, rv, close_ms.astype(np.float64)),
        "bootstrap_seed": K.BOOT_SEED,
        "bootstrap_draws": K.BOOT_DRAWS,
    }
    RESULT_JSON.write_text(json.dumps(_jsonable(result), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(result, RESULT_MD)
    print(route, flush=True)
    return result


if __name__ == "__main__":
    run()
