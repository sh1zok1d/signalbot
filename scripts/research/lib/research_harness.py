"""Reusable research-integrity primitives for Signalbot Batch02+ experiments.

This module does not encode any market hypothesis, threshold, or outcome.
It provides fail-closed primitives that new research code must use before
opening development outcomes.

Frozen H01-H05 runners remain historical artifacts and must not be refactored
onto this module merely for deduplication.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from numbers import Integral
from pathlib import Path
from typing import AbstractSet, Hashable, Mapping, Sequence

import yaml


class ResearchHarnessError(RuntimeError):
    """Base error for fail-closed research-integrity checks."""


class DatasetIdentityError(ResearchHarnessError):
    """Dataset identity, checksum, or authorization proof failed."""


class CodeIdentityError(ResearchHarnessError):
    """Git/code freeze identity proof failed."""


class OutcomeBoundaryError(ResearchHarnessError):
    """An outcome window crossed the authorized development boundary."""


class LookaheadError(ResearchHarnessError):
    """An input was unavailable at the claimed decision time."""


class SupportMismatchError(ResearchHarnessError):
    """Candidate/reference comparison did not use identical support."""


class ArtifactExistsError(ResearchHarnessError):
    """An immutable evidence artifact already exists."""


_AUTHORIZATION_TOKEN = object()
_CODE_FREEZE_TOKEN = object()

DISCOVERY_STAGE = "development"
DISCOVERY_END_EXCLUSIVE_MS = 1_735_689_600_000  # 2025-01-01T00:00:00Z
MIN_PLAUSIBLE_EPOCH_MS = 100_000_000_000
MAX_PLAUSIBLE_EPOCH_MS = 10_000_000_000_000


@dataclass(frozen=True)
class DatasetIdentityContract:
    dataset_id: str
    snapshot_id: str
    required_status: str = "ACCEPTED_FOR_DISCOVERY"
    research_authorized: bool = True
    confirmatory_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.dataset_id, str) or not self.dataset_id.strip():
            raise ValueError("dataset_id must be a non-empty string")
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id.strip():
            raise ValueError("snapshot_id must be a non-empty string")
        if self.required_status != "ACCEPTED_FOR_DISCOVERY":
            raise ValueError("required_status is fixed to ACCEPTED_FOR_DISCOVERY in v1")
        if self.research_authorized is not True:
            raise ValueError("research_authorized must be literal True in v1")
        if self.confirmatory_authorized is not False:
            raise ValueError("confirmatory_authorized must be literal False in v1")


@dataclass(frozen=True)
class OutcomeAccessPolicy:
    stage: str
    start_inclusive_ms: int
    end_exclusive_ms: int
    allowed_years: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.stage != DISCOVERY_STAGE:
            raise ValueError(
                f"v1 authorizes only {DISCOVERY_STAGE!r}, got {self.stage!r}"
            )
        if type(self.start_inclusive_ms) is not int:
            raise ValueError("start_inclusive_ms must be an integer millisecond timestamp")
        if type(self.end_exclusive_ms) is not int:
            raise ValueError("end_exclusive_ms must be an integer millisecond timestamp")
        if self.end_exclusive_ms <= self.start_inclusive_ms:
            raise ValueError("end_exclusive_ms must be greater than start_inclusive_ms")
        if self.end_exclusive_ms > DISCOVERY_END_EXCLUSIVE_MS:
            raise ValueError(
                "development policy may not reach the 2025 validation pool"
            )
        if not self.allowed_years:
            raise ValueError("allowed_years must be non-empty")
        if any(type(year) is not int for year in self.allowed_years):
            raise ValueError("allowed_years must contain integers")
        object.__setattr__(self, "allowed_years", tuple(self.allowed_years))
        if len(set(self.allowed_years)) != len(self.allowed_years):
            raise ValueError("allowed_years must be unique")

        start_year = datetime.fromtimestamp(
            self.start_inclusive_ms / 1000, tz=timezone.utc
        ).year
        last_year = datetime.fromtimestamp(
            (self.end_exclusive_ms - 1) / 1000, tz=timezone.utc
        ).year
        outside = [
            year
            for year in self.allowed_years
            if year < start_year or year > last_year
        ]
        if outside:
            raise ValueError(
                f"allowed_years {outside!r} fall outside frozen time window "
                f"[{start_year}, {last_year}]"
            )


@dataclass(frozen=True)
class PromotionGateContract:
    """Pre-outcome set of mandatory per-cell gate names."""

    required_gate_names: tuple[str, ...]

    def __post_init__(self) -> None:
        names = tuple(self.required_gate_names)
        object.__setattr__(self, "required_gate_names", names)
        if not names:
            raise ValueError("required_gate_names must be non-empty")
        if any(type(name) is not str or not name.strip() for name in names):
            raise ValueError("required_gate_names must contain non-empty strings")
        if len(set(names)) != len(names):
            raise ValueError("required_gate_names must be unique")

    @property
    def sha256(self) -> str:
        encoded = json.dumps(
            list(self.required_gate_names),
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class VerifiedCodeFreeze:
    """Proof that tracked repository bytes match an exact clean Git HEAD."""

    repo_root: Path
    code_sha: str
    tree_oid: str
    _verification_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._verification_token is not _CODE_FREEZE_TOKEN:
            raise CodeIdentityError(
                "VerifiedCodeFreeze must be created by verify_git_freeze"
            )


@dataclass(frozen=True)
class AuthorizedPartition:
    path: Path
    relative_path: str
    sha256: str


def _partition_proof_sha256(
    partitions: Sequence[AuthorizedPartition],
) -> str:
    payload = [
        {
            "relative_path": partition.relative_path,
            "sha256": partition.sha256,
        }
        for partition in partitions
    ]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class AuthorizedDataset:
    """Proof carrying only authorized, frozen development partitions."""

    identity: DatasetIdentityContract
    policy: OutcomeAccessPolicy
    code_sha: str
    repo_manifest_git_path: str
    frozen_snapshot_git_path: str
    runtime_snapshot_path: Path
    partitions: tuple[AuthorizedPartition, ...]
    _partition_proof: str = field(default="", repr=False, compare=False)
    _authorization_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.assert_minted()
        if not self.partitions:
            raise DatasetIdentityError("authorized partition set must be non-empty")
        if self._partition_proof != _partition_proof_sha256(self.partitions):
            raise DatasetIdentityError("authorized partition proof mismatch")

    def assert_minted(self) -> None:
        """Reject hollow/forged instances even when __post_init__ was bypassed."""
        if getattr(self, "_authorization_token", None) is not _AUTHORIZATION_TOKEN:
            raise DatasetIdentityError(
                "AuthorizedDataset must be created by authorize_dataset_access"
            )
        partitions = getattr(self, "partitions", None)
        proof = getattr(self, "_partition_proof", None)
        if not isinstance(partitions, tuple) or not partitions:
            raise DatasetIdentityError("authorized partition proof is incomplete")
        if not isinstance(proof, str) or proof != _partition_proof_sha256(partitions):
            raise DatasetIdentityError("authorized partition proof mismatch")

    def list_monthly_partitions(self) -> list[Path]:
        """Re-verify and return only the already-authorized partition paths."""
        self.assert_minted()
        root = self.runtime_snapshot_path.parent.parent.resolve()
        monthly = (root / "canonical" / "1m" / "monthly").resolve()
        if monthly.is_symlink() or not monthly.is_dir():
            raise DatasetIdentityError(
                "authorized canonical monthly directory is missing or became a symlink"
            )

        out: list[Path] = []
        for partition in self.partitions:
            if not isinstance(partition, AuthorizedPartition):
                raise DatasetIdentityError("authorized partition entry has invalid type")
            path = partition.path
            if path.is_symlink():
                raise DatasetIdentityError(
                    f"authorized partition became a symlink: {partition.relative_path}"
                )
            if not path.is_file():
                raise DatasetIdentityError(
                    f"authorized partition is missing: {partition.relative_path}"
                )
            resolved = path.resolve()
            if resolved.parent != monthly:
                raise DatasetIdentityError(
                    f"authorized partition escaped canonical monthly directory: "
                    f"{partition.relative_path}"
                )
            try:
                actual_relative = resolved.relative_to(root).as_posix()
            except ValueError as exc:
                raise DatasetIdentityError(
                    f"authorized partition escaped dataset root: {partition.relative_path}"
                ) from exc
            if actual_relative != partition.relative_path:
                raise DatasetIdentityError(
                    f"authorized partition path identity drift: {actual_relative} != "
                    f"{partition.relative_path}"
                )
            actual = sha256_file(resolved)
            if actual != partition.sha256:
                raise DatasetIdentityError(
                    f"authorized partition checksum drift: {partition.relative_path} "
                    f"{actual} != {partition.sha256}"
                )
            out.append(resolved)
        return out

    def partition_evidence(self) -> list[dict[str, str]]:
        self.assert_minted()
        return [
            {
                "relative_path": partition.relative_path,
                "sha256": partition.sha256,
            }
            for partition in self.partitions
        ]

    def assert_outcome_window(self, decision_t_ms: int, horizon_ms: int) -> None:
        self.assert_minted()
        decision = _coerce_timestamp_ms(decision_t_ms, "decision_t_ms")
        if isinstance(horizon_ms, bool) or not isinstance(horizon_ms, Integral):
            raise OutcomeBoundaryError("horizon_ms must be an integer")
        horizon = int(horizon_ms)
        if horizon < 0:
            raise OutcomeBoundaryError("horizon_ms must be >= 0")
        if decision < self.policy.start_inclusive_ms:
            raise OutcomeBoundaryError(
                f"decision {decision} precedes {self.policy.start_inclusive_ms}"
            )
        end_ms = decision + horizon
        if end_ms >= self.policy.end_exclusive_ms:
            raise OutcomeBoundaryError(
                f"outcome window end {end_ms} reaches/exceeds "
                f"{self.policy.end_exclusive_ms}"
            )


def _run_git(
    repo_root: Path,
    *args: str,
    input_bytes: bytes | None = None,
) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repo_root), *args],
            input=input_bytes,
            check=True,
            capture_output=True,
        ).stdout
    # CR-03: catch OSError broadly (not just FileNotFoundError) so every
    # subprocess-spawn/execution failure -- e.g. PermissionError on a
    # non-executable git binary, or any other OS-level spawn failure --
    # is owned by the harness's CodeIdentityError boundary, not leaked as
    # a raw OSError. subprocess.CalledProcessError (a non-zero exit from
    # `check=True`) is preserved unchanged.
    except (OSError, subprocess.CalledProcessError) as exc:
        raise CodeIdentityError(
            f"git command failed at {repo_root}: {' '.join(args)}"
        ) from exc


def _git_show_text(code_freeze: VerifiedCodeFreeze, git_path: str) -> str:
    if not git_path or git_path.startswith("/") or ".." in Path(git_path).parts:
        raise DatasetIdentityError(f"invalid frozen git path: {git_path!r}")
    raw = _run_git(
        code_freeze.repo_root,
        "show",
        f"{code_freeze.code_sha}:{git_path}",
    )
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatasetIdentityError(
            f"invalid UTF-8 in frozen git evidence: {git_path}"
        ) from exc


def _worktree_blob_oid(repo_root: Path, path: Path, mode: str) -> str:
    if mode == "120000":
        if not path.is_symlink():
            raise CodeIdentityError(f"tracked symlink type changed: {path}")
        # CR-03: os.readlink can raise OSError (e.g. a TOCTOU race where the
        # symlink is removed/replaced between is_symlink() and readlink(),
        # or a permission failure) -- must not leak as a raw OSError.
        try:
            data = os.fsencode(os.readlink(path))
        except OSError as exc:
            raise CodeIdentityError(
                f"unable to read tracked symlink target: {path}"
            ) from exc
    else:
        if path.is_symlink():
            raise CodeIdentityError(f"tracked regular file became symlink: {path}")
        if not path.is_file():
            raise CodeIdentityError(f"tracked file missing from worktree: {path}")
        # CR-03: Path.read_bytes can raise OSError (permission denied, race
        # where the file disappears/changes type after is_file(), I/O
        # error, etc.) -- must not leak as a raw OSError.
        try:
            data = path.read_bytes()
        except OSError as exc:
            raise CodeIdentityError(
                f"unable to read tracked worktree file: {path}"
            ) from exc
    return _run_git(repo_root, "hash-object", "--stdin", input_bytes=data).decode().strip()


def verify_git_freeze(repo_root: Path, expected_sha: str) -> VerifiedCodeFreeze:
    """Require exact HEAD, no index hiding flags, and byte-identical tracked files."""
    expected = expected_sha.strip().lower()
    if len(expected) != 40 or any(ch not in "0123456789abcdef" for ch in expected):
        raise CodeIdentityError("expected_sha must be an exact 40-hex commit SHA")

    root = repo_root.resolve()
    top = _run_git(root, "rev-parse", "--show-toplevel").decode().strip()
    if Path(top).resolve() != root:
        raise CodeIdentityError(
            f"repo_root must be the Git top-level: {root} != {Path(top).resolve()}"
        )

    head = _run_git(root, "rev-parse", "HEAD").decode().strip().lower()
    if head != expected:
        raise CodeIdentityError(f"git HEAD mismatch: {head} != {expected}")

    status = _run_git(
        root,
        "status",
        "--porcelain",
        "--untracked-files=all",
    ).decode("utf-8", errors="surrogateescape")
    if status.strip():
        raise CodeIdentityError("working tree is not clean at frozen code SHA")

    flagged = _run_git(root, "ls-files", "-v", "-z")
    for raw_entry in flagged.split(b"\0"):
        if not raw_entry:
            continue
        text = raw_entry.decode("utf-8", errors="surrogateescape")
        tag = text[0]
        if tag == "S" or tag.islower():
            raise CodeIdentityError(
                f"tracked file uses skip-worktree/assume-unchanged: {text[2:]}"
            )

    tree_raw = _run_git(root, "ls-tree", "-r", "-z", "HEAD")
    for raw_entry in tree_raw.split(b"\0"):
        if not raw_entry:
            continue
        try:
            meta, raw_path = raw_entry.split(b"\t", 1)
            mode_b, type_b, oid_b = meta.split(b" ", 2)
        except ValueError as exc:
            raise CodeIdentityError("unable to parse git tree entry") from exc
        mode = mode_b.decode()
        object_type = type_b.decode()
        expected_oid = oid_b.decode()
        if object_type != "blob":
            raise CodeIdentityError(
                f"unsupported tracked non-blob object in research repo: {raw_path!r}"
            )
        rel = raw_path.decode("utf-8", errors="surrogateescape")
        actual_oid = _worktree_blob_oid(root, root / rel, mode)
        if actual_oid != expected_oid:
            raise CodeIdentityError(
                f"tracked worktree bytes differ from HEAD for {rel}: "
                f"{actual_oid} != {expected_oid}"
            )

    tree_oid = _run_git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    return VerifiedCodeFreeze(
        repo_root=root,
        code_sha=head,
        tree_oid=tree_oid,
        _verification_token=_CODE_FREEZE_TOKEN,
    )


def _require_equal(actual, expected, label: str) -> None:
    if actual != expected:
        raise DatasetIdentityError(f"{label} mismatch: {actual!r} != {expected!r}")


def _reverify_code_freeze(code_freeze: VerifiedCodeFreeze) -> None:
    current = verify_git_freeze(code_freeze.repo_root, code_freeze.code_sha)
    if current.tree_oid != code_freeze.tree_oid:
        raise CodeIdentityError(
            f"git tree mismatch during freeze recheck: "
            f"{current.tree_oid} != {code_freeze.tree_oid}"
        )


def _normalize_checksum_mapping(value: object, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise DatasetIdentityError(f"{label} must be a mapping")
    out: dict[str, str] = {}
    for rel, digest in value.items():
        if not isinstance(rel, str) or not rel:
            raise DatasetIdentityError(f"{label} path must be non-empty string")
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(ch not in "0123456789abcdef" for ch in digest.lower())
        ):
            raise DatasetIdentityError(
                f"{label} checksum is not sha256 for {rel!r}: {digest!r}"
            )
        out[rel] = digest.lower()
    return out


def authorize_dataset_access(
    *,
    code_freeze: VerifiedCodeFreeze,
    dataset_root: Path,
    identity: DatasetIdentityContract,
    policy: OutcomeAccessPolicy,
) -> AuthorizedDataset:
    """Bind local dataset bytes to evidence frozen in the verified Git commit."""
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise CodeIdentityError("code_freeze must be a verify_git_freeze proof")
    _reverify_code_freeze(code_freeze)

    repo_manifest_git_path = f"docs/manifests/{identity.dataset_id}.yaml"
    try:
        repo_manifest = yaml.safe_load(
            _git_show_text(code_freeze, repo_manifest_git_path)
        )
    except yaml.YAMLError as exc:
        raise DatasetIdentityError(
            f"invalid frozen repository dataset manifest YAML: "
            f"{repo_manifest_git_path}"
        ) from exc
    if not isinstance(repo_manifest, Mapping):
        raise DatasetIdentityError("frozen repository dataset manifest must be a mapping")

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

    materialization_identity = repo_manifest.get("materialization_identity")
    if not isinstance(materialization_identity, Mapping):
        raise DatasetIdentityError(
            "frozen manifest materialization_identity must be a mapping"
        )
    frozen_snapshot_git_path = materialization_identity.get(
        "snapshot_manifest_path"
    )
    if not isinstance(frozen_snapshot_git_path, str):
        raise DatasetIdentityError(
            "frozen manifest snapshot_manifest_path must be a string"
        )
    expected_prefix = f"docs/research_data/{identity.dataset_id}/"
    if (
        not frozen_snapshot_git_path.startswith(expected_prefix)
        or not Path(frozen_snapshot_git_path).name.startswith("SNAPSHOT_")
        or not frozen_snapshot_git_path.endswith(".json")
    ):
        raise DatasetIdentityError(
            f"non-canonical frozen snapshot path: {frozen_snapshot_git_path!r}"
        )

    try:
        frozen_snapshot = json.loads(
            _git_show_text(code_freeze, frozen_snapshot_git_path)
        )
    except json.JSONDecodeError as exc:
        raise DatasetIdentityError(
            f"invalid frozen snapshot JSON: {frozen_snapshot_git_path}"
        ) from exc
    if not isinstance(frozen_snapshot, Mapping):
        raise DatasetIdentityError("frozen snapshot manifest must be a mapping")

    _require_equal(
        frozen_snapshot.get("snapshot_id"),
        identity.snapshot_id,
        "frozen snapshot_id",
    )
    frozen_payload = frozen_snapshot.get("identity_payload")
    if not isinstance(frozen_payload, Mapping):
        raise DatasetIdentityError("frozen snapshot identity_payload must be a mapping")
    _require_equal(
        frozen_payload.get("dataset_id"),
        identity.dataset_id,
        "frozen dataset_id",
    )
    frozen_checksums = _normalize_checksum_mapping(
        frozen_payload.get("output_checksums"),
        "frozen output_checksums",
    )

    root = dataset_root.resolve()
    runtime_snapshot_path = root / "reports" / "snapshot_manifest.json"
    try:
        runtime = json.loads(runtime_snapshot_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DatasetIdentityError(
            f"missing runtime dataset identity evidence: {runtime_snapshot_path}"
        ) from exc
    except UnicodeDecodeError as exc:
        raise DatasetIdentityError(
            f"invalid runtime snapshot encoding: {runtime_snapshot_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DatasetIdentityError(
            f"invalid runtime snapshot JSON: {runtime_snapshot_path}"
        ) from exc
    if not isinstance(runtime, Mapping):
        raise DatasetIdentityError("runtime snapshot manifest must be a mapping")

    _require_equal(runtime.get("snapshot_id"), identity.snapshot_id, "runtime snapshot_id")
    runtime_payload = runtime.get("identity_payload")
    if not isinstance(runtime_payload, Mapping):
        raise DatasetIdentityError("runtime identity_payload must be a mapping")
    _require_equal(
        runtime_payload.get("dataset_id"),
        identity.dataset_id,
        "runtime dataset_id",
    )
    if runtime_payload.get("snapshot_id") is not None:
        _require_equal(
            runtime_payload.get("snapshot_id"),
            identity.snapshot_id,
            "runtime identity_payload snapshot_id",
        )

    # CR-01: runtime checksum evidence can be present at the top level, at
    # `identity_payload.output_checksums`, both, or neither. Every
    # representation that is PRESENT must independently equal the
    # Git-frozen checksum map -- one present location must never silently
    # shadow another, whether that other location agrees or disagrees.
    runtime_checksums_top = runtime.get("output_checksums")
    runtime_checksums_nested = runtime_payload.get("output_checksums")

    if runtime_checksums_top is None and runtime_checksums_nested is None:
        raise DatasetIdentityError(
            "no runtime output_checksums evidence present "
            "(neither top-level nor identity_payload)"
        )

    if runtime_checksums_top is not None:
        normalized_top = _normalize_checksum_mapping(
            runtime_checksums_top,
            "runtime output_checksums (top-level)",
        )
        if normalized_top != frozen_checksums:
            raise DatasetIdentityError(
                "runtime output_checksums (top-level) differ from "
                "Git-frozen snapshot evidence"
            )

    if runtime_checksums_nested is not None:
        normalized_nested = _normalize_checksum_mapping(
            runtime_checksums_nested,
            "runtime output_checksums (identity_payload)",
        )
        if normalized_nested != frozen_checksums:
            raise DatasetIdentityError(
                "runtime output_checksums (identity_payload) differ from "
                "Git-frozen snapshot evidence"
            )

    monthly = root / "canonical" / "1m" / "monthly"
    if not monthly.is_dir():
        raise DatasetIdentityError(f"missing canonical monthly directory: {monthly}")
    if monthly.is_symlink():
        raise DatasetIdentityError("canonical monthly directory must not be a symlink")

    selected: list[AuthorizedPartition] = []
    for year in policy.allowed_years:
        prefix = f"{year:04d}-"
        for path in sorted(monthly.glob(f"{prefix}*.parquet")):
            if path.is_symlink():
                raise DatasetIdentityError(
                    f"selected partition must not be a symlink: {path.name}"
                )
            if not path.is_file():
                raise DatasetIdentityError(
                    f"selected partition is not a regular file: {path.name}"
                )
            relative = path.relative_to(root).as_posix()
            expected = frozen_checksums.get(relative)
            if expected is None:
                raise DatasetIdentityError(
                    f"selected partition missing Git-frozen checksum: {relative}"
                )
            actual = sha256_file(path)
            if actual != expected:
                raise DatasetIdentityError(
                    f"selected partition checksum mismatch: {relative} "
                    f"{actual} != {expected}"
                )
            selected.append(
                AuthorizedPartition(
                    path=path.resolve(),
                    relative_path=relative,
                    sha256=expected,
                )
            )

    if not selected:
        raise DatasetIdentityError(
            f"no monthly partitions found for allowed years {policy.allowed_years}"
        )

    return AuthorizedDataset(
        identity=identity,
        policy=policy,
        code_sha=code_freeze.code_sha,
        repo_manifest_git_path=repo_manifest_git_path,
        frozen_snapshot_git_path=frozen_snapshot_git_path,
        runtime_snapshot_path=runtime_snapshot_path,
        partitions=tuple(selected),
        _partition_proof=_partition_proof_sha256(tuple(selected)),
        _authorization_token=_AUTHORIZATION_TOKEN,
    )


def _coerce_timestamp_ms(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise LookaheadError(f"{label} must be an integer UTC epoch millisecond")
    out = int(value)
    if out < MIN_PLAUSIBLE_EPOCH_MS or out > MAX_PLAUSIBLE_EPOCH_MS:
        raise LookaheadError(
            f"{label} is not a plausible UTC epoch millisecond: {out}"
        )
    return out


def _normalize_timestamp_input(value: object, label: str) -> tuple[int, ...]:
    if isinstance(value, Integral) and not isinstance(value, bool):
        return (_coerce_timestamp_ms(value, label),)
    if isinstance(value, (str, bytes, bytearray)):
        raise LookaheadError(f"{label} must not be text/bytes")
    # CR-02: `tuple(mapping)` silently yields mapping KEYS, not values -- a
    # dict/Mapping passed here (accidentally or otherwise) must never be
    # reinterpreted as a timestamp sequence via generic iterable
    # conversion. Reject explicitly, before falling through to `tuple(...)`.
    if isinstance(value, Mapping):
        raise LookaheadError(f"{label} must not be a mapping")
    # CR-04: `set`/`frozenset` are unordered -- iterating one yields items in
    # an implementation-defined order, which would silently break the
    # positional decision/availability pairing that `assert_no_lookahead`
    # relies on for deterministic replay. Reject explicitly, before falling
    # through to the generic `tuple(...)` conversion. Ordered sequences
    # (list, tuple) are unaffected.
    if isinstance(value, AbstractSet):
        raise LookaheadError(f"{label} must not be an unordered set")
    try:
        raw = tuple(value)  # type: ignore[arg-type]
    except TypeError as exc:
        raise LookaheadError(
            f"{label} must be an integer timestamp or non-empty sequence"
        ) from exc
    if not raw:
        raise LookaheadError(f"{label} must be non-empty")
    return tuple(
        _coerce_timestamp_ms(item, f"{label}[{idx}]")
        for idx, item in enumerate(raw)
    )


def assert_no_lookahead(
    decision_t_ms: object,
    available_at_ms: object,
) -> None:
    """Require every input availability timestamp to be <= its decision time."""
    decisions = _normalize_timestamp_input(decision_t_ms, "decision_t_ms")
    available = _normalize_timestamp_input(available_at_ms, "available_at_ms")
    if len(decisions) != len(available):
        raise LookaheadError(
            f"decision/availability length mismatch: "
            f"{len(decisions)} != {len(available)}"
        )
    for idx, (decision, avail) in enumerate(zip(decisions, available)):
        if avail > decision:
            raise LookaheadError(
                f"lookahead at index {idx}: "
                f"available_at_ms={avail} > decision_t_ms={decision}"
            )


def _finite_float(value: object, label: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise SupportMismatchError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(out):
        raise SupportMismatchError(f"{label} is not finite: {value!r}")
    return out


def _validate_support_key(key: Hashable, label: str) -> None:
    try:
        if key != key:
            raise SupportMismatchError(f"{label} contains NaN-like key: {key!r}")
    except SupportMismatchError:
        raise
    except Exception as exc:
        raise SupportMismatchError(
            f"{label} key equality is not deterministic: {key!r}"
        ) from exc


def paired_same_support_delta(
    candidate_by_id: Mapping[Hashable, float],
    reference_by_id: Mapping[Hashable, float],
) -> dict:
    """Compute paired delta only when candidate/reference supports are identical."""
    candidate_keys = set(candidate_by_id)
    reference_keys = set(reference_by_id)
    for key in candidate_keys:
        _validate_support_key(key, "candidate support")
    for key in reference_keys:
        _validate_support_key(key, "reference support")
    if candidate_keys != reference_keys:
        raise SupportMismatchError(
            "candidate/reference supports differ; silent or explicit subset "
            "selection is forbidden in this primitive"
        )
    ids = tuple(sorted(candidate_keys, key=repr))
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
) -> dict:
    """Compute weighted means using exactly the same keys and same weights."""
    candidate_keys = set(candidate_by_key)
    reference_keys = set(reference_by_key)
    weight_keys = set(weights_by_key)
    for key in candidate_keys:
        _validate_support_key(key, "candidate support")
    for key in reference_keys:
        _validate_support_key(key, "reference support")
    for key in weight_keys:
        _validate_support_key(key, "weight support")
    if not (candidate_keys == reference_keys == weight_keys):
        raise SupportMismatchError(
            "candidate/reference/weight supports differ; subset selection "
            "is forbidden in this primitive"
        )
    keys = tuple(sorted(candidate_keys, key=repr))
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
        candidate.append(
            _finite_float(candidate_by_key[key], f"candidate[{key!r}]")
        )
        reference.append(
            _finite_float(reference_by_key[key], f"reference[{key!r}]")
        )

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
    gate_contract: PromotionGateContract,
) -> bool:
    """Pass only when every frozen mandatory gate exists and is literal True."""
    if not isinstance(gate_contract, PromotionGateContract):
        return False
    return all(
        name in gates and gates[name] is True
        for name in gate_contract.required_gate_names
    )


def build_run_identity(
    *,
    hypothesis_id: str,
    stage: str,
    code_freeze: VerifiedCodeFreeze,
    authorized_dataset: AuthorizedDataset,
    gate_contract: PromotionGateContract,
    command: Sequence[str],
    seeds: Mapping[str, int] | None = None,
) -> dict:
    """Build deterministic provenance fields that must accompany a result."""
    if not hypothesis_id or not stage:
        raise ValueError("hypothesis_id and stage are required")
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise CodeIdentityError("code_freeze must be a verify_git_freeze proof")
    if not isinstance(authorized_dataset, AuthorizedDataset):
        raise DatasetIdentityError(
            "authorized_dataset must be an authorize_dataset_access proof"
        )
    if not isinstance(gate_contract, PromotionGateContract):
        raise ValueError("gate_contract must be a PromotionGateContract")
    _reverify_code_freeze(code_freeze)
    authorized_dataset.list_monthly_partitions()
    if authorized_dataset.code_sha != code_freeze.code_sha:
        raise CodeIdentityError(
            "dataset authorization and run provenance use different code SHAs"
        )
    if stage != authorized_dataset.policy.stage:
        raise ValueError(
            f"stage mismatch: {stage!r} != {authorized_dataset.policy.stage!r}"
        )
    if not command or any(type(item) is not str or not item for item in command):
        raise ValueError("command must be a non-empty sequence of strings")
    normalized_seeds: dict[str, int] = {}
    for key, value in (seeds or {}).items():
        if type(key) is not str or not key:
            raise ValueError("seed names must be non-empty strings")
        if type(value) is not int:
            raise ValueError("seed values must be integers")
        normalized_seeds[key] = value

    return {
        "hypothesis_id": hypothesis_id,
        "stage": stage,
        "code_sha": code_freeze.code_sha,
        "code_tree_oid": code_freeze.tree_oid,
        "dataset_id": authorized_dataset.identity.dataset_id,
        "snapshot_id": authorized_dataset.identity.snapshot_id,
        "repo_manifest_git_path": authorized_dataset.repo_manifest_git_path,
        "frozen_snapshot_git_path": authorized_dataset.frozen_snapshot_git_path,
        "runtime_snapshot_path": str(authorized_dataset.runtime_snapshot_path),
        "partitions": authorized_dataset.partition_evidence(),
        "window": {
            "start_inclusive_ms": authorized_dataset.policy.start_inclusive_ms,
            "end_exclusive_ms": authorized_dataset.policy.end_exclusive_ms,
            "allowed_years": list(authorized_dataset.policy.allowed_years),
        },
        "promotion_gate_contract": {
            "required_gate_names": list(gate_contract.required_gate_names),
            "sha256": gate_contract.sha256,
        },
        "command": list(command),
        "seeds": dict(sorted(normalized_seeds.items())),
    }


def write_json_new(path: Path, payload: object) -> str:
    """Write canonical JSON exactly once and return the persisted-byte SHA256."""
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(
            payload,
            sort_keys=True,
            indent=2,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        fd = os.open(path, flags, 0o644)
    except FileExistsError as exc:
        raise ArtifactExistsError(
            f"refusing to overwrite existing artifact: {path}"
        ) from exc

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        persisted = path.read_bytes()
        if persisted != encoded:
            raise ResearchHarnessError(
                f"persisted artifact bytes differ from encoded payload: {path}"
            )
        return hashlib.sha256(persisted).hexdigest()
    except Exception:
        try:
            path.unlink(missing_ok=True)
        finally:
            raise


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
