"""Corrected one-shot D2 BitMEX replication execution.

Integrity-repair lineage. Does not edit frozen scientific kernels.
Does not overwrite the original INVALID result.
Does not open Binance 2025/2026.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from scripts.research.d2_bitmex_pre2020 import (
    AUTHORITY_REL,
    refuse_binance_protected_path,
    utc_ms,
)
from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_NOT_SUPPORTED,
    CLASS_SUPPORTED,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
    N_REPLICATES,
    REPLICATION_RANDOM_SEED,
    bars_from_canonical_jsonl,
    classify_replication,
    construct_rows_for_decisions,
    evaluate_constructed_rows,
    load_sealed_canonical_bytes,
    split_warmup_eligible,
    timestamp_complete_decisions,
    verify_eligibility,
)
from scripts.research.d2_bitmex_replication_integrity_diagnostic import (
    diagnose_scientific_eligibility,
)
from scripts.research.d2_bitmex_replication_prereg import (
    CANONICAL_REL,
    JSON_REL,
    file_sha256,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import (
    canonical_result_bytes,
    result_payload_sha256,
)

UTC = timezone.utc

UNIT = "D2_BITMEX_REPLICATION_CORRECTED_ONE_SHOT_EXECUTION"
EVIDENCE_CLASS = "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION"
NEW_RUN_IDENTITY = "8e3e9ecfadc18f71dae800cd16d0b0b36845c17710a108a0258c833af0420b43"
ORIGINAL_INVALID_RUN_IDENTITY = "b873d473e5d5ef1394d161d557b1e0ca7602bfa92e6d78d8e80df8f4d1493d71"
ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256 = (
    "9af98e72e7afc2c3e8af7f2d359401110e1e9c9829e69185ab23519e06fba48a"
)
FROZEN_PREREG_SHA256 = "939fe29243956195f2ca97723a7b94b666ce59359c55e096f8fba4d65c7d9044"
FROZEN_IMPLEMENTATION_SHA256 = "087e7ea5892f2ab81f26bd61c82b2709b6812b6916554e5c92846a52496d77aa"
FROZEN_SOURCE_AUTHORITY_SHA256 = "2a48e025a9ecb596f7a37646a39367cae031e5aa3fd0555416c3fab692594dff"
FROZEN_AMENDMENT_SHA256 = "43bfd6a9aa0a6ad0c204e017185ab0f9f8fc5c04016b32b399c0feae69961ad6"
FROZEN_ADJUDICATION_SHA256 = "42941fb9030e5ff815dcaa353767eb91fda7c5bc60b1a7dd180f2d86419ee3a8"

CORRECTED_CONSTRUCTED_N = 1317
CORRECTED_WARMUP_N = 250
CORRECTED_ELIGIBLE_N = 1067
CORRECTED_YEAR_ELIGIBLE_N = {"2017": 341, "2018": 363, "2019": 363}
CORRECTED_FIRST_T = "2017-01-24T00:05:00Z"
CORRECTED_LAST_T = "2019-12-30T00:05:00Z"
EXPECTED_DROPPED = (
    ("2018-03-17T00:05:00Z", "BTC_RET_24H_EQ_0"),
    ("2019-02-10T00:05:00Z", "BTC_RET_24H_EQ_0"),
)

CLASS_CORRECTED_INVALID = "D2_BITMEX_REPLICATION_CORRECTED_INVALID"
PERMIT_REL = "docs/research_data/D2_BITMEX_REPLICATION_CORRECTED_EXECUTION_PERMIT.json"
ORCHESTRATION_REL = "scripts/research/d2_bitmex_replication_corrected_one_shot.py"
RESULT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.json"
RESULT_MD_REL = "docs/research/D2_BITMEX_REPLICATION_CORRECTED_RESULT.md"
ORIGINAL_RESULT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_RESULT.json"
ADJUDICATION_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION.json"
AMENDMENT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_PREREG_AMENDMENT_V1.json"


def _iso_z(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _json_load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _py(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_py(v) for v in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def _relative(delta: float | None, uncond: float | None) -> float | None:
    if delta is None or uncond is None or float(uncond) == 0.0:
        return None
    return float(delta) / float(uncond)


def load_permit(repo: Path) -> dict[str, Any]:
    path = repo / PERMIT_REL
    if not path.is_file():
        raise RuntimeError("NO_CORRECTED_EXECUTION_PERMIT")
    return _json_load(path)


def verify_frozen_authorities(repo: Path) -> list[str]:
    blockers: list[str] = []
    permit = load_permit(repo)
    expected = {
        "UNIT": UNIT,
        "RUN_IDENTITY": NEW_RUN_IDENTITY,
        "ORIGINAL_INVALID_RUN_IDENTITY": ORIGINAL_INVALID_RUN_IDENTITY,
        "ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256": ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256,
        "ADJUDICATION_CLASS": "REPAIRABLE_PREDECLARED_ELIGIBILITY_IDENTITY_MISMATCH",
        "CORRECTED_EXPECTED_N": CORRECTED_ELIGIBLE_N,
        "CORRECTED_CONSTRUCTED_N": CORRECTED_CONSTRUCTED_N,
        "WARMUP_N": CORRECTED_WARMUP_N,
        "YEAR_2017_N": 341,
        "YEAR_2018_N": 363,
        "YEAR_2019_N": 363,
        "FIRST_T": CORRECTED_FIRST_T,
        "LAST_T": CORRECTED_LAST_T,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "FINAL_SCIENTIFIC_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "ONE_SHOT": True,
        "EXECUTION_AUTHORIZED": True,
        "RERUN_AUTHORIZED": False,
        "ORIGINAL_PREREG_JSON_SHA256": FROZEN_PREREG_SHA256,
        "PREREG_AMENDMENT_JSON_SHA256": FROZEN_AMENDMENT_SHA256,
        "ADJUDICATION_JSON_SHA256": FROZEN_ADJUDICATION_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
    }
    for key, value in expected.items():
        if permit.get(key) != value:
            blockers.append(f"PERMIT_FIELD:{key}")
    if file_sha256(repo / JSON_REL) != FROZEN_PREREG_SHA256:
        blockers.append("PREREG_SHA")
    if file_sha256(repo / AMENDMENT_JSON_REL) != FROZEN_AMENDMENT_SHA256:
        blockers.append("AMENDMENT_SHA")
    if file_sha256(repo / ADJUDICATION_JSON_REL) != FROZEN_ADJUDICATION_SHA256:
        blockers.append("ADJUDICATION_SHA")
    if file_sha256(repo / AUTHORITY_REL) != FROZEN_SOURCE_AUTHORITY_SHA256:
        blockers.append("SOURCE_AUTHORITY_SHA")
    if file_sha256(repo / "scripts/research/d2_bitmex_replication_evaluator.py") != FROZEN_IMPLEMENTATION_SHA256:
        blockers.append("SCIENTIFIC_IMPLEMENTATION_SHA")
    orch_sha = file_sha256(repo / ORCHESTRATION_REL)
    if str(permit.get("CORRECTED_ORCHESTRATION_SHA256") or "") != orch_sha:
        blockers.append("ORCHESTRATION_SHA")
    original = _json_load(repo / ORIGINAL_RESULT_JSON_REL)
    if original.get("RUN_IDENTITY") != ORIGINAL_INVALID_RUN_IDENTITY:
        blockers.append("ORIGINAL_RUN_IDENTITY_DRIFT")
    if original.get("RESULT_PAYLOAD_SHA256") != ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256:
        blockers.append("ORIGINAL_RESULT_PAYLOAD_DRIFT")
    if original.get("CLASSIFICATION") != "D2_BITMEX_REPLICATION_INVALID":
        blockers.append("ORIGINAL_CLASSIFICATION_DRIFT")
    refuse_binance_protected_path(repo / CANONICAL_REL)
    return blockers


def reconstruct_corrected_sample(repo: Path) -> tuple[list[C.DiscoveryRow] | None, dict[str, Any], list[str]]:
    blockers: list[str] = []
    identity: dict[str, Any] = {
        "TIMESTAMP_CENSUS_N": None,
        "CONSTRUCTED_N": None,
        "WARMUP_N": None,
        "ELIGIBLE_N": None,
        "FIRST_T": None,
        "LAST_T": None,
        "YEAR_ELIGIBLE_N": None,
        "DROPPED_ROWS": None,
        "KNOWN_GAP_NEVER_FILLED": None,
        "TRAILING_HISTORY_AUTHORITY": "VALID_CONSTRUCTED_ROWS",
    }
    try:
        census = verify_eligibility(repo=repo)
        jsonl_bytes = load_sealed_canonical_bytes(repo)
        perp = bars_from_canonical_jsonl(jsonl_bytes)
        raw_open = utc_ms(
            datetime.fromisoformat(str(census["legal"]["RAW_DATA_START"]).replace("Z", "+00:00"))
        )
        complete = timestamp_complete_decisions(set(perp), raw_open_ms=raw_open)
        rows = construct_rows_for_decisions(complete, perp)
        warmup, eligible = split_warmup_eligible(rows)
    except Exception as exc:  # noqa: BLE001
        blockers.append(f"SAMPLE_RECONSTRUCT:{type(exc).__name__}:{exc}")
        return None, identity, blockers
    identity["TIMESTAMP_CENSUS_N"] = int(census["legal"]["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"])
    identity["KNOWN_GAP_NEVER_FILLED"] = bool(census.get("KNOWN_GAP_NEVER_FILLED") is True)
    identity["CONSTRUCTED_N"] = int(len(rows))
    identity["WARMUP_N"] = int(len(warmup))
    identity["ELIGIBLE_N"] = int(len(eligible))
    if identity["TIMESTAMP_CENSUS_N"] != 1069:
        blockers.append(f"TIMESTAMP_CENSUS_N:{identity['TIMESTAMP_CENSUS_N']}")
    if len(rows) != CORRECTED_CONSTRUCTED_N:
        blockers.append(f"CONSTRUCTED_N:{len(rows)}")
    if len(warmup) != CORRECTED_WARMUP_N:
        blockers.append(f"WARMUP_N:{len(warmup)}")
    if len(eligible) != CORRECTED_ELIGIBLE_N:
        blockers.append(f"ELIGIBLE_N:{len(eligible)}")
    if eligible:
        first = C.utc_from_ms(eligible[0].t_ms)
        last = C.utc_from_ms(eligible[-1].t_ms)
        identity["FIRST_T"] = _iso_z(first)
        identity["LAST_T"] = _iso_z(last)
        year_n = {str(y): int(Counter(row.year for row in eligible)[y]) for y in (2017, 2018, 2019)}
        identity["YEAR_ELIGIBLE_N"] = year_n
        if identity["FIRST_T"] != CORRECTED_FIRST_T:
            blockers.append(f"FIRST_T:{identity['FIRST_T']}")
        if identity["LAST_T"] != CORRECTED_LAST_T:
            blockers.append(f"LAST_T:{identity['LAST_T']}")
        if year_n != CORRECTED_YEAR_ELIGIBLE_N:
            blockers.append(f"YEAR_ELIGIBLE_N:{year_n}")
    complete_iso = [_iso_z(t) for t in complete]
    constructed_iso = {_iso_z(C.utc_from_ms(row.t_ms)) for row in rows}
    dropped_iso = [ts for ts in complete_iso if ts not in constructed_iso]
    dropped_payload = []
    for ts in dropped_iso:
        moment = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        reason = diagnose_scientific_eligibility(C.ms_from_utc(moment), perp)
        dropped_payload.append(
            {
                "DROP_TIMESTAMP": ts,
                "DROP_YEAR": int(moment.year),
                "EXACT_INELIGIBILITY_REASON": reason,
            }
        )
    identity["DROPPED_ROWS"] = dropped_payload
    expected_dropped = [
        {
            "DROP_TIMESTAMP": ts,
            "DROP_YEAR": int(ts[:4]),
            "EXACT_INELIGIBILITY_REASON": reason,
        }
        for ts, reason in EXPECTED_DROPPED
    ]
    if dropped_payload != expected_dropped:
        blockers.append(f"DROPPED_ROWS:{dropped_payload}")
    return rows, identity, blockers


def yearly_with_relative(
    evaluated: Mapping[str, Any],
    eligible: list[C.DiscoveryRow],
) -> dict[str, Any]:
    by_year_uncond: dict[int, float] = {}
    for year in (2017, 2018, 2019):
        sevs = [float(row.severity) for row in eligible if int(row.year) == year]
        by_year_uncond[year] = float(sum(sevs) / len(sevs)) if sevs else float("nan")
    out: dict[str, Any] = {}
    raw = evaluated.get("YEARLY_DIAGNOSTICS") or {}
    for year in (2017, 2018, 2019):
        payload = dict(raw.get(str(year)) or {})
        delta = payload.get("DELTA")
        uncond_y = by_year_uncond[year]
        payload["UNCONDITIONAL_MEAN"] = None if uncond_y != uncond_y else float(uncond_y)
        payload["RELATIVE_DELTA"] = _relative(
            None if delta is None else float(delta),
            payload["UNCONDITIONAL_MEAN"],
        )
        payload["ELIGIBLE_N"] = int(payload.get("eligible_n") or 0)
        payload["K"] = int(payload.get("candidate_k") or 0)
        out[str(year)] = payload
    return out


def _next_unit(classification: str) -> str:
    if classification == CLASS_SUPPORTED:
        return "PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED"
    if classification == CLASS_NOT_SUPPORTED:
        return "PROGRAM_UPDATE_POST_D2_BITMEX_REPLICATION"
    return "D2_BITMEX_REPLICATION_CORRECTED_INTEGRITY_ADJUDICATION"


def _evidence_label(classification: str) -> str:
    if classification == CLASS_SUPPORTED:
        return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED"
    if classification == CLASS_NOT_SUPPORTED:
        return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_NOT_SUPPORTED"
    return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_CORRECTED_INVALID"


def _replication_status(classification: str) -> str | None:
    if classification == CLASS_SUPPORTED:
        return "SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE"
    if classification == CLASS_NOT_SUPPORTED:
        return "NOT_SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE"
    return "CORRECTED_INVALID_PENDING_INTEGRITY_ADJUDICATION"


def render_markdown(result: Mapping[str, Any]) -> str:
    primary = result["PRIMARY_METRICS"]
    gates = result["GATES"]
    years = result["YEARLY_DIAGNOSTICS"]
    year_lines = []
    for year in ("2017", "2018", "2019"):
        body = years[year]
        year_lines.append(
            f"- `{year}`: ELIGIBLE_N={body['ELIGIBLE_N']} K={body['K']} "
            f"MU_RULE={body['MU_RULE']} MU_CONTROL_MEAN={body['MU_CONTROL_MEAN']} "
            f"DELTA={body['DELTA']} RELATIVE_DELTA={body['RELATIVE_DELTA']}"
        )
    supported_note = ""
    if result["CLASSIFICATION"] == CLASS_SUPPORTED:
        supported_note = (
            "\nThis is **not** `EXACT_BINANCE_CONFIRMATION`, "
            "`PROVEN_ALPHA`, or `VALIDATED_TRADING_EDGE`. "
            "The frozen mechanism replicated on an earlier era and a different "
            "perpetual venue/contract environment.\n"
        )
    elif result["CLASSIFICATION"] == CLASS_NOT_SUPPORTED:
        supported_note = (
            "\nD2 remains a historical discovery prototype that failed "
            "independent cross-venue temporal replication. No rescue. "
            "The original INVALID run is not a negative scientific result.\n"
        )
    return f"""# D2 BitMEX replication CORRECTED RESULT

**Unit:** `{result["unit"]}`  
**Kind:** integrity-repair one-shot scientific execution.

The original run remains `D2_BITMEX_REPLICATION_INVALID`. This file is a
new lineage, not a rewrite of that history.

## Identity

```
EVIDENCE_CLASS = {result["EVIDENCE_CLASS"]}
EVIDENCE_LABEL = {result["EVIDENCE_LABEL"]}
NEW_RUN_IDENTITY = {result["RUN_IDENTITY"]}
CORRECTED_PERMIT_COMMIT = {result["CORRECTED_PERMIT_COMMIT"]}
ORIGINAL_INVALID_RUN_IDENTITY = {result["ORIGINAL_INVALID_RUN_IDENTITY"]}
ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256 = {result["ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256"]}
SEED = {result["RANDOM_SEED"]}
N_CONTROLS = {result["N_CONTROLS"]}
CORRECTED_RESULT_PAYLOAD_SHA256 = {result["CORRECTED_RESULT_PAYLOAD_SHA256"]}
```

## Corrected sample identity

```
CONSTRUCTED_N = {result["SAMPLE_IDENTITY"]["CONSTRUCTED_N"]}
WARMUP_N = {result["SAMPLE_IDENTITY"]["WARMUP_N"]}
ELIGIBLE_N = {result["SAMPLE_IDENTITY"]["ELIGIBLE_N"]}
FIRST_T = {result["SAMPLE_IDENTITY"]["FIRST_T"]}
LAST_T = {result["SAMPLE_IDENTITY"]["LAST_T"]}
YEAR_ELIGIBLE_N = {result["SAMPLE_IDENTITY"]["YEAR_ELIGIBLE_N"]}
TRAILING_HISTORY_AUTHORITY = {result["SAMPLE_IDENTITY"]["TRAILING_HISTORY_AUTHORITY"]}
```

## Primary metrics

```
ELIGIBLE_N = {primary["ELIGIBLE_N"]}
ABSTAIN_COUNT_TOTAL = {primary["ABSTAIN_COUNT_TOTAL"]}
ABSTAIN_RATE = {primary["ABSTAIN_RATE"]}
K_2017 = {primary["K_2017"]}
K_2018 = {primary["K_2018"]}
K_2019 = {primary["K_2019"]}
MU_RULE = {primary["MU_RULE"]}
MU_CONTROL_MEAN = {primary["MU_CONTROL_MEAN"]}
DELTA = {primary["DELTA"]}
UNCONDITIONAL_MEAN = {primary["UNCONDITIONAL_MEAN"]}
RELATIVE_DELTA = {primary["RELATIVE_DELTA"]}
CONTROL_P95 = {primary["CONTROL_P95"]}
MC_P = {primary["MC_P"]}
```

## Gates and classification

```
STATISTICAL_GATE = {gates["STATISTICAL_GATE"]}
PRACTICAL_GATE = {gates["PRACTICAL_GATE"]}
PRIMARY_PASS = {gates["PRIMARY_PASS"]}
CLASSIFICATION = {result["CLASSIFICATION"]}
ORIGINAL_RUN_CLASSIFICATION = {result["ORIGINAL_RUN_CLASSIFICATION"]}
```
{supported_note}
## Yearly diagnostics (cannot change classification)

{chr(10).join(year_lines)}

## Program flags

```
RERUN_AUTHORIZED = {result["RERUN_AUTHORIZED"]}
PROTECTED_2025_OPENED = {result["PROTECTED_2025_OPENED"]}
PROTECTED_2026_OPENED = {result["PROTECTED_2026_OPENED"]}
MARKET_07_CREATED = {result["MARKET_07_CREATED"]}
D2_DISCOVERY_STATUS = {result["D2_DISCOVERY_STATUS"]}
D2_REPLICATION_STATUS = {result["D2_REPLICATION_STATUS"]}
NEXT_UNIT = {result["NEXT_UNIT"]}
BLOCKER = {result.get("BLOCKER")}
```
"""


def _base_result(
    *,
    permit_commit: str,
    identity: Mapping[str, Any],
    classification: str,
    outcome_computed: bool,
    blockers: list[str] | None,
    primary: Mapping[str, Any] | None = None,
    gates: Mapping[str, Any] | None = None,
    yearly: Mapping[str, Any] | None = None,
    orchestration_sha: str | None = None,
) -> dict[str, Any]:
    empty_year = {
        str(year): {
            "ELIGIBLE_N": None,
            "K": None,
            "eligible_n": None,
            "candidate_k": None,
            "MU_RULE": None,
            "MU_CONTROL_MEAN": None,
            "DELTA": None,
            "UNCONDITIONAL_MEAN": None,
            "RELATIVE_DELTA": None,
        }
        for year in (2017, 2018, 2019)
    }
    empty_primary = {
        "ELIGIBLE_N": identity.get("ELIGIBLE_N"),
        "ABSTAIN_COUNT_TOTAL": None,
        "ABSTAIN_COUNT_2017": None,
        "ABSTAIN_COUNT_2018": None,
        "ABSTAIN_COUNT_2019": None,
        "ABSTAIN_RATE": None,
        "K_2017": None,
        "K_2018": None,
        "K_2019": None,
        "MU_RULE": None,
        "MU_CONTROL_MEAN": None,
        "DELTA": None,
        "UNCONDITIONAL_MEAN": None,
        "RELATIVE_DELTA": None,
        "CONTROL_P95": None,
        "MC_P": None,
    }
    return {
        "unit": UNIT,
        "kind": "INTEGRITY_REPAIR_ONE_SHOT_SCIENTIFIC_EXECUTION",
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "EVIDENCE_LABEL": _evidence_label(classification),
        "RUN_IDENTITY": NEW_RUN_IDENTITY,
        "CORRECTED_PERMIT_COMMIT": permit_commit,
        "ORIGINAL_INVALID_RUN_IDENTITY": ORIGINAL_INVALID_RUN_IDENTITY,
        "ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256": ORIGINAL_INVALID_RESULT_PAYLOAD_SHA256,
        "ORIGINAL_RUN_CLASSIFICATION": "D2_BITMEX_REPLICATION_INVALID",
        "ORIGINAL_PRIMARY_OUTCOME_COMPUTED": False,
        "ADJUDICATION_JSON_SHA256": FROZEN_ADJUDICATION_SHA256,
        "PREREG_AMENDMENT_JSON_SHA256": FROZEN_AMENDMENT_SHA256,
        "ORIGINAL_PREREG_JSON_SHA256": FROZEN_PREREG_SHA256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
        "CORRECTED_ORCHESTRATION_SHA256": orchestration_sha,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "SAMPLE_IDENTITY": dict(identity),
        "PRIMARY_METRICS": dict(primary or empty_primary),
        "GATES": dict(
            gates
            or {
                "STATISTICAL_GATE": False,
                "PRACTICAL_GATE": False,
                "PRIMARY_PASS": False,
            }
        ),
        "CLASSIFICATION": classification,
        "YEARLY_DIAGNOSTICS": dict(yearly or empty_year),
        "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
        "NO_YEARLY_RESCUE": True,
        "NO_TWO_OF_THREE_YEAR_REQUIREMENT": True,
        "D2_BITMEX_OUTCOME_COMPUTED": bool(outcome_computed),
        "D2_DISCOVERY_STATUS": "PROMISING_PROTOTYPE",
        "D2_REPLICATION_STATUS": _replication_status(classification),
        "PROTECTED_2025_OPENED": False,
        "PROTECTED_2026_OPENED": False,
        "2025_OPEN_AUTHORIZED": False,
        "2026_OPEN_AUTHORIZED": False,
        "MARKET_07_CREATED": False,
        "RERUN_AUTHORIZED": False,
        "ONE_SHOT": True,
        "EXECUTION_AUTHORIZED": True,
        "NOT_EXACT_BINANCE_CONFIRMATION": True,
        "NOT_VALIDATED_TRADING_EDGE": True,
        "NOT_PROVEN_ALPHA": True,
        "NEXT_UNIT": _next_unit(classification),
        "BLOCKER": blockers,
    }


def write_result(repo: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    hashed = {k: v for k, v in payload.items() if k != "CORRECTED_RESULT_PAYLOAD_SHA256"}
    digest = result_payload_sha256(hashed)
    written = dict(hashed)
    written["CORRECTED_RESULT_PAYLOAD_SHA256"] = digest
    (repo / RESULT_JSON_REL).write_bytes(canonical_result_bytes(written))
    (repo / RESULT_MD_REL).write_text(render_markdown(written), encoding="utf-8")
    return written


def execute_corrected_one_shot(repo: Path | None = None) -> dict[str, Any]:
    base = repo if repo is not None else C.repo_root()
    if (base / RESULT_JSON_REL).is_file():
        raise RuntimeError("CORRECTED_RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN")
    original = (base / ORIGINAL_RESULT_JSON_REL).read_bytes()
    permit_commit = _git(base, "rev-parse", "HEAD")
    orch_sha = file_sha256(base / ORCHESTRATION_REL)
    authority_blockers = verify_frozen_authorities(base)
    if authority_blockers:
        written = write_result(
            base,
            _base_result(
                permit_commit=permit_commit,
                identity={
                    "TIMESTAMP_CENSUS_N": None,
                    "CONSTRUCTED_N": None,
                    "WARMUP_N": None,
                    "ELIGIBLE_N": None,
                    "FIRST_T": None,
                    "LAST_T": None,
                    "YEAR_ELIGIBLE_N": None,
                    "DROPPED_ROWS": None,
                    "TRAILING_HISTORY_AUTHORITY": "VALID_CONSTRUCTED_ROWS",
                },
                classification=CLASS_CORRECTED_INVALID,
                outcome_computed=False,
                blockers=authority_blockers,
                orchestration_sha=orch_sha,
            ),
        )
        if (base / ORIGINAL_RESULT_JSON_REL).read_bytes() != original:
            raise RuntimeError("ORIGINAL_INVALID_RESULT_MUTATED")
        return written
    rows, identity, sample_blockers = reconstruct_corrected_sample(base)
    if sample_blockers or rows is None:
        written = write_result(
            base,
            _base_result(
                permit_commit=permit_commit,
                identity=identity,
                classification=CLASS_CORRECTED_INVALID,
                outcome_computed=False,
                blockers=sample_blockers or ["SAMPLE_RECONSTRUCT_FAILED"],
                orchestration_sha=orch_sha,
            ),
        )
        if (base / ORIGINAL_RESULT_JSON_REL).read_bytes() != original:
            raise RuntimeError("ORIGINAL_INVALID_RESULT_MUTATED")
        return written
    warmup, eligible = split_warmup_eligible(rows)
    del warmup
    evaluated = evaluate_constructed_rows(
        rows,
        seed=REPLICATION_RANDOM_SEED,
        n_replicates=N_REPLICATES,
        enforce_sample_identity=False,
    )
    yearly = yearly_with_relative(evaluated, eligible)
    k_2017 = int(yearly["2017"]["K"])
    k_2018 = int(yearly["2018"]["K"])
    k_2019 = int(yearly["2019"]["K"])
    abstain_total = int(evaluated["ABSTAIN_COUNT"])
    eligible_n = int(evaluated["ELIGIBLE_N"])
    mu_rule_raw = evaluated["MU_RULE"]
    statistical = bool(evaluated["STATISTICAL_GATE"])
    practical = bool(evaluated["PRACTICAL_GATE"])
    classification = classify_replication(
        integrity_invalid=False,
        statistical=statistical,
        practical=practical,
    )
    primary_pass = bool(statistical and practical)
    if mu_rule_raw is None:
        primary = {
            "ELIGIBLE_N": eligible_n,
            "ABSTAIN_COUNT_TOTAL": abstain_total,
            "ABSTAIN_COUNT_2017": k_2017,
            "ABSTAIN_COUNT_2018": k_2018,
            "ABSTAIN_COUNT_2019": k_2019,
            "ABSTAIN_RATE": float(abstain_total) / float(eligible_n) if eligible_n else None,
            "K_2017": k_2017,
            "K_2018": k_2018,
            "K_2019": k_2019,
            "MU_RULE": None,
            "MU_CONTROL_MEAN": None,
            "DELTA": None,
            "UNCONDITIONAL_MEAN": evaluated["UNCONDITIONAL_MEAN"],
            "RELATIVE_DELTA": None,
            "CONTROL_P95": None,
            "MC_P": None,
        }
        gates = {
            "STATISTICAL_GATE": False,
            "PRACTICAL_GATE": False,
            "PRIMARY_PASS": False,
        }
        outcome_computed = False
    else:
        mu_rule = float(mu_rule_raw)
        mu_control = float(evaluated["MU_CONTROL_MEAN"])
        delta = float(evaluated["DELTA"])
        uncond = float(evaluated["UNCONDITIONAL_MEAN"])
        primary = {
            "ELIGIBLE_N": eligible_n,
            "ABSTAIN_COUNT_TOTAL": abstain_total,
            "ABSTAIN_COUNT_2017": k_2017,
            "ABSTAIN_COUNT_2018": k_2018,
            "ABSTAIN_COUNT_2019": k_2019,
            "ABSTAIN_RATE": float(abstain_total) / float(eligible_n),
            "K_2017": k_2017,
            "K_2018": k_2018,
            "K_2019": k_2019,
            "MU_RULE": mu_rule,
            "MU_CONTROL_MEAN": mu_control,
            "DELTA": delta,
            "UNCONDITIONAL_MEAN": uncond,
            "RELATIVE_DELTA": _relative(delta, uncond),
            "CONTROL_P95": float(evaluated["CONTROL_P95"]),
            "MC_P": float(evaluated["MC_P"]),
        }
        gates = {
            "STATISTICAL_GATE": statistical,
            "PRACTICAL_GATE": practical,
            "PRIMARY_PASS": primary_pass,
        }
        outcome_computed = True
    written = write_result(
        base,
        _py(
            _base_result(
                permit_commit=permit_commit,
                identity=identity,
                classification=classification,
                outcome_computed=outcome_computed,
                blockers=None,
                primary=primary,
                gates=gates,
                yearly=yearly,
                orchestration_sha=orch_sha,
            )
        ),
    )
    if (base / ORIGINAL_RESULT_JSON_REL).read_bytes() != original:
        raise RuntimeError("ORIGINAL_INVALID_RESULT_MUTATED")
    return written


def main() -> None:
    execute_corrected_one_shot()


if __name__ == "__main__":
    main()
