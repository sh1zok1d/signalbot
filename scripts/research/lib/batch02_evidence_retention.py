"""Forward-only durable evidence retention for Batch02 B2-03+ runs.

This module is infrastructure, not a market-hypothesis runner. Hypothesis
code must not import it: the public ceremony lives on batch02_contracts.

V1 stores outcome-blind reservations and exact persisted result bytes on a
Git remote bound to the execution repository's configured `origin`. Tests
use a temporary local bare Git remote. There is no S3/R2/object-storage
backend in this unit.

Subprocess Git invocations use argument arrays only (shell invocation is
forbidden). Caller-controlled tokens are validated before they are embedded
in ref or path names. Isolated evidence workspaces are created outside the
execution worktree so archival cannot rewrite frozen tracked bytes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import weakref
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping, Sequence

from scripts.research.lib.research_harness import (
    VerifiedCodeFreeze,
    verify_git_freeze,
)

SCHEMA_VERSION = "batch02_durable_evidence_retention_v1"
RESERVATION_KIND = "batch02_pre_outcome_evidence_reservation"
RECEIPT_KIND = "batch02_durable_archive_receipt"
POST_OUTCOME_STATE = "POST_OUTCOME_RETENTION_FAILURE"
EVIDENCE_REF_PREFIX = "refs/heads/research-evidence/batch02/"
CANONICAL_REMOTE_HOST = "github.com"
CANONICAL_REMOTE_PATH = "sh1zok1d/signalbot"
RESERVATION_BLOB_PATH = "reservation.json"
RECEIPT_BLOB_PATH = "receipt.json"

_HYPOTHESIS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HEX40_RE = re.compile(r"^[a-f0-9]{40}$")
_HEX64_RE = re.compile(r"^[a-f0-9]{64}$")
_EVIDENCE_REF_RE = re.compile(
    r"^refs/heads/research-evidence/batch02/"
    r"[A-Za-z0-9][A-Za-z0-9._-]*/[a-f0-9]{40}$"
)
_HTTPS_USERINFO_RE = re.compile(r"^https://[^/]*@", re.IGNORECASE)
_CREDENTIAL_URL_RE = re.compile(
    r"https://(?:[^/\s]*:[^@/\s]+@|[^/@\s]+@)",
    re.IGNORECASE,
)
_TOKEN_ASSIGN_RE = re.compile(
    r"(?i)(token|authorization|x-access-token|password|secret|credential)[=:]\s*\S+"
)
_FORBIDDEN_GIT_FLAGS = {
    "--force",
    "-f",
    "--force-with-lease",
    "--force-if-includes",
}

_RESERVATION_MINT_TOKEN = object()
_RECEIPT_MINT_TOKEN = object()
_BOUND_RESERVATIONS: dict[int, tuple[object, ...]] = {}
_BACKEND_BY_ID: dict[int, "_EvidenceBackend"] = {}


class PreOutcomeRetentionError(RuntimeError):
    """Durable reservation failed before any market-outcome authorization."""

    outcome_consumed = False
    rerun_authorized = False


class PostOutcomeRetentionFailure(RuntimeError):
    """Local canonical result exists, but durable remote archival failed."""

    outcome_consumed = True
    rerun_authorized = False
    state = POST_OUTCOME_STATE

    def __init__(
        self,
        message: str,
        *,
        local_artifact_path: Path,
        local_sha256: str,
        local_size_bytes: int,
        evidence_ref: str,
        reservation_sha256: str,
        recovery_path: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.local_artifact_path = local_artifact_path
        self.local_sha256 = local_sha256
        self.local_size_bytes = local_size_bytes
        self.evidence_ref = evidence_ref
        self.reservation_sha256 = reservation_sha256
        self.recovery_path = recovery_path


@dataclass(frozen=True)
class _EvidenceBackend:
    origin_url: str
    reservation_bytes: bytes
    evidence_ref: str
    evidence_head_sha: str


@dataclass(frozen=True)
class DurableEvidenceReservation:
    """Minted proof that a remote, outcome-blind reservation was read back."""

    hypothesis_id: str
    stage: str
    code_sha: str
    code_tree: str
    repo_root: Path
    remote_repository_identity: str
    evidence_ref: str
    reservation_sha256: str
    evidence_head_sha: str
    dataset_id: str
    snapshot_id: str
    start_inclusive_ms: int
    end_exclusive_ms: int
    allowed_years: tuple[int, ...]
    required_gate_names: tuple[str, ...]
    gate_contract_sha256: str
    seeds: Mapping[str, int]
    _mint_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "seeds", dict(self.seeds))
        object.__setattr__(self, "allowed_years", tuple(self.allowed_years))
        object.__setattr__(self, "required_gate_names", tuple(self.required_gate_names))
        if getattr(self, "_mint_token", None) is not _RESERVATION_MINT_TOKEN:
            raise PreOutcomeRetentionError(
                "DurableEvidenceReservation must be minted by "
                "prepare_batch02_evidence_reservation"
            )

    def assert_minted(self) -> None:
        if getattr(self, "_mint_token", None) is not _RESERVATION_MINT_TOKEN:
            raise PreOutcomeRetentionError(
                "DurableEvidenceReservation must be minted by "
                "prepare_batch02_evidence_reservation"
            )
        bound = _BOUND_RESERVATIONS.get(id(self))
        if bound is None or bound != _reservation_identity(self):
            raise PreOutcomeRetentionError(
                "DurableEvidenceReservation provenance was mutated or forged"
            )
        if id(self) not in _BACKEND_BY_ID:
            raise PreOutcomeRetentionError(
                "DurableEvidenceReservation is missing its bound evidence backend"
            )


@dataclass(frozen=True)
class DurableArchiveReceipt:
    """Verified metadata after exact-byte remote archival and readback."""

    schema_version: str
    hypothesis_id: str
    stage: str
    code_sha: str
    code_tree: str
    run_identity_sha256: str
    dataset_id: str
    dataset_snapshot: str
    artifact_sha256: str
    artifact_size_bytes: int
    remote_repository_identity: str
    evidence_ref: str
    evidence_path: str
    reservation_sha256: str
    archive_commit_sha: str
    receipt_payload: Mapping[str, object]
    _mint_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_mint_token", None) is not _RECEIPT_MINT_TOKEN:
            raise TypeError(
                "DurableArchiveReceipt must be minted by archive_batch02_result"
            )


def hypothesis_requires_durable_retention(hypothesis_id: str) -> bool:
    """Return True for numbered Batch02 hypotheses at B2-03 and later."""
    if not isinstance(hypothesis_id, str):
        return False
    match = re.match(r"^B2[-_](\d+)", hypothesis_id)
    if match is None:
        return False
    return int(match.group(1)) >= 3


def canonical_json_bytes(payload: Mapping[str, object]) -> bytes:
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PreOutcomeRetentionError("payload must be canonical JSON") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _reservation_identity(reservation: DurableEvidenceReservation) -> tuple[object, ...]:
    return (
        reservation.hypothesis_id,
        reservation.stage,
        reservation.code_sha,
        reservation.code_tree,
        str(reservation.repo_root),
        reservation.remote_repository_identity,
        reservation.evidence_ref,
        reservation.reservation_sha256,
        reservation.evidence_head_sha,
        reservation.dataset_id,
        reservation.snapshot_id,
        reservation.start_inclusive_ms,
        reservation.end_exclusive_ms,
        reservation.allowed_years,
        reservation.required_gate_names,
        reservation.gate_contract_sha256,
        tuple(sorted(reservation.seeds.items())),
    )


def _redact(text: str) -> str:
    redacted = _CREDENTIAL_URL_RE.sub("https://<redacted>@", text)
    redacted = _TOKEN_ASSIGN_RE.sub(r"\1=<redacted>", redacted)
    return redacted


def _assert_safe_git_args(args: Sequence[str]) -> None:
    for arg in args:
        if arg in _FORBIDDEN_GIT_FLAGS:
            raise PreOutcomeRetentionError("force Git semantics are forbidden")
        if arg.startswith("+") and ":" in arg:
            raise PreOutcomeRetentionError("force Git refspec is forbidden")


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GC_AUTO"] = "0"
    for key in (
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    ):
        env.pop(key, None)
    return env


def run_git(cwd: Path, args: Sequence[str]) -> bytes:
    """Run git with an argument array in an isolated working directory."""
    _assert_safe_git_args(args)
    if cwd.is_symlink():
        raise PreOutcomeRetentionError("git cwd may not be a symlink")
    cmd = ["git", "-C", str(cwd), *args]
    try:
        completed = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            env=_git_env(),
        )
    except subprocess.CalledProcessError as exc:
        stdout = _redact((exc.stdout or b"").decode("utf-8", errors="replace"))
        stderr = _redact((exc.stderr or b"").decode("utf-8", errors="replace"))
        display = [_redact(part) for part in cmd]
        raise PreOutcomeRetentionError(
            f"git command failed: {display[0:8]} stderr={stderr!r} stdout={stdout!r}"
        ) from None
    except OSError:
        raise PreOutcomeRetentionError("git execution failed") from None
    return completed.stdout


def _safe_hypothesis_token(hypothesis_id: str) -> str:
    if not isinstance(hypothesis_id, str) or not _HYPOTHESIS_RE.fullmatch(hypothesis_id):
        raise PreOutcomeRetentionError("hypothesis_id is not a Git-safe evidence token")
    if ".." in hypothesis_id or hypothesis_id.startswith("-"):
        raise PreOutcomeRetentionError("hypothesis_id failed path-safety validation")
    return hypothesis_id


def evidence_ref_for(hypothesis_id: str, code_sha: str) -> str:
    token = _safe_hypothesis_token(hypothesis_id)
    if not _HEX40_RE.fullmatch(code_sha):
        raise PreOutcomeRetentionError("code_sha must be an exact 40-hex commit SHA")
    ref = f"{EVIDENCE_REF_PREFIX}{token}/{code_sha}"
    if not _EVIDENCE_REF_RE.fullmatch(ref) or len(ref) > 255:
        raise PreOutcomeRetentionError("evidence ref failed Git namespace validation")
    return ref


def artifact_relpath(hypothesis_id: str, code_sha: str, artifact_sha256: str) -> str:
    token = _safe_hypothesis_token(hypothesis_id)
    if not _HEX40_RE.fullmatch(code_sha):
        raise PreOutcomeRetentionError("code_sha must be an exact 40-hex commit SHA")
    if not _HEX64_RE.fullmatch(artifact_sha256):
        raise PreOutcomeRetentionError("artifact_sha256 must be a 64-hex digest")
    relative = f"batch02/{token}/{code_sha}/{artifact_sha256}.json"
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts) or Path(relative).is_absolute():
        raise PreOutcomeRetentionError("evidence path failed traversal validation")
    return relative


def _has_credential_userinfo(url: str) -> bool:
    stripped = url.strip()
    if _HTTPS_USERINFO_RE.match(stripped):
        return True
    if re.match(r"^ssh://(?!git@)[^@/]+@", stripped, re.IGNORECASE):
        return True
    return False


def sanitize_remote_identity(url: str) -> str:
    """Return a secret-free remote identity, or fail closed."""
    if not isinstance(url, str) or not url.strip():
        raise PreOutcomeRetentionError("evidence remote is missing")
    raw = url.strip()
    if _has_credential_userinfo(raw):
        raise PreOutcomeRetentionError(
            "credential-bearing remote URL is not allowed"
        )

    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", raw)
    if ssh is not None:
        host = ssh.group(1).lower()
        path = ssh.group(2).strip("/")
        return _canonical_host_identity(host, path)

    ssh_scheme = re.match(r"^ssh://git@([^/]+)/(.+?)(?:\.git)?/?$", raw, re.IGNORECASE)
    if ssh_scheme is not None:
        host = ssh_scheme.group(1).lower()
        path = ssh_scheme.group(2).strip("/")
        return _canonical_host_identity(host, path)

    https = re.match(r"^https://([^/]+)/(.+?)(?:\.git)?/?$", raw, re.IGNORECASE)
    if https is not None:
        host = https.group(1).lower()
        path = https.group(2).strip("/")
        return _canonical_host_identity(host, path)

    file_url = re.match(r"^file://(/.*)$", raw)
    if file_url is not None:
        raw = file_url.group(1)

    candidate = Path(raw)
    if not candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise PreOutcomeRetentionError("invalid evidence remote")
    if candidate.is_symlink():
        raise PreOutcomeRetentionError("evidence remote may not be a symlink")
    if not _is_git_repository(candidate):
        raise PreOutcomeRetentionError("evidence remote is not a Git repository")
    return f"local-git:{candidate.resolve()}"


def _canonical_host_identity(host: str, path: str) -> str:
    if host != CANONICAL_REMOTE_HOST:
        raise PreOutcomeRetentionError("evidence remote is not the canonical repository")
    if path.lower() != CANONICAL_REMOTE_PATH:
        raise PreOutcomeRetentionError("evidence remote is not the canonical repository")
    if ".." in path or path.startswith("/"):
        raise PreOutcomeRetentionError("evidence remote path is invalid")
    return f"{host}/{CANONICAL_REMOTE_PATH}"


def _is_git_repository(path: Path) -> bool:
    if (path / "HEAD").is_file() and (path / "objects").is_dir():
        return True
    if (path / ".git").exists():
        return True
    return False


def origin_url_for(repo_root: Path) -> str:
    if repo_root.is_symlink():
        raise PreOutcomeRetentionError("execution repo_root may not be a symlink")
    try:
        raw = run_git(repo_root, ["remote", "get-url", "origin"]).decode("utf-8").strip()
    except PreOutcomeRetentionError as exc:
        raise PreOutcomeRetentionError(
            "evidence backend is not configured: origin remote is missing"
        ) from exc
    if not raw:
        raise PreOutcomeRetentionError("evidence backend is not configured")
    return raw


def _isolated_workspace(repo_root: Path) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="batch02-evidence-")
    isolated = Path(workspace.name).resolve()
    if isolated == repo_root.resolve() or isolated.is_relative_to(repo_root.resolve()):
        workspace.cleanup()
        raise PreOutcomeRetentionError(
            "evidence workspace must not be inside the execution worktree"
        )
    return workspace


def _init_isolated_repo(isolated: Path, origin_url: str) -> None:
    run_git(isolated, ["init"])
    run_git(isolated, ["config", "user.name", "Signalbot Evidence Retention"])
    run_git(isolated, ["config", "user.email", "evidence-retention@signalbot.invalid"])
    run_git(isolated, ["config", "commit.gpgsign", "false"])
    run_git(isolated, ["remote", "add", "origin", origin_url])


def _ls_remote_sha(isolated: Path, evidence_ref: str) -> str | None:
    raw = run_git(isolated, ["ls-remote", "--heads", "origin", evidence_ref]).decode("utf-8")
    line = raw.strip()
    if not line:
        return None
    sha = line.split()[0].strip().lower()
    if not _HEX40_RE.fullmatch(sha):
        raise PreOutcomeRetentionError("remote evidence ref SHA is malformed")
    return sha


def _write_bytes_new(path: Path, data: bytes) -> None:
    if path.is_symlink() or path.parent.is_symlink():
        raise PreOutcomeRetentionError("refusing to write through a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o644)
    except OSError as exc:
        raise PreOutcomeRetentionError(f"unable to create exclusive file {path.name}") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    persisted = path.read_bytes()
    if persisted != data:
        raise PreOutcomeRetentionError("written evidence bytes differ from source bytes")


def _show_blob(isolated: Path, commit: str, relative: str) -> bytes:
    if not _HEX40_RE.fullmatch(commit):
        raise PreOutcomeRetentionError("commit SHA is malformed")
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise PreOutcomeRetentionError("refusing to read a traversed evidence path")
    return run_git(isolated, ["show", f"{commit}:{relative}"])


def _independent_readback(
    *,
    repo_root: Path,
    origin_url: str,
    evidence_ref: str,
    relative: str,
    expected_commit: str | None = None,
) -> tuple[str, bytes]:
    with _isolated_workspace(repo_root) as raw_dir:
        isolated = Path(raw_dir)
        _init_isolated_repo(isolated, origin_url)
        try:
            run_git(isolated, ["fetch", "--no-tags", "origin", evidence_ref])
        except PreOutcomeRetentionError as exc:
            raise PreOutcomeRetentionError(
                "remote reservation/archive was not independently readable"
            ) from exc
        commit = run_git(isolated, ["rev-parse", "FETCH_HEAD"]).decode("utf-8").strip().lower()
        if not _HEX40_RE.fullmatch(commit):
            raise PreOutcomeRetentionError("readback commit SHA is malformed")
        if expected_commit is not None and commit != expected_commit:
            raise PreOutcomeRetentionError(
                "independent readback commit does not match the pushed evidence head"
            )
        payload = _show_blob(isolated, commit, relative)
        return commit, payload


def _gate_contract_sha256(required_gate_names: Sequence[str]) -> str:
    encoded = json.dumps(
        list(required_gate_names),
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_reservation_payload(
    *,
    hypothesis_id: str,
    stage: str,
    code_sha: str,
    code_tree: str,
    dataset_id: str,
    snapshot_id: str,
    start_inclusive_ms: int,
    end_exclusive_ms: int,
    allowed_years: Sequence[int],
    required_gate_names: Sequence[str],
    seeds: Mapping[str, int],
    remote_repository_identity: str,
) -> dict[str, object]:
    if stage != "development":
        raise PreOutcomeRetentionError("evidence reservation is restricted to development")
    if type(start_inclusive_ms) is not int or type(end_exclusive_ms) is not int:
        raise PreOutcomeRetentionError("development window bounds must be integers")
    if start_inclusive_ms >= end_exclusive_ms:
        raise PreOutcomeRetentionError("development window is empty")
    years = tuple(int(year) for year in allowed_years)
    if not years or len(set(years)) != len(years):
        raise PreOutcomeRetentionError("allowed_years must be unique and non-empty")
    gates = tuple(required_gate_names)
    if not gates or any(type(name) is not str or not name.strip() for name in gates):
        raise PreOutcomeRetentionError("required_gate_names are invalid")
    if len(set(gates)) != len(gates):
        raise PreOutcomeRetentionError("required_gate_names must be unique")
    normalized_seeds: dict[str, int] = {}
    for key, value in seeds.items():
        if type(key) is not str or not key or type(value) is not int or isinstance(value, bool):
            raise PreOutcomeRetentionError("seeds must map strings to integers")
        normalized_seeds[key] = value
    if not isinstance(dataset_id, str) or not dataset_id.strip():
        raise PreOutcomeRetentionError("dataset_id is required")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise PreOutcomeRetentionError("snapshot_id is required")
    if not _HEX40_RE.fullmatch(code_sha) or not _HEX40_RE.fullmatch(code_tree):
        raise PreOutcomeRetentionError("code identity SHAs are malformed")
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RESERVATION_KIND,
        "hypothesis_id": _safe_hypothesis_token(hypothesis_id),
        "stage": stage,
        "code_sha": code_sha,
        "code_tree": code_tree,
        "dataset_id": dataset_id,
        "snapshot_id": snapshot_id,
        "development_window": {
            "start_inclusive_ms": start_inclusive_ms,
            "end_exclusive_ms": end_exclusive_ms,
            "allowed_years": list(years),
        },
        "required_gate_names": list(gates),
        "gate_contract_sha256": _gate_contract_sha256(gates),
        "seeds": dict(sorted(normalized_seeds.items())),
        "repository_identity": remote_repository_identity,
        "outcomes": None,
    }


def _mint_reservation(
    *,
    payload: Mapping[str, object],
    payload_bytes: bytes,
    repo_root: Path,
    origin_url: str,
    remote_identity: str,
    evidence_ref: str,
    evidence_head_sha: str,
) -> DurableEvidenceReservation:
    reservation = DurableEvidenceReservation(
        hypothesis_id=str(payload["hypothesis_id"]),
        stage=str(payload["stage"]),
        code_sha=str(payload["code_sha"]),
        code_tree=str(payload["code_tree"]),
        repo_root=repo_root.resolve(),
        remote_repository_identity=remote_identity,
        evidence_ref=evidence_ref,
        reservation_sha256=sha256_bytes(payload_bytes),
        evidence_head_sha=evidence_head_sha,
        dataset_id=str(payload["dataset_id"]),
        snapshot_id=str(payload["snapshot_id"]),
        start_inclusive_ms=int(payload["development_window"]["start_inclusive_ms"]),  # type: ignore[index]
        end_exclusive_ms=int(payload["development_window"]["end_exclusive_ms"]),  # type: ignore[index]
        allowed_years=tuple(payload["development_window"]["allowed_years"]),  # type: ignore[index]
        required_gate_names=tuple(payload["required_gate_names"]),
        gate_contract_sha256=str(payload["gate_contract_sha256"]),
        seeds=dict(payload["seeds"]),  # type: ignore[arg-type]
        _mint_token=_RESERVATION_MINT_TOKEN,
    )
    _BOUND_RESERVATIONS[id(reservation)] = _reservation_identity(reservation)
    _BACKEND_BY_ID[id(reservation)] = _EvidenceBackend(
        origin_url=origin_url,
        reservation_bytes=payload_bytes,
        evidence_ref=evidence_ref,
        evidence_head_sha=evidence_head_sha,
    )
    weakref.finalize(reservation, _BOUND_RESERVATIONS.pop, id(reservation), None)
    weakref.finalize(reservation, _BACKEND_BY_ID.pop, id(reservation), None)
    return reservation


def create_verified_remote_reservation(
    *,
    code_freeze: VerifiedCodeFreeze,
    hypothesis_id: str,
    stage: str,
    dataset_id: str,
    snapshot_id: str,
    start_inclusive_ms: int,
    end_exclusive_ms: int,
    allowed_years: Sequence[int],
    required_gate_names: Sequence[str],
    seeds: Mapping[str, int],
) -> DurableEvidenceReservation:
    """Push an outcome-blind reservation and independently read it back."""
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise PreOutcomeRetentionError(
            "code_freeze must be a VerifiedCodeFreeze from verify_batch02_code"
        )
    freeze = verify_git_freeze(code_freeze.repo_root, code_freeze.code_sha)
    if freeze.tree_oid != code_freeze.tree_oid:
        raise PreOutcomeRetentionError("code tree drifted before evidence reservation")

    origin_url = origin_url_for(freeze.repo_root)
    remote_identity = sanitize_remote_identity(origin_url)
    evidence_ref = evidence_ref_for(hypothesis_id, freeze.code_sha)
    payload = build_reservation_payload(
        hypothesis_id=hypothesis_id,
        stage=stage,
        code_sha=freeze.code_sha,
        code_tree=freeze.tree_oid,
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        start_inclusive_ms=start_inclusive_ms,
        end_exclusive_ms=end_exclusive_ms,
        allowed_years=allowed_years,
        required_gate_names=required_gate_names,
        seeds=seeds,
        remote_repository_identity=remote_identity,
    )
    payload_bytes = canonical_json_bytes(payload)
    reservation_sha = sha256_bytes(payload_bytes)

    with _isolated_workspace(freeze.repo_root) as raw_dir:
        isolated = Path(raw_dir)
        _init_isolated_repo(isolated, origin_url)
        existing = _ls_remote_sha(isolated, evidence_ref)
        if existing is None:
            _write_bytes_new(isolated / RESERVATION_BLOB_PATH, payload_bytes)
            run_git(isolated, ["add", "--", RESERVATION_BLOB_PATH])
            run_git(
                isolated,
                [
                    "commit",
                    "-m",
                    f"batch02 evidence reservation {reservation_sha[:16]}",
                ],
            )
            head = run_git(isolated, ["rev-parse", "HEAD"]).decode("utf-8").strip().lower()
            run_git(isolated, ["push", "origin", f"HEAD:{evidence_ref}"])
            expected_head = head
        else:
            run_git(isolated, ["fetch", "--no-tags", "origin", evidence_ref])
            run_git(isolated, ["checkout", "--detach", "FETCH_HEAD"])
            existing_bytes = (isolated / RESERVATION_BLOB_PATH).read_bytes()
            if existing_bytes != payload_bytes:
                raise PreOutcomeRetentionError(
                    "incompatible pre-existing evidence reservation"
                )
            expected_head = existing

    commit, remote_bytes = _independent_readback(
        repo_root=freeze.repo_root,
        origin_url=origin_url,
        evidence_ref=evidence_ref,
        relative=RESERVATION_BLOB_PATH,
        expected_commit=expected_head,
    )
    if remote_bytes != payload_bytes or sha256_bytes(remote_bytes) != reservation_sha:
        raise PreOutcomeRetentionError("reservation readback digest mismatch")
    verify_git_freeze(freeze.repo_root, freeze.code_sha)
    minted = _mint_reservation(
        payload=payload,
        payload_bytes=payload_bytes,
        repo_root=freeze.repo_root,
        origin_url=origin_url,
        remote_identity=remote_identity,
        evidence_ref=evidence_ref,
        evidence_head_sha=commit,
    )
    minted.assert_minted()
    return minted


def assert_reservation_still_current(reservation: DurableEvidenceReservation) -> None:
    """Fail closed if the remote reservation head drifted before outcomes."""
    reservation.assert_minted()
    backend = _BACKEND_BY_ID[id(reservation)]
    freeze = verify_git_freeze(reservation.repo_root, reservation.code_sha)
    if freeze.tree_oid != reservation.code_tree:
        raise PreOutcomeRetentionError("code tree drifted after evidence reservation")
    current_identity = sanitize_remote_identity(origin_url_for(freeze.repo_root))
    if current_identity != reservation.remote_repository_identity:
        raise PreOutcomeRetentionError("evidence remote identity drifted after reservation")
    with _isolated_workspace(freeze.repo_root) as raw_dir:
        isolated = Path(raw_dir)
        _init_isolated_repo(isolated, backend.origin_url)
        head = _ls_remote_sha(isolated, reservation.evidence_ref)
        if head != reservation.evidence_head_sha:
            raise PreOutcomeRetentionError(
                "evidence reservation ref drifted before outcome access"
            )


def _recovery_payload(
    *,
    result_path: Path,
    local_sha256: str,
    local_size_bytes: int,
    reservation: DurableEvidenceReservation,
    reason: str,
) -> dict[str, object]:
    return {
        "state": POST_OUTCOME_STATE,
        "outcome_consumed": True,
        "rerun_authorized": False,
        "local_canonical_artifact_must_be_preserved": True,
        "operator_recovery_required": True,
        "reason": reason,
        "local_artifact_path": str(result_path),
        "local_sha256": local_sha256,
        "local_size_bytes": local_size_bytes,
        "evidence_ref": reservation.evidence_ref,
        "reservation_sha256": reservation.reservation_sha256,
        "remote_repository_identity": reservation.remote_repository_identity,
        "hypothesis_id": reservation.hypothesis_id,
        "code_sha": reservation.code_sha,
    }


def _write_recovery_sidecar(result_path: Path, payload: Mapping[str, object]) -> Path | None:
    sidecar = result_path.with_name(result_path.name + ".POST_OUTCOME_RETENTION_FAILURE.json")
    try:
        _write_bytes_new(sidecar, canonical_json_bytes(payload) + b"\n")
        return sidecar
    except Exception:
        return sidecar if sidecar.exists() else None


def _raise_post_outcome(
    *,
    result_path: Path,
    local_sha256: str,
    local_size_bytes: int,
    reservation: DurableEvidenceReservation,
    reason: str,
) -> None:
    recovery = _recovery_payload(
        result_path=result_path,
        local_sha256=local_sha256,
        local_size_bytes=local_size_bytes,
        reservation=reservation,
        reason=reason,
    )
    sidecar = _write_recovery_sidecar(result_path, recovery)
    message = (
        f"{POST_OUTCOME_STATE}: {reason}. "
        "OUTCOME CONSUMED = YES; RERUN AUTHORIZED = NO; "
        "LOCAL CANONICAL ARTIFACT MUST BE PRESERVED; OPERATOR RECOVERY REQUIRED. "
        f"local_sha256={local_sha256} size={local_size_bytes} "
        f"ref={reservation.evidence_ref} reservation={reservation.reservation_sha256}"
    )
    raise PostOutcomeRetentionFailure(
        _redact(message),
        local_artifact_path=result_path,
        local_sha256=local_sha256,
        local_size_bytes=local_size_bytes,
        evidence_ref=reservation.evidence_ref,
        reservation_sha256=reservation.reservation_sha256,
        recovery_path=sidecar,
    )


def archive_persisted_result_bytes(
    *,
    reservation: DurableEvidenceReservation,
    result_path: Path,
    expected_sha256: str,
    run_identity_sha256: str,
    code_freeze: VerifiedCodeFreeze,
) -> DurableArchiveReceipt:
    """Archive exact persisted bytes and independently verify remote identity."""
    reservation.assert_minted()
    backend = _BACKEND_BY_ID[id(reservation)]
    try:
        freeze = verify_git_freeze(code_freeze.repo_root, code_freeze.code_sha)
    except Exception as exc:
        raise PreOutcomeRetentionError("execution worktree is no longer frozen") from exc
    if freeze.tree_oid != reservation.code_tree or freeze.code_sha != reservation.code_sha:
        raise PreOutcomeRetentionError("reservation is bound to a different code freeze")
    if result_path.is_symlink() or not result_path.is_file():
        _raise_post_outcome(
            result_path=result_path,
            local_sha256="",
            local_size_bytes=0,
            reservation=reservation,
            reason="canonical local result is missing or is a symlink",
        )
    source = result_path.read_bytes()
    source_sha = sha256_bytes(source)
    source_size = len(source)
    if source_sha != expected_sha256 or not _HEX64_RE.fullmatch(expected_sha256):
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="canonical local result bytes no longer match the persist digest",
        )
    if not _HEX64_RE.fullmatch(run_identity_sha256):
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="run identity digest is malformed",
        )

    lock_path = result_path.with_name(result_path.name + ".durable_retention.lock.json")
    if not lock_path.exists():
        try:
            _write_bytes_new(
                lock_path,
                canonical_json_bytes(
                    {
                        "kind": "batch02_durable_retention_lock",
                        "reservation_sha256": reservation.reservation_sha256,
                        "evidence_ref": reservation.evidence_ref,
                        "artifact_sha256": source_sha,
                    }
                )
                + b"\n",
            )
        except Exception:
            pass

    relative = artifact_relpath(
        reservation.hypothesis_id,
        reservation.code_sha,
        source_sha,
    )
    receipt_payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "hypothesis_id": reservation.hypothesis_id,
        "stage": reservation.stage,
        "code_sha": reservation.code_sha,
        "code_tree": reservation.code_tree,
        "run_identity_sha256": run_identity_sha256,
        "dataset_id": reservation.dataset_id,
        "dataset_snapshot": reservation.snapshot_id,
        "artifact_sha256": source_sha,
        "artifact_size_bytes": source_size,
        "remote_repository_identity": reservation.remote_repository_identity,
        "evidence_ref": reservation.evidence_ref,
        "evidence_path": relative,
        "reservation_sha256": reservation.reservation_sha256,
    }
    receipt_bytes = canonical_json_bytes(receipt_payload) + b"\n"
    origin_url = backend.origin_url
    current_identity = sanitize_remote_identity(origin_url_for(freeze.repo_root))
    if current_identity != reservation.remote_repository_identity:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="evidence remote identity drifted after reservation",
        )

    try:
        with _isolated_workspace(freeze.repo_root) as raw_dir:
            isolated = Path(raw_dir)
            _init_isolated_repo(isolated, origin_url)
            remote_head = _ls_remote_sha(isolated, reservation.evidence_ref)
            if remote_head is None:
                raise PreOutcomeRetentionError("reserved evidence ref is missing")
            if remote_head != reservation.evidence_head_sha:
                raise PreOutcomeRetentionError(
                    "evidence ref drifted between reservation and archive"
                )
            run_git(isolated, ["fetch", "--no-tags", "origin", reservation.evidence_ref])
            run_git(isolated, ["checkout", "--detach", "FETCH_HEAD"])
            reserved = (isolated / RESERVATION_BLOB_PATH).read_bytes()
            if reserved != backend.reservation_bytes:
                raise PreOutcomeRetentionError("reservation bytes changed on the evidence ref")

            dest = isolated / relative
            if dest.exists() or dest.is_symlink():
                existing = dest.read_bytes()
                if existing != source:
                    raise PreOutcomeRetentionError(
                        "existing remote artifact has a different digest"
                    )
            else:
                _write_bytes_new(dest, source)
            receipt_path = isolated / RECEIPT_BLOB_PATH
            if receipt_path.exists():
                if receipt_path.read_bytes() != receipt_bytes:
                    raise PreOutcomeRetentionError(
                        "existing receipt does not match this archive"
                    )
            else:
                _write_bytes_new(receipt_path, receipt_bytes)

            run_git(isolated, ["add", "--", relative, RECEIPT_BLOB_PATH, RESERVATION_BLOB_PATH])
            status = run_git(isolated, ["status", "--porcelain"]).decode("utf-8")
            if status.strip():
                run_git(
                    isolated,
                    [
                        "commit",
                        "-m",
                        f"batch02 evidence archive {source_sha[:16]}",
                    ],
                )
            pushed_sha = run_git(isolated, ["rev-parse", "HEAD"]).decode("utf-8").strip().lower()
            run_git(
                isolated,
                ["push", "origin", f"{pushed_sha}:{reservation.evidence_ref}"],
            )
    except PostOutcomeRetentionFailure:
        raise
    except Exception as exc:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason=_redact(str(exc)),
        )

    try:
        remote_commit, remote_artifact = _independent_readback(
            repo_root=freeze.repo_root,
            origin_url=origin_url,
            evidence_ref=reservation.evidence_ref,
            relative=relative,
            expected_commit=pushed_sha,
        )
        _, remote_receipt = _independent_readback(
            repo_root=freeze.repo_root,
            origin_url=origin_url,
            evidence_ref=reservation.evidence_ref,
            relative=RECEIPT_BLOB_PATH,
            expected_commit=pushed_sha,
        )
    except Exception as exc:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason=_redact(f"archive readback failed: {exc}"),
        )

    remote_sha = sha256_bytes(remote_artifact)
    remote_size = len(remote_artifact)
    if remote_sha != source_sha or remote_size != source_size:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="remote artifact bytes do not match the canonical local result",
        )
    if remote_receipt != receipt_bytes:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="remote receipt bytes do not match the local receipt",
        )
    if remote_commit != pushed_sha:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason="archive commit SHA readback mismatch",
        )

    still_local = result_path.read_bytes()
    if still_local != source or sha256_bytes(still_local) != source_sha:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=sha256_bytes(still_local),
            local_size_bytes=len(still_local),
            reservation=reservation,
            reason="canonical local result changed during archival",
        )
    verify_git_freeze(freeze.repo_root, freeze.code_sha)
    return DurableArchiveReceipt(
        schema_version=SCHEMA_VERSION,
        hypothesis_id=reservation.hypothesis_id,
        stage=reservation.stage,
        code_sha=reservation.code_sha,
        code_tree=reservation.code_tree,
        run_identity_sha256=run_identity_sha256,
        dataset_id=reservation.dataset_id,
        dataset_snapshot=reservation.snapshot_id,
        artifact_sha256=source_sha,
        artifact_size_bytes=source_size,
        remote_repository_identity=reservation.remote_repository_identity,
        evidence_ref=reservation.evidence_ref,
        evidence_path=relative,
        reservation_sha256=reservation.reservation_sha256,
        archive_commit_sha=remote_commit,
        receipt_payload=json.loads(receipt_bytes),
        _mint_token=_RECEIPT_MINT_TOKEN,
    )
