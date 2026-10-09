"""Anchor census. Counts only. No rank correlation and no stored return."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import constants as K
from .sample import build_grid, classify, load_rows, rows_to_arrays

ROOT = Path(__file__).resolve().parents[3]
SUPPORT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_SUPPORT.json"
SUPPORT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1_SUPPORT.md"


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def _gap_identity(opened: np.ndarray, hole: np.ndarray) -> dict:
    missing = opened[hole]
    expected = np.arange(K.GAP_START_MS, K.GAP_END_MS + K.BAR_MS, K.BAR_MS, dtype=np.int64)
    inside = hole & (opened >= K.GAP_START_MS) & (opened <= K.GAP_END_MS)
    matches = bool(missing.size == expected.size and np.array_equal(missing, expected))
    return {
        "measured_gap_missing": int(missing.size),
        "measured_gap_first_open": _iso(int(missing[0])) if missing.size else None,
        "measured_gap_last_open": _iso(int(missing[-1])) if missing.size else None,
        "declared_gap_matches_file": matches,
        "other_holes": int(np.sum(hole) - np.sum(inside)),
    }


def census(rows: list[dict] | None = None) -> dict:
    if rows is None:
        rows = load_rows(ROOT / K.SERIES)
    opens, highs, lows, closes = rows_to_arrays(rows)
    grid = build_grid(opens, highs, lows, closes)
    masks = classify(grid)
    phase_n = int(masks["phase"].sum())
    eligible_n = int(masks["eligible"].sum())
    gap_n = int(masks["gap"].sum())
    lookback_n = int(masks["lookback"].sum())
    future_n = int(masks["future"].sum())
    if phase_n != eligible_n + gap_n + lookback_n + future_n:
        raise SystemExit("PARTITION_MISMATCH")
    identity = _gap_identity(grid["grid_open"], masks["hole"])
    idx = np.flatnonzero(masks["eligible"])
    if idx.size:
        close_ms = grid["close_at_decision"][idx]
        ts = pd.to_datetime(close_ms, unit="ms", utc=True)
        iso = ts.isocalendar()
        week_id = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
        years = ts.year.to_numpy(dtype=np.int64)
        per_year = {str(int(year)): int(np.sum(years == year)) for year in sorted(set(years.tolist()))}
        first_t = _iso(int(close_ms[0]))
        last_t = _iso(int(close_ms[-1]))
        week_n = int(np.unique(week_id).size)
        year_list = sorted(per_year)
    else:
        per_year = {}
        first_t = None
        last_t = None
        week_n = 0
        year_list = []
    adequate = bool(
        eligible_n >= K.MIN_ELIGIBLE
        and week_n >= K.MIN_WEEKS
        and identity["declared_gap_matches_file"]
        and identity["other_holes"] == 0
    )
    return {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "relation_computed": False,
        "series": K.SERIES,
        "series_sha256": K.SERIES_SHA256,
        "price_transform": "last_trade_price_space_no_inverse",
        "occupied_bars": int(grid["occupied"]),
        "grid_slots": int(grid["slots"]),
        "holes": int(grid["holes"]),
        "first_open": _iso(int(grid["grid_open"][0])),
        "last_open": _iso(int(grid["grid_open"][-1])),
        "phase_anchors": phase_n,
        "eligible": eligible_n,
        "lost_to_gap": gap_n,
        "lost_to_lookback": lookback_n,
        "lost_to_future": future_n,
        "iso_weeks": week_n,
        "years": year_list,
        "per_year_n": per_year,
        "first_eligible_t": first_t,
        "last_eligible_t": last_t,
        "adequate": adequate,
        "adequacy_rule": "eligible>=1000 and iso_weeks>=20 and the only holes are the declared 288-bar run",
        **identity,
    }


def write_markdown(payload: dict, path: Path) -> None:
    lines = [
        "# RANGE_POSITION_4H_BITMEX_TEMPORAL_REPLICATION_V1 — support",
        "",
        "Census only. No return, rank correlation, or outcome bin is in this file.",
        "",
        f"**Relation computed:** `{str(payload['relation_computed']).lower()}`.",
        f"**Adequate for estimation:** `{str(payload['adequate']).lower()}`.",
        f"**Series SHA256:** `{payload['series_sha256']}`.",
        "",
        f"Opens `{payload['first_open']}` through `{payload['last_open']}`.",
        f"Grid slots `{payload['grid_slots']}`, occupied `{payload['occupied_bars']}`, holes `{payload['holes']}`.",
        f"Declared gap matches the file: `{str(payload['declared_gap_matches_file']).lower()}`. "
        f"Missing opens `{payload['measured_gap_missing']}`, "
        f"`{payload['measured_gap_first_open']}` through `{payload['measured_gap_last_open']}`. "
        f"Other holes `{payload['other_holes']}`.",
        "",
        f"Phase anchors `{payload['phase_anchors']}`. Eligible `{payload['eligible']}`. "
        f"Lost to the 2016 gap `{payload['lost_to_gap']}`. "
        f"Lost to incomplete lookback `{payload['lost_to_lookback']}`. "
        f"Lost to incomplete future `{payload['lost_to_future']}`.",
        f"ISO weeks `{payload['iso_weeks']}`. Years `{payload['years']}`.",
        f"First eligible T `{payload['first_eligible_t']}`. Last eligible T `{payload['last_eligible_t']}`.",
        "",
        "| year | N |",
        "|---|---|",
    ]
    for year, count in payload["per_year_n"].items():
        lines.append(f"| {year} | {count} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> dict:
    payload = census()
    if payload["relation_computed"]:
        raise SystemExit("SUPPORT_COMPUTED_A_RELATION")
    SUPPORT_JSON.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, SUPPORT_MD)
    print(
        f"eligible {payload['eligible']} weeks {payload['iso_weeks']} adequate {payload['adequate']}",
        flush=True,
    )
    return payload


if __name__ == "__main__":
    main()
