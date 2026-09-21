"""Canonical one-shot D2 BitMEX replication execution.

Reuses frozen scientific kernels. Does not edit evaluator formulas.
Does not open Binance 2025/2026. Refuses a second scientific run.
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
    sha256_bytes,
    utc_ms,
)
from scripts.research.d2_bitmex_replication_evaluator import (
    CLASS_INVALID,
    CLASS_NOT_SUPPORTED,
    CLASS_SUPPORTED,
    EXECUTION_PERMIT_REL as EVALUATOR_STUB_PERMIT_REL,
    FROZEN_CANONICAL_GZ_SHA256,
    FROZEN_CANONICAL_JSONL_SHA256,
    N_REPLICATES,
    REPLICATION_RANDOM_SEED,
    bars_from_canonical_jsonl,
    classify_replication,
    construct_rows_for_decisions,
    current_implementation_file_sha256,
    evaluate_constructed_rows,
    load_sealed_canonical_bytes,
    split_warmup_eligible,
    timestamp_complete_decisions,
    verify_eligibility,
)
from scripts.research.d2_bitmex_replication_prereg import (
    BINDING_REL,
    CANONICAL_REL,
    FROZEN_EXPECTED_ELIGIBLE_N,
    FROZEN_FIRST_RULE_ELIGIBLE_T,
    FROZEN_LAST_RULE_ELIGIBLE_T,
    IMPLEMENTATION_FILES,
    JSON_REL,
    file_sha256,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import (
    canonical_result_bytes,
    result_payload_sha256,
)

UTC = timezone.utc

UNIT = "D2_BITMEX_REPLICATION_ONE_SHOT_EXECUTION"
EVIDENCE_CLASS = "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION"
FROZEN_RUN_IDENTITY = "b873d473e5d5ef1394d161d557b1e0ca7602bfa92e6d78d8e80df8f4d1493d71"
FROZEN_PREREG_SHA256 = "939fe29243956195f2ca97723a7b94b666ce59359c55e096f8fba4d65c7d9044"
FROZEN_IMPLEMENTATION_SHA256 = "087e7ea5892f2ab81f26bd61c82b2709b6812b6916554e5c92846a52496d77aa"
FROZEN_SOURCE_AUTHORITY_SHA256 = "2a48e025a9ecb596f7a37646a39367cae031e5aa3fd0555416c3fab692594dff"
FROZEN_YEAR_ELIGIBLE_N = {"2017": 341, "2018": 364, "2019": 364}
PERMIT_REL = "docs/research_data/D2_BITMEX_REPLICATION_EXECUTION_PERMIT.json"
RESULT_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_RESULT.json"
RESULT_MD_REL = "docs/research/D2_BITMEX_REPLICATION_RESULT.md"
REVIEW_JSON_REL = "docs/research/D2_BITMEX_REPLICATION_IMPLEMENTATION_REVIEW.json"
D2_DISCOVERY_RESULT_REL = "docs/research/discovery_results/D2_DISCOVERY_RESULT.json"
FEASIBILITY_JSON_REL = "docs/research/D2_ALTERNATIVE_INDEPENDENT_SURFACE_FEASIBILITY.json"

FROZEN_IMPL_FILE_SHA256 = {
    "scripts/research/d2_bitmex_pre2020.py": "f0c16c8e120fd6813039abf09421a41ed01f741fe699e1e9df41e9105ca86056",
    "scripts/research/d2_bitmex_replication_evaluator.py": FROZEN_IMPLEMENTATION_SHA256,
    "scripts/research/discovery_sprint_01/common.py": "ab152da63fa8c923fba3fd0255b7cd4d6457389b6a45be9959abc7235fa912ef",
    "scripts/research/market_06_cross_venue_dislocation_evaluator.py": "ff87062edf583af1a67affcc18cda5e184379d9e63f7ff8b0e18383978890ead",
}


def _iso_z(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def _iso_ms(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%S.000Z")


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
    if isinstance(value, (int,)) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return float(value)
    return value


def load_permit(repo: Path) -> dict[str, Any]:
    path = repo / PERMIT_REL
    if not path.is_file():
        raise RuntimeError("NO_EXECUTION_PERMIT")
    return _json_load(path)


def verify_frozen_authorities(repo: Path) -> list[str]:
    """Return blocker codes. Empty list means authorities match."""
    blockers: list[str] = []
    permit = load_permit(repo)
    expected_permit = {
        "UNIT": UNIT,
        "RUN_IDENTITY": FROZEN_RUN_IDENTITY,
        "PREREG_ARTIFACT_SHA256": FROZEN_PREREG_SHA256,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "EXPECTED_N": FROZEN_EXPECTED_ELIGIBLE_N,
        "FIRST_T": "2017-01-24T00:05:00Z",
        "LAST_T": "2019-12-30T00:05:00Z",
        "EXECUTION_AUTHORIZED": True,
        "ONE_SHOT": True,
        "RERUN_AUTHORIZED": False,
    }
    for key, value in expected_permit.items():
        if permit.get(key) != value:
            blockers.append(f"PERMIT_FIELD:{key}")
    if file_sha256(repo / JSON_REL) != FROZEN_PREREG_SHA256:
        blockers.append("PREREG_SHA")
    if file_sha256(repo / AUTHORITY_REL) != FROZEN_SOURCE_AUTHORITY_SHA256:
        blockers.append("SOURCE_AUTHORITY_SHA")
    impl = current_implementation_file_sha256(repo)
    for rel in IMPLEMENTATION_FILES:
        if impl.get(rel) != FROZEN_IMPL_FILE_SHA256[rel]:
            blockers.append(f"IMPLEMENTATION_SHA:{rel}")
    if impl.get("scripts/research/d2_bitmex_replication_evaluator.py") != FROZEN_IMPLEMENTATION_SHA256:
        blockers.append("FINAL_IMPLEMENTATION_SHA")
    review = _json_load(repo / REVIEW_JSON_REL)
    if review.get("RUN_IDENTITY") != FROZEN_RUN_IDENTITY:
        blockers.append("REVIEW_RUN_IDENTITY")
    binding = _json_load(repo / BINDING_REL)
    if binding.get("RUN_IDENTITY") != FROZEN_RUN_IDENTITY:
        blockers.append("BINDING_RUN_IDENTITY")
    if str(binding.get("EXECUTION_PERMIT_REL") or "") != PERMIT_REL:
        blockers.append("BINDING_PERMIT_POINTER")
    if (repo / EVALUATOR_STUB_PERMIT_REL).is_file():
        blockers.append("EVALUATOR_STUB_PERMIT_PATH_PRESENT")
    refuse_binance_protected_path(repo / CANONICAL_REL)
    return blockers


def reconstruct_sample(repo: Path) -> tuple[list[C.DiscoveryRow] | None, dict[str, Any], list[str]]:
    """Build constructed rows and sample-identity payload. No primary metrics."""
    blockers: list[str] = []
    identity: dict[str, Any] = {
        "ELIGIBLE_N": None,
        "FIRST_T": None,
        "LAST_T": None,
        "YEAR_ELIGIBLE_N": None,
        "KNOWN_GAP_NEVER_FILLED": None,
        "WARMUP_N": None,
        "CONSTRUCTED_N": None,
    }
    try:
        census = verify_eligibility(repo=repo)
    except Exception as exc:  # noqa: BLE001 — fail closed into INVALID
        blockers.append(f"CENSUS:{type(exc).__name__}:{exc}")
        return None, identity, blockers
    legal = census["legal"]
    if int(legal["MAX_PRE2020_ELIGIBLE_DECISION_ROWS"]) != FROZEN_EXPECTED_ELIGIBLE_N:
        blockers.append(f"CENSUS_N:{legal['MAX_PRE2020_ELIGIBLE_DECISION_ROWS']}")
    if str(legal["FIRST_RULE_ELIGIBLE_T"]) != _iso_ms(FROZEN_FIRST_RULE_ELIGIBLE_T):
        blockers.append(f"CENSUS_FIRST_T:{legal['FIRST_RULE_ELIGIBLE_T']}")
    if str(legal["LAST_RULE_ELIGIBLE_T"]) != _iso_ms(FROZEN_LAST_RULE_ELIGIBLE_T):
        blockers.append(f"CENSUS_LAST_T:{legal['LAST_RULE_ELIGIBLE_T']}")
    years_census = {str(k): int(v) for k, v in census["year_eligible_n"].items()}
    if years_census != FROZEN_YEAR_ELIGIBLE_N:
        blockers.append(f"CENSUS_YEAR_N:{years_census}")
    if census.get("KNOWN_GAP_NEVER_FILLED") is not True:
        blockers.append("GAP_FILLED_OR_UNVERIFIED")
    identity["KNOWN_GAP_NEVER_FILLED"] = bool(census.get("KNOWN_GAP_NEVER_FILLED") is True)
    identity["YEAR_ELIGIBLE_N_CENSUS"] = years_census
    try:
        jsonl_bytes = load_sealed_canonical_bytes(repo)
        if sha256_bytes(jsonl_bytes) != FROZEN_CANONICAL_JSONL_SHA256:
            blockers.append("CANONICAL_JSONL_SHA")
            return None, identity, blockers
        perp = bars_from_canonical_jsonl(jsonl_bytes)
        raw_open = utc_ms(
            datetime.fromisoformat(str(legal["RAW_DATA_START"]).replace("Z", "+00:00"))
        )
        decisions = timestamp_complete_decisions(set(perp), raw_open_ms=raw_open)
        rows = construct_rows_for_decisions(decisions, perp)
        warmup, eligible = split_warmup_eligible(rows)
    except Exception as exc:  # noqa: BLE001 — fail closed into INVALID
        blockers.append(f"SAMPLE_RECONSTRUCT:{type(exc).__name__}:{exc}")
        return None, identity, blockers
    identity["WARMUP_N"] = int(len(warmup))
    identity["CONSTRUCTED_N"] = int(len(rows))
    identity["ELIGIBLE_N"] = int(len(eligible))
    if eligible:
        first = C.utc_from_ms(eligible[0].t_ms)
        last = C.utc_from_ms(eligible[-1].t_ms)
        identity["FIRST_T"] = _iso_z(first)
        identity["LAST_T"] = _iso_z(last)
        year_n = {str(y): int(Counter(row.year for row in eligible)[y]) for y in (2017, 2018, 2019)}
        identity["YEAR_ELIGIBLE_N"] = year_n
        if len(eligible) != FROZEN_EXPECTED_ELIGIBLE_N:
            blockers.append(f"ELIGIBLE_N:{len(eligible)}")
        if first != FROZEN_FIRST_RULE_ELIGIBLE_T:
            blockers.append(f"FIRST_T:{_iso_z(first)}")
        if last != FROZEN_LAST_RULE_ELIGIBLE_T:
            blockers.append(f"LAST_T:{_iso_z(last)}")
        if year_n != FROZEN_YEAR_ELIGIBLE_N:
            blockers.append(f"YEAR_ELIGIBLE_N:{year_n}")
    else:
        blockers.append("ELIGIBLE_EMPTY")
    return rows, identity, blockers


def _relative(delta: float | None, uncond: float | None) -> float | None:
    if delta is None or uncond is None or float(uncond) == 0.0:
        return None
    return float(delta) / float(uncond)


def _next_unit(classification: str) -> str:
    if classification == CLASS_SUPPORTED:
        return "PROGRAM_DECISION_POST_D2_BITMEX_REPLICATION_SUPPORTED"
    if classification == CLASS_NOT_SUPPORTED:
        return "PROGRAM_UPDATE_POST_D2_BITMEX_REPLICATION"
    return "D2_BITMEX_REPLICATION_INTEGRITY_ADJUDICATION"


def _replication_status(classification: str) -> str | None:
    if classification == CLASS_SUPPORTED:
        return "SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE"
    if classification == CLASS_NOT_SUPPORTED:
        return "NOT_SUPPORTED_ON_INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_SURFACE"
    return None


def _evidence_label(classification: str) -> str:
    if classification == CLASS_SUPPORTED:
        return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_SUPPORTED"
    if classification == CLASS_NOT_SUPPORTED:
        return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_NOT_SUPPORTED"
    return "INDEPENDENT_PRE2020_CROSS_VENUE_TEMPORAL_REPLICATION_INVALID"


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
            "`VALIDATED_BINANCE_EDGE`, or `PROVEN_ALPHA`. "
            "The frozen mechanism replicated on an earlier era and a different "
            "perpetual venue/contract environment.\n"
        )
    elif result["CLASSIFICATION"] == CLASS_NOT_SUPPORTED:
        supported_note = (
            "\nD2 remains a historical discovery prototype that failed "
            "independent cross-venue temporal replication. No rescue. "
            "Discovery history is preserved.\n"
        )
    return f"""# D2 BitMEX replication RESULT

**Unit:** `{result["unit"]}`  
**Kind:** canonical one-shot scientific execution.

## Identity

```
EVIDENCE_CLASS = {result["EVIDENCE_CLASS"]}
EVIDENCE_LABEL = {result["EVIDENCE_LABEL"]}
RUN_IDENTITY = {result["RUN_IDENTITY"]}
PERMIT_COMMIT = {result["PERMIT_COMMIT"]}
PREREG_SHA = {result["PREREG_ARTIFACT_SHA256"]}
IMPLEMENTATION_SHA = {result["FINAL_IMPLEMENTATION_SHA256"]}
CANONICAL_DATA_SHA = {result["BITMEX_CANONICAL_SHA256"]}
SOURCE_AUTHORITY_SHA = {result["SOURCE_AUTHORITY_SHA256"]}
SEED = {result["RANDOM_SEED"]}
N_CONTROLS = {result["N_CONTROLS"]}
RESULT_PAYLOAD_SHA256 = {result["RESULT_PAYLOAD_SHA256"]}
```

## Sample identity

```
ELIGIBLE_N = {result["SAMPLE_IDENTITY"]["ELIGIBLE_N"]}
FIRST_T = {result["SAMPLE_IDENTITY"]["FIRST_T"]}
LAST_T = {result["SAMPLE_IDENTITY"]["LAST_T"]}
YEAR_ELIGIBLE_N = {result["SAMPLE_IDENTITY"]["YEAR_ELIGIBLE_N"]}
KNOWN_GAP_NEVER_FILLED = {result["SAMPLE_IDENTITY"]["KNOWN_GAP_NEVER_FILLED"]}
```

## Primary metrics

```
ELIGIBLE_N = {primary["ELIGIBLE_N"]}
ABSTAIN_COUNT_TOTAL = {primary["ABSTAIN_COUNT_TOTAL"]}
ABSTAIN_COUNT_2017 = {primary["ABSTAIN_COUNT_2017"]}
ABSTAIN_COUNT_2018 = {primary["ABSTAIN_COUNT_2018"]}
ABSTAIN_COUNT_2019 = {primary["ABSTAIN_COUNT_2019"]}
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


def build_invalid_result(
    *,
    permit_commit: str,
    identity: Mapping[str, Any],
    blockers: list[str],
) -> dict[str, Any]:
    classification = CLASS_INVALID
    yearly = {
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
    return {
        "unit": UNIT,
        "kind": "CANONICAL_ONE_SHOT_SCIENTIFIC_EXECUTION",
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "EVIDENCE_LABEL": _evidence_label(classification),
        "RUN_IDENTITY": FROZEN_RUN_IDENTITY,
        "PERMIT_COMMIT": permit_commit,
        "PREREG_ARTIFACT_SHA256": FROZEN_PREREG_SHA256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": N_REPLICATES,
        "SAMPLE_IDENTITY": dict(identity),
        "PRIMARY_METRICS": {
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
        },
        "GATES": {
            "STATISTICAL_GATE": False,
            "PRACTICAL_GATE": False,
            "PRIMARY_PASS": False,
        },
        "CLASSIFICATION": classification,
        "YEARLY_DIAGNOSTICS": yearly,
        "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
        "NO_YEARLY_RESCUE": True,
        "NO_TWO_OF_THREE_YEAR_REQUIREMENT": True,
        "D2_BITMEX_OUTCOME_COMPUTED": False,
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
        "NOT_VALIDATED_BINANCE_EDGE": True,
        "NOT_PROVEN_ALPHA": True,
        "NEXT_UNIT": _next_unit(classification),
        "BLOCKER": blockers,
    }


def build_scientific_result(
    *,
    permit_commit: str,
    identity: Mapping[str, Any],
    eligible: list[C.DiscoveryRow],
    evaluated: Mapping[str, Any],
) -> dict[str, Any]:
    yearly = yearly_with_relative(evaluated, eligible)
    k_2017 = int(yearly["2017"]["K"])
    k_2018 = int(yearly["2018"]["K"])
    k_2019 = int(yearly["2019"]["K"])
    abstain_total = int(evaluated["ABSTAIN_COUNT"])
    eligible_n = int(evaluated["ELIGIBLE_N"])
    mu_rule = float(evaluated["MU_RULE"])
    mu_control = float(evaluated["MU_CONTROL_MEAN"])
    delta = float(evaluated["DELTA"])
    uncond = float(evaluated["UNCONDITIONAL_MEAN"])
    statistical = bool(evaluated["STATISTICAL_GATE"])
    practical = bool(evaluated["PRACTICAL_GATE"])
    integrity_invalid = bool(evaluated.get("integrity_invalid"))
    classification = classify_replication(
        integrity_invalid=integrity_invalid,
        statistical=statistical,
        practical=practical,
    )
    primary_pass = bool(statistical and practical and not integrity_invalid)
    if classification != CLASS_INVALID:
        # Pooled gates only; yearly diagnostics cannot change this.
        assert classification == (
            CLASS_SUPPORTED if primary_pass else CLASS_NOT_SUPPORTED
        )
    return {
        "unit": UNIT,
        "kind": "CANONICAL_ONE_SHOT_SCIENTIFIC_EXECUTION",
        "EVIDENCE_CLASS": EVIDENCE_CLASS,
        "EVIDENCE_LABEL": _evidence_label(classification),
        "RUN_IDENTITY": FROZEN_RUN_IDENTITY,
        "PERMIT_COMMIT": permit_commit,
        "PREREG_ARTIFACT_SHA256": FROZEN_PREREG_SHA256,
        "FINAL_IMPLEMENTATION_SHA256": FROZEN_IMPLEMENTATION_SHA256,
        "BITMEX_CANONICAL_SHA256": FROZEN_CANONICAL_JSONL_SHA256,
        "BITMEX_CANONICAL_GZ_SHA256": FROZEN_CANONICAL_GZ_SHA256,
        "SOURCE_AUTHORITY_SHA256": FROZEN_SOURCE_AUTHORITY_SHA256,
        "RANDOM_SEED": REPLICATION_RANDOM_SEED,
        "N_CONTROLS": int(evaluated.get("N_RANDOM_CONTROLS") or N_REPLICATES),
        "SAMPLE_IDENTITY": dict(identity),
        "PRIMARY_METRICS": {
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
        },
        "GATES": {
            "STATISTICAL_GATE": statistical,
            "PRACTICAL_GATE": practical,
            "PRIMARY_PASS": primary_pass,
        },
        "CLASSIFICATION": classification,
        "YEARLY_DIAGNOSTICS": yearly,
        "YEARLY_BREAKDOWN_DIAGNOSTIC_ONLY": True,
        "NO_YEARLY_RESCUE": True,
        "NO_TWO_OF_THREE_YEAR_REQUIREMENT": True,
        "D2_BITMEX_OUTCOME_COMPUTED": True,
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
        "NOT_VALIDATED_BINANCE_EDGE": True,
        "NOT_PROVEN_ALPHA": True,
        "NEXT_UNIT": _next_unit(classification),
        "BLOCKER": None,
    }


def write_result(repo: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    hashed = {k: v for k, v in payload.items() if k != "RESULT_PAYLOAD_SHA256"}
    digest = result_payload_sha256(hashed)
    written = dict(hashed)
    written["RESULT_PAYLOAD_SHA256"] = digest
    json_bytes = canonical_result_bytes(written)
    md_bytes = render_markdown(written).encode("utf-8")
    (repo / RESULT_JSON_REL).write_bytes(json_bytes)
    (repo / RESULT_MD_REL).write_bytes(md_bytes)
    return written


def update_binding(repo: Path, result: Mapping[str, Any]) -> None:
    binding = _json_load(repo / BINDING_REL)
    binding["D2_BITMEX_OUTCOME_COMPUTED"] = bool(result["D2_BITMEX_OUTCOME_COMPUTED"])
    binding["CLASSIFICATION_ASSIGNED"] = result["CLASSIFICATION"]
    binding["RESULT_REL"] = RESULT_JSON_REL
    binding["PERMIT_COMMIT"] = result["PERMIT_COMMIT"]
    binding["RESULT_PAYLOAD_SHA256"] = result["RESULT_PAYLOAD_SHA256"]
    binding["RERUN_AUTHORIZED"] = False
    binding["PROTECTED_2025_OPENED"] = False
    binding["PROTECTED_2026_OPENED"] = False
    binding["MARKET_07_CREATED"] = False
    binding["NEXT_UNIT"] = result["NEXT_UNIT"]
    (repo / BINDING_REL).write_text(
        json.dumps(binding, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def execute_one_shot(repo: Path | None = None) -> dict[str, Any]:
    base = repo if repo is not None else C.repo_root()
    if (base / RESULT_JSON_REL).is_file():
        raise RuntimeError("RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN")
    permit_commit = _git(base, "rev-parse", "HEAD")
    authority_blockers = verify_frozen_authorities(base)
    if authority_blockers:
        result = build_invalid_result(
            permit_commit=permit_commit,
            identity={
                "ELIGIBLE_N": None,
                "FIRST_T": None,
                "LAST_T": None,
                "YEAR_ELIGIBLE_N": None,
                "KNOWN_GAP_NEVER_FILLED": None,
            },
            blockers=authority_blockers,
        )
        written = write_result(base, result)
        update_binding(base, written)
        return written
    rows, identity, sample_blockers = reconstruct_sample(base)
    if sample_blockers or rows is None:
        result = build_invalid_result(
            permit_commit=permit_commit,
            identity=identity,
            blockers=sample_blockers or ["SAMPLE_RECONSTRUCT_FAILED"],
        )
        written = write_result(base, result)
        update_binding(base, written)
        return written
    warmup, eligible = split_warmup_eligible(rows)
    del warmup
    evaluated = evaluate_constructed_rows(
        rows,
        seed=REPLICATION_RANDOM_SEED,
        n_replicates=N_REPLICATES,
        enforce_sample_identity=True,
    )
    if bool(evaluated.get("integrity_invalid")):
        result = build_invalid_result(
            permit_commit=permit_commit,
            identity=identity,
            blockers=[f"EVALUATOR_IDENTITY:{evaluated.get('identity_error')}"],
        )
        written = write_result(base, result)
        update_binding(base, written)
        return written
    result = build_scientific_result(
        permit_commit=permit_commit,
        identity=identity,
        eligible=eligible,
        evaluated=evaluated,
    )
    written = write_result(base, _py(result))
    update_binding(base, written)
    return written


def main() -> None:
    execute_one_shot()


if __name__ == "__main__":
    main()
