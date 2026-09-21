"""MARKET-05 atomic execution-claim protocol.

Stdlib only. Creating the claim IS scientific consumption.

    O_CREAT | O_EXCL -> write -> fsync file -> fsync directory

Exactly one process can succeed. A valid claim means
CANONICAL_EXECUTIONS_CONSUMED = 1 for every later authorization decision.
The production API never deletes a claim.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

CLAIM_REL = "docs/research/MARKET_05_EXECUTION_CLAIM.json"
RESULT_JSON_REL = "docs/research/MARKET_05_RESULT.json"
EXECUTION_CLAIM_PROTOCOL = "MARKET_05_ATOMIC_O_EXCL_CLAIM_V1"
CANONICAL_EXECUTION_NUMBER = 1


class Market05ExecutionClaimError(RuntimeError):
    """Claim create/authenticate failure."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _path(rel: str) -> Path:
    return _repo_root() / rel


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def claim_path() -> Path:
    return _path(CLAIM_REL)


def claim_exists() -> bool:
    return claim_path().exists()


def load_execution_claim() -> dict[str, Any]:
    path = claim_path()
    if path.is_symlink():
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_SYMLINK_REFUSED")
    if not path.is_file():
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_MISSING")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_MALFORMED") from exc
    if not isinstance(payload, dict):
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_MALFORMED")
    return payload


def scientific_run_consumed() -> bool:
    """Any existing valid-path claim consumes the one-shot, even if malformed
    enough to fail later authentication: presence itself blocks rerun."""
    return claim_exists()


def canonical_result_integrity_status() -> str:
    """Integrity state after a claim. Never fabricates a scientific class."""
    if not claim_exists():
        return "UNCLAIMED"
    path = _path(RESULT_JSON_REL)
    if path.is_symlink():
        return "MARKET_05_INCOMPLETE_EXECUTION"
    if path.is_file():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "MARKET_05_INCOMPLETE_EXECUTION"
        if isinstance(payload, dict) and payload.get("result_status") == "COMPLETE":
            return "COMPLETE"
    return "MARKET_05_INCOMPLETE_EXECUTION"


def _fsync_directory(directory: Path) -> None:
    flags = os.O_RDONLY
    if hasattr(os, "O_DIRECTORY"):
        flags |= os.O_DIRECTORY
    fd = os.open(str(directory), flags)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _exclusive_create_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(str(path), flags, 0o644)
    except FileExistsError as exc:
        raise Market05ExecutionClaimError("MARKET_05_EXECUTION_CLAIM_ALREADY_EXISTS") from exc
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_directory(path.parent)


def validate_claim_payload(payload: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    required = (
        "research_id",
        "run_identity",
        "arm_json_sha256",
        "reservation_sha256",
        "scientific_implementation_head",
        "scientific_implementation_tree",
        "btc_snapshot_id",
        "eth_snapshot_id",
        "eth_execution_data_id",
        "result_schema_identity",
        "canonical_execution_number",
        "execution_claim_protocol",
        "scientific_run_consumed",
    )
    for key in required:
        if key not in payload:
            raise Market05ExecutionClaimError(f"MARKET_05_CLAIM_MISSING_FIELD:{key}")
    forbidden = (
        "classification",
        "gates",
        "coefficients",
        "bootstrap",
        "maes",
        "year_metrics",
        "RESULT",
        "result",
        "Y",
        "MAE",
    )
    for key in forbidden:
        if key in payload:
            raise Market05ExecutionClaimError("MARKET_05_CLAIM_CONTAINS_OUTCOME_FIELD")
    for key, value in expected.items():
        if payload.get(key) != value:
            raise Market05ExecutionClaimError(f"MARKET_05_CLAIM_FIELD_MISMATCH:{key}")
    if payload.get("canonical_execution_number") != CANONICAL_EXECUTION_NUMBER:
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_EXECUTION_NUMBER_MISMATCH")
    if payload.get("scientific_run_consumed") is not True:
        raise Market05ExecutionClaimError("MARKET_05_CLAIM_NOT_MARKED_CONSUMED")


def create_execution_claim_atomically(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Durably claim the single canonical execution. No outcomes in payload."""
    if claim_exists():
        raise Market05ExecutionClaimError("MARKET_05_EXECUTION_CLAIM_ALREADY_EXISTS")
    body = dict(payload)
    body["execution_claim_protocol"] = EXECUTION_CLAIM_PROTOCOL
    body["canonical_execution_number"] = CANONICAL_EXECUTION_NUMBER
    body["scientific_run_consumed"] = True
    body["result_status"] = "INCOMPLETE_OR_UNKNOWN"
    data = canonical_json_bytes(body)
    _exclusive_create_bytes(claim_path(), data)
    return json.loads(data.decode("utf-8"))


def update_claim_result_status(status: str) -> None:
    """Best-effort status stamp. Never recreates or deletes the claim."""
    payload = load_execution_claim()
    payload["result_status"] = status
    path = claim_path()
    tmp = path.with_name(path.name + ".status.tmp")
    data = canonical_json_bytes(payload)
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(str(tmp), str(path))
    _fsync_directory(path.parent)


def sha256_claim_file() -> str:
    import hashlib

    return hashlib.sha256(claim_path().read_bytes()).hexdigest()
