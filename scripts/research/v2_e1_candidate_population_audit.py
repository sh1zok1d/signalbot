#!/usr/bin/env python3
"""Outcome-free population diagnostics for E1-RUN-001 Stage-5 candidates.

Reads only the candidate-inventory JSON produced before outcome inspection.
No DB access, no raw future prices, no Stage-6 imports, no outcome modules.
The clustering below is a dependence diagnostic only; it is NOT episode
reconstruction and never changes the raw E1 population.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
DEFAULT_SPLIT = datetime(2026, 8, 21, 0, 0, tzinfo=UTC)
CLUSTER_GAPS_MINUTES = (15, 30, 60)


def _parse_ts(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None or dt.utcoffset() != timedelta(0):
        raise ValueError(f"candidate T must be UTC-aware, got {value!r}")
    return dt.astimezone(UTC)


def _partition(rows: list[dict], split: datetime):
    dev, holdout = [], []
    for row in rows:
        T = _parse_ts(row["T"])
        (dev if T < split else holdout).append(row)
    return dev, holdout


def _counts(rows: list[dict]) -> dict:
    by_family = Counter(r["family"] for r in rows)
    by_family_direction = Counter((r["family"], r["direction"]) for r in rows)
    return {
        "total": len(rows),
        "by_family": dict(sorted(by_family.items())),
        "by_family_direction": {
            f"{f}:{d}": n for (f, d), n in sorted(by_family_direction.items())
        },
    }


def _same_t_overlap(rows: list[dict]) -> dict:
    by_t: dict[datetime, list[dict]] = defaultdict(list)
    for row in rows:
        by_t[_parse_ts(row["T"])].append(row)

    multi = {T: rs for T, rs in by_t.items() if len(rs) > 1}
    combos = Counter()
    direction_conflicts = 0
    for rs in multi.values():
        combos[tuple(sorted(r["family"] for r in rs))] += 1
        if len({r["direction"] for r in rs}) > 1:
            direction_conflicts += 1

    return {
        "unique_candidate_times": len(by_t),
        "same_T_multi_family_times": len(multi),
        "same_T_multi_family_share_of_unique_T": (
            len(multi) / len(by_t) if by_t else 0.0
        ),
        "same_T_direction_conflict_times": direction_conflicts,
        "family_combinations": {
            "+".join(combo): n for combo, n in sorted(combos.items())
        },
    }


def _cluster_counts(rows: list[dict], gap_minutes: int) -> dict:
    gap = timedelta(minutes=gap_minutes)
    by_key: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    for row in rows:
        by_key[(row["family"], row["direction"])].append(_parse_ts(row["T"]))

    total_clusters = 0
    by_family = Counter()
    by_family_direction = Counter()
    cluster_sizes: list[int] = []

    for key, times in by_key.items():
        times.sort()
        if not times:
            continue
        size = 1
        clusters_for_key = 0
        for prev, cur in zip(times, times[1:]):
            if cur - prev <= gap:
                size += 1
            else:
                cluster_sizes.append(size)
                clusters_for_key += 1
                size = 1
        cluster_sizes.append(size)
        clusters_for_key += 1
        total_clusters += clusters_for_key
        by_family[key[0]] += clusters_for_key
        by_family_direction[key] += clusters_for_key

    return {
        "gap_minutes": gap_minutes,
        "clusters_total": total_clusters,
        "raw_to_cluster_ratio": (len(rows) / total_clusters if total_clusters else None),
        "largest_cluster_size": max(cluster_sizes) if cluster_sizes else 0,
        "median_cluster_size": (
            sorted(cluster_sizes)[len(cluster_sizes) // 2] if cluster_sizes else 0
        ),
        "by_family": dict(sorted(by_family.items())),
        "by_family_direction": {
            f"{f}:{d}": n for (f, d), n in sorted(by_family_direction.items())
        },
    }


def _day_concentration(rows: list[dict]) -> dict:
    by_day = Counter(_parse_ts(r["T"]).date().isoformat() for r in rows)
    ordered = sorted(by_day.items(), key=lambda kv: (-kv[1], kv[0]))
    total = len(rows)

    def share(k: int) -> float:
        return sum(n for _, n in ordered[:k]) / total if total else 0.0

    return {
        "days_with_candidates": len(by_day),
        "top_days": ordered[:10],
        "top_1_day_share": share(1),
        "top_3_days_share": share(3),
        "top_5_days_share": share(5),
    }


def _audit(rows: list[dict]) -> dict:
    return {
        "counts": _counts(rows),
        "same_T_overlap": _same_t_overlap(rows),
        "clustering_sensitivity": [
            _cluster_counts(rows, gap) for gap in CLUSTER_GAPS_MINUTES
        ],
        "day_concentration": _day_concentration(rows),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Outcome-free E1 candidate population audit")
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--split", default=DEFAULT_SPLIT.isoformat())
    args = p.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if payload.get("outcomes_included") is not False:
        raise SystemExit("refusing input that is not explicitly outcomes_included=false")
    rows = payload.get("candidates")
    if not isinstance(rows, list):
        raise SystemExit("input candidates must be a list")

    split = _parse_ts(args.split)
    dev, holdout = _partition(rows, split)

    report = {
        "study": payload.get("study"),
        "kind": "CANDIDATE_POPULATION_AUDIT_NO_OUTCOMES",
        "source_outcomes_included": False,
        "split": split.isoformat(),
        "full": _audit(rows),
        "development": _audit(dev),
        "holdout_counts_only": _counts(holdout),
        "holdout_outcomes_opened": False,
        "note": (
            "Time-gap clusters are dependence diagnostics only, not Stage-6 episode "
            "reconstruction and not a replacement population."
        ),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
