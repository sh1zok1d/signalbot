"""Run the authorized Discovery Sprint 01 partial batch: D2, D3, D4_ROLLING, D5."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.research.discovery_sprint_01 import common as C
from scripts.research.discovery_sprint_01.d2_abstention_tail_risk import run_d2
from scripts.research.discovery_sprint_01.d3_path_morphology import run_d3
from scripts.research.discovery_sprint_01.d4_btc_eth_relative_structure import run_d4
from scripts.research.discovery_sprint_01.d5_composed_decision import run_d5


AUTHORIZED = ("D2", "D3", "D4_ROLLING", "D5")


def run_partial_batch(
    *,
    output_dir: Path | None = None,
    repo: Path | None = None,
    implementation_commit: str | None = None,
    n_replicates: int = C.N_REPLICATES,
) -> dict:
    base = repo or C.repo_root()
    out = output_dir or (base / "docs" / "research" / "discovery_results")
    out.mkdir(parents=True, exist_ok=True)
    commit = implementation_commit or C.current_git_commit(base)
    preflight = C.preflight_local_data(base)
    results = {
        "D2": run_d2(
            implementation_commit=commit,
            output_dir=out,
            repo=base,
            n_replicates=n_replicates,
        ),
        "D3": run_d3(
            implementation_commit=commit,
            output_dir=out,
            repo=base,
            n_replicates=n_replicates,
        ),
        "D4": run_d4(
            implementation_commit=commit,
            output_dir=out,
            repo=base,
            n_replicates=n_replicates,
        ),
        "D5": run_d5(
            implementation_commit=commit,
            output_dir=out,
            repo=base,
            n_replicates=n_replicates,
        ),
    }
    summary = {
        "AUTHORIZED": list(AUTHORIZED),
        "NOT_EXECUTED": ["D1", "D4_LEAD_LAG_1DAY", "D6"],
        "MARKET_07_CREATED": False,
        "PREFLIGHT": preflight,
        "IMPLEMENTATION_COMMIT": commit,
        "CLASSIFICATIONS": {
            key: value.get("TERMINAL_CLASSIFICATION") for key, value in results.items()
        },
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
    }
    (out / "PARTIAL_BATCH_SUMMARY.json").write_text(
        json.dumps(C.jsonable(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"summary": summary, "results": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    payload = run_partial_batch(output_dir=args.output_dir)
    print(json.dumps(C.jsonable(payload["summary"]), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
