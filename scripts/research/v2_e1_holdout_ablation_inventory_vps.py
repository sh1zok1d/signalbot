#!/usr/bin/env python3
"""Outcome-free E1 holdout ablation/simple-baseline census.

This is a narrow wrapper around the already-frozen development ablation census
and its legacy-VPS mappingproxy compatibility shim.  It changes only the
candidate decision window from development to the sealed chronological holdout.
It does NOT read future outcome paths.

Hard invariant before any holdout outcome can be opened:
FULL populations must reproduce the candidate-only census frozen earlier:
TP=105, CB=17, FB=19.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

# Importing the VPS launcher applies ONLY the mappingproxy thaw patch to the
# frozen ablation implementation.
import scripts.research.v2_e1_development_ablation_inventory_vps  # noqa: F401
import scripts.research.v2_e1_development_ablation_inventory as impl

UTC = timezone.utc
HOLDOUT_START = datetime(2026, 8, 16, 0, 0, tzinfo=UTC)
HOLDOUT_END = datetime(2026, 8, 25, 17, 20, tzinfo=UTC)
EXPECTED_BOUNDARIES = 2800
EXPECTED_FULL = {
    impl.TP_FULL: 105,
    impl.CB_FULL: 17,
    impl.FB_FULL: 19,
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Inventory frozen E1 holdout ablations without reading outcomes")
    p.add_argument("--dsn", required=True)
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--market-type", default="perp")
    p.add_argument("--calculation-version", required=True)
    p.add_argument("--feature-schema-version", type=int, default=1)
    p.add_argument("--health-exchanges", nargs="+", required=True)
    p.add_argument("--health-metrics", nargs="+", required=True)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--progress-every", type=int, default=500)
    return p


async def _run(args: argparse.Namespace) -> dict:
    # The underlying implementation uses these globals in both its exact-grid
    # iterator and its per-boundary fail-closed window assertion.
    impl.DEV_START = HOLDOUT_START
    impl.HOLDOUT_START = HOLDOUT_END

    payload = await impl._run(args)

    window = payload.get("development_window") or {}
    if window.get("boundaries") != EXPECTED_BOUNDARIES:
        raise RuntimeError(
            f"holdout boundary count mismatch: expected {EXPECTED_BOUNDARIES}, "
            f"got {window.get('boundaries')!r}")

    by_variant = payload.get("summary", {}).get("by_variant", {})
    for variant, expected in EXPECTED_FULL.items():
        actual = by_variant.get(variant)
        if actual != expected:
            raise RuntimeError(
                "HOLDOUT FULL POPULATION REPRODUCIBILITY FAILURE: "
                f"{variant} expected {expected}, got {actual!r}. "
                "Do not open holdout outcomes."
            )

    # Structural equivalence frozen before outcomes.
    if by_variant.get(impl.FB_NO_CONTEXT) != by_variant.get(impl.FB_DUMB):
        raise RuntimeError(
            "FB_NO_CONTEXT and FB_DUMB_48H_LEVEL_BREAKOUT counts diverged in holdout")

    directions = payload.get("summary", {}).get("by_variant_direction", {})
    for direction in ("LONG", "SHORT"):
        a = directions.get(f"{impl.FB_NO_CONTEXT}:{direction}")
        b = directions.get(f"{impl.FB_DUMB}:{direction}")
        if a != b:
            raise RuntimeError(
                "FB_NO_CONTEXT and FB_DUMB direction counts diverged in holdout: "
                f"{direction} {a!r} != {b!r}")

    payload["kind"] = "HOLDOUT_ABLATION_INVENTORY_NO_OUTCOMES"
    payload["protocol"] = "docs/e1/E1_RUN_001_PRE_HOLDOUT_FREEZE.md"
    payload["holdout_window"] = {
        "start_inclusive": HOLDOUT_START.isoformat(),
        "end_exclusive": HOLDOUT_END.isoformat(),
        "boundaries": EXPECTED_BOUNDARIES,
    }
    payload.pop("development_window", None)
    payload["full_population_reproduced"] = True
    payload["expected_full_counts"] = EXPECTED_FULL
    payload["outcomes_included"] = False
    payload["holdout_outcomes_opened"] = False
    payload["holdout_market_rows_read"] = False
    return payload


def main() -> int:
    args = _parser().parse_args()
    payload = asyncio.run(_run(args))
    impl._write_json_atomic(args.output, payload)
    print(json.dumps({
        "kind": payload["kind"],
        "holdout_window": payload["holdout_window"],
        "full_population_reproduced": payload["full_population_reproduced"],
        "summary": payload["summary"],
        "outcomes_included": payload["outcomes_included"],
        "holdout_outcomes_opened": payload["holdout_outcomes_opened"],
        "holdout_market_rows_read": payload["holdout_market_rows_read"],
    }, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
