"""Write the outcome-blind D2 BitMEX implementation-review artifacts.

Does not execute scientific BitMEX outcomes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from scripts.research.d2_bitmex_pre2020 import AUTHORITY_REL, sha256_bytes
from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_INVALID,
    CLASS_NOT_SUPPORTED,
    CLASS_SUPPORTED,
    EXECUTION_AUTHORIZED,
    EXECUTION_PERMIT_REL,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
    N_REPLICATES,
    REPLICATION_RANDOM_SEED,
    compute_run_identity,
    current_implementation_file_sha256,
    verify_eligibility,
)
from scripts.research.d2_bitmex_replication_prereg import (
    BINDING_REL,
    FROZEN_EXPECTED_ELIGIBLE_N,
    FROZEN_FIRST_RULE_ELIGIBLE_T,
    FROZEN_LAST_RULE_ELIGIBLE_T,
    IMPLEMENTATION_FILES,
    JSON_REL,
)
from scripts.research.discovery_sprint_01 import common as C

UTC_ISO = "%Y-%m-%dT%H:%M:%S.000Z"
REVIEW_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.json"
REVIEW_MD_REL = "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.md"

ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256 = {
    "scripts/research/d2_bitmex_pre2020.py": "f0c16c8e120fd6813039abf09421a41ed01f741fe699e1e9df41e9105ca86056",
    "scripts/research/d2_bitmex_replication_evaluator.py": "e132f5ee24029b18aa971c4dda6a2e453282038a9527d8362d6656ecd40b75de",
    "scripts/research/discovery_sprint_01/common.py": "ab152da63fa8c923fba3fd0255b7cd4d6457389b6a45be9959abc7235fa912ef",
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py": "ff87062edf583af1a67affcc18cda5e184379d9e63f7ff8b0e18383978890ead",
}

RED_TEAM = {
    "F1_LOOKAHEAD": {
        "status": "NOT_CONFIRMED",
        "note": "Features use frozen feature_cutoff E=T-5m and bars ending at E via construct_discovery_row.",
    },
    "F2_ENTRY_OVERLAP": {
        "status": "NOT_CONFIRMED",
        "note": "Entry uses get_perp_bar_opening_at(T). Feature close uses the bar that ended at E, a different open.",
    },
    "F3_OUTCOME_OVERLAP": {
        "status": "NOT_CONFIRMED",
        "note": "Future path is 288 bars opening at T, T+5m, ... through T+287*5m via frozen construct_discovery_row.",
    },
    "F4_BITMEX_TIMESTAMP": {
        "status": "NOT_CONFIRMED",
        "note": "Canonical rows are keyed by open_time_ms = official bucket-end timestamp minus 5m. Tests refuse keying by bucket end.",
    },
    "F5_GAP_LEAKAGE": {
        "status": "NOT_CONFIRMED",
        "note": "No fill. Missing feature or future open makes construct_discovery_row return None. Timestamp census still 1069.",
    },
    "F6_ROLLING_HISTORY": {
        "status": "NOT_CONFIRMED",
        "note": "rv_abstention_mask uses previous 250 valid constructed rows, not 250 calendar days. Warmup cannot abstain.",
    },
    "F7_PERCENTILE": {
        "status": "NOT_CONFIRMED",
        "note": "P90 of prior 250, t excluded, strict >. Equality does not fire.",
    },
    "F8_INVERSE_CONTRACT": {
        "status": "NOT_CONFIRMED",
        "note": "Severity is frozen arithmetic_mae last-trade price-path MAE, not inverse PnL, mark, index, or funding.",
    },
    "F9_COMPARATOR": {
        "status": "NOT_CONFIRMED",
        "note": "Controls draw exact K_y within each of 2017/2018/2019. Pooled-K sampling is not used.",
    },
    "F10_RNG": {
        "status": "NOT_CONFIRMED",
        "note": "numpy.random.Generator(numpy.random.PCG64(20260921125)). Matches frozen rate_matched_random_abstention masks.",
    },
    "F11_SAMPLE_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": "Timestamp census reproduces 1069 / 2017-01-24T00:05Z / 2019-12-30T00:05Z. Execution identity gate classifies INVALID on mismatch.",
    },
    "F12_RESULT_RESCUE": {
        "status": "NOT_CONFIRMED",
        "note": "classify_replication ignores yearly diagnostics. No 2/3-year gate. Discovery TEMPORAL_CONSISTENCY is not copied.",
    },
    "F13_AUTHORITY_DRIFT": {
        "status": "NOT_CONFIRMED",
        "note": "Sealed gz/jsonl/authority hashes fail closed. Reacquisition forbidden.",
    },
    "F14_ACCIDENTAL_OUTCOME_INSPECTION": {
        "status": "NOT_CONFIRMED",
        "note": "execute_replication and real OHLC load require a missing execution permit. No RESULT written.",
    },
}


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _iso(moment) -> str:
    return moment.strftime(UTC_ISO)


def build_review(*, repo: Path, implementation_commit: str | None) -> dict[str, Any]:
    census = verify_eligibility(repo=repo)
    if int(census["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"]) != FROZEN_EXPECTED_ELIGIBLE_N:
        raise RuntimeError("PREREG_N_DRIFT")
    impl = current_implementation_file_sha256(repo)
    if impl["scripts/research/d2_bitmex_replication_evaluator.py"] == ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256[
        "scripts/research/d2_bitmex_replication_evaluator.py"
    ]:
        raise RuntimeError("STUB_SHA_NOT_REPLACED")
    for rel in IMPLEMENTATION_FILES:
        if rel == "scripts/research/d2_bitmex_replication_evaluator.py":
            continue
        if impl[rel] != ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256[rel]:
            raise RuntimeError(f"UNEXPECTED_SCIENTIFIC_FILE_DRIFT:{rel}")
    prereg_sha = sha256_bytes((repo / JSON_REL).read_bytes())
    authority_sha = sha256_bytes((repo / AUTHORITY_REL).read_bytes())
    head = _git(repo, "rev-parse", "HEAD")
    tree = _git(repo, "rev-parse", "HEAD^{tree}")
    commit = implementation_commit or head
    identity_inputs = {
        "PREREG_ARTIFACT_SHA256": prereg_sha,
        "ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256": ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256,
        "FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256": impl,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": authority_sha,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "EXPECTED_N": FROZEN_EXPECTED_ELIGIBLE_N,
        "FIRST_T": _iso(FROZEN_FIRST_RULE_ELIGIBLE_T),
        "LAST_T": _iso(FROZEN_LAST_RULE_ELIGIBLE_T),
        "FINAL_IMPLEMENTATION_COMMIT": commit,
        "FINAL_IMPLEMENTATION_TREE": tree if commit == head else None,
    }
    run_identity = compute_run_identity(identity_inputs)
    blocking = [k for k, v in RED_TEAM.items() if v["status"] == "BLOCKING"]
    review_pass = not blocking
    payload = {
        "unit": "D2_BITMEX_REPLICATION_IMPLEMENTATION_AND_OUTCOME_BLIND_REVIEW",
        "kind": "OUTCOME_BLIND_IMPLEMENTATION_REVIEW",
        "PREREG_SCIENTIFIC_CONTRACT": JSON_REL,
        "POST_PREREG_OUTCOME_BLIND_IMPLEMENTATION_IDENTITY": True,
        "PREREG_FROZEN": True,
        "EVIDENCE_CLASS": "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION",
        "CANDIDATE": "D2 / RULE_1 / RV_ABSTENTION",
        "IMPLEMENTATION_REVIEW": "PASS" if review_pass else "BLOCKED",
        "EXECUTION_READY": bool(review_pass),
        "EXECUTION_AUTHORIZED": False,
        "EXPECTED_ELIGIBLE_N": FROZEN_EXPECTED_ELIGIBLE_N,
        "FIRST_RULE_ELIGIBLE_T": _iso(FROZEN_FIRST_RULE_ELIGIBLE_T),
        "LAST_RULE_ELIGIBLE_T": _iso(FROZEN_LAST_RULE_ELIGIBLE_T),
        "verified_timestamp_census": {
            "EXPECTED_ELIGIBLE_N": census["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"],
            "FIRST_RULE_ELIGIBLE_T": census["legal"]["FIRST_RULE_ELIGIBLE_T"],
            "LAST_RULE_ELIGIBLE_T": census["legal"]["LAST_RULE_ELIGIBLE_T"],
        },
        "ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256": ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256,
        "FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256": impl,
        "FINAL_IMPLEMENTATION_COMMIT": commit,
        "FINAL_IMPLEMENTATION_TREE": identity_inputs["FINAL_IMPLEMENTATION_TREE"],
        "PRE_REVIEW_HEAD": head,
        "PREREG_ARTIFACT_SHA256": prereg_sha,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": authority_sha,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "RUN_IDENTITY": run_identity,
        "RUN_IDENTITY_INPUTS": identity_inputs,
        "RED_TEAM_FINDINGS": RED_TEAM,
        "BLOCKING_FINDINGS": blocking,
        "CLASSIFICATIONS_UNASSIGNED": [CLASS_SUPPORTED, CLASS_NOT_SUPPORTED, CLASS_INVALID],
        "CLASSIFICATION_ASSIGNED": None,
        "D2_BITMEX_OUTCOME_COMPUTED": False,
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "MARKET_07_CREATED": False,
        "EXECUTION_PERMIT_PRESENT": (repo / EXECUTION_PERMIT_REL).is_file(),
        "EXECUTION_AUTHORIZED_FLAG": EXECUTION_AUTHORIZED,
        "NEXT_UNIT": "D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION"
        if review_pass
        else "D2_BITMEX_REPLICATION_IMPLEMENTATION_REPAIR",
        "PR_READY_TO_MERGE": bool(review_pass),
        "NOT_CREATED": ["RESULT", "execution permit", "MARKET-07", "ARM"],
    }
    return payload


def render_markdown(review: dict[str, Any]) -> str:
    findings = "\n".join(
        f"- `{name}`: **{body['status']}** — {body['note']}"
        for name, body in review["RED_TEAM_FINDINGS"].items()
    )
    return f"""# D2 BitMEX replication implementation review

**Unit:** `{review["unit"]}`  
**Kind:** outcome-blind implementation review. **Not executed.**

## Lineage

The frozen prereg scientific contract is unchanged. The prereg-bound
evaluator SHA was a firewalled stub. This unit replaces that stub with a
reviewed execution implementation without inspecting BitMEX outcomes.

- `PREREG_SCIENTIFIC_CONTRACT` = `{review["PREREG_SCIENTIFIC_CONTRACT"]}`
- original stub SHA256 (`d2_bitmex_replication_evaluator.py`) =
  `{review["ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256"]["scripts/research/d2_bitmex_replication_evaluator.py"]}`
- final reviewed SHA256 (`d2_bitmex_replication_evaluator.py`) =
  `{review["FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"]["scripts/research/d2_bitmex_replication_evaluator.py"]}`

Scientific files `d2_bitmex_pre2020.py`, `common.py`, and
`market_06_cross_venue_dislocation_evaluator.py` are byte-identical to the
prereg-bound hashes.

## Identity

```
IMPLEMENTATION_REVIEW = {review["IMPLEMENTATION_REVIEW"]}
EXECUTION_READY = {review["EXECUTION_READY"]}
EXECUTION_AUTHORIZED = {review["EXECUTION_AUTHORIZED"]}
EXPECTED_ELIGIBLE_N = {review["EXPECTED_ELIGIBLE_N"]}
FIRST_RULE_ELIGIBLE_T = {review["FIRST_RULE_ELIGIBLE_T"]}
LAST_RULE_ELIGIBLE_T = {review["LAST_RULE_ELIGIBLE_T"]}
PREREG_ARTIFACT_SHA256 = {review["PREREG_ARTIFACT_SHA256"]}
BITMEX_CANONICAL_SHA256 = {review["BITMEX_CANONICAL_SHA256"]}
RUN_IDENTITY = {review["RUN_IDENTITY"]}
RANDOM_SEED = {review["RANDOM_SEED"]}
N_CONTROLS = {review["N_CONTROLS"]}
```

No execution permit exists. `execute_replication` fails closed.

## Red-team (F1–F14)

{findings}

## Next

`NEXT_UNIT = {review["NEXT_UNIT"]}`  
`D2_BITMEX_OUTCOME_COMPUTED = false`  
`PROTECTED_2025_OPENED = false`  
`PROTECTED_2026_OPENED = false`
"""


def write_binding(repo: Path, review: dict[str, Any]) -> dict[str, Any]:
    existing = json.loads((repo / BINDING_REL).read_text(encoding="utf-8"))
    binding = dict(existing)
    binding["schema"] = "signalbot_d2_bitmex_replication_execution_binding"
    binding["ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256"] = review[
        "ORIGINAL_PREREG_IMPLEMENTATION_FILE_SHA256"
    ]
    binding["FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"] = review[
        "FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"
    ]
    binding["IMPLEMENTATION_REVIEW_COMMIT"] = review["FINAL_IMPLEMENTATION_COMMIT"]
    binding["FINAL_IMPLEMENTATION_TREE"] = review["FINAL_IMPLEMENTATION_TREE"]
    binding["RUN_IDENTITY"] = review["RUN_IDENTITY"]
    binding["EXECUTION_READY"] = review["EXECUTION_READY"]
    binding["EXECUTION_AUTHORIZED"] = False
    binding["D2_BITMEX_OUTCOME_COMPUTED"] = False
    binding["CLASSIFICATION_ASSIGNED"] = None
    binding["IMPLEMENTATION_FILE_SHA256"] = review["FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"]
    binding["PREREG_ARTIFACT_SHA256"] = review["PREREG_ARTIFACT_SHA256"]
    (repo / BINDING_REL).write_text(
        json.dumps(binding, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    binding_sha = sha256_bytes((repo / BINDING_REL).read_bytes())
    review["EXECUTION_BINDING_SHA256"] = binding_sha
    return binding


def write_artifacts(*, repo: Path | None = None, implementation_commit: str | None = None) -> dict[str, Any]:
    base = repo or C.repo_root()
    review = build_review(repo=base, implementation_commit=implementation_commit)
    write_binding(base, review)
    (base / REVIEW_JSON_REL).write_text(
        json.dumps(review, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (base / REVIEW_MD_REL).write_text(render_markdown(review), encoding="utf-8")
    return review


if __name__ == "__main__":
    written = write_artifacts()
    keys = (
        "IMPLEMENTATION_REVIEW",
        "EXECUTION_READY",
        "EXECUTION_AUTHORIZED",
        "EXPECTED_ELIGIBLE_N",
        "FIRST_RULE_ELIGIBLE_T",
        "LAST_RULE_ELIGIBLE_T",
        "PREREG_ARTIFACT_SHA256",
        "EXECUTION_BINDING_SHA256",
        "BITMEX_CANONICAL_SHA256",
        "RUN_IDENTITY",
        "NEXT_UNIT",
        "D2_BITMEX_OUTCOME_COMPUTED",
    )
    print(json.dumps({k: written[k] for k in keys}, indent=2))
    print(
        "evaluator",
        written["FINAL_REVIEWED_IMPLEMENTATION_FILE_SHA256"][
            "scripts/research/d2_bitmex_replication_evaluator.py"
        ],
    )
