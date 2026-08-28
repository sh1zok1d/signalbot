"""Reusable research-integrity primitives for Signalbot Batch02+ experiments.

This module is intentionally small. It does not encode any hypothesis, threshold,
or market conclusion. It turns the strongest pre-outcome controls learned during
Batch01/H05 into executable defaults for new research only.

Frozen H01-H05 runners are historical artifacts and MUST NOT be refactored to
import this module merely for code deduplication.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Hashable, Iterable, Mapping, Sequence

import yaml


class ResearchHarnessError(RuntimeError):
    """Base error for fail-closed research-integrity checks."""


class DatasetIdentityError(ResearchHarnessError):
    pass


class OutcomeBoundaryError(ResearchHarnessError):
    pass


class LookaheadError(ResearchHarnessError):
    pass


class SupportMismatchError(ResearchHarnessError):
    pass


class ArtifactExistsError(ResearchHarnessError):
    pass


@dataclass(frozen=True)
class DatasetIdentityContract:
    dataset_id: str
    snapshot_id: str
    required_status: str = "ACCEPTED_FOR_DISCOVERY"
    research_authorized: bool = True
    confirmatory_authorized: bool = False


@dataclass(frozen=True)
class OutcomeAccessPolicy:
    stage: str
    start_inclusive_ms: int
    end_exclusive_ms: int
    allowed_years: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.stage:
            raise ValueError("stage must be non-empty")
        if self.end_exclusive_ms <= self.start_inclusive_ms:
            raise ValueError("end_exclusive_ms must be greater than start_inclusive_ms")
        if not self.allowed_years:
            raise ValueError("allowed_years must be non-empty")
        if len(set(self.allowed_years)) != len(self.allowed_years):
            raise ValueError("allowed_years must be unique")


@dataclass(frozen=True)
class AuthorizedDataset:
    """Proof that repository + runtime dataset identity were checked first."""

    dataset_root: Path
    identity: DatasetIdentityContract
    policy: OutcomeAccessPolicy
    repo_manifest_path: Path
    runtime_snapshot_path: Path

    def list_monthly_partitions(self) -> list[Path]:
        """Return only explicitly allowed year partitions.

        This deliberately avoids a broad `*.parquet` scan followed by a row
        filter. Future/holdout partitions can coexist on disk without becoming
        visible to a development runner through this API.
        """
        monthly = self.dataset_root / "canonical" / "1m" / "monthly"
        if not monthly.is_dir():
            raise DatasetIdentityError(f"missing canonical monthly directory: {monthly}")

        out: list[Path] = []
        for year in self.policy.allowed_years:
            prefix = f"{year:04d}-"
            for path in sorted(monthly.glob(f"{prefix}*.parquet")):
                if not path.name.startswith(prefix):
                    raise DatasetIdentityError(
                        f"partition escaped allowed-year selector: {path.name}"
                    )
                out.append(path)

        if not out:
            raise DatasetIdentityError(
                f"no monthly partitions found for allowed years {self.policy.allowed_years}"
            )
        return out

    def assert_outcome_window(self, decision_t_ms: int, horizon_ms: int) -> None:
        if horizon_ms < 0:
            raise OutcomeBoundaryError("horizon_ms must be >= 0")
        if decision_t_ms < self.policy.start_inclusive_ms:
            raise OutcomeBoundaryError(
                f"decision {decision_t_ms} precedes {self.policy.start_inclusive_ms}"
            )
        end_ms = decision_t_ms + horizon_ms
        if end_ms >= self.policy.end_exclusive_ms:
            raise OutcomeBoundaryError(
                f"outcome window end {end_ms} reaches/exceeds "
                f"{self.policy.end_exclusive_ms}"
            )


def _require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise DatasetIdentityError(f"{label} mismatch: {actual!r} != {expected!r}")


def authorize_dataset_access(
    *,
    repo_manifest_path: Path,
    dataset_root: Path,
    identity: DatasetIdentityContract,
    policy: OutcomeAccessPolicy,
) -> AuthorizedDataset:
    """Verify dataset identity before a runner can obtain outcome paths."""
    try:
        repo_manifest = yaml.safe_load(repo_manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetIdentityError(
            f"missing repository dataset manifest: {repo_manifest_path}"
        ) from exc

    if not isinstance(repo_manifest, Mapping):
        raise DatasetIdentityError("repository dataset manifest must be a mapping")

    _require_equal(repo_manifest.get("dataset_id"), identity.dataset_id, "dataset_id")
    _require_equal(repo_manifest.get("snapshot_id"), identity.snapshot_id, "snapshot_id")
    _require_equal(repo_manifest.get("status"), identity.required_status, "status")
    _require_equal(
        repo_manifest.get("research_authorized"),
        identity.research_authorized,
        "research_authorized",
    )
    _require_equal(
        repo_manifest.get("confirmatory_authorized"),
        identity.confirmatory_authorized,
        "confirmatory_authorized",
    )

    runtime_snapshot = dataset_root / "reports" / "snapshot_manifest.json"
    try:
        runtime = json.loads(runtime_snapshot.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetIdentityError(
            f"missing runtime dataset identity evidence: {runtime_snapshot}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DatasetIdentityError(
            f"invalid runtime snapshot JSON: {runtime_snapshot}"
        ) from exc

    if not isinstance(runtime, Mapping):
        raise DatasetIdentityError("runtime snapshot manifest must be a mapping")

    if "dataset_id" in runtime:
        _require_equal(runtime.get("dataset_id"), identity.dataset_id, "runtime dataset_id")
    _require_equal(runtime.get("snapshot_id"), identity.snapshot_id, "runtime snapshot_id")

    return AuthorizedDataset(
        dataset_root=dataset_root,
        identity=identity,
        policy=policy,
        repo_manifest_path=repo_manifest_path,
        runtime_snapshot_path=runtime_snapshot,
    )


def assert_no_lookahead(
    decision_t_ms: int | Sequence[int],
    available_at_ms: int | Sequence[int],
) -> None:
    """Require every input to be available no later than its decision time."""
    decisions = (
        (decision_t_ms,)
        if isinstance(decision_t_ms, int)
        else tuple(int(x) for x in decision_t_ms)
    )
    available = (
        (available_at_ms,)
        if isinstance(available_at_ms, int)
        else tuple(int(x) for x in available_at_ms)
    )
    if len(decisions) != len(available):
        raise LookaheadError(
            f"decision/availability length mismatch: {len(decisions)} != {len(available)}"
        )
    for idx, (decision, avail) in enumerate(zip(decisions, available)):
        if avail > decision:
            raise LookaheadError(
                f"lookahead at index {idx}: available_at_ms={avail} > decision_t_ms={decision}"
            )


def _finite_float(value, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise SupportMismatchError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(out):
        raise SupportMismatchError(f"{label} is not finite: {value!r}")
    return out


def paired_same_support_delta(
    candidate_by_id: Mapping[Hashable, float],
    reference_by_id: Mapping[Hashable, float],
    *,
    support_ids: Iterable[Hashable] | None = None,
) -> dict:
    """Compute a paired candidate-reference delta on one explicit support.

    If `support_ids` is omitted, candidate and reference key sets must be
    exactly equal. Silent intersection is forbidden.
    """
    candidate_keys = set(candidate_by_id)
    reference_keys = set(reference_by_id)

    if support_ids is None:
        if candidate_keys != reference_keys:
            raise SupportMismatchError(
                "candidate/reference supports differ; pass an explicit predeclared "
                "support_ids subset or repair the comparator"
            )
        ids = tuple(sorted(candidate_keys, key=repr))
    else:
        ids = tuple(dict.fromkeys(support_ids))
        if not ids:
            raise SupportMismatchError("support_ids must be non-empty")
        missing_candidate = [key for key in ids if key not in candidate_by_id]
        missing_reference = [key for key in ids if key not in reference_by_id]
        if missing_candidate or missing_reference:
            raise SupportMismatchError(
                f"explicit support missing candidate={missing_candidate!r} "
                f"reference={missing_reference!r}"
            )

    if not ids:
        raise SupportMismatchError("paired support must be non-empty")

    candidate_values = [
        _finite_float(candidate_by_id[key], f"candidate[{key!r}]") for key in ids
    ]
    reference_values = [
        _finite_float(reference_by_id[key], f"reference[{key!r}]") for key in ids
    ]
    candidate_mean = sum(candidate_values) / len(candidate_values)
    reference_mean = sum(reference_values) / len(reference_values)
    return {
        "support_n": len(ids),
        "candidate_support_mean": candidate_mean,
        "reference_support_mean": reference_mean,
        "delta": candidate_mean - reference_mean,
        "support_ids": list(ids),
    }


def weighted_same_support_delta(
    candidate_by_key: Mapping[Hashable, float],
    reference_by_key: Mapping[Hashable, float],
    weights_by_key: Mapping[Hashable, float],
    *,
    support_keys: Iterable[Hashable] | None = None,
) -> dict:
    """Compute candidate-reference means using the same keys and same weights.

    This is the reusable guard against the H05 B-01 class: a full candidate
    mean must never be compared with a control mean estimated only on overlap
    strata. Extra candidate strata are harmless only when the caller supplies
    an explicit, predeclared `support_keys` subset and both sides are then
    evaluated on exactly that subset.
    """
    candidate_keys = set(candidate_by_key)
    reference_keys = set(reference_by_key)
    weight_keys = set(weights_by_key)

    if support_keys is None:
        if not (candidate_keys == reference_keys == weight_keys):
            raise SupportMismatchError(
                "candidate/reference/weight supports differ; silent intersection "
                "is forbidden"
            )
        keys = tuple(sorted(candidate_keys, key=repr))
    else:
        keys = tuple(dict.fromkeys(support_keys))
        if not keys:
            raise SupportMismatchError("support_keys must be non-empty")
        missing_candidate = [key for key in keys if key not in candidate_by_key]
        missing_reference = [key for key in keys if key not in reference_by_key]
        missing_weight = [key for key in keys if key not in weights_by_key]
        if missing_candidate or missing_reference or missing_weight:
            raise SupportMismatchError(
                f"explicit support missing candidate={missing_candidate!r} "
                f"reference={missing_reference!r} weights={missing_weight!r}"
            )

    if not keys:
        raise SupportMismatchError("weighted support must be non-empty")

    weights: list[float] = []
    candidate: list[float] = []
    reference: list[float] = []
    for key in keys:
        weight = _finite_float(weights_by_key[key], f"weight[{key!r}]")
        if weight <= 0.0:
            raise SupportMismatchError(f"weight[{key!r}] must be > 0")
        weights.append(weight)
        candidate.append(_finite_float(candidate_by_key[key], f"candidate[{key!r}]"))
        reference.append(_finite_float(reference_by_key[key], f"reference[{key!r}]"))

    weight_sum = sum(weights)
    candidate_mean = sum(w * x for w, x in zip(weights, candidate)) / weight_sum
    reference_mean = sum(w * x for w, x in zip(weights, reference)) / weight_sum

    return {
        "support_n": len(keys),
        "weight_sum": weight_sum,
        "candidate_support_mean": candidate_mean,
        "reference_support_mean": reference_mean,
        "delta": candidate_mean - reference_mean,
        "support_keys": list(keys),
    }


def fail_closed_gate_conjunction(
    gates: Mapping[str, object],
    required_gate_names: Sequence[str],
) -> bool:
    """Pass only when every required gate exists and is literal `True`."""
    if not required_gate_names:
        return False
    return all(gates.get(name) is True for name in required_gate_names)


def build_run_identity(
    *,
    hypothesis_id: str,
    stage: str,
    code_sha: str,
    authorized_dataset: AuthorizedDataset,
    command: Sequence[str],
    seeds: Mapping[str, int] | None = None,
) -> dict:
    """Build deterministic provenance fields that must accompany a result."""
    if not hypothesis_id or not stage or not code_sha:
        raise ValueError("hypothesis_id, stage and code_sha are required")
    if not command:
        raise ValueError("command must be non-empty")
    return {
        "hypothesis_id": hypothesis_id,
        "stage": stage,
        "code_sha": code_sha,
        "dataset_id": authorized_dataset.identity.dataset_id,
        "snapshot_id": authorized_dataset.identity.snapshot_id,
        "window": {
            "start_inclusive_ms": authorized_dataset.policy.start_inclusive_ms,
            "end_exclusive_ms": authorized_dataset.policy.end_exclusive_ms,
            "allowed_years": list(authorized_dataset.policy.allowed_years),
        },
        "command": list(command),
        "seeds": dict(sorted((seeds or {}).items())),
    }


def write_json_new(path: Path, payload: object) -> str:
    """Write a canonical JSON artifact exactly once and return its SHA256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise ArtifactExistsError(f"refusing to overwrite existing artifact: {path}") from exc

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise

    return hashlib.sha256(encoded).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
