"""Run the refined D2 fresh-N power grid on exposed Binance 2020-2024 only.

Does not open 2025/2026. Does not use BitMEX outcomes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.d2_confirmation_dependence_preserving_power import (
    COARSE_REFINED_N_GRID,
    D2_REFINED_FRESH_N_SEED,
    N_POWER_OUTER,
    N_REPLICATES_CONFIRMATION,
    extract_complete_year_blocks,
    estimate_refined_fresh_n_power,
)
from scripts.research.d2_confirmation_feasibility_and_design import (
    load_exposed_rule1_rows,
    refuse_protected_price_path,
)
from scripts.research.discovery_sprint_01 import common as C

CHECKPOINT_REL = "artifacts/research_data/D2_REFINED_FRESH_N_POWER_CHECKPOINT.json"
RESULT_REL = "artifacts/research_data/D2_REFINED_FRESH_N_POWER.json"


def _strip_rng(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.pop("rng_state", None)
    return out


def run_refined_power(
    *,
    repo: Path | None = None,
    n_outer: int = N_POWER_OUTER,
    n_inner: int = N_REPLICATES_CONFIRMATION,
) -> dict[str, Any]:
    base = repo or C.repo_root()
    rows, log = load_exposed_rule1_rows(repo=base)
    years = sorted({Path(rel).name[:4] for rel in log.files if rel.endswith(".parquet")})
    for rel in log.files:
        refuse_protected_price_path(base / rel if not str(rel).startswith("/") else Path(rel))
        if "2025-" in rel or "2026-" in rel:
            raise RuntimeError(f"PROTECTED_FILE_IN_POWER:{rel}")
    if years != ["2020", "2021", "2022", "2023", "2024"]:
        raise RuntimeError(f"POWER_YEARS:{years}")
    year_blocks = extract_complete_year_blocks(rows)
    if set(year_blocks) != {2021, 2022, 2023, 2024}:
        raise RuntimeError(f"YEAR_BLOCKS:{sorted(year_blocks)}")
    ck_path = base / CHECKPOINT_REL
    ck_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = None
    if ck_path.is_file():
        checkpoint = json.loads(ck_path.read_text(encoding="utf-8"))
        if int(checkpoint.get("REFINED_FRESH_N_SEED") or 0) != D2_REFINED_FRESH_N_SEED:
            checkpoint = None
    result = estimate_refined_fresh_n_power(
        rows,
        seed=D2_REFINED_FRESH_N_SEED,
        n_outer=n_outer,
        n_inner=n_inner,
        coarse_grid=COARSE_REFINED_N_GRID,
        checkpoint=checkpoint,
    )
    out = _strip_rng(result)
    out["EXPOSED_FILES_OPENED_YEARS"] = years
    out["POWER_USES_BINANCE_2025_2026"] = False
    out["POWER_USES_BITMEX_OUTCOMES"] = False
    out["year_block_lengths"] = {str(y): int(year_blocks[y]["severity"].size) for y in year_blocks}
    (base / RESULT_REL).write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ck_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    payload = run_refined_power()
    keys = (
        "MIN_REQUIRED_FRESH_DECISION_ROWS",
        "POWER_AT_REFINED_MIN_N",
        "POWER_95CI_AT_REFINED_MIN_N",
        "N_BELOW",
        "N_ABOVE",
        "FIVE_ROW_REFINEMENT_GRID",
        "POWER_BY_N",
        "POWER_USES_BINANCE_2025_2026",
        "POWER_USES_BITMEX_OUTCOMES",
    )
    print(json.dumps({k: payload[k] for k in keys}, indent=2))
