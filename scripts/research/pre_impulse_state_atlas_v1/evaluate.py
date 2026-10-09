"""One logged discovery pass for PRE_IMPULSE_STATE_ATLAS_V1.

A second call returns REFUSING_RERUN before any price is loaded.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import constants as K
from .features import FORMULA, INPUTS, LOOKBACK, align_closes, compute_features
from .report import write_figure, write_markdown
from .stats import (
    bootstrap_cell,
    discovery_score,
    half_split,
    hour_adjust,
    leave_one_year_out,
    outcome_slices,
    partial_given_rv,
    quintile_table,
    spearman,
    state_from_sign,
    weekly_spearman,
    yearly_table,
)

ROOT = Path(__file__).resolve().parents[3]
DESIGN_PATH = ROOT / "docs" / "research" / "PRE_IMPULSE_STATE_ATLAS_V1_DESIGN.md"
RESULT_PATH = ROOT / "docs" / "research" / "PRE_IMPULSE_STATE_ATLAS_V1.json"
LEDGER_PATH = ROOT / "docs" / "research" / "PRE_IMPULSE_STATE_ATLAS_V1_LEDGER.json"
MD_PATH = ROOT / "docs" / "research" / "PRE_IMPULSE_STATE_ATLAS_V1.md"
PNG_PATH = ROOT / "docs" / "research" / "PRE_IMPULSE_STATE_ATLAS_V1.png"
ARTIFACT_PNG = Path("/opt/cursor/artifacts/PRE_IMPULSE_STATE_ATLAS_V1.png")

GOVERNING = (
    "We do not demand a preselected effect magnitude from the market. We inspect a bounded, "
    "fully logged historical state space, characterize what systematically precedes directional "
    "movement, and then freeze separate successor hypotheses for independent testing. Effect "
    "magnitude and useful structure are outputs of discovery, not admission thresholds."
)

SUCCESSOR_BY_FAMILY = {
    "geometry": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span. This pass uses Bybit only for the 15-minute lead features.",
    "compression": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span. This pass uses Bybit only for the 15-minute lead features.",
    "boundary": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span. Rolling highs and lows only. Not the level-engine event.",
    "acceptance": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span. Not an H02 event replay.",
    "countertrend": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span.",
    "speed": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span. Keep the distance at one 4h realized-volatility unit.",
    "morphology": "Same formula on Bybit linear BTCUSDT 5m over the same pre-2025 span.",
    "clock": "Same state and the same UTC session on Bybit linear BTCUSDT 5m. Do not search a new hour.",
    "cross_venue": "Do not reuse this Binance, Bybit and OKX triple. Freeze a prospective protocol, or an older pair that is not these files. Not 2025/2026.",
    "flow": "No successor. The cell is logged because it sits next to H05 and B2-05, and it is not eligible.",
}


def refuse_if_scored(paths=None) -> None:
    for path in paths or (RESULT_PATH, LEDGER_PATH, MD_PATH, PNG_PATH):
        if path.exists():
            raise SystemExit(K.REFUSAL_RERUN)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _code_digest() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if value is None:
        return None
    return value


def _write(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(_jsonable(payload), indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_venue(path: Path, expected: str) -> tuple[np.ndarray, np.ndarray]:
    found = _sha256(path)
    if found != expected:
        raise SystemExit(f"VENUE_HASH_MISMATCH {path.name}")
    frame = pd.read_csv(path, usecols=["open_ms", "close"])
    open_ms = frame["open_ms"].to_numpy(np.int64)
    close = frame["close"].to_numpy(np.float64)
    if open_ms.size and (np.any(open_ms >= K.SURFACE_END_MS) or np.any(np.diff(open_ms) <= 0)):
        raise SystemExit(f"VENUE_GRID_ILLEGAL {path.name}")
    return open_ms, close


def _clock_specs() -> list[dict]:
    rows = []
    for base in K.CLOCK_BASES:
        parent = K.FEATURE_BY_ID[base]
        for name, lo, hi in K.SESSIONS:
            rows.append({
                "id": f"{base}__{name}",
                "family": "clock",
                "eligible": True,
                "mirror": None,
                "expect": None,
                "high_means": f"{parent['high_means']}, inside UTC session {name} [{lo},{hi})",
                "collision": K.CLOCK_COLLISION,
                "parent": base,
                "hour_lo": lo,
                "hour_hi": hi,
            })
    return rows


def _cell(spec: dict, horizon: str, representation: str, x: np.ndarray, y: np.ndarray,
          hour: np.ndarray, blocks: np.ndarray, year: np.ndarray, when: np.ndarray,
          q10: float, q90: float, dst: np.ndarray | None) -> dict:
    target = y if representation == "SPEARMAN_RAW" else hour_adjust(y, hour)
    rho = spearman(x, target)
    week = weekly_spearman(x, target, blocks)
    years = yearly_table(x, target, year) if representation == "SPEARMAN_RAW" else []
    table = quintile_table(x, y) if representation == "SPEARMAN_RAW" else {"degenerate": True, "bins": None, "delta_p": None, "delta_mean": None}
    state = state_from_sign(table, rho, y) if representation == "SPEARMAN_RAW" else {}
    slices = outcome_slices(x, y, q10, q90) if representation == "SPEARMAN_RAW" else None
    primary = horizon in K.PRIMARY_HORIZONS and representation == "SPEARMAN_RAW"
    score = discovery_score(rho, years, week["n_weeks"]) if primary else None
    dst_split = None
    if dst is not None and representation == "SPEARMAN_RAW":
        dst_split = {
            "summer": {"n": int(dst.sum()), "spearman": spearman(x[dst], y[dst]) if int(dst.sum()) >= 3 else None},
            "standard": {"n": int((~dst).sum()), "spearman": spearman(x[~dst], y[~dst]) if int((~dst).sum()) >= 3 else None},
        }
    return {
        "candidate_id": spec["id"],
        "family": spec["family"],
        "eligible": bool(spec["eligible"]),
        "collision": spec["collision"],
        "high_means": spec["high_means"],
        "formula": FORMULA[spec.get("parent") or spec["id"]],
        "required_inputs": INPUTS[spec.get("parent") or spec["id"]],
        "lookback": LOOKBACK[spec.get("parent") or spec["id"]],
        "target_horizon": horizon,
        "horizon": horizon,
        "representation": representation,
        "n": int(x.shape[0]),
        "n_weeks": week["n_weeks"],
        "spearman": rho,
        "week_mean": week["week_mean"],
        "week_se": week["week_se"],
        "years": years,
        "quintiles": table if representation == "SPEARMAN_RAW" else None,
        "outcome_slices": slices,
        "state": state,
        "score": score,
        "dst": dst_split,
        "mirror_agrees": None,
        "when_median_split": None,
        "exposure_status": "EXPOSED",
        "_arrays_kept": False,
    }


def _attach_mirror(cells: list[dict]) -> None:
    index = {
        (row["candidate_id"], row["horizon"], row["representation"]): row["spearman"]
        for row in cells
    }
    for row in cells:
        if row["representation"] != "SPEARMAN_RAW":
            continue
        spec = K.FEATURE_BY_ID.get(row["candidate_id"])
        if not spec or not spec["mirror"] or spec["expect"] != "opposite":
            continue
        other = index.get((spec["mirror"], row["horizon"], "SPEARMAN_RAW"))
        rho = row["spearman"]
        if rho is None or other is None or rho == 0.0 or other == 0.0:
            row["mirror_agrees"] = False
            continue
        row["mirror_agrees"] = bool(math.copysign(1.0, rho) == -math.copysign(1.0, other))


def _disappeared(raw: dict, adjusted: dict) -> bool:
    rho = raw["spearman"]
    adj = adjusted["spearman"]
    if rho is None or adj is None or not math.isfinite(rho) or not math.isfinite(adj) or rho == 0.0:
        return False
    if math.copysign(1.0, rho) != math.copysign(1.0, adj) and adj != 0.0:
        return True
    if adj == 0.0:
        return True
    return abs(adj) < 0.5 * abs(rho)


def _narrative(result: dict) -> dict:
    top = result["top10"]
    lead = top[0]["candidate_id"] if top else "none"
    return {
        "states": (
            f"The ranked pass kept every eligible primary cell. The highest discovery score is `{lead}`. "
            "Scores order the logged cells. They do not admit a state into a product claim."
        ),
        "nulls": _null_text(result),
        "clock": _family_text(result, "clock"),
        "boundary": _family_text(result, "boundary") + " " + _family_text(result, "acceptance"),
        "flow_oi": (
            "Open interest was not opened. MARKET-01 and MARKET-02 already closed that family on this surface. "
            + _family_text(result, "flow")
            + " Flow cells stay out of the shortlist."
        ),
        "cross_venue": _family_text(result, "cross_venue"),
        "misleading": _misleading_text(result),
        "unknown": (
            "This pass does not say whether a shortlisted state survives another venue, an older tape, or a prospective window. "
            "It does not separate a causal path from a coincident one. It does not turn a historical frequency into a current probability."
        ),
    }


def _family_text(result: dict, family: str) -> str:
    winner = result["category"].get(family)
    if not winner:
        return f"No finite {family} cell."
    return (
        f"Strongest {family} cell `{winner['candidate_id']}` at `{winner['horizon']}`, "
        f"Spearman {_fmt(winner['spearman'])}, score {_fmt(winner['score'])}, collision `{winner['collision']}`."
    )


def _fmt(value) -> str:
    if value is None:
        return "NA"
    return f"{float(value):.6g}"


def _null_text(result: dict) -> str:
    parts = []
    for row in result["family_max_abs"]:
        parts.append(f"{row['family']} max abs Spearman {_fmt(row['abs_spearman'])} at `{row['candidate_id']}` `{row['horizon']}`")
    smallest = ", ".join(
        f"`{row['candidate_id']}` `{row['horizon']}` {_fmt(row['spearman'])}" for row in result["smallest_abs"][:8]
    )
    return "Family peaks: " + "; ".join(parts) + ". Smallest absolute associations: " + smallest + "."


def _misleading_text(result: dict) -> str:
    clock = result["shrunk_after_clock"]
    vol = result["shrunk_after_rv"]
    if not clock and not vol:
        return "No primary cell in the top decile of absolute Spearman lost its sign or half its magnitude after the UTC-hour adjustment, and none of the top 10 did so after the 4h realized-volatility partial."
    bits = []
    if clock:
        bits.append("UTC-hour adjustment: " + ", ".join(f"`{r['candidate_id']}` `{r['horizon']}`" for r in clock[:12]))
    if vol:
        bits.append("4h RV partial: " + ", ".join(f"`{r['candidate_id']}` `{r['horizon']}`" for r in vol))
    return " ".join(bits)


def run() -> dict:
    refuse_if_scored()
    if K.DESIGN_SHA256 == "PENDING_DESIGN_HASH":
        raise SystemExit("DESIGN_HASH_UNSET")
    if _sha256(DESIGN_PATH) != K.DESIGN_SHA256:
        raise SystemExit("DESIGN_HASH_MISMATCH")
    import matplotlib
    matplotlib.use("Agg")

    from scripts.research.level_touch_degradation_v1.data import load_discovery_bars

    bars = load_discovery_bars()
    if int(bars.t0) != K.DATA_START_MS or int(bars.t0) % K.ANCHOR_MS != 0:
        raise SystemExit("GRID_ORIGIN_ILLEGAL")
    if int(bars.times[-1]) >= K.SURFACE_END_MS:
        raise SystemExit("SURFACE_CROSSES_2025")
    n = bars.n
    index = np.arange(n, dtype=np.int64)
    close_ms = bars.t0 + (index + 1) * K.BAR_MS
    anchor = (index >= K.MIN_INDEX) & ((index % 3) == 2) & (close_ms < K.SURFACE_END_MS)
    # The 24h terminal bar must still open before 2025-01-01. Shorter horizons keep later anchors.
    anchor_idx = index[anchor]
    by_open, by_close = _load_venue(ROOT / K.BYBIT_PRICE, K.BYBIT_SHA256)
    ok_open, ok_close = _load_venue(ROOT / K.OKX_PRICE, K.OKX_SHA256)
    bybit = align_closes(bars.times, by_open, by_close)
    okx = align_closes(bars.times, ok_open, ok_close)
    print(f"computing features on {n} bars", flush=True)
    feat = compute_features(bars.open, bars.high, bars.low, bars.close, bars.quote, bars.taker_buy_quote, bybit, okx)
    # Open interest is present on the bar object and is not an input.
    del bybit, okx, by_open, by_close, ok_open, ok_close

    close = np.asarray(bars.close, dtype=np.float64)
    returns = {}
    horizon_n = {}
    for name, bars_ahead, _primary in K.HORIZONS:
        fut = anchor_idx + bars_ahead
        fut_open = bars.t0 + fut * K.BAR_MS
        legal = fut_open < K.SURFACE_END_MS
        dest = np.full(anchor_idx.shape[0], np.nan)
        ok = legal & np.isfinite(close[anchor_idx]) & np.isfinite(close[np.clip(fut, 0, n - 1)])
        ok &= fut < n
        with np.errstate(divide="ignore", invalid="ignore"):
            dest[ok] = np.log(close[fut[ok]] / close[anchor_idx[ok]])
        returns[name] = dest
        horizon_n[name] = int(np.isfinite(dest).sum())
    cuts = {}
    for name, values in returns.items():
        finite = values[np.isfinite(values)]
        q10, q90 = np.quantile(finite, [0.1, 0.9])
        cuts[name] = (float(q10), float(q90))

    on = {row["id"]: feat[row["id"]][anchor_idx] for row in K.FEATURES}
    del feat
    ts = pd.to_datetime(close_ms[anchor_idx], unit="ms", utc=True)
    kyiv = ts.tz_convert("Europe/Kyiv")
    utc_hour = ts.hour.to_numpy(dtype=np.int64)
    kyiv_hour = kyiv.hour.to_numpy(dtype=np.int64)
    iso = ts.isocalendar()
    blocks = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
    year = ts.year.to_numpy(dtype=np.int64)
    when = close_ms[anchor_idx].astype(np.float64)
    offset = ((kyiv_hour - utc_hour + 12) % 24) - 12
    summer = offset == 3

    specs = list(K.FEATURES) + _clock_specs()
    cells = []
    print(f"scoring {len(specs)} series", flush=True)
    for spec in specs:
        parent = spec.get("parent") or spec["id"]
        x_full = on[parent]
        for name, _bars, _primary in K.HORIZONS:
            y_full = returns[name]
            mask = np.isfinite(x_full) & np.isfinite(y_full)
            if "hour_lo" in spec:
                mask &= (utc_hour >= spec["hour_lo"]) & (utc_hour < spec["hour_hi"])
            x = x_full[mask]
            y = y_full[mask]
            hour = utc_hour[mask]
            q10, q90 = cuts[name]
            raw = _cell(spec, name, "SPEARMAN_RAW", x, y, hour, blocks[mask], year[mask], when[mask], q10, q90,
                        summer[mask] if spec["family"] == "clock" else None)
            adj = _cell(spec, name, "SPEARMAN_HOUR_ADJUSTED", x, y, hour, blocks[mask], year[mask], when[mask], q10, q90, None)
            cells.extend((raw, adj))
    _attach_mirror(cells)

    raw_primary = [
        row for row in cells
        if row["representation"] == "SPEARMAN_RAW" and row["horizon"] in K.PRIMARY_HORIZONS and row["eligible"]
    ]
    ranked = sorted(raw_primary, key=lambda row: (-(row["score"] or 0.0), -abs(row["spearman"] or 0.0), row["candidate_id"], row["horizon"]))
    top10 = ranked[:10]
    print("bootstrap top 10", flush=True)
    shrunk_rv = []
    for row in top10:
        spec = next(s for s in specs if s["id"] == row["candidate_id"])
        parent = spec.get("parent") or spec["id"]
        y_full = returns[row["horizon"]]
        mask = np.isfinite(on[parent]) & np.isfinite(y_full)
        if "hour_lo" in spec:
            mask &= (utc_hour >= spec["hour_lo"]) & (utc_hour < spec["hour_hi"])
        x, y = on[parent][mask], y_full[mask]
        side_top = bool(row["spearman"] and row["spearman"] > 0.0)
        row["bootstrap"] = bootstrap_cell(x, y, blocks[mask], side_top=side_top)
        row["half"] = half_split(x, y, when[mask])
        row["leave_one_year_out"] = leave_one_year_out(x, y, year[mask])
        partial = partial_given_rv(x, y, on["rv_4h"][mask])
        row["partial_rv_4h"] = partial
        rho = row["spearman"]
        pr = partial["rho"]
        if rho not in (None, 0.0) and pr is not None and math.isfinite(pr):
            if pr == 0.0 or math.copysign(1.0, pr) != math.copysign(1.0, rho) or abs(pr) < 0.5 * abs(rho):
                shrunk_rv.append({"candidate_id": row["candidate_id"], "horizon": row["horizon"], "spearman": rho, "partial": pr})
        elif partial["degenerate"]:
            row["partial_note"] = "degenerate"

    abs_values = [abs(row["spearman"]) for row in raw_primary if row["spearman"] is not None]
    threshold = float(np.quantile(abs_values, 0.9)) if abs_values else None
    by_key = {(row["candidate_id"], row["horizon"], row["representation"]): row for row in cells}
    shrunk_clock = []
    if threshold is not None:
        for row in raw_primary:
            if row["spearman"] is None or abs(row["spearman"]) < threshold:
                continue
            other = by_key[(row["candidate_id"], row["horizon"], "SPEARMAN_HOUR_ADJUSTED")]
            if _disappeared(row, other):
                shrunk_clock.append({
                    "candidate_id": row["candidate_id"], "horizon": row["horizon"],
                    "spearman": row["spearman"], "hour_adjusted": other["spearman"],
                })

    def best(pred):
        pool = [row for row in raw_primary if pred(row)]
        if not pool:
            return None
        return sorted(pool, key=lambda row: (-(row["score"] or 0.0), -abs(row["spearman"] or 0.0), row["candidate_id"]))[0]

    category = {
        "up": best(lambda row: (row["spearman"] or 0.0) > 0.0),
        "down": best(lambda row: (row["spearman"] or 0.0) < 0.0),
        "boundary": best(lambda row: row["family"] == "boundary"),
        "compression": best(lambda row: row["family"] == "compression"),
        "clock": best(lambda row: row["family"] == "clock"),
        "cross_venue": best(lambda row: row["family"] == "cross_venue"),
        "acceptance": best(lambda row: row["family"] == "acceptance"),
    }
    flow_pool = [
        row for row in cells
        if row["family"] == "flow" and row["representation"] == "SPEARMAN_RAW" and row["horizon"] in K.PRIMARY_HORIZONS
    ]
    for row in flow_pool:
        if row["score"] is None:
            row["score"] = discovery_score(row["spearman"], row["years"], row["n_weeks"])
    category["flow"] = sorted(flow_pool, key=lambda row: (-(row["score"] or 0.0), -abs(row["spearman"] or 0.0)))[0] if flow_pool else None

    family_max = []
    for family in sorted({row["family"] for row in raw_primary}):
        pool = [row for row in raw_primary if row["family"] == family and row["spearman"] is not None]
        if not pool:
            continue
        winner = max(pool, key=lambda row: abs(row["spearman"]))
        family_max.append({
            "family": family, "candidate_id": winner["candidate_id"], "horizon": winner["horizon"],
            "abs_spearman": abs(winner["spearman"]), "spearman": winner["spearman"],
        })
    smallest = sorted(
        [row for row in raw_primary if row["spearman"] is not None],
        key=lambda row: abs(row["spearman"]),
    )[:10]

    successors = []
    seen = set()
    for row in ranked:
        if row["candidate_id"] in seen:
            continue
        seen.add(row["candidate_id"])
        successors.append({
            "candidate_id": row["candidate_id"],
            "horizon": row["horizon"],
            "score": row["score"],
            "family": row["family"],
            "successor": SUCCESSOR_BY_FAMILY[row["family"]],
        })
        if len(successors) == 3:
            break

    clock_marginal = {}
    for name in returns:
        utc_rows = []
        kyiv_rows = []
        y = returns[name]
        for hour_value in range(24):
            mu = (utc_hour == hour_value) & np.isfinite(y)
            mk = (kyiv_hour == hour_value) & np.isfinite(y)
            utc_rows.append({"hour": hour_value, "n": int(mu.sum()), "mean_return": float(y[mu].mean()) if mu.any() else None, "p_up": float(np.mean(y[mu] > 0.0)) if mu.any() else None})
            kyiv_rows.append({"hour": hour_value, "n": int(mk.sum()), "mean_return": float(y[mk].mean()) if mk.any() else None, "p_up": float(np.mean(y[mk] > 0.0)) if mk.any() else None})
        clock_marginal[name] = {"utc": utc_rows, "kyiv": kyiv_rows, "cuts": {"q10": cuts[name][0], "q90": cuts[name][1]}}

    finite_anchors = int(np.isfinite(returns["8h"]).sum())
    result = {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "claim_ceiling": K.CLAIM_CEILING,
        "governing_principle": GOVERNING,
        "read_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "design_sha256": K.DESIGN_SHA256,
        "evaluator_digest": _code_digest(),
        "surface": K.SURFACE,
        "venues": {
            "binance": K.SURFACE,
            "bybit_sha256": K.BYBIT_SHA256,
            "okx_sha256": K.OKX_SHA256,
        },
        "time_range": [_iso(int(close_ms[anchor_idx[0]])), _iso(int(close_ms[anchor_idx[-1]]) + K.BAR_MS)],
        "first_t": _iso(int(close_ms[anchor_idx[0]])),
        "last_t": _iso(int(close_ms[anchor_idx[-1]])),
        "anchor_n": int(anchor_idx.shape[0]),
        "anchor_weeks": int(np.unique(blocks).size),
        "anchors_with_finite_8h": finite_anchors,
        "horizon_n": horizon_n,
        "horizons": [name for name, _b, _p in K.HORIZONS],
        "primary_horizons": list(K.PRIMARY_HORIZONS),
        "feature_count": len(K.FEATURES) + len(_clock_specs()),
        "base_feature_count": len(K.FEATURES),
        "cell_count": len(cells),
        "objects_2025_2026_used": K.OBJECTS_2025_2026_USED,
        "oi_opened": K.OI_OPENED,
        "level_engine_used": K.LEVEL_ENGINE_USED,
        "product_code_changed": K.PRODUCT_CODE_CHANGED,
        "product_integration_candidate": False,
        "outcome_cuts": {name: {"q10": pair[0], "q90": pair[1]} for name, pair in cuts.items()},
        "cells": cells,
        "top10": top10,
        "category": {key: value for key, value in category.items()},
        "family_max_abs": family_max,
        "smallest_abs": [
            {"candidate_id": row["candidate_id"], "horizon": row["horizon"], "spearman": row["spearman"], "n": row["n"]}
            for row in smallest
        ],
        "shrunk_after_clock": shrunk_clock,
        "shrunk_after_rv": shrunk_rv,
        "clock_hour_threshold": threshold,
        "successors": successors,
        "clock_marginal": clock_marginal,
        "up_associated": [row for row in ranked if (row["spearman"] or 0.0) > 0.0][:8],
        "down_associated": [row for row in ranked if (row["spearman"] or 0.0) < 0.0][:8],
        "ledger_path": str(LEDGER_PATH.relative_to(ROOT)),
        "bootstrap_seed": K.BOOT_SEED,
        "bootstrap_draws": K.BOOT_DRAWS,
    }
    result["narrative"] = _narrative(result)
    ledger = {
        "unit": K.UNIT,
        "design_sha256": K.DESIGN_SHA256,
        "exposure_status": "EXPOSED",
        "cell_count": len(cells),
        "cells": [
            {k: v for k, v in row.items() if k not in {"bootstrap", "half", "leave_one_year_out", "partial_rv_4h"}}
            for row in cells
        ],
    }
    _write(LEDGER_PATH, ledger)
    result["ledger_sha256"] = _sha256(LEDGER_PATH)
    _write(RESULT_PATH, result)
    write_markdown(result, MD_PATH)
    write_figure(result, PNG_PATH)
    ARTIFACT_PNG.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PNG.write_bytes(PNG_PATH.read_bytes())
    print(f"LEDGER {result['ledger_sha256']} cells {len(cells)} top {top10[0]['candidate_id'] if top10 else 'none'}", flush=True)
    return result


if __name__ == "__main__":
    run()
