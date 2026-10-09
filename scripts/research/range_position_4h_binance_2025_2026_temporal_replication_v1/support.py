"""Anchor and object census. No future-return association."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import constants as K
from .sample import build_grid, classify, load_rows, rows_to_arrays, sha256

ROOT = Path(__file__).resolve().parents[3]
SUPPORT_JSON = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1_SUPPORT.json"
SUPPORT_MD = ROOT / "docs" / "research" / "RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1_SUPPORT.md"


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


def _runs(opens: np.ndarray) -> list[dict]:
    if opens.size == 0:
        return []
    cuts = np.flatnonzero(np.diff(opens) != K.BAR_MS)
    starts = np.r_[0, cuts + 1]
    ends = np.r_[cuts, opens.size - 1]
    return [
        {"first": _iso(int(opens[a])), "last": _iso(int(opens[b])), "count": int(b - a + 1)}
        for a, b in zip(starts, ends)
    ]


def census() -> dict:
    manifest_path = ROOT / K.OBJECTS_MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("relation_computed") is not False:
        raise SystemExit("OBJECTS_ALREADY_SCORED")
    if sha256(ROOT / K.SERIES) != manifest["canonical_sha256"]:
        raise SystemExit("SERIES_MANIFEST_MISMATCH")
    rows = load_rows(ROOT / K.SERIES)
    opens, highs, lows, closes = rows_to_arrays(rows)
    grid = build_grid(opens, highs, lows, closes)
    masks = classify(grid)
    phase_n = int(masks["phase"].sum())
    eligible_n = int(masks["eligible"].sum())
    excluded_n = int(masks["excluded"].sum())
    lookback_n = int(masks["lookback"].sum())
    future_n = int(masks["future"].sum())
    if phase_n != eligible_n + excluded_n + lookback_n + future_n:
        raise SystemExit("PARTITION_MISMATCH")
    missing = grid["grid_open"][masks["hole"]]
    verified = [row for row in manifest["objects"] if row["status"] == "OK"]
    missing_objects = [row for row in manifest["objects"] if row["status"] != "OK"]
    idx = np.flatnonzero(masks["eligible"])
    if idx.size:
        close_ms = grid["close_at_decision"][idx]
        ts = pd.to_datetime(close_ms, unit="ms", utc=True)
        iso = ts.isocalendar()
        week_id = iso.year.to_numpy(dtype=np.int64) * 100 + iso.week.to_numpy(dtype=np.int64)
        years = ts.year.to_numpy(dtype=np.int64)
        per_year = {str(int(year)): int(np.sum(years == year)) for year in sorted(set(int(v) for v in years))}
        first_t = _iso(int(close_ms[0]))
        last_t = _iso(int(close_ms[-1]))
        week_n = int(np.unique(week_id).size)
    else:
        per_year = {}
        first_t = None
        last_t = None
        week_n = 0
    unexpected_holes = int(np.sum(masks["hole"] & ~masks["in_object_hole"]))
    object_hole_slots = int(np.sum(masks["in_object_hole"]))
    object_hole_missing = int(np.sum(masks["hole"] & masks["in_object_hole"]))
    adequate = bool(
        eligible_n >= K.MIN_ELIGIBLE
        and week_n >= K.MIN_WEEKS
        and unexpected_holes == 0
        and object_hole_slots > 0
        and object_hole_missing == object_hole_slots
        and int(np.sum(masks["hole"] & masks["in_e1"])) == int(np.sum(masks["in_e1"]))
    )
    return {
        "unit": K.UNIT,
        "evidence_class": K.EVIDENCE_CLASS,
        "relation_computed": False,
        "spearman_computed": False,
        "quintiles_computed": False,
        "future_return_mean_computed": False,
        "series_sha256": manifest["canonical_sha256"],
        "requested_objects": [row["key"] for row in manifest["objects"]],
        "verified_objects": [row["key"] for row in verified],
        "missing_objects": [row["key"] for row in missing_objects],
        "rejected_not_requested": manifest["rejected_not_requested"],
        "first_usable_bar": _iso(int(grid["grid_open"][0])),
        "last_usable_bar": _iso(int(grid["grid_open"][np.isfinite(grid["close"])][-1])),
        "occupied_bars": int(grid["occupied"]),
        "grid_slots": int(grid["slots"]),
        "holes": int(grid["holes"]),
        "unexpected_holes": unexpected_holes,
        "missing_runs": _runs(missing),
        "e1_interval": ["2026-08-16T00:00:00Z", "2026-08-25T17:20:00Z"],
        "e1_interval_end_exclusive": True,
        "object_hole_interval": ["2026-08-16T00:00:00Z", "2026-08-26T00:00:00Z"],
        "phase_anchors": phase_n,
        "eligible": eligible_n,
        "lost_to_object_hole": excluded_n,
        "lost_to_e1_timestamp": int(masks["e1_touch"].sum()),
        "lost_to_lookback": lookback_n,
        "lost_to_future": future_n,
        "iso_weeks": week_n,
        "years": sorted(per_year),
        "per_year_n": per_year,
        "first_eligible_t": first_t,
        "last_eligible_t": last_t,
        "adequate": adequate,
        "adequacy_rule": "eligible>=1000 and iso_weeks>=20 and every hole is inside the rejected August object span",
    }


def write_markdown(payload: dict, path: Path) -> None:
    lines = [
        "# RANGE_POSITION_4H_BINANCE_2025_2026_TEMPORAL_REPLICATION_V1 — support",
        "",
        "Census only. No future-return association, rank correlation, quintile, or P(UP) is in this file.",
        "",
        f"**Relation computed:** `{str(payload['relation_computed']).lower()}`.",
        f"**Adequate for estimation:** `{str(payload['adequate']).lower()}`.",
        f"**Series SHA256:** `{payload['series_sha256']}`.",
        "",
        f"Verified objects `{len(payload['verified_objects'])}`. Missing objects `{payload['missing_objects']}`.",
        f"Not requested: `{payload['rejected_not_requested']}`.",
        f"Usable bars `{payload['first_usable_bar']}` through `{payload['last_usable_bar']}`.",
        f"Grid slots `{payload['grid_slots']}`, occupied `{payload['occupied_bars']}`, holes `{payload['holes']}`.",
        f"E1 interval `{payload['e1_interval'][0]}` inclusive to `{payload['e1_interval'][1]}` exclusive.",
        f"Object hole `{payload['object_hole_interval'][0]}` inclusive to `{payload['object_hole_interval'][1]}` exclusive.",
        "",
        f"Phase anchors `{payload['phase_anchors']}`. Eligible `{payload['eligible']}`. "
        f"Lost to the object hole `{payload['lost_to_object_hole']}`. "
        f"Of those, timestamp-inside-E1 `{payload['lost_to_e1_timestamp']}`. "
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
    lines.extend(["", "Missing runs:", ""])
    for run in payload["missing_runs"]:
        lines.append(f"- `{run['first']}` through `{run['last']}`, count `{run['count']}`.")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> dict:
    payload = census()
    SUPPORT_JSON.write_text(json.dumps(_jsonable(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(payload, SUPPORT_MD)
    print(
        f"eligible {payload['eligible']} weeks {payload['iso_weeks']} adequate {payload['adequate']}",
        flush=True,
    )
    return payload


if __name__ == "__main__":
    main()
