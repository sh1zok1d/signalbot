#!/usr/bin/env python3
"""H01 compression → expansion development runner.

Reads CORE_BTC_BINANCE_V0 2020-2024 canonical 1m only. Refuses 2025/2026.
Does not promote confirmatory status or inspect reserved windows.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.h01_compression_expansion_lib import (
    DATASET_ID,
    PREREG_JSON,
    REPO_ROOT,
    REQUIRED_SNAPSHOT,
    ValidationWindowForbidden,
    build_panel,
    dumps_json,
    evaluate_h01,
    load_development_arrays,
    load_prereg,
    require_snapshot,
)

UTC = timezone.utc
DEFAULT_ROOT = REPO_ROOT / "artifacts" / "research_data" / DATASET_ID
DEFAULT_OUT = REPO_ROOT / "artifacts" / "h01"


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
        "# H01 development summary",
        "",
        f"hypothesis: `{results['hypothesis_id']}`",
        f"snapshot_id: `{results['snapshot_id']}`",
        f"prereg_commit_sha: `{results.get('prereg_commit_sha')}`",
        f"research_code_sha: `{results.get('research_code_sha')}`",
        f"eligible development 15m boundaries: {results['eligible_development_boundaries']}",
        f"primary cells: {results['search_surface']['primary_threshold_cells']}",
        f"development window: {results['windows']['development_start_inclusive']} → {results['windows']['development_end_exclusive']}",
        f"t_max_inclusive: {results['windows']['t_max_inclusive']}",
        "2025 validation inspected: NO",
        "2026 OOS inspected: NO",
        "",
        "## Primary cells (L, q, H)",
        "",
        "| L | q | H | N | mean norm RV | baseline A | minus matched | minus baseline | p(exp) | year diffs 2020-2024 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in results["cells"]:
        y = c["year_breakdown"]
        yds = ",".join(
            "NA" if y[str(yr)]["diff_norm_rv"] is None else f"{y[str(yr)]['diff_norm_rv']:+.3f}"
            for yr in (2020, 2021, 2022, 2023, 2024)
        )
        lines.append(
            "| {L} | {q:.2f} | {H} | {N} | {mn} | {ba} | {tm} | {tb} | {pe} | {yds} |".format(
                L=c["L"], q=c["q"], H=c["H"], N=c["N"],
                mn="NA" if c["mean_norm_rv"] is None else f"{c['mean_norm_rv']:.4f}",
                ba="NA" if c["baseline_A_mean_norm_rv"] is None else f"{c['baseline_A_mean_norm_rv']:.4f}",
                tm="NA" if c["true_minus_matched_norm_rv"] is None else f"{c['true_minus_matched_norm_rv']:+.4f}",
                tb="NA" if c["true_minus_baseline_norm_rv"] is None else f"{c['true_minus_baseline_norm_rv']:+.4f}",
                pe="NA" if c["p_expansion"] is None else f"{c['p_expansion']:.3f}",
                yds=yds,
            )
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Primary outcome is FUTURE_RV_H / PAST_MEDIAN_RV_H, not future/current compressed RV.",
        "- Deciles are diagnostic only.",
        "- Verdict is recorded after human inspection of this table and JSON; not auto-claimed here.",
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
        frame = load_development_arrays(args.dataset_root)
        panel = build_panel(frame)
        results = evaluate_h01(panel)
    except ValidationWindowForbidden as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results["prereg_path"] = str(PREREG_JSON.relative_to(REPO_ROOT))
    results["prereg_commit_sha"] = args.prereg_commit_sha or _git_sha()
    results["research_code_sha"] = _git_sha()
    results["generated_at_utc"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    results["forbidden_windows_inspected"] = {"2025": False, "2026": False}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "H01_DEV_RESULTS.json"
    md_path = args.out_dir / "H01_DEV_SUMMARY.md"
    json_path.write_text(dumps_json(results), encoding="utf-8")
    write_summary(results, md_path)
    print(json.dumps({
        "overall_status": "H01_DEV_COMPLETE",
        "eligible_development_boundaries": results["eligible_development_boundaries"],
        "cells": len(results["cells"]),
        "json": str(json_path),
        "md": str(md_path),
        "validation_inspected": False,
        "oos_inspected": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
