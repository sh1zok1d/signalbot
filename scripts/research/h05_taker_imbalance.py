#!/usr/bin/env python3
"""H05 taker-imbalance -> subsequent-return-distribution development runner.

Reads CORE_BTC_BINANCE_V0 2020-2024 canonical 1m only, derives 15m bars.
Refuses 2025/2026. Does not promote confirmatory status. Does not run R3.
Does not start H06 or Batch01 synthesis.

This is a preregistration + implementation freeze: `--stage dev-run` is not
invoked against real accepted parquet as part of that freeze -- see
`docs/research/H05_TAKER_IMBALANCE_PREREG.md`. The pipeline below is wired
and unit-tested against synthetic fixtures only
(tests/research/test_h05_taker_imbalance.py); it is not executed against
real data in this task.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.h05_taker_imbalance_lib import (
    DATASET_ID,
    PREREG_JSON,
    REPO_ROOT,
    REQUIRED_SNAPSHOT,
    ValidationWindowForbidden,
    aggregate_1m_to_15m,
    build_panel,
    dumps_json,
    evaluate_h05,
    load_development_1m,
    load_prereg,
    require_snapshot,
)

UTC = timezone.utc
DEFAULT_ROOT = REPO_ROOT / "artifacts" / "research_data" / DATASET_ID
DEFAULT_OUT = REPO_ROOT / "artifacts" / "h05"


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
        "# H05 development summary",
        "",
        f"hypothesis: `{results['hypothesis_id']}`",
        f"snapshot_id: `{results['snapshot_id']}`",
        f"prereg_commit_sha: `{results.get('prereg_commit_sha')}`",
        f"research_code_sha: `{results.get('research_code_sha')}`",
        f"primary cells: {results['search_surface']['primary_threshold_cells']}",
        f"batch01 cumulative cells: {results['search_surface']['batch01_cumulative_cells']}",
        f"development window: {results['windows']['development_start_inclusive']} -> {results['windows']['development_end_exclusive']}",
        f"t_max_inclusive: {results['windows']['t_max_inclusive']}",
        "2025 validation inspected: NO",
        "2026 OOS inspected: NO",
        "",
        "## Primary cells (W, q, H)",
        "",
        "| W | q | H | N | candidate_mean | P(X>0) | primary(C) | primary(R) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for c in results["cells"]:
        def _b(v):
            return "NA" if v is None else ("Y" if v else "N")
        lines.append(
            "| {W} | {q} | {H} | {N} | {mn} | {pp} | {pc} | {pr} |".format(
                W=c["W"], q=c["q"], H=c["H"], N=c["N"],
                mn="NA" if c["candidate_mean"] is None else f"{c['candidate_mean']:.4f}",
                pp="NA" if c["P_X_pos"] is None else f"{c['P_X_pos']:.3f}",
                pc=_b(c["claim_evaluation"]["continuation"]["primary_gate"]),
                pr=_b(c["claim_evaluation"]["reversal"]["primary_gate"]),
            )
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Primary outcome is D-signed future return / trailing 30d median |RET_H| (no floor).",
        "- Both continuation and reversal are preregistered on the SAME 45 cells; anti-cherry-pick"
        " rule: a sign may not be selected/promoted because the other sign failed first.",
        "- Verdict is recorded after inspection of this table, the JSON, and the independent"
        " pre-outcome implementation audit; not auto-claimed here.",
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
        # Identity stage uses repository/dataset metadata only -- it never
        # computes market outcomes and never opens 1m/15m parquet rows.
        return 0

    # --stage dev-run: wired but intentionally not exercised against real
    # accepted parquet in the preregistration + implementation-freeze task.
    # Every function it calls is exercised only against synthetic fixtures
    # in tests/research/test_h05_taker_imbalance.py.
    try:
        frame1 = load_development_1m(args.dataset_root)
        frame15 = aggregate_1m_to_15m(frame1)
        panel = build_panel(frame15)
        results = evaluate_h05(panel)
    except ValidationWindowForbidden as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results["prereg_path"] = str(PREREG_JSON.relative_to(REPO_ROOT))
    results["prereg_commit_sha"] = args.prereg_commit_sha or _git_sha()
    results["research_code_sha"] = _git_sha()
    results["generated_at_utc"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    results["forbidden_windows_inspected"] = {"2025": False, "2026": False}
    results["validation_untouched"] = True
    results["oos_untouched"] = True

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "H05_DEV_RESULTS.json"
    md_path = args.out_dir / "H05_DEV_SUMMARY.md"
    json_path.write_text(dumps_json(results), encoding="utf-8")
    write_summary(results, md_path)
    print(json.dumps({
        "overall_status": "H05_DEV_COMPLETE",
        "cells": len(results["cells"]),
        "json": str(json_path),
        "md": str(md_path),
        "validation_inspected": False,
        "oos_inspected": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
