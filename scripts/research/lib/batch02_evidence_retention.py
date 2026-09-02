"""Forward-only durable evidence retention for Batch02 B2-03+ runs.

This module is infrastructure, not a market-hypothesis runner. Hypothesis
code must not import it: the public ceremony lives on batch02_contracts.

Remote evidence refs follow an append-only state machine:

    RESERVED
      -> OUTCOME_ACCESS_CLAIMED   (before dataset authorization)
      -> ARCHIVED                 (exact persisted bytes)

Remote reservation proves storage readiness.
Remote outcome-access claim durably consumes/claims the one-shot
authorization before dataset access.
Remote archive proves preservation of exact result bytes.

Numbered B2-03+ one-shot uniqueness is bound to a canonical slot key
(B2-03, B2-04, ...) derived case-insensitively from the numbered prefix.
Exact hypothesis_id spelling remains in reservation/run provenance; it
must not create a second evidence ref.

Production transport is the canonical GitHub repository only. Local bare Git
remotes exist solely through prepare_test_evidence_reservation(), which is
not re-exported from batch02_contracts.
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
GIT_TIMEOUT_SECONDS = 60
RESERVATION_KIND = "batch02_pre_outcome_evidence_reservation"
CLAIM_KIND = "batch02_outcome_access_claim"
RECEIPT_KIND = "batch02_durable_archive_receipt"
POST_OUTCOME_STATE = "POST_OUTCOME_RETENTION_FAILURE"
AMBIGUOUS_CLAIM_STATE = "AMBIGUOUS_OUTCOME_ACCESS_CLAIM"
STATE_RESERVED = "RESERVED"
STATE_CLAIMED = "OUTCOME_ACCESS_CLAIMED"
STATE_ARCHIVED = "ARCHIVED"
STATE_UNKNOWN = "UNKNOWN"
EVIDENCE_REF_PREFIX = "refs/heads/research-evidence/batch02/"
CANONICAL_REMOTE_HOST = "github.com"
CANONICAL_REMOTE_PATH = "sh1zok1d/signalbot"
CANONICAL_REMOTE_IDENTITY = f"{CANONICAL_REMOTE_HOST}/{CANONICAL_REMOTE_PATH}"
RESERVATION_BLOB_PATH = "reservation.json"
CLAIM_BLOB_PATH = "outcome_claim.json"
RECEIPT_BLOB_PATH = "receipt.json"

_HYPOTHESIS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_NUMBERED_B2_RE = re.compile(r"^b2[-_](\d+)", re.IGNORECASE)
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
_ARTIFACT_PATH_RE = re.compile(
    r"^batch02/[A-Za-z0-9][A-Za-z0-9._-]*/[a-f0-9]{40}/[a-f0-9]{64}\.json$"
)
_FORBIDDEN_GIT_FLAGS = {
    "--force",
    "-f",
    "--force-with-lease",
    "--force-if-includes",
}

_RESERVATION_MINT_TOKEN = object()
_CLAIM_MINT_TOKEN = object()
_PERSIST_MINT_TOKEN = object()
_RECEIPT_MINT_TOKEN = object()
_BOUND_RESERVATIONS: dict[int, tuple[object, ...]] = {}
_BOUND_CLAIMS: dict[int, tuple[object, ...]] = {}
_BOUND_PERSISTED: dict[int, tuple[object, ...]] = {}
_BACKEND_BY_ID: dict[int, "_EvidenceBackend"] = {}


class PreOutcomeRetentionError(RuntimeError):
    """Durable reservation/claim failed before market-outcome authorization."""

    outcome_consumed = False
    rerun_authorized = False


class GitTimeoutError(PreOutcomeRetentionError):
    """A Git subprocess exceeded GIT_TIMEOUT_SECONDS."""


class AmbiguousOutcomeAccessStateError(PreOutcomeRetentionError):
    """Claim push may have succeeded but independent readback is unproven."""

    operator_adjudication_required = True
    state = AMBIGUOUS_CLAIM_STATE


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
class VerifiedEvidenceTransport:
    identity: str
    endpoint: str
    allow_local: bool


@dataclass
class _EvidenceBackend:
    transport: VerifiedEvidenceTransport
    reservation_bytes: bytes
    evidence_ref: str
    evidence_head_sha: str
    claim_head_sha: str | None = None
    claim_bytes: bytes | None = None


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
class DurableOutcomeAccessClaim:
    """Minted proof that the remote one-shot outcome-access claim was read back."""

    hypothesis_id: str
    reservation_sha256: str
    claim_sha256: str
    claim_head_sha: str
    reservation_commit_sha: str
    evidence_ref: str
    remote_repository_identity: str
    _mint_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_mint_token", None) is not _CLAIM_MINT_TOKEN:
            raise PreOutcomeRetentionError(
                "DurableOutcomeAccessClaim must be minted by "
                "prepare_batch02_retained_run"
            )

    def assert_minted(self) -> None:
        if getattr(self, "_mint_token", None) is not _CLAIM_MINT_TOKEN:
            raise PreOutcomeRetentionError(
                "DurableOutcomeAccessClaim must be minted by "
                "prepare_batch02_retained_run"
            )
        bound = _BOUND_CLAIMS.get(id(self))
        if bound is None or bound != _claim_identity(self):
            raise PreOutcomeRetentionError(
                "DurableOutcomeAccessClaim provenance was mutated or forged"
            )


@dataclass(frozen=True)
class PersistedBatch02ResultProof:
    """Minted proof of the exact bytes written by retained persistence."""

    result_path: Path
    artifact_sha256: str
    artifact_size_bytes: int
    run_identity_sha256: str
    hypothesis_id: str
    code_sha: str
    code_tree: str
    claim_sha256: str
    claim_head_sha: str
    evidence_ref: str
    reservation_sha256: str
    _mint_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_mint_token", None) is not _PERSIST_MINT_TOKEN:
            raise PostOutcomeRetentionFailure(
                f"{POST_OUTCOME_STATE}: PersistedBatch02ResultProof must be minted "
                "by persist_batch02_retained_result. OUTCOME CONSUMED = YES; "
                "RERUN AUTHORIZED = NO; LOCAL CANONICAL ARTIFACT MUST BE PRESERVED; "
                "OPERATOR RECOVERY REQUIRED.",
                local_artifact_path=Path("."),
                local_sha256="",
                local_size_bytes=0,
                evidence_ref="",
                reservation_sha256="",
            )

    def assert_minted(self) -> None:
        if getattr(self, "_mint_token", None) is not _PERSIST_MINT_TOKEN:
            raise PostOutcomeRetentionFailure(
                f"{POST_OUTCOME_STATE}: unminted persisted-result proof. "
                "OUTCOME CONSUMED = YES; RERUN AUTHORIZED = NO; "
                "LOCAL CANONICAL ARTIFACT MUST BE PRESERVED; OPERATOR RECOVERY REQUIRED.",
                local_artifact_path=getattr(self, "result_path", Path(".")),
                local_sha256=str(getattr(self, "artifact_sha256", "")),
                local_size_bytes=int(getattr(self, "artifact_size_bytes", 0) or 0),
                evidence_ref=str(getattr(self, "evidence_ref", "")),
                reservation_sha256=str(getattr(self, "reservation_sha256", "")),
            )
        bound = _BOUND_PERSISTED.get(id(self))
        if bound is None or bound != _persisted_identity(self):
            raise PostOutcomeRetentionFailure(
                f"{POST_OUTCOME_STATE}: persisted-result proof was mutated or forged. "
                "OUTCOME CONSUMED = YES; RERUN AUTHORIZED = NO; "
                "LOCAL CANONICAL ARTIFACT MUST BE PRESERVED; OPERATOR RECOVERY REQUIRED.",
                local_artifact_path=self.result_path,
                local_sha256=self.artifact_sha256,
                local_size_bytes=self.artifact_size_bytes,
                evidence_ref=self.evidence_ref,
                reservation_sha256=self.reservation_sha256,
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
    claim_sha256: str
    archive_commit_sha: str
    receipt_payload: Mapping[str, object]
    _mint_token: object = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if getattr(self, "_mint_token", None) is not _RECEIPT_MINT_TOKEN:
            raise TypeError(
                "DurableArchiveReceipt must be minted by archive_batch02_result"
            )


def numbered_batch02_index(hypothesis_id: str) -> int | None:
    """Return the numbered B2 index, or None when the ID is not numbered B2."""
    if not isinstance(hypothesis_id, str):
        return None
    match = _NUMBERED_B2_RE.match(hypothesis_id.strip())
    if match is None:
        return None
    return int(match.group(1))


def hypothesis_requires_durable_retention(hypothesis_id: str) -> bool:
    """Return True for numbered Batch02 hypotheses at B2-03 and later.

    Numbered B2 IDs are classified case-insensitively. Values such as
    ``b2-03`` / ``b2_03`` require durable retention and must not enter
    historical B2-01/B2-02 machinery.
    """
    index = numbered_batch02_index(hypothesis_id)
    return index is not None and index >= 3


def durable_evidence_slot_key(hypothesis_id: str) -> str:
    """Canonical one-shot identity for a numbered B2 evidence slot.

    Aliases that differ only by ``B2`` casing, the ``-``/``_`` separator
    after ``B2``, or equivalent zero-padding of the number map to one
    slot. ``B2-03_X``, ``b2-03_X``, ``B2_03_X``, and ``B2-003_X`` all
    become ``B2-03``. Distinct numbers remain distinct: ``B2-03`` is not
    ``B2-04``. Non-numbered IDs keep their Git-safe exact token.
    """
    token = _safe_hypothesis_token(hypothesis_id)
    index = numbered_batch02_index(token)
    if index is None:
        return token
    return f"B2-{index:02d}"


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


def _claim_identity(claim: DurableOutcomeAccessClaim) -> tuple[object, ...]:
    return (
        claim.hypothesis_id,
        claim.reservation_sha256,
        claim.claim_sha256,
        claim.claim_head_sha,
        claim.reservation_commit_sha,
        claim.evidence_ref,
        claim.remote_repository_identity,
    )


def _persisted_identity(proof: PersistedBatch02ResultProof) -> tuple[object, ...]:
    return (
        str(proof.result_path),
        proof.artifact_sha256,
        proof.artifact_size_bytes,
        proof.run_identity_sha256,
        proof.hypothesis_id,
        proof.code_sha,
        proof.code_tree,
        proof.claim_sha256,
        proof.claim_head_sha,
        proof.evidence_ref,
        proof.reservation_sha256,
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
    """Isolated Git environment for evidence transport.

    Inherited TLS/config injection and SSH-transport overrides
    (GIT_SSH, GIT_SSH_COMMAND, GIT_SSH_VARIANT) are removed so the
    caller cannot replace the SSH executable. SSH agent sockets and
    credential helpers remain usable.
    """
    env = os.environ.copy()
    for key in list(env):
        if (
            key == "GIT_CONFIG_COUNT"
            or key.startswith("GIT_CONFIG_KEY_")
            or key.startswith("GIT_CONFIG_VALUE_")
            or key
            in {
                "GIT_SSL_NO_VERIFY",
                "GIT_CONFIG_PARAMETERS",
                "GIT_ALLOW_PROTOCOL",
                "GIT_PROXY_COMMAND",
                "GIT_SSH",
                "GIT_SSH_COMMAND",
                "GIT_SSH_VARIANT",
            }
        ):
            env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GC_AUTO"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_AUTHOR_NAME"] = "signalbot-batch02"
    env["GIT_AUTHOR_EMAIL"] = "batch02@signalbot.invalid"
    env["GIT_COMMITTER_NAME"] = "signalbot-batch02"
    env["GIT_COMMITTER_EMAIL"] = "batch02@signalbot.invalid"
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
    """Run git with an argument array in an isolated working directory.

    Every invocation is bounded by GIT_TIMEOUT_SECONDS. Callers classify a
    GitTimeoutError according to lifecycle stage.
    """
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
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise GitTimeoutError(
            f"git command timed out after {GIT_TIMEOUT_SECONDS}s: "
            f"{[_redact(part) for part in cmd][0:8]}"
        ) from None
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
    """Return the durable evidence ref for the canonical B2 slot + code SHA."""
    token = durable_evidence_slot_key(hypothesis_id)
    if not _HEX40_RE.fullmatch(code_sha):
        raise PreOutcomeRetentionError("code_sha must be an exact 40-hex commit SHA")
    ref = f"{EVIDENCE_REF_PREFIX}{token}/{code_sha}"
    if not _EVIDENCE_REF_RE.fullmatch(ref) or len(ref) > 255:
        raise PreOutcomeRetentionError("evidence ref failed Git namespace validation")
    return ref


def artifact_relpath(hypothesis_id: str, code_sha: str, artifact_sha256: str) -> str:
    token = durable_evidence_slot_key(hypothesis_id)
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


def _canonical_host_identity(host: str, path: str) -> str:
    if host != CANONICAL_REMOTE_HOST:
        raise PreOutcomeRetentionError("evidence remote is not the canonical repository")
    if path.lower() != CANONICAL_REMOTE_PATH:
        raise PreOutcomeRetentionError("evidence remote is not the canonical repository")
    if ".." in path or path.startswith("/"):
        raise PreOutcomeRetentionError("evidence remote path is invalid")
    return CANONICAL_REMOTE_IDENTITY


def canonicalize_remote_url(url: str, *, allow_local: bool) -> str:
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
        return _canonical_host_identity(ssh.group(1).lower(), ssh.group(2).strip("/"))

    ssh_scheme = re.match(r"^ssh://git@([^/]+)/(.+?)(?:\.git)?/?$", raw, re.IGNORECASE)
    if ssh_scheme is not None:
        return _canonical_host_identity(
            ssh_scheme.group(1).lower(), ssh_scheme.group(2).strip("/")
        )

    https = re.match(r"^https://([^/]+)/(.+?)(?:\.git)?/?$", raw, re.IGNORECASE)
    if https is not None:
        return _canonical_host_identity(https.group(1).lower(), https.group(2).strip("/"))

    file_url = re.match(r"^file://(/.*)$", raw)
    if file_url is not None:
        raw = file_url.group(1)

    if not allow_local:
        raise PreOutcomeRetentionError(
            "production evidence transport must be the canonical GitHub repository, "
            "not a local filesystem Git remote"
        )
    candidate = Path(raw)
    if not candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        raise PreOutcomeRetentionError("invalid evidence remote")
    if candidate.is_symlink():
        raise PreOutcomeRetentionError("evidence remote may not be a symlink")
    if not _is_git_repository(candidate):
        raise PreOutcomeRetentionError("evidence remote is not a Git repository")
    return f"local-git:{candidate.resolve()}"


def sanitize_remote_identity(url: str) -> str:
    """Production sanitizer: canonical GitHub only, never a local Git remote."""
    return canonicalize_remote_url(url, allow_local=False)


def _is_git_repository(path: Path) -> bool:
    if (path / "HEAD").is_file() and (path / "objects").is_dir():
        return True
    if (path / ".git").exists():
        return True
    return False


def _config_all(repo_root: Path, key: str) -> list[str]:
    try:
        raw = run_git(repo_root, ["config", "--get-all", key]).decode("utf-8")
    except PreOutcomeRetentionError:
        return []
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _reject_url_rewrites(repo_root: Path) -> None:
    try:
        raw = run_git(repo_root, ["config", "--list", "--show-origin"]).decode(
            "utf-8", errors="replace"
        )
    except PreOutcomeRetentionError as exc:
        raise PreOutcomeRetentionError(
            "unable to inspect Git config for evidence transport rewrites"
        ) from exc
    for line in raw.splitlines():
        lowered = line.lower()
        if "insteadof=" in lowered or "pushinsteadof=" in lowered:
            raise PreOutcomeRetentionError(
                "Git URL rewrite configuration is not allowed for evidence transport"
            )


def inspect_production_evidence_transport(repo_root: Path) -> VerifiedEvidenceTransport:
    """Bind production evidence I/O to the canonical GitHub repository only."""
    if repo_root.is_symlink():
        raise PreOutcomeRetentionError("execution repo_root may not be a symlink")
    _reject_url_rewrites(repo_root)
    fetch_urls = _config_all(repo_root, "remote.origin.url")
    if not fetch_urls:
        try:
            fetch_urls = [
                run_git(repo_root, ["remote", "get-url", "origin"]).decode("utf-8").strip()
            ]
            fetch_urls = [url for url in fetch_urls if url]
        except PreOutcomeRetentionError as exc:
            raise PreOutcomeRetentionError(
                "evidence backend is not configured: origin remote is missing"
            ) from exc
    if len(fetch_urls) != 1:
        raise PreOutcomeRetentionError("origin must have exactly one fetch URL")
    try:
        listed_fetch = [
            line.strip()
            for line in run_git(repo_root, ["remote", "get-url", "--all", "origin"])
            .decode("utf-8")
            .splitlines()
            if line.strip()
        ]
    except PreOutcomeRetentionError:
        listed_fetch = list(fetch_urls)
    if len(listed_fetch) != 1:
        raise PreOutcomeRetentionError("origin must have exactly one fetch URL")
    push_urls = _config_all(repo_root, "remote.origin.pushurl")
    if len(push_urls) > 1:
        raise PreOutcomeRetentionError("multiple origin push URLs are not allowed")
    try:
        listed_push = [
            line.strip()
            for line in run_git(
                repo_root, ["remote", "get-url", "--push", "--all", "origin"]
            )
            .decode("utf-8")
            .splitlines()
            if line.strip()
        ]
    except PreOutcomeRetentionError:
        listed_push = list(push_urls) if push_urls else list(fetch_urls)
    if len(listed_push) != 1:
        raise PreOutcomeRetentionError("multiple origin push URLs are not allowed")
    fetch_url = fetch_urls[0]
    push_url = push_urls[0] if push_urls else fetch_url
    if listed_fetch[0] != fetch_url.strip():
        raise PreOutcomeRetentionError("origin fetch URL inspection mismatch")
    if listed_push[0] != push_url.strip():
        raise PreOutcomeRetentionError(
            "origin push URL diverges from the verified fetch URL"
        )
    fetch_identity = canonicalize_remote_url(fetch_url, allow_local=False)
    push_identity = canonicalize_remote_url(push_url, allow_local=False)
    if fetch_identity != push_identity or fetch_identity != CANONICAL_REMOTE_IDENTITY:
        raise PreOutcomeRetentionError(
            "evidence fetch/push transport is not the canonical repository"
        )
    if fetch_url.strip() != push_url.strip():
        raise PreOutcomeRetentionError(
            "origin push URL diverges from the verified fetch URL"
        )
    return VerifiedEvidenceTransport(
        identity=fetch_identity,
        endpoint=fetch_url.strip(),
        allow_local=False,
    )


def prepare_test_evidence_transport(bare_remote: Path) -> VerifiedEvidenceTransport:
    """TEST-ONLY local bare remote. Not re-exported from batch02_contracts."""
    if not isinstance(bare_remote, Path):
        raise PreOutcomeRetentionError("test evidence remote must be a Path")
    if not bare_remote.is_absolute() or any(part == ".." for part in bare_remote.parts):
        raise PreOutcomeRetentionError("invalid test evidence remote")
    if bare_remote.is_symlink():
        raise PreOutcomeRetentionError("test evidence remote may not be a symlink")
    if not _is_git_repository(bare_remote):
        raise PreOutcomeRetentionError("test evidence remote is not a Git repository")
    resolved = bare_remote.resolve()
    return VerifiedEvidenceTransport(
        identity=f"local-git:{resolved}",
        endpoint=str(resolved),
        allow_local=True,
    )


def _isolated_workspace(repo_root: Path) -> tempfile.TemporaryDirectory[str]:
    workspace = tempfile.TemporaryDirectory(prefix="batch02-evidence-")
    isolated = Path(workspace.name).resolve()
    if isolated == repo_root.resolve() or isolated.is_relative_to(repo_root.resolve()):
        workspace.cleanup()
        raise PreOutcomeRetentionError(
            "evidence workspace must not be inside the execution worktree"
        )
    return workspace


def _init_isolated_repo(isolated: Path) -> None:
    run_git(isolated, ["init"])
    run_git(isolated, ["config", "user.name", "Signalbot Evidence Retention"])
    run_git(isolated, ["config", "user.email", "evidence-retention@signalbot.invalid"])
    run_git(isolated, ["config", "commit.gpgsign", "false"])


def _ls_remote_sha(isolated: Path, endpoint: str, evidence_ref: str) -> str | None:
    raw = run_git(isolated, ["ls-remote", "--heads", endpoint, evidence_ref]).decode("utf-8")
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


def _tree_names(isolated: Path, commit: str) -> tuple[str, ...]:
    raw = run_git(isolated, ["ls-tree", "-r", "--name-only", commit]).decode("utf-8")
    return tuple(line for line in raw.splitlines() if line.strip())


def classify_evidence_tree(names: Sequence[str]) -> str:
    files = set(names)
    artifacts = {name for name in files if _ARTIFACT_PATH_RE.fullmatch(name)}
    extras = files - {RESERVATION_BLOB_PATH, CLAIM_BLOB_PATH, RECEIPT_BLOB_PATH} - artifacts
    if extras or len(artifacts) > 1:
        return STATE_UNKNOWN
    if files == {RESERVATION_BLOB_PATH}:
        return STATE_RESERVED
    if files == {RESERVATION_BLOB_PATH, CLAIM_BLOB_PATH}:
        return STATE_CLAIMED
    if (
        RESERVATION_BLOB_PATH in files
        and CLAIM_BLOB_PATH in files
        and RECEIPT_BLOB_PATH in files
        and len(artifacts) == 1
    ):
        return STATE_ARCHIVED
    return STATE_UNKNOWN


def _independent_readback(
    *,
    repo_root: Path,
    endpoint: str,
    evidence_ref: str,
    relative: str,
    expected_commit: str | None = None,
) -> tuple[str, bytes]:
    with _isolated_workspace(repo_root) as raw_dir:
        isolated = Path(raw_dir)
        _init_isolated_repo(isolated)
        try:
            run_git(isolated, ["fetch", "--no-tags", endpoint, evidence_ref])
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


def _fetch_evidence_commit(
    isolated: Path, endpoint: str, evidence_ref: str
) -> str:
    run_git(isolated, ["fetch", "--no-tags", endpoint, evidence_ref])
    commit = run_git(isolated, ["rev-parse", "FETCH_HEAD"]).decode("utf-8").strip().lower()
    if not _HEX40_RE.fullmatch(commit):
        raise PreOutcomeRetentionError("fetched evidence commit SHA is malformed")
    return commit


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
    transport: VerifiedEvidenceTransport,
    evidence_ref: str,
    evidence_head_sha: str,
) -> DurableEvidenceReservation:
    reservation = DurableEvidenceReservation(
        hypothesis_id=str(payload["hypothesis_id"]),
        stage=str(payload["stage"]),
        code_sha=str(payload["code_sha"]),
        code_tree=str(payload["code_tree"]),
        repo_root=repo_root.resolve(),
        remote_repository_identity=transport.identity,
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
        transport=transport,
        reservation_bytes=payload_bytes,
        evidence_ref=evidence_ref,
        evidence_head_sha=evidence_head_sha,
    )
    weakref.finalize(reservation, _BOUND_RESERVATIONS.pop, id(reservation), None)
    weakref.finalize(reservation, _BACKEND_BY_ID.pop, id(reservation), None)
    return reservation


def _create_verified_remote_reservation(
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
    transport: VerifiedEvidenceTransport,
) -> DurableEvidenceReservation:
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise PreOutcomeRetentionError(
            "code_freeze must be a VerifiedCodeFreeze from verify_batch02_code"
        )
    freeze = verify_git_freeze(code_freeze.repo_root, code_freeze.code_sha)
    if freeze.tree_oid != code_freeze.tree_oid:
        raise PreOutcomeRetentionError("code tree drifted before evidence reservation")
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
        remote_repository_identity=transport.identity,
    )
    payload_bytes = canonical_json_bytes(payload)
    reservation_sha = sha256_bytes(payload_bytes)

    with _isolated_workspace(freeze.repo_root) as raw_dir:
        isolated = Path(raw_dir)
        _init_isolated_repo(isolated)
        existing = _ls_remote_sha(isolated, transport.endpoint, evidence_ref)
        if existing is None:
            _write_bytes_new(isolated / RESERVATION_BLOB_PATH, payload_bytes)
            run_git(isolated, ["add", "--", RESERVATION_BLOB_PATH])
            run_git(
                isolated,
                ["commit", "-m", f"batch02 evidence reservation {reservation_sha[:16]}"],
            )
            head = run_git(isolated, ["rev-parse", "HEAD"]).decode("utf-8").strip().lower()
            run_git(isolated, ["push", transport.endpoint, f"HEAD:{evidence_ref}"])
            expected_head = head
        else:
            commit = _fetch_evidence_commit(isolated, transport.endpoint, evidence_ref)
            names = _tree_names(isolated, commit)
            state = classify_evidence_tree(names)
            if state != STATE_RESERVED:
                raise PreOutcomeRetentionError(
                    f"evidence ref is not a pristine RESERVED state ({state}); "
                    "new reservation/run is not authorized"
                )
            existing_bytes = _show_blob(isolated, commit, RESERVATION_BLOB_PATH)
            if existing_bytes != payload_bytes:
                raise PreOutcomeRetentionError(
                    "incompatible pre-existing evidence reservation on this "
                    "normalized B2 slot; exact hypothesis_id/payload mismatch "
                    "is not overwritten"
                )
            expected_head = existing

    commit, remote_bytes = _independent_readback(
        repo_root=freeze.repo_root,
        endpoint=transport.endpoint,
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
        transport=transport,
        evidence_ref=evidence_ref,
        evidence_head_sha=commit,
    )
    minted.assert_minted()
    return minted


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
    """Production reservation: canonical GitHub transport only."""
    transport = inspect_production_evidence_transport(code_freeze.repo_root)
    return _create_verified_remote_reservation(
        code_freeze=code_freeze,
        hypothesis_id=hypothesis_id,
        stage=stage,
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        start_inclusive_ms=start_inclusive_ms,
        end_exclusive_ms=end_exclusive_ms,
        allowed_years=allowed_years,
        required_gate_names=required_gate_names,
        seeds=seeds,
        transport=transport,
    )


def prepare_test_evidence_reservation(
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
    test_bare_remote: Path,
) -> DurableEvidenceReservation:
    """TEST-ONLY reservation against a temporary local bare Git remote.

    Not re-exported from batch02_contracts and not part of the hypothesis API.
    """
    transport = prepare_test_evidence_transport(test_bare_remote)
    return _create_verified_remote_reservation(
        code_freeze=code_freeze,
        hypothesis_id=hypothesis_id,
        stage=stage,
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        start_inclusive_ms=start_inclusive_ms,
        end_exclusive_ms=end_exclusive_ms,
        allowed_years=allowed_years,
        required_gate_names=required_gate_names,
        seeds=seeds,
        transport=transport,
    )


def claim_remote_outcome_access(
    reservation: DurableEvidenceReservation,
) -> DurableOutcomeAccessClaim:
    """Fast-forward RESERVED -> OUTCOME_ACCESS_CLAIMED, then independently read back."""
    reservation.assert_minted()
    backend = _BACKEND_BY_ID[id(reservation)]
    if backend.claim_head_sha is not None:
        raise PreOutcomeRetentionError(
            "this reservation already claimed outcome access"
        )
    freeze = verify_git_freeze(reservation.repo_root, reservation.code_sha)
    if freeze.tree_oid != reservation.code_tree:
        raise PreOutcomeRetentionError("code tree drifted after evidence reservation")
    transport = backend.transport
    claim_payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": CLAIM_KIND,
        "reservation_sha256": reservation.reservation_sha256,
        "hypothesis_id": reservation.hypothesis_id,
        "stage": reservation.stage,
        "code_sha": reservation.code_sha,
        "code_tree": reservation.code_tree,
        "dataset_id": reservation.dataset_id,
        "snapshot_id": reservation.snapshot_id,
        "development_window": {
            "start_inclusive_ms": reservation.start_inclusive_ms,
            "end_exclusive_ms": reservation.end_exclusive_ms,
            "allowed_years": list(reservation.allowed_years),
        },
        "gate_contract_sha256": reservation.gate_contract_sha256,
        "seeds": dict(sorted(reservation.seeds.items())),
        "remote_repository_identity": reservation.remote_repository_identity,
        "reservation_commit_sha": reservation.evidence_head_sha,
        "outcomes": None,
    }
    claim_bytes = canonical_json_bytes(claim_payload)
    claim_sha = sha256_bytes(claim_bytes)
    pushed_sha: str | None = None
    remote_mutation_attempted = False
    try:
        with _isolated_workspace(freeze.repo_root) as raw_dir:
            isolated = Path(raw_dir)
            _init_isolated_repo(isolated)
            remote_head = _ls_remote_sha(
                isolated, transport.endpoint, reservation.evidence_ref
            )
            if remote_head != reservation.evidence_head_sha:
                raise PreOutcomeRetentionError(
                    "evidence reservation ref drifted before outcome-access claim"
                )
            commit = _fetch_evidence_commit(
                isolated, transport.endpoint, reservation.evidence_ref
            )
            state = classify_evidence_tree(_tree_names(isolated, commit))
            if state != STATE_RESERVED:
                raise PreOutcomeRetentionError(
                    f"outcome-access claim requires RESERVED state, found {state}"
                )
            reserved = _show_blob(isolated, commit, RESERVATION_BLOB_PATH)
            if reserved != backend.reservation_bytes:
                raise PreOutcomeRetentionError("reservation bytes changed before claim")
            run_git(isolated, ["checkout", "--detach", commit])
            _write_bytes_new(isolated / CLAIM_BLOB_PATH, claim_bytes)
            run_git(isolated, ["add", "--", CLAIM_BLOB_PATH, RESERVATION_BLOB_PATH])
            run_git(
                isolated,
                ["commit", "-m", f"batch02 outcome access claim {claim_sha[:16]}"],
            )
            parent = run_git(
                isolated, ["rev-parse", "HEAD^"]
            ).decode("utf-8").strip().lower()
            if parent != reservation.evidence_head_sha:
                raise PreOutcomeRetentionError(
                    "outcome-access claim parent is not the verified reservation head"
                )
            pushed_sha = run_git(isolated, ["rev-parse", "HEAD"]).decode("utf-8").strip().lower()
            remote_mutation_attempted = True
            run_git(
                isolated,
                ["push", transport.endpoint, f"{pushed_sha}:{reservation.evidence_ref}"],
            )
    except AmbiguousOutcomeAccessStateError:
        raise
    except (GitTimeoutError, PreOutcomeRetentionError, Exception) as exc:
        if remote_mutation_attempted:
            raise AmbiguousOutcomeAccessStateError(
                f"{AMBIGUOUS_CLAIM_STATE}: claim push timed out or failed after the "
                "remote mutation was attempted; the remote claim may already exist. "
                "Dataset authorization is blocked. Do not reset or delete the remote "
                "claim. Operator adjudication required."
            ) from None
        if isinstance(exc, (GitTimeoutError, PreOutcomeRetentionError)):
            raise
        raise PreOutcomeRetentionError(
            _redact(f"outcome-access claim failed: {exc}")
        ) from exc

    try:
        read_commit, remote_claim = _independent_readback(
            repo_root=freeze.repo_root,
            endpoint=transport.endpoint,
            evidence_ref=reservation.evidence_ref,
            relative=CLAIM_BLOB_PATH,
            expected_commit=pushed_sha,
        )
        _, remote_reservation = _independent_readback(
            repo_root=freeze.repo_root,
            endpoint=transport.endpoint,
            evidence_ref=reservation.evidence_ref,
            relative=RESERVATION_BLOB_PATH,
            expected_commit=pushed_sha,
        )
        if remote_claim != claim_bytes or sha256_bytes(remote_claim) != claim_sha:
            raise AmbiguousOutcomeAccessStateError(
                f"{AMBIGUOUS_CLAIM_STATE}: claim readback digest mismatch. "
                "Dataset authorization is blocked. Operator adjudication required."
            )
        if remote_reservation != backend.reservation_bytes:
            raise AmbiguousOutcomeAccessStateError(
                f"{AMBIGUOUS_CLAIM_STATE}: reservation bytes changed across the claim. "
                "Dataset authorization is blocked. Operator adjudication required."
            )
        with _isolated_workspace(freeze.repo_root) as raw_dir:
            isolated = Path(raw_dir)
            _init_isolated_repo(isolated)
            run_git(
                isolated,
                ["fetch", "--no-tags", transport.endpoint, reservation.evidence_ref],
            )
            parent = run_git(
                isolated, ["rev-parse", f"{read_commit}^"]
            ).decode("utf-8").strip().lower()
            if parent != reservation.evidence_head_sha:
                raise AmbiguousOutcomeAccessStateError(
                    f"{AMBIGUOUS_CLAIM_STATE}: claim parent is not the reservation head. "
                    "Dataset authorization is blocked. Operator adjudication required."
                )
            state = classify_evidence_tree(_tree_names(isolated, read_commit))
            if state != STATE_CLAIMED:
                raise AmbiguousOutcomeAccessStateError(
                    f"{AMBIGUOUS_CLAIM_STATE}: claimed tree is not OUTCOME_ACCESS_CLAIMED "
                    f"({state}). Dataset authorization is blocked."
                )
    except AmbiguousOutcomeAccessStateError:
        raise
    except Exception as exc:
        raise AmbiguousOutcomeAccessStateError(
            f"{AMBIGUOUS_CLAIM_STATE}: claim push may have succeeded but independent "
            "readback could not be proven. Dataset authorization is blocked. "
            "Do not reset or delete the remote claim. Operator adjudication required. "
            f"detail={_redact(str(exc))}"
        ) from None

    claim = DurableOutcomeAccessClaim(
        hypothesis_id=reservation.hypothesis_id,
        reservation_sha256=reservation.reservation_sha256,
        claim_sha256=claim_sha,
        claim_head_sha=read_commit,
        reservation_commit_sha=reservation.evidence_head_sha,
        evidence_ref=reservation.evidence_ref,
        remote_repository_identity=reservation.remote_repository_identity,
        _mint_token=_CLAIM_MINT_TOKEN,
    )
    _BOUND_CLAIMS[id(claim)] = _claim_identity(claim)
    weakref.finalize(claim, _BOUND_CLAIMS.pop, id(claim), None)
    backend.claim_head_sha = read_commit
    backend.claim_bytes = claim_bytes
    claim.assert_minted()
    verify_git_freeze(freeze.repo_root, freeze.code_sha)
    return claim


def mint_persisted_result_proof(
    *,
    result_path: Path,
    artifact_sha256: str,
    artifact_size_bytes: int,
    run_identity_sha256: str,
    hypothesis_id: str,
    code_sha: str,
    code_tree: str,
    claim: DurableOutcomeAccessClaim,
    reservation: DurableEvidenceReservation,
) -> PersistedBatch02ResultProof:
    """Mint a persisted-result proof. Called only after canonical persist."""
    claim.assert_minted()
    reservation.assert_minted()
    proof = PersistedBatch02ResultProof(
        result_path=result_path.resolve(strict=False),
        artifact_sha256=artifact_sha256,
        artifact_size_bytes=artifact_size_bytes,
        run_identity_sha256=run_identity_sha256,
        hypothesis_id=hypothesis_id,
        code_sha=code_sha,
        code_tree=code_tree,
        claim_sha256=claim.claim_sha256,
        claim_head_sha=claim.claim_head_sha,
        evidence_ref=reservation.evidence_ref,
        reservation_sha256=reservation.reservation_sha256,
        _mint_token=_PERSIST_MINT_TOKEN,
    )
    _BOUND_PERSISTED[id(proof)] = _persisted_identity(proof)
    weakref.finalize(proof, _BOUND_PERSISTED.pop, id(proof), None)
    return proof


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


def archive_persisted_result_proof(
    *,
    persisted: PersistedBatch02ResultProof,
    reservation: DurableEvidenceReservation,
    claim: DurableOutcomeAccessClaim,
    run_identity_sha256: str,
    code_freeze: VerifiedCodeFreeze,
    stage: str,
    dataset_id: str,
    snapshot_id: str,
) -> DurableArchiveReceipt:
    """Archive exact persisted bytes from a minted persist proof."""
    try:
        persisted.assert_minted()
        reservation.assert_minted()
        claim.assert_minted()
    except PostOutcomeRetentionFailure:
        raise
    except Exception as exc:
        _raise_post_outcome(
            result_path=getattr(persisted, "result_path", Path(".")),
            local_sha256=str(getattr(persisted, "artifact_sha256", "")),
            local_size_bytes=int(getattr(persisted, "artifact_size_bytes", 0) or 0),
            reservation=reservation,
            reason=_redact(f"archive authority failure: {exc}"),
        )

    result_path = persisted.result_path
    backend = _BACKEND_BY_ID[id(reservation)]
    try:
        freeze = verify_git_freeze(code_freeze.repo_root, code_freeze.code_sha)
        if freeze.tree_oid != reservation.code_tree or freeze.code_sha != reservation.code_sha:
            raise RuntimeError("reservation is bound to a different code freeze")
        if (
            persisted.hypothesis_id != reservation.hypothesis_id
            or persisted.claim_sha256 != claim.claim_sha256
            or persisted.claim_head_sha != claim.claim_head_sha
            or persisted.run_identity_sha256 != run_identity_sha256
        ):
            raise RuntimeError("persisted-result proof does not match claim/run identity")
        if result_path.is_symlink() or not result_path.is_file():
            raise RuntimeError("canonical local result is missing or is a symlink")
        source = result_path.read_bytes()
        source_sha = sha256_bytes(source)
        source_size = len(source)
        if source_sha != persisted.artifact_sha256 or source_size != persisted.artifact_size_bytes:
            raise RuntimeError(
                "canonical local result bytes no longer match the persist proof"
            )
        if claim.claim_head_sha != backend.claim_head_sha:
            raise RuntimeError("claim head is not the backend-bound outcome-access claim")
    except PostOutcomeRetentionFailure:
        raise
    except Exception as exc:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=str(getattr(persisted, "artifact_sha256", "")),
            local_size_bytes=int(getattr(persisted, "artifact_size_bytes", 0) or 0),
            reservation=reservation,
            reason=_redact(str(exc)),
        )

    # Local fail-closed guard against a mismatched concurrent archive of the
    # same canonical result. This is not a durability substitute; remote
    # claim/archive remain authoritative. Unreadable, mismatched, or
    # unwritable lock bytes fail as POST_OUTCOME_RETENTION_FAILURE.
    lock_path = result_path.with_name(result_path.name + ".durable_retention.lock.json")
    lock_bytes = canonical_json_bytes(
        {
            "kind": "batch02_durable_retention_lock",
            "reservation_sha256": reservation.reservation_sha256,
            "claim_sha256": claim.claim_sha256,
            "evidence_ref": reservation.evidence_ref,
            "artifact_sha256": source_sha,
        }
    ) + b"\n"
    if lock_path.exists():
        try:
            existing_lock = lock_path.read_bytes()
        except OSError as exc:
            _raise_post_outcome(
                result_path=result_path,
                local_sha256=source_sha,
                local_size_bytes=source_size,
                reservation=reservation,
                reason=_redact(f"retention lock is unreadable: {exc}"),
            )
        if existing_lock != lock_bytes:
            _raise_post_outcome(
                result_path=result_path,
                local_sha256=source_sha,
                local_size_bytes=source_size,
                reservation=reservation,
                reason="retention lock does not match this persisted result",
            )
    else:
        try:
            _write_bytes_new(lock_path, lock_bytes)
        except Exception as exc:
            _raise_post_outcome(
                result_path=result_path,
                local_sha256=source_sha,
                local_size_bytes=source_size,
                reservation=reservation,
                reason=_redact(f"retention lock write failed: {exc}"),
            )

    relative = artifact_relpath(
        reservation.hypothesis_id,
        reservation.code_sha,
        source_sha,
    )
    receipt_payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": RECEIPT_KIND,
        "hypothesis_id": reservation.hypothesis_id,
        "stage": stage,
        "code_sha": reservation.code_sha,
        "code_tree": reservation.code_tree,
        "run_identity_sha256": run_identity_sha256,
        "dataset_id": dataset_id,
        "dataset_snapshot": snapshot_id,
        "artifact_sha256": source_sha,
        "artifact_size_bytes": source_size,
        "remote_repository_identity": reservation.remote_repository_identity,
        "evidence_ref": reservation.evidence_ref,
        "evidence_path": relative,
        "reservation_sha256": reservation.reservation_sha256,
        "claim_sha256": claim.claim_sha256,
    }
    receipt_bytes = canonical_json_bytes(receipt_payload) + b"\n"
    transport = backend.transport

    try:
        with _isolated_workspace(freeze.repo_root) as raw_dir:
            isolated = Path(raw_dir)
            _init_isolated_repo(isolated)
            remote_head = _ls_remote_sha(
                isolated, transport.endpoint, reservation.evidence_ref
            )
            if remote_head != claim.claim_head_sha:
                raise RuntimeError(
                    "evidence ref drifted from the claim head that authorized outcomes"
                )
            commit = _fetch_evidence_commit(
                isolated, transport.endpoint, reservation.evidence_ref
            )
            state = classify_evidence_tree(_tree_names(isolated, commit))
            if state != STATE_CLAIMED:
                raise RuntimeError(
                    f"archive requires OUTCOME_ACCESS_CLAIMED parent, found {state}"
                )
            parent = run_git(isolated, ["rev-parse", f"{commit}^"]).decode("utf-8").strip().lower()
            if parent != reservation.evidence_head_sha:
                raise RuntimeError("claim parent is not the verified reservation head")
            reserved = _show_blob(isolated, commit, RESERVATION_BLOB_PATH)
            claimed = _show_blob(isolated, commit, CLAIM_BLOB_PATH)
            if reserved != backend.reservation_bytes or claimed != backend.claim_bytes:
                raise RuntimeError("reservation/claim bytes changed before archive")
            run_git(isolated, ["checkout", "--detach", commit])
            dest = isolated / relative
            if dest.exists() or dest.is_symlink():
                existing = dest.read_bytes()
                if existing != source:
                    raise RuntimeError("existing remote artifact has a different digest")
            else:
                _write_bytes_new(dest, source)
            receipt_path = isolated / RECEIPT_BLOB_PATH
            if receipt_path.exists():
                if receipt_path.read_bytes() != receipt_bytes:
                    raise RuntimeError("existing receipt does not match this archive")
            else:
                _write_bytes_new(receipt_path, receipt_bytes)
            run_git(
                isolated,
                [
                    "add",
                    "--",
                    relative,
                    RECEIPT_BLOB_PATH,
                    CLAIM_BLOB_PATH,
                    RESERVATION_BLOB_PATH,
                ],
            )
            status = run_git(isolated, ["status", "--porcelain"]).decode("utf-8")
            if status.strip():
                run_git(
                    isolated,
                    ["commit", "-m", f"batch02 evidence archive {source_sha[:16]}"],
                )
            archive_parent = run_git(
                isolated, ["rev-parse", "HEAD^"]
            ).decode("utf-8").strip().lower()
            if archive_parent != claim.claim_head_sha:
                raise RuntimeError(
                    "archive commit is not a direct child of the outcome-access claim"
                )
            pushed_sha = run_git(isolated, ["rev-parse", "HEAD"]).decode("utf-8").strip().lower()
            run_git(
                isolated,
                ["push", transport.endpoint, f"{pushed_sha}:{reservation.evidence_ref}"],
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
            endpoint=transport.endpoint,
            evidence_ref=reservation.evidence_ref,
            relative=relative,
            expected_commit=pushed_sha,
        )
        _, remote_receipt = _independent_readback(
            repo_root=freeze.repo_root,
            endpoint=transport.endpoint,
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

    if sha256_bytes(remote_artifact) != source_sha or len(remote_artifact) != source_size:
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
    try:
        still_local = result_path.read_bytes()
    except OSError as exc:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason=_redact(f"canonical local result could not be re-read: {exc}"),
        )
    if still_local != source:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=sha256_bytes(still_local),
            local_size_bytes=len(still_local),
            reservation=reservation,
            reason="canonical local result changed during archival",
        )
    try:
        verify_git_freeze(freeze.repo_root, freeze.code_sha)
    except Exception as exc:
        _raise_post_outcome(
            result_path=result_path,
            local_sha256=source_sha,
            local_size_bytes=source_size,
            reservation=reservation,
            reason=_redact(f"execution worktree changed during archive: {exc}"),
        )
    return DurableArchiveReceipt(
        schema_version=SCHEMA_VERSION,
        hypothesis_id=reservation.hypothesis_id,
        stage=stage,
        code_sha=reservation.code_sha,
        code_tree=reservation.code_tree,
        run_identity_sha256=run_identity_sha256,
        dataset_id=dataset_id,
        dataset_snapshot=snapshot_id,
        artifact_sha256=source_sha,
        artifact_size_bytes=source_size,
        remote_repository_identity=reservation.remote_repository_identity,
        evidence_ref=reservation.evidence_ref,
        evidence_path=relative,
        reservation_sha256=reservation.reservation_sha256,
        claim_sha256=claim.claim_sha256,
        archive_commit_sha=remote_commit,
        receipt_payload=json.loads(receipt_bytes),
        _mint_token=_RECEIPT_MINT_TOKEN,
    )
