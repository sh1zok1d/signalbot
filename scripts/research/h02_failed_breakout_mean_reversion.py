#!/usr/bin/env python3
"""H02 failed-breakout → mean-reversion development runner.

Reads CORE_BTC_BINANCE_V0 2020-2024 canonical 1m only, derives 5m bars.
Refuses 2025/2026. Does not promote confirmatory status.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.h02_failed_breakout_mean_reversion_lib import (
    DATASET_ID,
    PREREG_JSON,
    REPO_ROOT,
    REQUIRED_SNAPSHOT,
    ValidationWindowForbidden,
    aggregate_1m_to_5m,
    build_panel,
    dumps_json,
    evaluate_h02,
    load_development_1m,
    load_prereg,
    require_snapshot,
)

UTC = timezone.utc
DEFAULT_ROOT = REPO_ROOT / "artifacts" / "research_data" / DATASET_ID
DEFAULT_OUT = REPO_ROOT / "artifacts" / "h02"


def _git_sha() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=3, check=True,
        )
        return r.stdout.strip() or "UNKNOWN"
    except (OSError, subprocess.SubprocessError):
        return "UNKNOWN"


def write_summary(results: dict, path: Path) -> None:
    lines = [
        "# H02 development summary",
        "",
        f"hypothesis: `{results['hypothesis_id']}`",
        f"snapshot_id: `{results['snapshot_id']}`",
        f"prereg_commit_sha: `{results.get('prereg_commit_sha')}`",
        f"research_code_sha: `{results.get('research_code_sha')}`",
        f"primary cells: {results['search_surface']['primary_threshold_cells']}",
        f"development window: {results['windows']['development_start_inclusive']} → {results['windows']['development_end_exclusive']}",
        f"t_max_inclusive: {results['windows']['t_max_inclusive']}",
        "2025 validation inspected: NO",
        "2026 OOS inspected: NO",
        "",
        "## Primary cells (L, s, H)",
        "",
        "| L | s | H | N | mean norm | p(rev>0) | minus matched | success mean | shift mean | year diffs |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in results["cells"]:
        y = c["year_breakdown"]
        yds = ",".join(
            "NA" if y[str(yr)]["diff_norm"] is None else f"{y[str(yr)]['diff_norm']:+.3f}"
            for yr in (2020, 2021, 2022, 2023, 2024)
        )
        lines.append(
            "| {L} | {s:.2f} | {H} | {N} | {mn} | {pp} | {tm} | {sm} | {sh} | {yds} |".format(
                L=c["L"], s=c["s"], H=c["H"], N=c["N"],
                mn="NA" if c["mean_norm_rev"] is None else f"{c['mean_norm_rev']:.4f}",
                pp="NA" if c["p_rev_pos"] is None else f"{c['p_rev_pos']:.3f}",
                tm="NA" if c["true_minus_matched_norm"] is None else f"{c['true_minus_matched_norm']:+.4f}",
                sm="NA" if c["successful_breakout"]["mean_norm_rev"] is None else f"{c['successful_breakout']['mean_norm_rev']:.4f}",
                sh="NA" if c["time_shift"]["mean_norm_rev"] is None else f"{c['time_shift']['mean_norm_rev']:.4f}",
                yds=yds,
            )
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Primary outcome is reversion-direction close return / trailing 30d median |RET_H|.",
        "- MFE/MAE are secondary and cannot promote H02.",
        "- Verdict is recorded after inspection of this table and JSON; not auto-claimed here.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stage", required=True, choices=["identity", "dev-run"])
    p.add_argument("--dataset-root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--prereg-commit-sha", default=None)
    args = p.parse_args(argv)

    prereg = load_prereg()
    if prereg["dataset"]["snapshot_id"] != REQUIRED_SNAPSHOT:
        print("prereg snapshot mismatch", file=sys.stderr)
        return 2
    snap = require_snapshot()
    print(json.dumps({"stage": args.stage, "snapshot_id": snap, "dataset_id": DATASET_ID}))
    if args.stage == "identity":
        return 0

    try:
        frame1 = load_development_1m(args.dataset_root)
        frame5 = aggregate_1m_to_5m(frame1)
        panel = build_panel(frame5)
        results = evaluate_h02(panel)
    except ValidationWindowForbidden as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results["prereg_path"] = str(PREREG_JSON.relative_to(REPO_ROOT))
    results["prereg_commit_sha"] = args.prereg_commit_sha or _git_sha()
    results["research_code_sha"] = _git_sha()
    results["generated_at_utc"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    results["forbidden_windows_inspected"] = {"2025": False, "2026": False}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "H02_DEV_RESULTS.json"
    md_path = args.out_dir / "H02_DEV_SUMMARY.md"
    json_path.write_text(dumps_json(results), encoding="utf-8")
    write_summary(results, md_path)
    print(json.dumps({
        "overall_status": "H02_DEV_COMPLETE",
        "cells": len(results["cells"]),
        "json": str(json_path),
        "md": str(md_path),
        "validation_inspected": False,
        "oos_inspected": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
