"""Write D2 BitMEX integrity-adjudication artifacts.

Does not compute D2 effect metrics. Does not rewrite the INVALID result
or the original prereg.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts.research.d2_bitmex_pre2020 import sha256_bytes
from scripts.research.d2_bitmex_replication_evaluator import compute_run_identity
from scripts.research.d2_bitmex_replication_integrity_diagnostic import (
    dropped_timestamp_complete_decisions,
)
from scripts.research.d2_bitmex_replication_prereg import file_sha256
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import (
    canonical_result_bytes,
    result_payload_sha256,
)

UNIT = "D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION"
ADJUDICATION_CLASS = "REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH"
ORIGINAL_RUN_IDENTITY = "b873d473e5d5ef1394d161d557b1e0ca7602bfa92e6d78d8e80df8f4d1493d71"
ORIGINAL_RESULT_PAYLOAD_SHA256 = "9af98e72e7afc2c3e8af7f2d359401110e1e9c9829e69185ab23519e06fba48a"
ORIGINAL_RESULT_COMMIT = "302674757eedc3015a0c570e6c88e5b60c7594a8"
ORIGINAL_PREREG_SHA256 = "939fe29243956195f2ca97723a7b94b666ce59359c55e096f8fba4d65c7d9044"
FROZEN_IMPLEMENTATION_SHA256 = "087e7ea5892f2ab81f26bd61c82b2709b6812b6916554e5c92846a52496d77aa"
FROZEN_CANONICAL_SHA256 = "b145013cbcda34294104a0234c89fa9e27965bded66e3bc18b23753dde03fd0f"
FROZEN_CANONICAL_GZ_SHA256 = "8e027433b528a8ee084a90690ff4b0c4f819d1f1b66c776d635cf466bd8e56fa"
FROZEN_SOURCE_AUTHORITY_SHA256 = "2a48e025a9ecb596f7a37646a39367cae031e5aa3fd0555416c3fab692594dff"
REPLICATION_RANDOM_SEED = 20260921125
ORIGINAL_EXPECTED_N = 1069
FROZEN_POWER_FLOOR = 815

ADJUDICATION_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.json"
ADJUDICATION_MD_REL = "docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.md"
AMENDMENT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.json"
AMENDMENT_MD_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.md"
RESULT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_RESULT.json"
PREREG_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG.json"


def _write_json(path: Path, payload: dict[str, Any]) -> str:
    data = bytes(canonical_result_bytes(payload))
    path.write_bytes(data)
    return sha256_bytes(data)


def build_amendment(diag: dict[str, Any]) -> dict[str, Any]:
    return {
        "unit": "D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1",
        "kind": "PREDECLARED_ELIGIBILITY_IDENTITY_AMENDMENT",
        "ORIGINAL_PREREG": PREREG_JSON_REL,
        "ORIGINAL_PREREG_ARTIFACT_SHA256": ORIGINAL_PREREG_SHA256,
        "ORIGINAL_INVALID_RUN": RESULT_JSON_REL,
        "ORIGINAL_RUN_IDENTITY": ORIGINAL_RUN_IDENTITY,
        "ORIGINAL_RESULT_COMMIT": ORIGINAL_RESULT_COMMIT,
        "ORIGINAL_RESULT_PAYLOAD_SHA256": ORIGINAL_RESULT_PAYLOAD_SHA256,
        "ORIGINAL_EXPECTED_N": ORIGINAL_EXPECTED_N,
        "ORIGINAL_EXPECTED_YEAR_ELIGIBLE_N": {"2017": 341, "2018": 364, "2019": 364},
        "CORRECTED_CONSTRUCTED_N": diag["SCIENTIFIC_CONSTRUCTED_N"],
        "CORRECTED_WARMUP_N": diag["SCIENTIFIC_WARMUP_N"],
        "CORRECTED_EXPECTED_N": diag["SCIENTIFIC_ELIGIBLE_N"],
        "CORRECTED_YEAR_ELIGIBLE_N": diag["SCIENTIFIC_YEAR_ELIGIBLE_N"],
        "CORRECTED_FIRST_T": diag["SCIENTIFIC_FIRST_T"],
        "CORRECTED_LAST_T": diag["SCIENTIFIC_LAST_T"],
        "EXACT_REASON_FOR_AMENDMENT": (
            "ORIGINAL_EXPECTED_N counted timestamp-complete decisions. "
            "Frozen construct_discovery_row already excludes BTC_RET_24H_EQ_0. "
            "Two timestamp-complete decisions are ineligible under that "
            "predeclared rule. Historical prereg bytes are preserved."
        ),
        "DROPPED_ROWS": diag["DROPPED"],
        "SCIENTIFIC_RULE_CHANGED": False,
        "TARGET_CHANGED": False,
        "THRESHOLD_CHANGED": False,
        "COMPARATOR_CHANGED": False,
        "DATA_CHANGED": False,
        "SEED_CHANGED": False,
        "REPLICATION_RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "ORIGINAL_PREREG_REWRITTEN": False,
        "ORIGINAL_INVALID_RUN_REWRITTEN": False,
        "ORIGINAL_RERUN_AUTHORIZED": False,
        "EXECUTION_AUTHORIZED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "MARKET_07_CREATED": False,
    }


def build_adjudication(
    diag: dict[str, Any],
    *,
    amendment_sha256: str,
    new_run_identity: str,
    identity_inputs: dict[str, Any],
) -> dict[str, Any]:
    eligible_n = int(diag["SCIENTIFIC_ELIGIBLE_N"])
    return {
        "unit": UNIT,
        "kind": "INTEGRITY_ADJUDICATION",
        "ADJUDICATION_CLASS": ADJUDICATION_CLASS,
        "ORIGINAL_INVALID_CLASSIFICATION": "D2_BITMEX_REPLICATION_INVALID",
        "ORIGINAL_RUN_IDENTITY": ORIGINAL_RUN_IDENTITY,
        "ORIGINAL_RESULT_COMMIT": ORIGINAL_RESULT_COMMIT,
        "ORIGINAL_RESULT_PAYLOAD_SHA256": ORIGINAL_RESULT_PAYLOAD_SHA256,
        "ORIGINAL_PREREG_ARTIFACT_SHA256": ORIGINAL_PREREG_SHA256,
        "ORIGINAL_EXPECTED_N": ORIGINAL_EXPECTED_N,
        "TIMESTAMP_CENSUS_N": 1069,
        "TIMESTAMP_COMPLETE_INCLUDING_WARMUP": diag["TIMESTAMP_COMPLETE_N"],
        "SCIENTIFIC_CONSTRUCTED_N": diag["SCIENTIFIC_CONSTRUCTED_N"],
        "SCIENTIFIC_WARMUP_N": diag["SCIENTIFIC_WARMUP_N"],
        "SCIENTIFIC_ELIGIBLE_N": eligible_n,
        "CORRECTED_CONSTRUCTED_N": diag["SCIENTIFIC_CONSTRUCTED_N"],
        "CORRECTED_WARMUP_N": diag["SCIENTIFIC_WARMUP_N"],
        "CORRECTED_ELIGIBLE_N": eligible_n,
        "CORRECTED_YEAR_ELIGIBLE_N": diag["SCIENTIFIC_YEAR_ELIGIBLE_N"],
        "CORRECTED_FIRST_T": diag["SCIENTIFIC_FIRST_T"],
        "CORRECTED_LAST_T": diag["SCIENTIFIC_LAST_T"],
        "DROPPED_ROWS": diag["DROPPED"],
        "TIMESTAMP_COMPLETE_VS_SCIENTIFIC_ELIGIBLE": {
            "TIMESTAMP_COMPLETE_DECISION": (
                "00:05Z decisions whose feature, entry, and 24h future 5m "
                "timestamps exist. Frozen census N=1069 after 250 warmup."
            ),
            "SCIENTIFICALLY_ELIGIBLE_D2_ROW": (
                "timestamp-complete AND construct_discovery_row succeeds, "
                "including frozen BTC_RET_24H==0 and RV<=0 ineligibility."
            ),
            "EXPECTED_ELIGIBLE_N_1069_WAS_TIMESTAMP_CENSUS_ONLY": True,
            "EXPECTED_ELIGIBLE_N_MECHANICALLY_WRONG_BEFORE_EXECUTION": True,
        },
        "TRAILING_HISTORY_AUTHORITY": "VALID_CONSTRUCTED_ROWS",
        "TRAILING_HISTORY_AUTHORITY_SOURCE": (
            "scripts/research/discovery_sprint_01/common.py::rv_abstention_mask "
            "indexes previous 250 DiscoveryRow objects produced by "
            "construct_discovery_row; None rows never enter the sequence."
        ),
        "ORIGINAL_PRIMARY_OUTCOME_COMPUTED": False,
        "ORIGINAL_RANDOM_CONTROLS_COMPUTED": False,
        "ARITHMETIC_MAE_COMPUTED_IN_DIAGNOSTIC": False,
        "SCIENTIFIC_RULE_CHANGED": False,
        "TARGET_CHANGED": False,
        "THRESHOLD_CHANGED": False,
        "COMPARATOR_CHANGED": False,
        "DATA_CHANGED": False,
        "SEED_CHANGED": False,
        "REPLICATION_RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "CAPACITY_ABOVE_FROZEN_POWER_FLOOR": bool(eligible_n > FROZEN_POWER_FLOOR),
        "FROZEN_MIN_REQUIRED_FRESH_DECISION_ROWS": FROZEN_POWER_FLOOR,
        "POWER_RESEARCH_PERFORMED": False,
        "ORIGINAL_RERUN_AUTHORIZED": False,
        "CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE": True,
        "NEW_RUN_IDENTITY": new_run_identity,
        "NEW_RUN_IDENTITY_INPUTS": identity_inputs,
        "PREREG_AMENDMENT_REL": AMENDMENT_JSON_REL,
        "PREREG_AMENDMENT_SHA256": amendment_sha256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
        "EXECUTION_AUTHORIZED": False,
        "EXECUTION_PERMIT_CREATED": False,
        "D2_DISCOVERY_STATUS": "PROMISING_PROTOTYPE",
        "D2_REPLICATION_STATUS": "INTEGRITY_REPAIR_PENDING_CORRECTED_EXECUTION",
        "CLASSIFICATION_ASSIGNED": None,
        "NOT_SUPPORTED": False,
        "NOT_SUPPORTED_MARKED": False,
        "SUPPORTED_MARKED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "MARKET_07_CREATED": False,
        "RED_TEAM": {
            "A1_EXCLUSION_REASONS_DETERMINISTIC": {
                "status": "PASS",
                "note": "Both drops are BTC_RET_24H_EQ_0 from frozen btc_ret_24h.",
            },
            "A2_RULES_PREDATE_BITMEX_OUTCOME_INSPECTION": {
                "status": "PASS",
                "note": "BTC_RET_24H_EQ_0 is frozen MARKET-06/D2 construct_discovery_row eligibility. Prereg zero_return_rows_ineligible=true.",
            },
            "A3_CANDIDATE_RULE_UNCHANGED": {
                "status": "PASS",
                "note": "RULE_1 RV_ABSTENTION P90/trailing-250 unchanged.",
            },
            "A4_TARGET_UNCHANGED": {
                "status": "PASS",
                "note": "BTC_SIDE and arithmetic_mae target unchanged; MAE was not computed.",
            },
            "A5_NO_CANDIDATE_CONTROL_RESULT_BEFORE_INVALID": {
                "status": "PASS",
                "note": "Invalid RESULT primary metrics are null; D2_BITMEX_OUTCOME_COMPUTED=false.",
            },
            "A6_RANDOM_CONTROLS_DID_NOT_RUN": {
                "status": "PASS",
                "note": "MU_CONTROL_MEAN and MC_P are null on the invalid RESULT.",
            },
            "A7_CORRECTION_SIGN_INDEPENDENT": {
                "status": "PASS",
                "note": "No D2 effect was observed. Identity correction is mechanical.",
            },
            "A8_ORIGINAL_D2_DISCOVERY_SAME_ELIGIBILITY": {
                "status": "PASS",
                "note": "D2 discovery build_rows uses the same construct_discovery_row kernel.",
            },
            "A9_PROTECTED_YEARS_SEALED": {
                "status": "PASS",
                "note": "2025/2026 unopened.",
            },
            "A10_CANONICAL_DATA_UNCHANGED": {
                "status": "PASS",
                "note": "BitMEX canonical SHA256 unchanged.",
            },
        },
        "OUTCOME_BLINDNESS_COMPROMISED": False,
        "NEXT_UNIT": "D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT",
    }


def render_adjudication_md(payload: dict[str, Any]) -> str:
    dropped = payload["DROPPED_ROWS"]
    years = payload["CORRECTED_YEAR_ELIGIBLE_N"]
    return f"""# D2 BitMEX replication integrity adjudication

**Unit:** `{payload["unit"]}`  
**Class:** `{payload["ADJUDICATION_CLASS"]}`

The original one-shot remains canonical history:

`D2_BITMEX_REPLICATION_INVALID`

Its RESULT bytes are not rewritten. `ORIGINAL_RERUN_AUTHORIZED = false`.

## Dropped timestamp-complete decisions

Exactly two timestamp-complete decisions fail frozen scientific row
construction. Both fail the predeclared `BTC_RET_24H == 0` ineligibility
rule inside frozen `btc_ret_24h` / `construct_discovery_row`. No raw
prices are reproduced here.

- `{dropped[0]["DROP_TIMESTAMP"]}` (`{dropped[0]["DROP_YEAR"]}`): `{dropped[0]["EXACT_INELIGIBILITY_REASON"]}`
- `{dropped[1]["DROP_TIMESTAMP"]}` (`{dropped[1]["DROP_YEAR"]}`): `{dropped[1]["EXACT_INELIGIBILITY_REASON"]}`

The diagnostic stops before `arithmetic_mae` / adverse severity. No
RV_ABSTENTION K, MU_RULE, controls, or gates were computed.

## Census vs scientific sample

`TIMESTAMP_COMPLETE_DECISION` is a 00:05Z decision whose feature, entry,
and 24h future 5m timestamps exist. The frozen census used that definition
and bound `EXPECTED_ELIGIBLE_N = 1069`.

`SCIENTIFICALLY_ELIGIBLE_D2_ROW` additionally requires frozen
`construct_discovery_row` success, including `BTC_RET_24H_EQ_0` and
`RV_LE_0_OR_NONFINITE`. That definition is older than the BitMEX run
(`zero_return_rows_ineligible = true` in the original prereg; same kernel
as D2 discovery).

`EXPECTED_ELIGIBLE_N = 1069` was therefore mechanically wrong before
execution: it counted timestamp-complete rows that the already-frozen
scientific constructor must drop. This is not an implementation bug, not
source corruption, and not a new post-outcome scientific choice.

## Trailing-250 authority

`TRAILING_HISTORY_AUTHORITY = VALID_CONSTRUCTED_ROWS`

Original D2 discovery `rv_abstention_mask` takes P90 over the previous 250
`DiscoveryRow` objects returned by `construct_discovery_row`. Rows that
return `None` never enter that sequence. The BitMEX evaluator reuses that
mask. Not timestamp-complete calendar decisions.

## Corrected sample identity

```
CORRECTED_CONSTRUCTED_N = {payload["CORRECTED_CONSTRUCTED_N"]}
CORRECTED_WARMUP_N = {payload["CORRECTED_WARMUP_N"]}
CORRECTED_ELIGIBLE_N = {payload["CORRECTED_ELIGIBLE_N"]}
CORRECTED_YEAR_2017_N = {years["2017"]}
CORRECTED_YEAR_2018_N = {years["2018"]}
CORRECTED_YEAR_2019_N = {years["2019"]}
CORRECTED_FIRST_T = {payload["CORRECTED_FIRST_T"]}
CORRECTED_LAST_T = {payload["CORRECTED_LAST_T"]}
```

`{payload["CORRECTED_ELIGIBLE_N"]} > {payload["FROZEN_MIN_REQUIRED_FRESH_DECISION_ROWS"]}`
(frozen feasibility floor). Power was not recomputed.

## Repair semantics

```
SCIENTIFIC_RULE_CHANGED = {payload["SCIENTIFIC_RULE_CHANGED"]}
TARGET_CHANGED = {payload["TARGET_CHANGED"]}
THRESHOLD_CHANGED = {payload["THRESHOLD_CHANGED"]}
COMPARATOR_CHANGED = {payload["COMPARATOR_CHANGED"]}
DATA_CHANGED = {payload["DATA_CHANGED"]}
ORIGINAL_PRIMARY_OUTCOME_COMPUTED = {payload["ORIGINAL_PRIMARY_OUTCOME_COMPUTED"]}
ORIGINAL_RANDOM_CONTROLS_COMPUTED = {payload["ORIGINAL_RANDOM_CONTROLS_COMPUTED"]}
ORIGINAL_RERUN_AUTHORIZED = {payload["ORIGINAL_RERUN_AUTHORIZED"]}
CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE = {payload["CORRECTED_EXECUTION_SCIENTIFICALLY_PERMISSIBLE"]}
REPLICATION_RANDOM_SEED = {payload["REPLICATION_RANDOM_SEED"]}
NEW_RUN_IDENTITY = {payload["NEW_RUN_IDENTITY"]}
EXECUTION_AUTHORIZED = {payload["EXECUTION_AUTHORIZED"]}
```

A corrected execution is a new integrity-repair lineage, not a rescue
rerun of `b873d473…`. No execution permit is created in this unit.

## Program flags

```
D2_DISCOVERY_STATUS = {payload["D2_DISCOVERY_STATUS"]}
D2_REPLICATION_STATUS = {payload["D2_REPLICATION_STATUS"]}
PROTECTED_2025_OPENED = {payload["PROTECTED_2025_OPENED"]}
PROTECTED_2026_OPENED = {payload["PROTECTED_2026_OPENED"]}
MARKET_07_CREATED = {payload["MARKET_07_CREATED"]}
NEXT_UNIT = {payload["NEXT_UNIT"]}
```
"""


def render_amendment_md(payload: dict[str, Any]) -> str:
    years = payload["CORRECTED_YEAR_ELIGIBLE_N"]
    return f"""# D2 BitMEX replication prereg amendment V1

**Unit:** `{payload["unit"]}`  
**Kind:** identity amendment only. Historical prereg bytes are unchanged.

The original prereg remains the frozen historical contract that produced
the INVALID run. This amendment records the mechanically corrected
scientific sample identity for a possible later integrity-repair
execution. It does not change the candidate rule, target, threshold,
comparator, data, or seed.

```
ORIGINAL_RUN_IDENTITY = {payload["ORIGINAL_RUN_IDENTITY"]}
ORIGINAL_EXPECTED_N = {payload["ORIGINAL_EXPECTED_N"]}
CORRECTED_EXPECTED_N = {payload["CORRECTED_EXPECTED_N"]}
CORRECTED_YEAR_2017_N = {years["2017"]}
CORRECTED_YEAR_2018_N = {years["2018"]}
CORRECTED_YEAR_2019_N = {years["2019"]}
CORRECTED_FIRST_T = {payload["CORRECTED_FIRST_T"]}
CORRECTED_LAST_T = {payload["CORRECTED_LAST_T"]}
SCIENTIFIC_RULE_CHANGED = {payload["SCIENTIFIC_RULE_CHANGED"]}
TARGET_CHANGED = {payload["TARGET_CHANGED"]}
THRESHOLD_CHANGED = {payload["THRESHOLD_CHANGED"]}
COMPARATOR_CHANGED = {payload["COMPARATOR_CHANGED"]}
DATA_CHANGED = {payload["DATA_CHANGED"]}
REPLICATION_RANDOM_SEED = {payload["REPLICATION_RANDOM_SEED"]}
EXECUTION_AUTHORIZED = {payload["EXECUTION_AUTHORIZED"]}
ORIGINAL_RERUN_AUTHORIZED = {payload["ORIGINAL_RERUN_AUTHORIZED"]}
```

`EXACT_REASON_FOR_AMENDMENT`: {payload["EXACT_REASON_FOR_AMENDMENT"]}
"""


def main() -> None:
    repo = C.repo_root()
    result = json.loads((repo / RESULT_JSON_REL).read_text(encoding="utf-8"))
    if result["CLASSIFICATION"] != "D2_BITMEX_REPLICATION_INVALID":
        raise RuntimeError("ORIGINAL_RESULT_NOT_INVALID")
    if result["D2_BITMEX_OUTCOME_COMPUTED"] is not False:
        raise RuntimeError("ORIGINAL_PRIMARY_OUTCOME_COMPUTED")
    if result["PRIMARY_METRICS"]["MU_CONTROL_MEAN"] is not None:
        raise RuntimeError("ORIGINAL_RANDOM_CONTROLS_COMPUTED")
    if result["RESULT_PAYLOAD_SHA256"] != ORIGINAL_RESULT_PAYLOAD_SHA256:
        raise RuntimeError("ORIGINAL_RESULT_SHA_DRIFT")
    if file_sha256(repo / PREREG_JSON_REL) != ORIGINAL_PREREG_SHA256:
        raise RuntimeError("ORIGINAL_PREREG_SHA_DRIFT")
    diag = dropped_timestamp_complete_decisions(repo)
    if len(diag["DROPPED"]) != 2:
        raise RuntimeError(f"DROPPED_N:{len(diag['DROPPED'])}")
    for row in diag["DROPPED"]:
        if row["EXACT_INELIGIBILITY_REASON"] != "BTC_RET_24H_EQ_0":
            raise RuntimeError(f"UNEXPECTED_REASON:{row}")
    amendment = build_amendment(diag)
    amendment_sha = _write_json(repo / AMENDMENT_JSON_REL, amendment)
    (repo / AMENDMENT_MD_REL).write_text(render_amendment_md(amendment), encoding="utf-8")
    identity_inputs = {
        "ORIGINAL_INVALID_RUN_IDENTITY": ORIGINAL_RUN_IDENTITY,
        "ORIGINAL_RESULT_PAYLOAD_SHA256": ORIGINAL_RESULT_PAYLOAD_SHA256,
        "PREREG_AMENDMENT_SHA256": amendment_sha,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_SHA256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "CORRECTED_ELIGIBLE_N": diag["SCIENTIFIC_ELIGIBLE_N"],
        "CORRECTED_FIRST_T": diag["SCIENTIFIC_FIRST_T"],
        "CORRECTED_LAST_T": diag["SCIENTIFIC_LAST_T"],
        "CORRECTED_YEAR_ELIGIBLE_N": diag["SCIENTIFIC_YEAR_ELIGIBLE_N"],
        "ADJUDICATION_CLASS": ADJUDICATION_CLASS,
        "DROPPED_ROWS": diag["DROPPED"],
    }
    new_run_identity = compute_run_identity(identity_inputs)
    adjudication = build_adjudication(
        diag,
        amendment_sha256=amendment_sha,
        new_run_identity=new_run_identity,
        identity_inputs=identity_inputs,
    )
    adj_sha = result_payload_sha256(
        {k: v for k, v in adjudication.items() if k != "ADJUDICATION_PAYLOAD_SHA256"}
    )
    adjudication["ADJUDICATION_PAYLOAD_SHA256"] = adj_sha
    _write_json(repo / ADJUDICATION_JSON_REL, adjudication)
    (repo / ADJUDICATION_MD_REL).write_text(
        render_adjudication_md(adjudication), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
