"""Recompile the sealed C033 V1 planning object under GV0R02 compiler V2.

The planning file is not rewritten. Support counts are copied from the
outcome-blind fields already recorded there. No market target is computed
and no stopping-rule number is added.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.research.generator_v0.feasibility_contract_v1 import to_compiler_proposal_v1
from scripts.research.gv0r02_feasibility_compiler_v2 import compile_proposal_v2

REPO = Path(__file__).resolve().parents[2]
PLANNING_PATH = REPO / "docs/research/GV0V03L40_C033_V1_PLANNING.json"
RESULT_PATH = REPO / "docs/research/GV0V03L40_C033_V2_FEASIBILITY.json"
RESULT_MD_PATH = REPO / "docs/research/GV0V03L40_C033_V2_FEASIBILITY.md"

FROZEN_PRIMARY = {
    "POST_WINDOW_H": 6,
    "PRIMARY_CELLS": 1,
    "SHOCK_SIGMA": 3,
    "TAKER_BAND": "p1_p99",
}
FROZEN_STOPPING_RULE = {
    "COUNTS_ONLY_MONITORING": True,
    "END_DATE": "2028-12-31",
    "MAX_EPISODES": 1500,
    "MIN_N": 1000,
    "PRODUCT_EXPOSURE_HANDLING": (
        "hidden from product users until the stopping rule fires and the replication "
        "result is separately authorized"
    ),
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_sealed_design(planning: dict) -> None:
    if planning.get("PRIMARY_FREEZE") != FROZEN_PRIMARY:
        raise RuntimeError("sealed C033 primary freeze differs from the recorded design")
    effect = (planning.get("EXPECTED_EFFECT") or {}).get("MIN_MEANINGFUL_EFFECT")
    if effect != 0.2:
        raise RuntimeError("sealed C033 minimum effect differs from 0.20")
    rule = ((planning.get("REPLICATION_SURFACE") or {}).get("STOPPING_RULE"))
    if rule != FROZEN_STOPPING_RULE:
        raise RuntimeError("sealed C033 stopping rule differs from the recorded declaration")
    if "MIN_MECHANISM_ACTIVE_N" in rule or "MIN_MECHANISM_INACTIVE_N" in rule:
        raise RuntimeError("sealed C033 stopping rule must not gain mechanism floors in this repair")


def mechanism_support_from_sealed(planning: dict) -> dict:
    """Copy the recorded zero joint count onto the nominal kept-shock sample."""
    counts = planning["OUTCOME_BLIND_COUNTS"]
    nominal = planning["NOMINAL_OBSERVATION_COUNT_CONSTRUCTION"]["DECLARED_NOMINAL_COUNT"]
    active = counts["TOTAL_ALL4_EVENTS"]
    if active != 0:
        raise RuntimeError("sealed C033 joint count is not the recorded zero")
    if nominal != counts["DEPENDENCE_CLUSTER_COUNT"]:
        raise RuntimeError("sealed nominal count and cluster count disagree")
    return {
        "KIND": "BINARY",
        "MECHANISM_VARIABLE": planning["PRIMARY_OBSERVABLE"],
        "MECHANISM_ACTIVE_N": active,
        "MECHANISM_INACTIVE_N": nominal,
    }


def compile_sealed_planning(planning: dict) -> dict:
    before = json.dumps(planning, sort_keys=True)
    assert_sealed_design(planning)
    proposal = to_compiler_proposal_v1(planning)
    proposal["COMPILER_SCHEMA_VERSION"] = "GV0R02_SCHEMA_V2"
    proposal["COMPILER_POLICY_VERSION"] = "GV0R02_POLICY_V2"
    proposal["PRIMARY_MECHANISM_SUPPORT"] = [mechanism_support_from_sealed(planning)]
    result = compile_proposal_v2(proposal)
    if json.dumps(planning, sort_keys=True) != before:
        raise RuntimeError("sealed planning object changed during V2 compile")
    support = result["PRIMARY_MECHANISM_SUPPORT"][0]
    status = result["FEASIBILITY_STATUS"]
    return {
        **result,
        "MECHANISM_ACTIVE_N": support["MECHANISM_ACTIVE_N"],
        "MECHANISM_INACTIVE_N": support["MECHANISM_INACTIVE_N"],
        "C033_NEXT": (
            "PREREGISTRATION_DESIGN"
            if status == "FEASIBLE_FOR_PREREGISTRATION"
            else "STOP / NOT_PREREGISTRABLE_UNDER_FROZEN_DESIGN"
        ),
        "MARKET_OUTCOMES_OPENED": False,
        "PROTECTED_2025_2026_OPENED": False,
        "SCIENTIFIC_DESIGN_CHANGED": False,
        "SOURCE_PLANNING": "docs/research/GV0V03L40_C033_V1_PLANNING.json",
    }


def _literal(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def render_markdown(result: dict) -> str:
    codes = ", ".join(b["BLOCKER_CODE"] for b in result["BLOCKERS"]) or "(none)"
    screen = result["DISCOVERY_SCREEN"]
    return f"""# GV0V03L40 C033 V2 feasibility

**Status:** `{result["FEASIBILITY_STATUS"]}`
**Date:** 2026-10-02

```
COMPILER_SCHEMA = {result["COMPILER_SCHEMA_VERSION"]}
COMPILER_POLICY = {result["COMPILER_POLICY_VERSION"]}
C033_NEXT = {result["C033_NEXT"]}
MECHANISM_ACTIVE_N = {result["MECHANISM_ACTIVE_N"]}
MECHANISM_INACTIVE_N = {result["MECHANISM_INACTIVE_N"]}
ALPHA_ATTAINABLE = {_literal(result["ALPHA_ATTAINABLE"])}
MIN_ATTAINABLE_P = {result["MIN_ATTAINABLE_P"]}
PRIMARY_LABEL_ORBIT_SIZE = {result["PRIMARY_LABEL_ORBIT_SIZE"]}
MDE_STRESS = {_literal(screen["MDE_STRESS"])}
POWER_STRESS = {_literal(screen["POWER_STRESS"])}
MARKET_OUTCOMES_OPENED = false
PROTECTED_2025_2026_OPENED = false
SCIENTIFIC_DESIGN_CHANGED = false
LLM_CALLS = 0
```

This is a recompile of the sealed V1 planning object under the stricter V2 compiler.
The primary cell, components, nuisance set, discovery window and prospective
stopping rule are the sealed declaration. No stopping floor was added.
`MECHANISM_ACTIVE_N = 0` is the recorded all-four count. It is an
outcome-blind support failure. It is not evidence about the market mechanism.

The headline status is `DEFINITION_INCOMPLETE` because the sealed prospective
stopping rule does not declare `MIN_MECHANISM_ACTIVE_N` and
`MIN_MECHANISM_INACTIVE_N`. `PRIMARY_MECHANISM_SUPPORT_ZERO` and
`ALPHA_UNATTAINABLE` are also present. Those two sit in
`INFERENCE_SUPPORT_INSUFFICIENT`, which the existing status order ranks
below a definition gap. No new top-level status was added.

The V1 artifact `GV0V03L40_C033_V1_FEASIBILITY.json` remains the V1 compiler
output, including its `FEASIBLE_FOR_PREREGISTRATION` status.

```
BLOCKERS = {codes}
```
"""


def write_result(planning_bytes: bytes, result: dict) -> dict:
    payload = {**result, "SOURCE_PLANNING_SHA256": _sha256(planning_bytes)}
    RESULT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    RESULT_MD_PATH.write_text(render_markdown(payload))
    return payload


def main() -> None:
    raw = PLANNING_PATH.read_bytes()
    planning = json.loads(raw)
    result = write_result(raw, compile_sealed_planning(planning))
    if PLANNING_PATH.read_bytes() != raw:
        raise SystemExit("planning file bytes changed")
    print(json.dumps({
        "FEASIBILITY_STATUS": result["FEASIBILITY_STATUS"],
        "BLOCKERS": [b["BLOCKER_CODE"] for b in result["BLOCKERS"]],
        "C033_NEXT": result["C033_NEXT"],
        "ALPHA_ATTAINABLE": result["ALPHA_ATTAINABLE"],
        "MIN_ATTAINABLE_P": result["MIN_ATTAINABLE_P"],
        "MDE_STRESS": result["DISCOVERY_SCREEN"]["MDE_STRESS"],
        "POWER_STRESS": result["DISCOVERY_SCREEN"]["POWER_STRESS"],
        "MECHANISM_ACTIVE_N": result["MECHANISM_ACTIVE_N"],
        "MECHANISM_INACTIVE_N": result["MECHANISM_INACTIVE_N"],
    }, indent=2))


if __name__ == "__main__":
    main()
