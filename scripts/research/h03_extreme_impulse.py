#!/usr/bin/env python3
"""H03 extreme-impulse continuation/exhaustion development runner.

Reads CORE_BTC_BINANCE_V0 2020-2024 canonical 1m only, derives 15m bars.
Refuses 2025/2026. Does not promote confirmatory status. Does not run R3.

This is a preregistration + implementation freeze: `--stage dev-run` is not
invoked against real accepted parquet as part of that freeze -- see
`docs/research/H03_EXTREME_IMPULSE_PREREG.md`. The pipeline below is wired
and unit-tested against synthetic fixtures only
(tests/research/test_h03_extreme_impulse.py); it is not executed against
real data in this task.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.research.h03_extreme_impulse_lib import (
    DATASET_ID,
    PREREG_JSON,
    REPO_ROOT,
    REQUIRED_SNAPSHOT,
    ValidationWindowForbidden,
    aggregate_1m_to_15m,
    build_panel,
    dumps_json,
    evaluate_h03,
    load_development_1m,
    load_prereg,
    require_snapshot,
)

UTC = timezone.utc
DEFAULT_ROOT = REPO_ROOT / "artifacts" / "research_data" / DATASET_ID
DEFAULT_OUT = REPO_ROOT / "artifacts" / "h03"


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
        "# H03 development summary",
        "",
        f"hypothesis: `{results['hypothesis_id']}`",
        f"snapshot_id: `{results['snapshot_id']}`",
        f"prereg_commit_sha: `{results.get('prereg_commit_sha')}`",
        f"research_code_sha: `{results.get('research_code_sha')}`",
        f"primary cells: {results['search_surface']['primary_threshold_cells']}",
        f"development window: {results['windows']['development_start_inclusive']} → {results['windows']['development_end_exclusive']}",
        f"t_max_inclusive: {results['windows']['t_max_inclusive']}",
        f"long-dependence L_dep: {results['long_dependence']['l_dep_label']}",
        "2025 validation inspected: NO",
        "2026 OOS inspected: NO",
        "",
        "## Primary cells (W, q, H)",
        "",
        "| W | q | H | N | mean norm | p(cont>0) | MPIE(cont) | MPIE(exh) | struct(cont) | struct(exh) | negctl(cont) | negctl(exh) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for c in results["cells"]:
        def _b(v):
            return "NA" if v is None else ("Y" if v else "N")
        lines.append(
            "| {W} | {q:.2f} | {H} | {N} | {mn} | {pp} | {mc} | {me} | {sc} | {se} | {nc} | {ne} |".format(
                W=c["W"], q=c["q"], H=c["H"], N=c["N"],
                mn="NA" if c["mean_norm_cont_ret"] is None else f"{c['mean_norm_cont_ret']:.4f}",
                pp="NA" if c["p_cont_ret_pos"] is None else f"{c['p_cont_ret_pos']:.3f}",
                mc=_b(c["mpie_gate_continuation"]), me=_b(c["mpie_gate_exhaustion"]),
                sc=_b(c["structural_gate_continuation"]), se=_b(c["structural_gate_exhaustion"]),
                nc=_b(c["negative_control_gate_continuation"]), ne=_b(c["negative_control_gate_exhaustion"]),
            )
        )
    lines.extend([
        "",
        "## Notes",
        "",
        "- Primary outcome is impulse-direction continuation return / trailing 30d median |RET_H| (no floor).",
        "- MFE/MAE are secondary and cannot promote H03 or satisfy the adjacent-horizon coherence gate.",
        "- H03 is a symmetric claim: promotion requires both UP and DOWN to support the same sign.",
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

    # --stage dev-run: wired but intentionally not exercised against real
    # accepted parquet in the preregistration + implementation-freeze task.
    # Every function it calls is exercised only against synthetic fixtures
    # in tests/research/test_h03_extreme_impulse.py.
    try:
        frame1 = load_development_1m(args.dataset_root)
        frame15 = aggregate_1m_to_15m(frame1)
        panel = build_panel(frame15)
        results = evaluate_h03(panel)
    except ValidationWindowForbidden as exc:
        print(str(exc), file=sys.stderr)
        return 2

    results["prereg_path"] = str(PREREG_JSON.relative_to(REPO_ROOT))
    results["prereg_commit_sha"] = args.prereg_commit_sha or _git_sha()
    results["research_code_sha"] = _git_sha()
    results["generated_at_utc"] = datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    results["forbidden_windows_inspected"] = {"2025": False, "2026": False}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "H03_DEV_RESULTS.json"
    md_path = args.out_dir / "H03_DEV_SUMMARY.md"
    json_path.write_text(dumps_json(results), encoding="utf-8")
    write_summary(results, md_path)
    print(json.dumps({
        "overall_status": "H03_DEV_COMPLETE",
        "cells": len(results["cells"]),
        "json": str(json_path),
        "md": str(md_path),
        "validation_inspected": False,
        "oos_inspected": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
