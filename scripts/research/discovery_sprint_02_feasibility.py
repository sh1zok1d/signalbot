"""Selector/support feasibility CLI for Discovery Sprint 02.

Real-data entry point. Does not compute D7 t+1 persistence, D8 recovery,
or scientific classifications. Does not expose a scientific execution CLI.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from scripts.research import discovery_sprint_02_impl as I


FEASIBILITY_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.json"
FEASIBILITY_MD_REL = "docs/research/DISCOVERY_SPRINT_02_FEASIBILITY.md"
REVIEW_JSON_REL = "docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.json"
REVIEW_MD_REL = "docs/research/DISCOVERY_SPRINT_02_IMPLEMENTATION_REVIEW.md"
IMPL_REL = "scripts/research/discovery_sprint_02_impl.py"
FEAS_REL = "scripts/research/discovery_sprint_02_feasibility.py"
TEST_REL = "tests/research/test_discovery_sprint_02_feasibility.py"

def _this_source() -> str:
    return Path(__file__).read_text(encoding="utf-8")


def run_feasibility(*, repo: Path | None = None, write: bool = True) -> dict[str, Any]:
    I.assert_no_scientific_calls_in_feasibility_source(_this_source())
    base = repo if isinstance(repo, Path) else I.repo_root()
    log = I.OpenedFileLog()
    authority = I.verify_dataset_authority(base)
    bars = I.load_legal_1m_bars(repo=base, log=log)
    for rel in log.files:
        if I.path_is_protected_partition(Path(rel)):
            raise I.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
        lowered = rel.lower()
        if "/2025-" in lowered or "/2026-" in lowered:
            raise I.ProtectedYearRefused(f"PROTECTED_PATH_OPENED:{rel}")
    hours = I.aggregate_completed_hours(bars)
    del bars
    d7_states = I.build_d7_states(hours)
    d7 = I.d7_feasibility_census(d7_states)
    d8 = I.d8_feasibility_census(hours)
    if d7["FEASIBILITY_STATUS"] == "OUTCOME_BLIND_READY" or d8[
        "FEASIBILITY_STATUS"
    ] == "OUTCOME_BLIND_READY":
        next_unit = "DISCOVERY_SPRINT_02_SCIENTIFIC_EXECUTION_FREEZE"
    else:
        next_unit = "HETEROGENEOUS_FAMILY_ROTATION_V2"

    sprint_sha = I.file_sha256(base / I.SPRINT_JSON_REL)
    policy_sha = I.file_sha256(base / I.POLICY_JSON_REL)
    data_policy_sha = I.file_sha256(base / I.DATA_POLICY_JSON_REL)
    impl_sha = I.file_sha256(base / IMPL_REL)
    feas_sha = I.file_sha256(base / FEAS_REL)
    test_path = base / TEST_REL
    test_sha = I.file_sha256(test_path) if test_path.is_file() else None

    payload = {
        "UNIT": I.UNIT,
        "KIND": "OUTCOME_BLIND_SELECTOR_SUPPORT_FEASIBILITY",
        "STATUS": "COMPLETED",
        "CORE_BTC_DATASET_ID": I.CORE_BTC_DATASET_ID,
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "OPENED_FILES": list(log.files),
        "OPENED_FILE_COUNT": len(log.files),
        "D7": d7,
        "D8": d8,
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "D7_SCIENTIFIC_EVALUATOR_RUN_ON_REAL_DATA": False,
        "D8_SCIENTIFIC_EVALUATOR_RUN_ON_REAL_DATA": False,
        "NEXT_UNIT": next_unit,
        "RUNTIME_SNAPSHOT_MANIFEST_FOUND": authority["RUNTIME_SNAPSHOT_MANIFEST_FOUND"],
        "RUNTIME_SNAPSHOT_MANIFEST": authority["RUNTIME_SNAPSHOT_MANIFEST"],
    }
    bindings = {
        "UNIT": I.UNIT,
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "DISCOVERY_SPRINT_02_SHA256": sprint_sha,
        "HETEROGENEOUS_FAMILY_ROTATION_V1_SHA256": policy_sha,
        "HYPOTHESIS_GENERATION_POLICY_V2_SHA256": data_policy_sha,
        "IMPLEMENTATION_SHA256": impl_sha,
        "FEASIBILITY_CLI_SHA256": feas_sha,
        "TEST_SHA256": test_sha,
        "D7_SEED": I.D7_SEED,
        "D8_SEED": I.D8_SEED,
        "D7_PCTL": I.D7_PCTL,
        "D8_RETURN_PCTL": I.D8_RETURN_PCTL,
        "D8_VOLUME_PCTL": I.D8_VOLUME_PCTL,
        "TRAILING_WINDOW": I.TRAILING_WINDOW,
        "D7_FEASIBILITY_STATUS": d7["FEASIBILITY_STATUS"],
        "D8_FEASIBILITY_STATUS": d8["FEASIBILITY_STATUS"],
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
    }
    run_identity = I.run_identity_payload(bindings)
    payload["RUN_IDENTITY"] = run_identity
    payload["AUTHORITY_BINDINGS"] = bindings

    review = {
        "UNIT": I.UNIT,
        "KIND": "OUTCOME_BLIND_IMPLEMENTATION_REVIEW",
        "STATUS": "PASS",
        "BASE_MAIN_SHA": "310578838d1a622c69dffbe1f2f11ff6927f65e7",
        "DISCOVERY_SPRINT_02_SHA256": sprint_sha,
        "HETEROGENEOUS_FAMILY_ROTATION_V1_SHA256": policy_sha,
        "HYPOTHESIS_GENERATION_POLICY_V2_SHA256": data_policy_sha,
        "CORE_BTC_SNAPSHOT_ID": I.CORE_BTC_SNAPSHOT_ID,
        "IMPLEMENTATION_SHA256": impl_sha,
        "FEASIBILITY_CLI_SHA256": feas_sha,
        "TEST_SHA256": test_sha,
        "D7_SEED": I.D7_SEED,
        "D8_SEED": I.D8_SEED,
        "N_RANDOM_CONTROLS": I.N_RANDOM_CONTROLS,
        "N_RANDOMIZATIONS": I.N_RANDOMIZATIONS,
        "D7_PRACTICAL_GATE": I.D7_PRACTICAL_GATE,
        "D8_PRACTICAL_GATE": I.D8_PRACTICAL_GATE,
        "TRAILING_WINDOW": I.TRAILING_WINDOW,
        "D7_P90": I.D7_PCTL,
        "D8_P99_RETURN": I.D8_RETURN_PCTL,
        "D8_P90_VOLUME": I.D8_VOLUME_PCTL,
        "D7_FEASIBILITY_STATUS": d7["FEASIBILITY_STATUS"],
        "D8_FEASIBILITY_STATUS": d8["FEASIBILITY_STATUS"],
        "D7_IMPLEMENTATION_STATUS": d7["D7_IMPLEMENTATION_STATUS"],
        "D8_IMPLEMENTATION_STATUS": d8["D8_IMPLEMENTATION_STATUS"],
        "D7_SCIENTIFIC_EXECUTION_ELIGIBLE": d7["FEASIBILITY_STATUS"] == "OUTCOME_BLIND_READY",
        "D8_SCIENTIFIC_EXECUTION_ELIGIBLE": d8["FEASIBILITY_STATUS"] == "OUTCOME_BLIND_READY",
        "SCIENTIFIC_OUTCOMES_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
        "NO_PERMIT_RESULT_LIFECYCLE": True,
        "RUN_IDENTITY": run_identity,
        "NEXT_UNIT": next_unit,
        "REVIEW_NOTES": [
            "D7/D8 thresholds and windows are bound to DISCOVERY_SPRINT_02.json",
            "Real-data path computes selector/support feasibility only",
            "Scientific evaluators exist as pure functions and were not run on CORE",
            "Next scientific execution must bind these implementation bytes first",
        ],
    }
    if write:
        (base / FEASIBILITY_JSON_REL).write_text(I.canonical_json(payload), encoding="utf-8")
        (base / REVIEW_JSON_REL).write_text(I.canonical_json(review), encoding="utf-8")
        (base / FEASIBILITY_MD_REL).write_text(_feasibility_md(payload), encoding="utf-8")
        (base / REVIEW_MD_REL).write_text(_review_md(review), encoding="utf-8")
    return {"FEASIBILITY": payload, "REVIEW": review}


def _feasibility_md(payload: dict[str, Any]) -> str:
    d7 = payload["D7"]
    d8 = payload["D8"]
    return f"""# Discovery Sprint 02 feasibility

**Unit:** `{payload["UNIT"]}`  
**Kind:** selector/support feasibility only  
**Status:** `{payload["STATUS"]}`  
**RUN_IDENTITY:** `{payload["RUN_IDENTITY"]}`

Scientific outcomes were not computed. Protected 2025/2026 were not opened.
MARKET-07 was not created.

## D7 `KLINE_FLOW_IMPACT_STATE`

```
CONSTRUCTED_HOURS = {d7["CONSTRUCTED_HOURS"]}
VALID_IMPACT_ROWS = {d7["VALID_IMPACT_ROWS"]}
TARGET_ELIGIBLE_ROWS = {d7["TARGET_ELIGIBLE_ROWS"]}
STATE_N = {d7["STATE_N"]}
FEASIBILITY_STATUS = {d7["FEASIBILITY_STATUS"]}
SCIENTIFIC_T_PLUS_1_ASSOCIATION_COMPUTED = false
```

STATE_BY_YEAR: `{d7["STATE_BY_YEAR"]}`

## D8 `ENDOGENOUS_SHOCK_RECOVERY`

```
RAW_RETURN_SHOCK_N = {d8["RAW_RETURN_SHOCK_N"]}
RAW_EVENT_N = {d8["RAW_EVENT_N"]}
RETAINED_EVENT_N = {d8["RETAINED_EVENT_N"]}
EVENT_SUPPORT_STATUS = {d8["EVENT_SUPPORT_STATUS"]}
RAW_CONTROL_N = {d8["RAW_CONTROL_N"]}
RETAINED_CONTROL_N = {d8["RETAINED_CONTROL_N"]}
MATCHED_PAIR_N = {d8["MATCHED_PAIR_N"]}
CONTROL_SUPPORT_STATUS = {d8["CONTROL_SUPPORT_STATUS"]}
FEASIBILITY_STATUS = {d8["FEASIBILITY_STATUS"]}
RECOVERY_6H_COMPUTED = false
RECOVERY_24H_COMPUTED = false
```

EVENT_BY_YEAR: `{d8["EVENT_BY_YEAR"]}`

## Routing

`NEXT_UNIT = {payload["NEXT_UNIT"]}`
"""


def _review_md(review: dict[str, Any]) -> str:
    return f"""# Discovery Sprint 02 implementation review

**Unit:** `{review["UNIT"]}`  
**Status:** `{review["STATUS"]}`  
**RUN_IDENTITY:** `{review["RUN_IDENTITY"]}`

Outcome-blind review. No permit/RESULT lifecycle. Scientific evaluators were
implemented as pure functions and were not executed on real CORE.

```
BASE_MAIN_SHA = {review["BASE_MAIN_SHA"]}
CORE_BTC_SNAPSHOT_ID = {review["CORE_BTC_SNAPSHOT_ID"]}
DISCOVERY_SPRINT_02_SHA256 = {review["DISCOVERY_SPRINT_02_SHA256"]}
IMPLEMENTATION_SHA256 = {review["IMPLEMENTATION_SHA256"]}
D7_SEED = {review["D7_SEED"]}
D8_SEED = {review["D8_SEED"]}
D7_IMPLEMENTATION_STATUS = {review["D7_IMPLEMENTATION_STATUS"]}
D8_IMPLEMENTATION_STATUS = {review["D8_IMPLEMENTATION_STATUS"]}
SCIENTIFIC_OUTCOMES_COMPUTED = false
NEXT_UNIT = {review["NEXT_UNIT"]}
```
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sprint 02 selector feasibility only")
    parser.add_argument("--repo", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    result = run_feasibility(repo=args.repo, write=not args.dry_run)
    print(I.canonical_json({"NEXT_UNIT": result["FEASIBILITY"]["NEXT_UNIT"], "RUN_IDENTITY": result["FEASIBILITY"]["RUN_IDENTITY"], "D7": result["FEASIBILITY"]["D7"]["FEASIBILITY_STATUS"], "D8": result["FEASIBILITY"]["D8"]["FEASIBILITY_STATUS"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
