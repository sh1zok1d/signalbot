#!/usr/bin/env python3
"""Outcome-free chronological split balance audit for E1-RUN-001.

Reads only the frozen Stage-5 candidate inventory JSON and inspects candidate
counts before/after candidate UTC-midnight split points. It never reads market
outcomes, raw future klines, or Stage-6 lifecycle state.

Pre-outcome split-selection rule (frozen in this script before execution):
select the LATEST UTC-midnight split such that the holdout contains:

- at least 25% of ALL raw qualifications; and
- at least 20% of EACH Stage-5 family's total raw qualifications.

The rule is deliberately count-only. It exists because a globally balanced
70/30 split can still leave one family with zero OOS observations.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
MIN_HOLDOUT_TOTAL_SHARE = 0.25
MIN_HOLDOUT_FAMILY_SHARE = 0.20
EXPECTED_FAMILIES = (
    "TREND_PULLBACK",
    "COMPRESSION_BREAKOUT",
    "CONFIRMED_BREAKOUT",
)


def _parse_utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None or dt.utcoffset() is None or dt.utcoffset() != timedelta(0):
        raise argparse.ArgumentTypeError("datetime must be timezone-aware UTC")
    if dt.hour or dt.minute or dt.second or dt.microsecond:
        raise argparse.ArgumentTypeError("split bounds must be UTC midnight")
    return dt.astimezone(UTC)


def _iter_midnights(start: datetime, end: datetime):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _counts(rows):
    by_family = Counter(row["family"] for row in rows)
    return {
        "total": len(rows),
        "by_family": {family: by_family.get(family, 0) for family in EXPECTED_FAMILIES},
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Audit E1 split balance from candidate counts only")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--start-split", required=True, type=_parse_utc)
    p.add_argument("--end-split", required=True, type=_parse_utc)
    args = p.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("outcomes_included") is not False:
        raise SystemExit("refusing input unless outcomes_included is exactly false")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise SystemExit("input candidates must be a list")

    parsed = []
    for row in rows:
        T = datetime.fromisoformat(row["T"])
        if T.tzinfo is None or T.utcoffset() != timedelta(0):
            raise SystemExit(f"candidate T is not UTC: {row['T']!r}")
        parsed.append((T.astimezone(UTC), row))

    totals = _counts([row for _, row in parsed])
    family_totals = totals["by_family"]
    if any(family_totals[f] <= 0 for f in EXPECTED_FAMILIES):
        raise SystemExit(f"all expected families must exist in full population: {family_totals!r}")

    audits = []
    eligible = []
    for split in _iter_midnights(args.start_split, args.end_split):
        dev = [row for T, row in parsed if T < split]
        hold = [row for T, row in parsed if T >= split]
        dev_counts = _counts(dev)
        hold_counts = _counts(hold)
        total_share = hold_counts["total"] / totals["total"] if totals["total"] else 0.0
        family_shares = {
            family: hold_counts["by_family"][family] / family_totals[family]
            for family in EXPECTED_FAMILIES
        }
        passes = (
            total_share >= MIN_HOLDOUT_TOTAL_SHARE
            and all(share >= MIN_HOLDOUT_FAMILY_SHARE for share in family_shares.values())
        )
        row = {
            "split": split.isoformat(),
            "development": dev_counts,
            "holdout": hold_counts,
            "holdout_total_share": total_share,
            "holdout_family_share": family_shares,
            "passes_pre_outcome_rule": passes,
        }
        audits.append(row)
        if passes:
            eligible.append(row)

    selected = eligible[-1] if eligible else None
    out = {
        "study": "E1-RUN-001",
        "kind": "COUNT_ONLY_SPLIT_BALANCE_AUDIT_NO_OUTCOMES",
        "source_outcomes_included": False,
        "selection_rule": {
            "latest_utc_midnight": True,
            "min_holdout_total_share": MIN_HOLDOUT_TOTAL_SHARE,
            "min_holdout_each_family_share": MIN_HOLDOUT_FAMILY_SHARE,
        },
        "full_counts": totals,
        "candidate_splits": audits,
        "selected_split": selected,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
