"""Timestamp-only tape census for WEEKDAY_WEEKEND_BASELINE_CALIBRATION_DESIGN_V1.

Reads bucket timestamps and per-venue OHLC PRESENCE booleans from beta_state_tape.
Never selects a market value. Offline tooling; no runtime module imports this.
Spec: docs/WEEKDAY_WEEKEND_CALIBRATION_CENSUS_SPEC_V1.md.

Usage: BETA_DSN=postgresql://... python -m scripts.product.weekday_weekend_census
       --calculation-version <16 hex> --schema-version <int> [--venues binance,bybit,okx]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs/WEEKDAY_WEEKEND_CALIBRATION_CENSUS_RESULT.json"
BUCKET = dt.timedelta(minutes=5)
LOOKBACK = dt.timedelta(days=30)
MIN_SAME_TYPE_DAYS = 8
MIN_VENUES = 2
OHLC = ("kline_open", "kline_high", "kline_low", "kline_close")
REASONS = ("MISSING_1H_BUCKET", "VENUE_COVERAGE_BELOW_MIN", "REFERENCE_IMMATURE", "INSUFFICIENT_SAME_TYPE_DATES")


def wtype(d: dt.date) -> str:
    return "WEEKEND" if d.weekday() >= 5 else "WEEKDAY"


def presence_sql(venues: list[str]) -> str:
    cols = []
    for v in venues:
        conds = " AND ".join(
            f"(metrics ? 'x:{v}:{f}' AND jsonb_typeof(metrics -> 'x:{v}:{f}') <> 'null')" for f in OHLC)
        cols.append(f"({conds}) AS v_{v}")
    return (
        "SELECT DISTINCT ON (bucket_ts) bucket_ts, " + ", ".join(cols) + " "
        "FROM beta_state_tape WHERE symbol='BTCUSDT' AND market_type='perp' AND timeframe='5m' "
        "AND calculation_version=$1 AND state_schema_version=$2 AND materialized "
        "ORDER BY bucket_ts, tape_id DESC"
    )


def census(rows: list[tuple], venues: list[str]) -> dict:
    """rows: (bucket_ts, {venue: present_bool}). Pure function; no values."""
    present = {b.astimezone(dt.timezone.utc).replace(tzinfo=None): pv for b, pv in rows}
    if not present:
        return {"CLOCK_HOURS": 0}
    first = min(present)
    last = max(present)
    first_hour = (first + dt.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    last_hour = last.replace(minute=0, second=0, microsecond=0)
    per = {s: {"CLOCK_HOURS": 0, "USABLE_C0": 0, "USABLE_C1": 0, "COMMON_SUPPORT": 0,
               "REASONS_C0": Counter(), "REASONS_C1": Counter(), "DATES": set(), "WEEKS": set(), "MONTHS": set(),
               "MISSING_BUCKETS": 0, "EXPECTED_BUCKETS": 0} for s in ("WEEKDAY", "WEEKEND", "AGGREGATE")}
    start_candidate = None
    both_ok = {"WEEKDAY": None, "WEEKEND": None}
    H = first_hour
    # sorted bucket list for span / same-type date counting
    keys = sorted(present)
    import bisect
    while H <= last_hour:
        ws = H - dt.timedelta(hours=1)
        s = wtype(ws.date())
        buckets = [ws + i * BUCKET for i in range(12)]
        reason_c0 = reason_c1 = None
        if any(b not in present for b in buckets):
            reason_c0 = reason_c1 = "MISSING_1H_BUCKET"
        else:
            ok_venues = sum(1 for v in venues if all(present[b].get(v) for b in buckets))
            if ok_venues < MIN_VENUES:
                reason_c0 = reason_c1 = "VENUE_COVERAGE_BELOW_MIN"
            else:
                lo = bisect.bisect_left(keys, H - LOOKBACK)
                hi = bisect.bisect_left(keys, H)
                window = keys[lo:hi]
                if not window or (window[-1] - window[0]) < LOOKBACK - BUCKET:
                    reason_c0 = reason_c1 = "REFERENCE_IMMATURE"
                else:
                    same = {b.date() for b in window if wtype(b.date()) == s}
                    if len(same) < MIN_SAME_TYPE_DAYS:
                        reason_c1 = "INSUFFICIENT_SAME_TYPE_DATES"
        for st in (s, "AGGREGATE"):
            p = per[st]
            p["CLOCK_HOURS"] += 1
            p["EXPECTED_BUCKETS"] += 12
            p["MISSING_BUCKETS"] += sum(1 for b in buckets if b not in present)
            if reason_c0 is None:
                p["USABLE_C0"] += 1
            else:
                p["REASONS_C0"][reason_c0] += 1
            if reason_c1 is None:
                p["USABLE_C1"] += 1
            else:
                p["REASONS_C1"][reason_c1] += 1
            if reason_c0 is None and reason_c1 is None:
                p["COMMON_SUPPORT"] += 1
                p["DATES"].add(ws.date().isoformat())
                y, w, _ = ws.date().isocalendar()
                p["WEEKS"].add(f"{y}-W{w:02d}")
                p["MONTHS"].add(ws.strftime("%Y-%m"))
        if reason_c0 is None and reason_c1 is None and both_ok[s] is None:
            both_ok[s] = H.isoformat()
        if start_candidate is None and all(both_ok.values()):
            start_candidate = max(both_ok.values())
        H += dt.timedelta(hours=1)
    out = {}
    for st, p in per.items():
        out[st] = {
            "CLOCK_HOURS": p["CLOCK_HOURS"], "USABLE_C0": p["USABLE_C0"], "USABLE_C1": p["USABLE_C1"],
            "COMMON_SUPPORT": p["COMMON_SUPPORT"],
            "A_C0": p["USABLE_C0"] / p["CLOCK_HOURS"] if p["CLOCK_HOURS"] else None,
            "A_C1": p["USABLE_C1"] / p["CLOCK_HOURS"] if p["CLOCK_HOURS"] else None,
            "CS": p["COMMON_SUPPORT"] / p["CLOCK_HOURS"] if p["CLOCK_HOURS"] else None,
            "REASONS_C0": dict(p["REASONS_C0"]), "REASONS_C1": dict(p["REASONS_C1"]),
            "MISSING_BUCKET_SHARE": p["MISSING_BUCKETS"] / p["EXPECTED_BUCKETS"] if p["EXPECTED_BUCKETS"] else None,
            "DISTINCT_DATES": len(p["DATES"]), "DISTINCT_WEEKS": len(p["WEEKS"]), "DISTINCT_MONTHS": len(p["MONTHS"]),
        }
    return {"CENSUS_PERIOD": [first.isoformat(), last.isoformat()], "PROSPECTIVE_START_CANDIDATE": start_candidate,
            "FIRST_BOTH_USABLE_BY_STRATUM": both_ok, "STRATA": out, "VALUES_READ": False}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--calculation-version", required=True)
    ap.add_argument("--schema-version", type=int, required=True)
    ap.add_argument("--venues", default="binance,bybit,okx")
    args = ap.parse_args()
    venues = [v.strip() for v in args.venues.split(",") if v.strip()]
    import asyncpg  # offline tooling dependency
    conn = await asyncpg.connect(os.environ["BETA_DSN"])
    try:
        rows = await conn.fetch(presence_sql(venues), args.calculation_version, args.schema_version)
    finally:
        await conn.close()
    parsed = [(r["bucket_ts"], {v: bool(r[f"v_{v}"]) for v in venues}) for r in rows]
    result = census(parsed, venues)
    result["SPEC"] = "docs/WEEKDAY_WEEKEND_CALIBRATION_CENSUS_SPEC_V1.md"
    OUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())
