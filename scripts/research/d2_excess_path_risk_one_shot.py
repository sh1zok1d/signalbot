"""Canonical one-shot D2 excess path-risk execution runner.

This module is the outcome-blind permit-commit runner. Import does not
execute science. ``execute_one_shot()`` is the only canonical route:

    raw = EV.execute_decomposition(repo=repo)

No alternate route, no direct ``evaluate_decomposition()``, no custom
seed / N / selector / target / comparator.

The reviewed evaluator still carries review-era
``REAL_DECOMPOSITION_OUTCOME_COMPUTED = false``. This runner does not
edit that module. After a normal evaluator return, the runner owns
lifecycle metadata on the persisted RESULT.

Authority / snapshot / selector failures before scientific target
evaluation fail closed and do not fabricate a RESULT. Arbitrary
exceptions are not converted into a scientific classification.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Mapping

from scripts.research import d2_excess_path_risk_evaluator as EV
from scripts.research.d2_excess_path_risk_beyond_vol_clustering_design import (
    file_sha256,
    verify_design_authorities,
)
from scripts.research.discovery_sprint_01 import common as C
from scripts.research.market_06_result_persistence import (
    canonical_result_bytes,
    result_payload_sha256,
)

UNIT = "D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_ONE_SHOT_EXECUTION"
KIND = "CANONICAL_ONE_SHOT_SCIENTIFIC_EXECUTION"
RESULT_JSON_REL = "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.json"
RESULT_MD_REL = "docs/research/D2_EXCESS_DIRECTION_ALIGNED_PATH_RISK_RESULT.md"

FROZEN_RUN_IDENTITY = (
    "bfe92af94df23d7aa6f3adc016dc6f558607d772977a1cc6613394ac9a92625f"
)
FROZEN_DESIGN_JSON_SHA256 = (
    "485983701d6e05a57f7dc8bb578613467d6d8f6fb1ec1e28c68d7ca42767c75b"
)
FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256 = (
    "3e26984e2dfd44764b1de32f4d4198c87dd1f413dead1d1a6b0f471188e9d60b"
)
FROZEN_REVIEWED_EVALUATOR_SHA256 = (
    "24571cf3e37356133494e7abd756f59c8acf6e1b18a1e859648040c1d4dac3ee"
)
FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256 = (
    "a982b316254ba54c4974512e0b19fa122a37f1744c8b0c49b2666046f352d13c"
)
FROZEN_CANONICAL_SELECTOR_DIGEST = (
    "5eeb8480f8d1e576dec5e23f1a5545354c3d7b0fa16d76e6fbdbb89135b71f69"
)
FROZEN_CORE_BTC_SNAPSHOT_ID = (
    "717d37a404f81eefd58c9a796cc11868c48226baf1de8ffecad5e5607f8dd415"
)


class OneShotExecutionError(RuntimeError):
    """Fail-closed one-shot lifecycle error. Not a scientific classification."""


def _git(repo: Path, *args: str) -> str:
    """Read git identity from ``repo`` when it is a work tree.

    Synthetic test checkouts copy artifacts into a temp directory that is
    not a git work tree. In that case HEAD is taken from the signalbot
    repository root — the executing commit — never invented.
    """

    probe = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    cwd = repo if probe.returncode == 0 else C.repo_root()
    return subprocess.check_output(["git", *args], cwd=cwd, text=True).strip()


def _jsonable(value: Any) -> Any:
    """Python JSON types only. Does not change scientific meaning."""

    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, bool):
        return bool(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return float(value)
    if value is None:
        return None
    item = getattr(value, "item", None)
    if callable(item):
        return _jsonable(item())
    return value


def result_exists(repo: Path) -> bool:
    return (repo / RESULT_JSON_REL).is_file() or (repo / RESULT_MD_REL).is_file()


def refuse_if_result_exists(repo: Path) -> None:
    if result_exists(repo):
        raise OneShotExecutionError("RESULT_ALREADY_EXISTS_RERUN_FORBIDDEN")


def verify_pre_scientific_authorities(repo: Path) -> dict[str, Any]:
    """Metadata/authority checks. Happens before CORE BTC OHLC opens."""

    permit = EV.verify_tracked_permit(repo)
    blockers = verify_design_authorities(repo)
    if blockers:
        raise OneShotExecutionError(
            f"DESIGN_AUTHORITY_BLOCKERS:{','.join(blockers)}"
        )
    identity = EV.verify_selector_identity_authority(repo)
    snapshot_id = EV.verify_core_btc_snapshot_identity(repo)
    digest = str(identity.get("CANONICAL_SELECTOR_DIGEST") or "")
    if digest != FROZEN_CANONICAL_SELECTOR_DIGEST:
        raise OneShotExecutionError(f"CANONICAL_SELECTOR_DIGEST_MISMATCH:{digest}")
    if str(snapshot_id) != FROZEN_CORE_BTC_SNAPSHOT_ID:
        raise OneShotExecutionError(f"CORE_BTC_SNAPSHOT_MISMATCH:{snapshot_id}")
    if str(permit.get("RUN_IDENTITY") or "") != FROZEN_RUN_IDENTITY:
        raise OneShotExecutionError("PERMIT_RUN_IDENTITY_MISMATCH")
    if str(permit.get("DESIGN_JSON_SHA256") or "") != FROZEN_DESIGN_JSON_SHA256:
        raise OneShotExecutionError("PERMIT_DESIGN_JSON_SHA256_MISMATCH")
    if (
        str(permit.get("IMPLEMENTATION_REVIEW_JSON_SHA256") or "")
        != FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
    ):
        raise OneShotExecutionError("PERMIT_REVIEW_JSON_SHA256_MISMATCH")
    if (
        str(permit.get("REVIEWED_EVALUATOR_SHA256") or "")
        != FROZEN_REVIEWED_EVALUATOR_SHA256
    ):
        raise OneShotExecutionError("PERMIT_REVIEWED_EVALUATOR_SHA256_MISMATCH")
    if (
        str(permit.get("SELECTOR_IDENTITY_AUTHORITY_SHA256") or "")
        != FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256
    ):
        raise OneShotExecutionError("PERMIT_SELECTOR_AUTHORITY_SHA256_MISMATCH")
    if str(permit.get("CORE_BTC_SNAPSHOT_ID") or "") != FROZEN_CORE_BTC_SNAPSHOT_ID:
        raise OneShotExecutionError("PERMIT_CORE_BTC_SNAPSHOT_MISMATCH")
    return {"permit": permit, "identity": identity, "snapshot_id": snapshot_id}


def wrap_one_shot_result(
    raw: Mapping[str, Any],
    *,
    permit_commit: str,
    execution_permit_sha256: str,
) -> dict[str, Any]:
    """Keep evaluator science; overlay one-shot lifecycle metadata.

    Does not reinterpret ``CLASSIFICATION``. If the evaluator returned
    ``D2_DECOMPOSITION_INVALID``, that exact classification and its
    integrity reasons are preserved.
    """

    if not isinstance(raw, Mapping):
        raise OneShotExecutionError("EVALUATOR_PAYLOAD_NOT_OBJECT")
    if "CLASSIFICATION" not in raw:
        raise OneShotExecutionError("EVALUATOR_CLASSIFICATION_MISSING")
    scientific = _jsonable(dict(raw))
    classification = scientific["CLASSIFICATION"]
    integrity_reasons = scientific.get("INTEGRITY_REASONS")
    scientific["kind"] = KIND
    scientific["ONE_SHOT"] = True
    scientific["EXECUTION_AUTHORIZED"] = True
    scientific["RERUN_AUTHORIZED"] = False
    scientific["REAL_DECOMPOSITION_OUTCOME_COMPUTED"] = True
    scientific["PERMIT_COMMIT"] = str(permit_commit)
    scientific["RUN_IDENTITY"] = FROZEN_RUN_IDENTITY
    scientific["EXECUTION_PERMIT_SHA256"] = str(execution_permit_sha256)
    scientific["SELECTOR_IDENTITY_AUTHORITY_SHA256"] = (
        FROZEN_SELECTOR_IDENTITY_AUTHORITY_SHA256
    )
    scientific["IMPLEMENTATION_REVIEW_JSON_SHA256"] = (
        FROZEN_IMPLEMENTATION_REVIEW_JSON_SHA256
    )
    scientific["REVIEWED_EVALUATOR_SHA256"] = FROZEN_REVIEWED_EVALUATOR_SHA256
    scientific["DESIGN_JSON_SHA256"] = FROZEN_DESIGN_JSON_SHA256
    scientific["PROTECTED_2025_OPENED"] = False
    scientific["PROTECTED_2026_OPENED"] = False
    scientific["BITMEX_2017_2019_REUSED_FOR_NEW_TARGET"] = False
    scientific["MARKET_07_CREATED"] = False
    scientific["CANONICAL_SELECTOR_DIGEST"] = FROZEN_CANONICAL_SELECTOR_DIGEST
    scientific["CLASSIFICATION"] = classification
    if integrity_reasons is not None:
        scientific["INTEGRITY_REASONS"] = integrity_reasons
    scientific["ONE_SHOT_UNIT"] = UNIT
    return scientific


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


def render_markdown(result: Mapping[str, Any]) -> str:
    classification = result.get("CLASSIFICATION")
    lines = [
        "# D2 excess direction-aligned path-risk — canonical one-shot RESULT",
        "",
        "Canonical one-shot scientific execution. Classification is the",
        "evaluator-produced value with no reinterpretation.",
        "",
        f"CLASSIFICATION = `{classification}`",
        f"kind = `{result.get('kind')}`",
        f"ONE_SHOT_UNIT = `{result.get('ONE_SHOT_UNIT')}`",
        "",
        "## Authority",
        "",
        f"- PERMIT_COMMIT = `{result.get('PERMIT_COMMIT')}`",
        f"- RUN_IDENTITY = `{result.get('RUN_IDENTITY')}`",
        f"- EXECUTION_PERMIT_SHA256 = `{result.get('EXECUTION_PERMIT_SHA256')}`",
        f"- SELECTOR_IDENTITY_AUTHORITY_SHA256 = `{result.get('SELECTOR_IDENTITY_AUTHORITY_SHA256')}`",
        f"- IMPLEMENTATION_REVIEW_JSON_SHA256 = `{result.get('IMPLEMENTATION_REVIEW_JSON_SHA256')}`",
        f"- REVIEWED_EVALUATOR_SHA256 = `{result.get('REVIEWED_EVALUATOR_SHA256')}`",
        f"- DESIGN_JSON_SHA256 = `{result.get('DESIGN_JSON_SHA256')}`",
        f"- CANONICAL_SELECTOR_DIGEST = `{result.get('CANONICAL_SELECTOR_DIGEST')}`",
        f"- RESULT_PAYLOAD_SHA256 = `{result.get('RESULT_PAYLOAD_SHA256')}`",
        "",
        "## Lifecycle",
        "",
        f"- ONE_SHOT = `{str(result.get('ONE_SHOT')).lower()}`",
        f"- EXECUTION_AUTHORIZED = `{str(result.get('EXECUTION_AUTHORIZED')).lower()}`",
        f"- RERUN_AUTHORIZED = `{str(result.get('RERUN_AUTHORIZED')).lower()}`",
        f"- REAL_DECOMPOSITION_OUTCOME_COMPUTED = `{str(result.get('REAL_DECOMPOSITION_OUTCOME_COMPUTED')).lower()}`",
        f"- PROTECTED_2025_OPENED = `{str(result.get('PROTECTED_2025_OPENED')).lower()}`",
        f"- PROTECTED_2026_OPENED = `{str(result.get('PROTECTED_2026_OPENED')).lower()}`",
        f"- BITMEX_2017_2019_REUSED_FOR_NEW_TARGET = `{str(result.get('BITMEX_2017_2019_REUSED_FOR_NEW_TARGET')).lower()}`",
        f"- MARKET_07_CREATED = `{str(result.get('MARKET_07_CREATED')).lower()}`",
        "",
        "## Integrity",
        "",
        f"- INTEGRITY_INVALID = `{result.get('INTEGRITY_INVALID')}`",
        f"- INTEGRITY_REASONS = `{result.get('INTEGRITY_REASONS')}`",
        "",
    ]
    return "\n".join(lines)


def persist_result(repo: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    hashed = {key: value for key, value in payload.items() if key != "RESULT_PAYLOAD_SHA256"}
    digest = result_payload_sha256(hashed)
    written = dict(hashed)
    written["RESULT_PAYLOAD_SHA256"] = digest
    json_bytes = canonical_result_bytes(written)
    md_bytes = render_markdown(written).encode("utf-8")
    _atomic_write(repo / RESULT_JSON_REL, json_bytes)
    _atomic_write(repo / RESULT_MD_REL, md_bytes)
    return written


def execute_one_shot(repo: Path | None = None) -> dict[str, Any]:
    base = repo if repo is not None else C.repo_root()
    refuse_if_result_exists(base)
    verify_pre_scientific_authorities(base)
    permit_commit = _git(base, "rev-parse", "HEAD")
    execution_permit_sha256 = file_sha256(base / EV.EXECUTION_PERMIT_REL)
    raw = EV.execute_decomposition(repo=base)
    wrapped = wrap_one_shot_result(
        raw,
        permit_commit=permit_commit,
        execution_permit_sha256=execution_permit_sha256,
    )
    return persist_result(base, wrapped)


def main() -> None:
    execute_one_shot()


if __name__ == "__main__":
    main()
