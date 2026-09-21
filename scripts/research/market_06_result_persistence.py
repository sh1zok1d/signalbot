"""Deterministic MARKET-06 canonical RESULT serialization and staging.

Repairs red-team L11 (result persistence): the canonical outcome must be
reducible to exact, reproducible bytes bound to the full authority chain,
not merely printed to stdout.

Determinism contract:

* canonical JSON (``sort_keys=True``, ``allow_nan=False``, 2-space indent,
  single trailing newline, UTF-8);
* ``RESULT_PAYLOAD_SHA256`` is taken over exactly those bytes;
* nothing clock-, path-, host-, process-, user-, or UUID-dependent may
  enter the payload, so the same scientific outcome always yields the same
  digest.

Staging only: this module writes the frozen result target paths and returns
the exact bytes and digest. It never runs ``git``; committing the staged
RESULT stays an explicit human/orchestration step.

No live RESULT is created by importing or testing this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scripts.research import market_06_execution_lifecycle as lifecycle
from scripts.research import market_06_git_authority as gitauth

RESULT_SCHEMA = "signalbot_market_06_cross_venue_dislocation_result"
RESULT_SCHEMA_VERSION = "1.0.0"

REQUIRED_GATES: tuple[str, ...] = ("G1", "G2", "G3", "G4", "G5", "G6")

REQUIRED_OUTCOME_METRICS: tuple[str, ...] = (
    "classification",
    "gates",
    "BETA_ABS_DISLOCATION_Z",
    "BETA_ABS_DISLOCATION_Z_CI95_LOW",
    "BETA_ABS_DISLOCATION_Z_CI95_HIGH",
    "POOLED_MAE_BASELINE",
    "POOLED_MAE_CANDIDATE",
    "RELATIVE_MAE_IMPROVEMENT",
    "RELATIVE_MAE_IMPROVEMENT_CI95_LOW",
    "RELATIVE_MAE_IMPROVEMENT_CI95_HIGH",
    "YEAR_2023_RELATIVE_MAE_IMPROVEMENT",
    "YEAR_2024_RELATIVE_MAE_IMPROVEMENT",
    "YEAR_2023_BASELINE_MAE",
    "YEAR_2023_CANDIDATE_MAE",
    "YEAR_2024_BASELINE_MAE",
    "YEAR_2024_CANDIDATE_MAE",
    "N_TRAIN",
    "N_2023",
    "N_2024",
    "BASELINE_COLUMNS",
    "CANDIDATE_COLUMNS",
    "TRAIN_SD_CONVENTION",
    "BLOCK_LENGTH_DAYS",
    "BOOTSTRAP_REPLICATES",
    "RANDOM_SEED",
)

LEGAL_CLASSIFICATIONS = (
    "MARKET_06_PROMOTED_HISTORICAL_CANDIDATE",
    "MARKET_06_NO_EVIDENCE",
    "MARKET_06_INCOMPLETE_EXECUTION",
)

# Identity must never depend on these. Matched EXACTLY (plus the suffix
# rules below), never as a substring: structural counts such as
# "binance_timestamps" are legitimate deterministic audit fields, while a
# clock value named "timestamp" is not.
FORBIDDEN_PAYLOAD_KEYS = frozenset(
    {
        "timestamp",
        "timestamp_utc",
        "generated_at",
        "created_at",
        "written_at",
        "executed_at",
        "utcnow",
        "now",
        "uuid",
        "guid",
        "hostname",
        "host",
        "pid",
        "process_id",
        "user",
        "username",
        "cwd",
        "path",
        "tmpdir",
        "random_state",
        "entropy",
        "elapsed",
        "elapsed_seconds",
        "duration",
        "duration_seconds",
        "wall_clock",
        "seed_from_clock",
    }
)

FORBIDDEN_KEY_SUFFIXES = ("_at", "_uuid", "_pid", "_hostname", "_path", "_paths")

# Deterministic structural fields that legitimately end in a banned suffix.
ALLOWED_KEY_EXCEPTIONS = frozenset({"result_target_paths"})


class Market06ResultError(RuntimeError):
    """The canonical RESULT could not be built or staged."""


@dataclass(frozen=True)
class StagedResult:
    run_identity: str
    payload: dict[str, Any]
    json_bytes: bytes
    sha256: str
    json_path: str
    md_path: str
    md_bytes: bytes

    def written_paths(self) -> tuple[str, str]:
        return self.json_path, self.md_path


def canonical_result_bytes(payload: Mapping[str, Any]) -> bytes:
    """Exact deterministic bytes the RESULT digest is taken over."""

    try:
        text = json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ": "),
        )
    except ValueError as exc:  # NaN / Infinity
        raise Market06ResultError("MARKET_06_RESULT_NONFINITE_VALUE") from exc
    return (text + "\n").encode("utf-8")


def result_payload_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_result_bytes(payload)).hexdigest()


def _assert_finite(value: Any, *, where: str) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise Market06ResultError(f"MARKET_06_RESULT_NONFINITE_VALUE:{where}")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _assert_finite(item, where=f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_finite(item, where=f"{where}[{index}]")


def _assert_no_forbidden_keys(value: Any, *, where: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            lowered = str(key).lower()
            if lowered not in ALLOWED_KEY_EXCEPTIONS:
                if lowered in FORBIDDEN_PAYLOAD_KEYS or lowered.endswith(
                    FORBIDDEN_KEY_SUFFIXES
                ):
                    raise Market06ResultError(
                        f"MARKET_06_RESULT_NONDETERMINISTIC_FIELD:{where}.{key}"
                    )
            _assert_no_forbidden_keys(item, where=f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_no_forbidden_keys(item, where=f"{where}[{index}]")


def validate_outcome(outcome: Mapping[str, Any]) -> None:
    for field in REQUIRED_OUTCOME_METRICS:
        if field not in outcome:
            raise Market06ResultError(f"MARKET_06_RESULT_METRIC_MISSING:{field}")
    classification = outcome["classification"]
    if classification not in LEGAL_CLASSIFICATIONS:
        raise Market06ResultError(f"MARKET_06_RESULT_ILLEGAL_CLASSIFICATION:{classification}")
    gates = outcome["gates"]
    if not isinstance(gates, Mapping):
        raise Market06ResultError("MARKET_06_RESULT_GATES_TYPE")
    for gate in REQUIRED_GATES:
        if gate not in gates:
            raise Market06ResultError(f"MARKET_06_RESULT_GATE_MISSING:{gate}")
        if not isinstance(gates[gate], bool):
            raise Market06ResultError(f"MARKET_06_RESULT_GATE_TYPE:{gate}")
    _assert_finite(outcome, where="outcome")
    _assert_no_forbidden_keys(outcome, where="outcome")


def build_canonical_result_payload(
    authority: lifecycle.ClaimAuthority,
    outcome: Mapping[str, Any],
    audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind the scientific outcome to the full authority chain."""

    if not isinstance(authority, lifecycle.ClaimAuthority):
        raise Market06ResultError("MARKET_06_RESULT_CLAIM_AUTHORITY_REQUIRED")
    lifecycle.require_permit(authority.permit)
    validate_outcome(outcome)
    _assert_finite(audit, where="audit")
    _assert_no_forbidden_keys(audit, where="audit")

    if audit.get("run_identity") != authority.run_identity:
        raise Market06ResultError("MARKET_06_RESULT_AUDIT_RUN_IDENTITY")
    if audit.get("dataset_id") != lifecycle.DATASET_ID:
        raise Market06ResultError("MARKET_06_RESULT_AUDIT_DATASET_ID")
    if audit.get("snapshot_id") != lifecycle.SNAPSHOT_ID:
        raise Market06ResultError("MARKET_06_RESULT_AUDIT_SNAPSHOT_ID")

    payload: dict[str, Any] = {
        "schema": RESULT_SCHEMA,
        "schema_version": RESULT_SCHEMA_VERSION,
        "research_id": lifecycle.RESEARCH_ID,
        "run_identity": authority.run_identity,
        "arm_commit": authority.arm_commit,
        "reservation_commit": authority.reservation_commit,
        "claim_commit": authority.claim_commit,
        "implementation_freeze_head": authority.permit.implementation_freeze_head,
        "implementation_freeze_tree": authority.permit.implementation_freeze_tree,
        "prereg_freeze_head": lifecycle.PREREG_FREEZE_HEAD,
        "prereg_freeze_tree": lifecycle.PREREG_FREEZE_TREE,
        "prereg_content_head": lifecycle.PREREG_CONTENT_HEAD,
        "prereg_content_tree": lifecycle.PREREG_CONTENT_TREE,
        "dataset_id": lifecycle.DATASET_ID,
        "snapshot_id": lifecycle.SNAPSHOT_ID,
        "durable_evidence_root_sha256": lifecycle.DURABLE_EVIDENCE_ROOT_SHA256,
        "authorization_kind": lifecycle.AUTHORIZATION_KIND,
        "classification": outcome["classification"],
        "gates": {gate: bool(outcome["gates"][gate]) for gate in sorted(outcome["gates"])},
        "metrics": {
            field: outcome[field]
            for field in REQUIRED_OUTCOME_METRICS
            if field not in ("classification", "gates")
        },
        "eligible_support": {
            "N_TRAIN": outcome["N_TRAIN"],
            "N_2023": outcome["N_2023"],
            "N_2024": outcome["N_2024"],
        },
        "bootstrap_constants": {
            "BLOCK_LENGTH_DAYS": outcome["BLOCK_LENGTH_DAYS"],
            "BOOTSTRAP_REPLICATES": outcome["BOOTSTRAP_REPLICATES"],
            "RANDOM_SEED": outcome["RANDOM_SEED"],
            "TRAIN_SD_CONVENTION": outcome["TRAIN_SD_CONVENTION"],
        },
        "reconstruction_audit": dict(sorted(audit.items())),
        "scientific_outcomes_inspected": True,
        "protected_2025_opened": False,
        "protected_2026_opened": False,
    }
    _assert_no_forbidden_keys(payload, where="result")
    _assert_finite(payload, where="result")
    return payload


def render_result_markdown(payload: Mapping[str, Any]) -> bytes:
    """Deterministic human-readable twin. No clock, no paths."""

    gates = payload["gates"]
    lines = [
        "# MARKET-06 — Cross-Venue Dislocation Adverse-Path Risk: RESULT",
        "",
        f"Classification: `{payload['classification']}`",
        f"Run identity: `{payload['run_identity']}`",
        "",
        "## Authority chain",
        "",
        f"- claim commit: `{payload['claim_commit']}`",
        f"- reservation commit: `{payload['reservation_commit']}`",
        f"- ARM commit: `{payload['arm_commit']}`",
        f"- implementation freeze: `{payload['implementation_freeze_head']}`",
        f"- prereg freeze: `{payload['prereg_freeze_head']}`",
        f"- dataset: `{payload['dataset_id']}` snapshot `{payload['snapshot_id']}`",
        "",
        "## Gates",
        "",
    ]
    for gate in sorted(gates):
        lines.append(f"- `{gate}` = `{str(bool(gates[gate])).lower()}`")
    lines += [
        "",
        "## Support",
        "",
        f"- N_TRAIN = `{payload['eligible_support']['N_TRAIN']}`",
        f"- N_2023 = `{payload['eligible_support']['N_2023']}`",
        f"- N_2024 = `{payload['eligible_support']['N_2024']}`",
        "",
        "Protected years remain unopened: "
        f"2025 `{str(payload['protected_2025_opened']).lower()}`, "
        f"2026 `{str(payload['protected_2026_opened']).lower()}`.",
        "",
    ]
    return ("\n".join(lines)).encode("utf-8")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    directory = os.open(str(path.parent), os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def stage_canonical_result(
    authority: lifecycle.ClaimAuthority,
    outcome: Mapping[str, Any],
    audit: Mapping[str, Any],
    *,
    write: bool = True,
) -> StagedResult:
    """Build and stage the canonical RESULT at the frozen target paths.

    Refuses if a RESULT for this run identity already exists. Writes only
    the frozen target paths; a caller-supplied path is impossible by
    construction. Does not commit.
    """

    if not isinstance(authority, lifecycle.ClaimAuthority):
        raise Market06ResultError("MARKET_06_RESULT_CLAIM_AUTHORITY_REQUIRED")

    lifecycle.require_no_existing_result(
        authority.run_identity, commit=authority.claim_commit
    )

    targets = authority.claim.get("result_target_paths") or []
    if lifecycle.RESULT_JSON_REL not in targets:
        raise Market06ResultError("MARKET_06_RESULT_TARGET_NOT_CLAIMED")

    payload = build_canonical_result_payload(authority, outcome, audit)
    json_bytes = canonical_result_bytes(payload)
    md_bytes = render_result_markdown(payload)
    digest = hashlib.sha256(json_bytes).hexdigest()

    if write:
        root = gitauth.repo_root()
        _atomic_write(root / lifecycle.RESULT_JSON_REL, json_bytes)
        _atomic_write(root / lifecycle.RESULT_MD_REL, md_bytes)

    return StagedResult(
        run_identity=authority.run_identity,
        payload=payload,
        json_bytes=json_bytes,
        sha256=digest,
        json_path=lifecycle.RESULT_JSON_REL,
        md_path=lifecycle.RESULT_MD_REL,
        md_bytes=md_bytes,
    )
