"""Canonical integrity contracts for Signalbot Batch02+ runtime code.

This module is the only supported entry point for new Batch02 hypothesis
runners. Frozen/consumed H01-H05 and B2-01 code is intentionally not
rewritten: changing those implementations after outcome access would mutate
historical experimental machinery.

New B2 hypotheses must use:
- verify_batch02_code() for identity-stage exact Git proof without dataset access;
- prepare_batch02_run() only after the explicit development outcome-access gate
  for historical B2-01/B2-02 machinery;
- prepare_batch02_evidence_reservation() then prepare_batch02_retained_run()
  for B2-03+ before any real dataset/outcome access;
- persist_batch02_result() for historical B2-01/B2-02 immutable JSON evidence;
- persist_batch02_retained_result() then archive_batch02_result() for B2-03+
  exact-byte durable remote archival of minted persisted-result proofs;
- rolling_midrank_percentile() as the canonical strict prior-window midrank
  primitive whenever a frozen hypothesis requires percentile/relative-standing
  semantics.

Repository regression tests enforce mechanically auditable B2-02+ integrity
boundaries and reject known alternate rank APIs/bindings. They do not claim
that AST linting can prove arbitrary numerical Python is semantically
equivalent to this primitive; that wiring remains part of each hypothesis
freeze/code review.
"""
from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left, bisect_right, insort_right
from collections import deque
from dataclasses import dataclass
from numbers import Integral
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from scripts.research.lib.batch02_evidence_retention import (
    AmbiguousOutcomeAccessStateError,
    DurableArchiveReceipt,
    DurableEvidenceReservation,
    DurableOutcomeAccessClaim,
    PersistedBatch02ResultProof,
    PostOutcomeRetentionFailure,
    PreOutcomeRetentionError,
    _raise_post_outcome,
    archive_persisted_result_proof,
    claim_remote_outcome_access,
    create_verified_remote_reservation,
    hypothesis_requires_durable_retention,
    mint_persisted_result_proof,
)
from scripts.research.lib.research_harness import (
    ArtifactExistsError,
    AuthorizedDataset,
    DatasetIdentityContract,
    OutcomeAccessPolicy,
    PromotionGateContract,
    VerifiedCodeFreeze,
    authorize_dataset_access,
    build_run_identity,
    verify_git_freeze,
    write_json_new,
)


class Batch02ContractError(RuntimeError):
    """Malformed input to a canonical Batch02 integrity primitive."""


_RUN_CONTEXT_TOKEN = object()


def _canonical_payload_sha256(payload: Mapping[str, object]) -> str:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise Batch02ContractError("run identity must be canonical JSON") from exc
    return hashlib.sha256(encoded).hexdigest()


def _copy_canonical_mapping(payload: Mapping[str, object]) -> dict[str, object]:
    try:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        value = json.loads(encoded)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise Batch02ContractError("mapping must be canonical JSON") from exc
    if not isinstance(value, dict):
        raise Batch02ContractError("mapping must canonicalize to a JSON object")
    return value


@dataclass(frozen=True)
class Batch02RunContext:
    """Minted verified provenance required for all outcome I/O and persistence."""

    code_freeze: VerifiedCodeFreeze
    _authorized_dataset: AuthorizedDataset
    run_identity: Mapping[str, object]
    _run_identity_sha256: str = ""
    _run_context_token: object = None
    _outcome_claim: DurableOutcomeAccessClaim | None = None
    _reservation: DurableEvidenceReservation | None = None

    def __post_init__(self) -> None:
        self.assert_minted()

    def assert_minted(self) -> None:
        if getattr(self, "_run_context_token", None) is not _RUN_CONTEXT_TOKEN:
            raise Batch02ContractError(
                "Batch02RunContext must be created by prepare_batch02_run "
                "or prepare_batch02_retained_run"
            )
        if not isinstance(self.code_freeze, VerifiedCodeFreeze):
            raise Batch02ContractError("run context has invalid code freeze proof")
        if not isinstance(self._authorized_dataset, AuthorizedDataset):
            raise Batch02ContractError("run context has invalid dataset proof")
        self._authorized_dataset.assert_minted()
        if (
            not isinstance(self._run_identity_sha256, str)
            or self._run_identity_sha256 != _canonical_payload_sha256(self.run_identity)
        ):
            raise Batch02ContractError("run context provenance was mutated")


def _reverify_run_code(run_context: Batch02RunContext) -> None:
    if not isinstance(run_context, Batch02RunContext):
        raise Batch02ContractError(
            "run_context must be a Batch02RunContext from prepare_batch02_run "
            "or prepare_batch02_retained_run"
        )
    run_context.assert_minted()
    current = verify_git_freeze(
        run_context.code_freeze.repo_root,
        run_context.code_freeze.code_sha,
    )
    if current.tree_oid != run_context.code_freeze.tree_oid:
        raise Batch02ContractError("run context Git tree changed after authorization")


def verify_batch02_code(
    *,
    repo_root: Path,
    expected_code_sha: str,
) -> VerifiedCodeFreeze:
    """Verify exact clean tracked Git bytes without touching dataset outcomes."""
    return verify_git_freeze(repo_root, expected_code_sha)


def prepare_batch02_run(
    *,
    code_freeze: VerifiedCodeFreeze,
    outcome_access_acknowledged: bool,
    dataset_root: Path,
    hypothesis_id: str,
    stage: str,
    command: Sequence[str],
    seeds: Mapping[str, int],
    identity: DatasetIdentityContract | None = None,
    policy: OutcomeAccessPolicy | None = None,
    gate_contract: PromotionGateContract | None = None,
    dataset_id: str | None = None,
    snapshot_id: str | None = None,
    start_inclusive_ms: int | None = None,
    end_exclusive_ms: int | None = None,
    allowed_years: Sequence[int] | None = None,
    required_gate_names: Sequence[str] | None = None,
) -> Batch02RunContext:
    """Authorize dataset bytes and build provenance for an outcome-bearing run.

    Historical B2-01/B2-02 machinery. B2-03+ cannot use this entry point:
    those hypotheses must first establish a remotely verified evidence
    reservation and then call prepare_batch02_retained_run().

    New B2 hypothesis code may use the primitive-only public form
    (dataset_id/snapshot_id/time window/years/gate names). The canonical
    contracts module constructs the internal Harness v1 dataclasses itself, so
    hypothesis code does not need access to internal harness types.

    The legacy typed-object form remains accepted for existing contract tests
    and trusted callers. Mixing typed objects with primitive contract fields is
    rejected to keep the authority boundary unambiguous.
    """
    if hypothesis_requires_durable_retention(hypothesis_id):
        raise Batch02ContractError(
            "B2-03+ requires prepare_batch02_evidence_reservation then "
            "prepare_batch02_retained_run before any dataset authorization"
        )
    return _prepare_batch02_run_body(
        code_freeze=code_freeze,
        outcome_access_acknowledged=outcome_access_acknowledged,
        dataset_root=dataset_root,
        hypothesis_id=hypothesis_id,
        stage=stage,
        command=command,
        seeds=seeds,
        identity=identity,
        policy=policy,
        gate_contract=gate_contract,
        dataset_id=dataset_id,
        snapshot_id=snapshot_id,
        start_inclusive_ms=start_inclusive_ms,
        end_exclusive_ms=end_exclusive_ms,
        allowed_years=allowed_years,
        required_gate_names=required_gate_names,
    )


def prepare_batch02_evidence_reservation(
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
    """Verify code freeze, then push and read back an outcome-blind reservation.

    This is the B2-03+ pre-outcome gate. It must succeed before
    prepare_batch02_retained_run() may authorize dataset bytes.
    """
    if not hypothesis_requires_durable_retention(hypothesis_id):
        raise Batch02ContractError(
            "historical B2-01/B2-02 must not use the V1 retention reservation API"
        )
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise Batch02ContractError(
            "code_freeze must be a VerifiedCodeFreeze from verify_batch02_code"
        )
    try:
        return create_verified_remote_reservation(
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
        )
    except PreOutcomeRetentionError:
        raise
    except Exception as exc:
        raise PreOutcomeRetentionError(
            "durable evidence reservation failed closed before outcome access"
        ) from exc


def prepare_batch02_retained_run(
    *,
    reservation: DurableEvidenceReservation,
    outcome_access_acknowledged: bool,
    dataset_root: Path,
    command: Sequence[str],
) -> Batch02RunContext:
    """Claim remote outcome access, then authorize dataset bytes.

    The durable OUTCOME_ACCESS_CLAIMED transition is completed and read back
    before authorize_dataset_access(). A second call cannot mint another run.
    """
    if not isinstance(reservation, DurableEvidenceReservation):
        raise PreOutcomeRetentionError(
            "prepare_batch02_retained_run requires a minted DurableEvidenceReservation"
        )
    reservation.assert_minted()
    if not hypothesis_requires_durable_retention(reservation.hypothesis_id):
        raise Batch02ContractError(
            "historical B2-01/B2-02 must not use the V1 retained-run API"
        )
    claim = claim_remote_outcome_access(reservation)
    return _prepare_batch02_run_body(
        code_freeze=verify_git_freeze(reservation.repo_root, reservation.code_sha),
        outcome_access_acknowledged=outcome_access_acknowledged,
        dataset_root=dataset_root,
        hypothesis_id=reservation.hypothesis_id,
        stage=reservation.stage,
        command=command,
        seeds=reservation.seeds,
        dataset_id=reservation.dataset_id,
        snapshot_id=reservation.snapshot_id,
        start_inclusive_ms=reservation.start_inclusive_ms,
        end_exclusive_ms=reservation.end_exclusive_ms,
        allowed_years=reservation.allowed_years,
        required_gate_names=reservation.required_gate_names,
        outcome_claim=claim,
        reservation=reservation,
    )


def archive_batch02_result(
    *,
    persisted_result: PersistedBatch02ResultProof,
    run_context: Batch02RunContext,
) -> DurableArchiveReceipt:
    """Archive exact bytes bound by a minted persist proof. No caller digest."""
    reservation = getattr(run_context, "_reservation", None)
    claim = getattr(run_context, "_outcome_claim", None)
    result_path = getattr(persisted_result, "result_path", Path("."))
    local_sha = str(getattr(persisted_result, "artifact_sha256", "") or "")
    local_size = int(getattr(persisted_result, "artifact_size_bytes", 0) or 0)

    def _fail(reason: str) -> None:
        if isinstance(reservation, DurableEvidenceReservation):
            _raise_post_outcome(
                result_path=result_path if isinstance(result_path, Path) else Path("."),
                local_sha256=local_sha,
                local_size_bytes=local_size,
                reservation=reservation,
                reason=reason,
            )
        raise PostOutcomeRetentionFailure(
            f"POST_OUTCOME_RETENTION_FAILURE: {reason}. "
            "OUTCOME CONSUMED = YES; RERUN AUTHORIZED = NO; "
            "LOCAL CANONICAL ARTIFACT MUST BE PRESERVED; OPERATOR RECOVERY REQUIRED.",
            local_artifact_path=result_path if isinstance(result_path, Path) else Path("."),
            local_sha256=local_sha,
            local_size_bytes=local_size,
            evidence_ref="",
            reservation_sha256="",
        )

    try:
        if not isinstance(persisted_result, PersistedBatch02ResultProof):
            raise RuntimeError("archive requires a minted PersistedBatch02ResultProof")
        persisted_result.assert_minted()
        _reverify_run_code(run_context)
        if not isinstance(reservation, DurableEvidenceReservation):
            raise RuntimeError("archive is missing the bound evidence reservation")
        if not isinstance(claim, DurableOutcomeAccessClaim):
            raise RuntimeError("archive is missing the bound outcome-access claim")
        reservation.assert_minted()
        claim.assert_minted()
        if run_context.run_identity.get("hypothesis_id") != reservation.hypothesis_id:
            raise RuntimeError("archive hypothesis does not match reservation")
        expected_path = _expected_result_path(run_context)
        if persisted_result.result_path.resolve(strict=False) != expected_path:
            raise RuntimeError("result path is not the canonical persist path")
        return archive_persisted_result_proof(
            persisted=persisted_result,
            reservation=reservation,
            claim=claim,
            run_identity_sha256=run_context._run_identity_sha256,
            code_freeze=run_context.code_freeze,
            stage=str(run_context.run_identity.get("stage") or reservation.stage),
            dataset_id=str(
                run_context.run_identity.get("dataset_id") or reservation.dataset_id
            ),
            snapshot_id=str(
                run_context.run_identity.get("snapshot_id") or reservation.snapshot_id
            ),
        )
    except PostOutcomeRetentionFailure:
        raise
    except Exception as exc:
        _fail(str(exc))
        raise  # pragma: no cover


def _prepare_batch02_run_body(
    *,
    code_freeze: VerifiedCodeFreeze,
    outcome_access_acknowledged: bool,
    dataset_root: Path,
    hypothesis_id: str,
    stage: str,
    command: Sequence[str],
    seeds: Mapping[str, int],
    identity: DatasetIdentityContract | None = None,
    policy: OutcomeAccessPolicy | None = None,
    gate_contract: PromotionGateContract | None = None,
    dataset_id: str | None = None,
    snapshot_id: str | None = None,
    start_inclusive_ms: int | None = None,
    end_exclusive_ms: int | None = None,
    allowed_years: Sequence[int] | None = None,
    required_gate_names: Sequence[str] | None = None,
    outcome_claim: DurableOutcomeAccessClaim | None = None,
    reservation: DurableEvidenceReservation | None = None,
) -> Batch02RunContext:
    if stage != "development":
        raise Batch02ContractError(
            "prepare_batch02_run is restricted to development stage"
        )
    if outcome_access_acknowledged is not True:
        raise Batch02ContractError(
            "development outcome access requires explicit acknowledgement"
        )
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise Batch02ContractError(
            "code_freeze must be a VerifiedCodeFreeze from verify_batch02_code"
        )

    typed_supplied = any(
        value is not None for value in (identity, policy, gate_contract)
    )
    primitive_supplied = any(
        value is not None
        for value in (
            dataset_id,
            snapshot_id,
            start_inclusive_ms,
            end_exclusive_ms,
            allowed_years,
            required_gate_names,
        )
    )
    if typed_supplied and primitive_supplied:
        raise Batch02ContractError(
            "prepare_batch02_run may not mix typed and primitive contract forms"
        )

    if primitive_supplied:
        if not (
            isinstance(dataset_id, str)
            and dataset_id.strip()
            and isinstance(snapshot_id, str)
            and snapshot_id.strip()
            and type(start_inclusive_ms) is int
            and type(end_exclusive_ms) is int
            and allowed_years is not None
            and required_gate_names is not None
        ):
            raise Batch02ContractError(
                "primitive Batch02 run contract is incomplete"
            )
        try:
            identity = DatasetIdentityContract(
                dataset_id=dataset_id,
                snapshot_id=snapshot_id,
            )
            policy = OutcomeAccessPolicy(
                stage=stage,
                start_inclusive_ms=start_inclusive_ms,
                end_exclusive_ms=end_exclusive_ms,
                allowed_years=tuple(allowed_years),
            )
            gate_contract = PromotionGateContract(
                required_gate_names=tuple(required_gate_names)
            )
        except (TypeError, ValueError) as exc:
            raise Batch02ContractError(
                "primitive Batch02 run contract is invalid"
            ) from exc
    elif not typed_supplied:
        raise Batch02ContractError(
            "prepare_batch02_run requires one complete contract form"
        )

    if not isinstance(identity, DatasetIdentityContract):
        raise Batch02ContractError("invalid dataset identity contract")
    if not isinstance(policy, OutcomeAccessPolicy):
        raise Batch02ContractError("invalid outcome access policy")
    if not isinstance(gate_contract, PromotionGateContract):
        raise Batch02ContractError("invalid promotion gate contract")

    authorized = authorize_dataset_access(
        code_freeze=code_freeze,
        dataset_root=dataset_root,
        identity=identity,
        policy=policy,
    )
    run_identity = build_run_identity(
        hypothesis_id=hypothesis_id,
        stage=stage,
        code_freeze=code_freeze,
        authorized_dataset=authorized,
        gate_contract=gate_contract,
        command=list(command),
        seeds=dict(seeds),
    )
    frozen_identity = _copy_canonical_mapping(run_identity)
    return Batch02RunContext(
        code_freeze=code_freeze,
        _authorized_dataset=authorized,
        run_identity=frozen_identity,
        _run_identity_sha256=_canonical_payload_sha256(frozen_identity),
        _run_context_token=_RUN_CONTEXT_TOKEN,
        _outcome_claim=outcome_claim,
        _reservation=reservation,
    )


def _evidence_lock_path(path: Path) -> Path:
    resolved = path.resolve(strict=False)
    key = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()
    return path.parent / ".batch02_evidence_locks" / f"{key}.json"


def _normalized_artifact_token(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise Batch02ContractError(
            f"run context provenance is missing a non-empty {label}"
        )
    raw = value.strip().upper()
    token = "".join(ch if ch.isalnum() else "_" for ch in raw)
    token = "_".join(part for part in token.split("_") if part)
    if not token:
        raise Batch02ContractError(
            f"run context provenance has invalid {label}"
        )
    return token


def _expected_result_path(run_context: Batch02RunContext) -> Path:
    hypothesis = _normalized_artifact_token(
        run_context.run_identity.get("hypothesis_id"),
        label="hypothesis_id",
    )
    stage_raw = run_context.run_identity.get("stage")
    stage = _normalized_artifact_token(stage_raw, label="stage")
    stage_token = "DEV" if stage == "DEVELOPMENT" else stage

    code_freeze = getattr(run_context, "code_freeze", None)
    repo_root = getattr(code_freeze, "repo_root", None)
    if not isinstance(repo_root, Path):
        raise Batch02ContractError(
            "run context provenance is missing a canonical repository root"
        )

    filename = f"{hypothesis}_{stage_token}_RESULTS.json"
    return (
        repo_root.resolve()
        / "artifacts"
        / hypothesis.lower()
        / filename
    ).resolve(strict=False)


def _persist_batch02_result_body(
    path: Path,
    payload: Mapping[str, object],
    *,
    run_context: Batch02RunContext,
) -> str:
    """Shared persist body for historical and retained Batch02 results."""
    _reverify_run_code(run_context)
    if "provenance" in payload:
        raise Batch02ContractError(
            "payload must not supply provenance; it is bound by run_context"
        )
    if path.name == "" or path.parent.name == ".batch02_evidence_locks":
        raise Batch02ContractError("invalid Batch02 result path")

    expected_path = _expected_result_path(run_context)
    actual_path = path.resolve(strict=False)
    if actual_path != expected_path:
        raise Batch02ContractError(
            "Batch02 result path is not bound to run identity: "
            f"{actual_path} != {expected_path}"
        )

    bound_payload = dict(payload)
    bound_payload["provenance"] = _copy_canonical_mapping(run_context.run_identity)

    lock_path = _evidence_lock_path(path)
    lock_payload = {
        "artifact_kind": "batch02_logical_result_reservation",
        "logical_result_path": str(path.resolve(strict=False)),
        "run_identity_sha256": run_context._run_identity_sha256,
    }
    try:
        write_json_new(lock_path, lock_payload)
    except ArtifactExistsError as exc:
        raise ArtifactExistsError(
            f"refusing to recreate previously reserved Batch02 artifact: {path}"
        ) from exc

    # Deliberately leave the reservation in place on every failure. A partial
    # or failed evidence attempt must require forensic/operator intervention.
    return write_json_new(path, bound_payload)


def persist_batch02_result(
    path: Path,
    payload: Mapping[str, object],
    *,
    run_context: Batch02RunContext,
) -> str:
    """Persist one provenance-bound Batch02 artifact with a durable lock.

    Historical B2-01/B2-02 API. B2-03+ must use persist_batch02_retained_result
    so archival consumes a minted persist proof rather than a caller digest.
    """
    hypothesis_id = ""
    if isinstance(getattr(run_context, "run_identity", None), Mapping):
        hypothesis_id = str(run_context.run_identity.get("hypothesis_id") or "")
    if hypothesis_requires_durable_retention(hypothesis_id):
        raise Batch02ContractError(
            "B2-03+ must persist through persist_batch02_retained_result"
        )
    return _persist_batch02_result_body(path, payload, run_context=run_context)


def persist_batch02_retained_result(
    path: Path,
    payload: Mapping[str, object],
    *,
    run_context: Batch02RunContext,
) -> PersistedBatch02ResultProof:
    """Persist canonical B2-03+ bytes and mint a non-forgeable persist proof."""
    run_context.assert_minted()
    hypothesis_id = str(run_context.run_identity.get("hypothesis_id") or "")
    if not hypothesis_requires_durable_retention(hypothesis_id):
        raise Batch02ContractError(
            "historical B2-01/B2-02 must use persist_batch02_result"
        )
    claim = getattr(run_context, "_outcome_claim", None)
    reservation = getattr(run_context, "_reservation", None)
    if not isinstance(claim, DurableOutcomeAccessClaim):
        raise Batch02ContractError(
            "persist_batch02_retained_result requires a minted outcome-access claim"
        )
    if not isinstance(reservation, DurableEvidenceReservation):
        raise Batch02ContractError(
            "persist_batch02_retained_result requires a minted evidence reservation"
        )
    claim.assert_minted()
    reservation.assert_minted()
    digest = _persist_batch02_result_body(path, payload, run_context=run_context)
    artifact = path.read_bytes()
    actual_digest = hashlib.sha256(artifact).hexdigest()
    if actual_digest != digest:
        _raise_post_outcome(
            result_path=path,
            local_sha256=actual_digest,
            local_size_bytes=len(artifact),
            reservation=reservation,
            reason="persisted bytes do not match the persist digest",
        )
    try:
        return mint_persisted_result_proof(
            result_path=path,
            artifact_sha256=digest,
            artifact_size_bytes=len(artifact),
            run_identity_sha256=run_context._run_identity_sha256,
            hypothesis_id=hypothesis_id,
            code_sha=run_context.code_freeze.code_sha,
            code_tree=run_context.code_freeze.tree_oid,
            claim=claim,
            reservation=reservation,
        )
    except PostOutcomeRetentionFailure:
        raise
    except Exception as exc:
        _raise_post_outcome(
            result_path=path,
            local_sha256=digest,
            local_size_bytes=len(artifact),
            reservation=reservation,
            reason=f"persisted-result proof mint failed: {exc}",
        )
        raise  # pragma: no cover


def load_authorized_parquet_table(
    *,
    run_context: Batch02RunContext,
    columns: Sequence[str],
):
    """Read parquet only from the minted dataset bound to this exact run."""
    _reverify_run_code(run_context)
    authorized_dataset = run_context._authorized_dataset

    names = tuple(columns)
    if (
        not names
        or any(type(name) is not str or not name for name in names)
        or len(set(names)) != len(names)
    ):
        raise Batch02ContractError("columns must be unique non-empty strings")

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise Batch02ContractError(
            "pyarrow is required for authorized Batch02 parquet loading"
        ) from exc

    tables = [
        pq.read_table(path, columns=list(names))
        for path in authorized_dataset.list_monthly_partitions()
    ]
    if not tables:
        raise Batch02ContractError("authorized dataset returned no partitions")
    if len(tables) == 1:
        return tables[0]
    return pa.concat_tables(tables)


def rolling_midrank_percentile(
    series: np.ndarray,
    *,
    window: int | None = None,
    timestamps_ms: np.ndarray | None = None,
    lookback_ms: int | None = None,
) -> np.ndarray:
    """Canonical causal midrank primitive for Batch02+.

    Two mutually exclusive modes are supported:

    Fixed-count mode:
      rolling_midrank_percentile(series, window=N)

    Time-window mode:
      rolling_midrank_percentile(
          series,
          timestamps_ms=times,
          lookback_ms=duration_ms,
      )

    Both modes exclude the current record. Ties use
    (count(<x) + 0.5*count(==x)) / reference_count. Any non-finite value inside
    the active reference set makes the current score unavailable. Time-window
    timestamps must be strictly increasing; an empty time reference is
    unavailable.

    Strictly increasing -- not merely non-decreasing -- is a deliberate part of
    the contract, not an incidental restriction. A caller that can present two
    references bearing the same timestamp has no causal ordering between them,
    so "strictly before the current record" would stop being well defined at
    the boundary. Callers are expected to supply one causally separated clock
    per reference group; B2-02 does this by grouping events per lookback L,
    where the frozen 30m refractory guarantees accepted breaches are separated
    in time. Relaxing this to non-decreasing would silently admit ambiguous
    reference sets for every caller, so it is not done for convenience.

    The trailing window boundary is inclusive: a reference whose timestamp is
    exactly `lookback_ms` older than the current record is still an active
    reference, and only strictly older records are purged.
    """
    try:
        values = np.asarray(series, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise Batch02ContractError(
            "series must be coercible to a one-dimensional float array"
        ) from exc
    if values.ndim != 1:
        raise Batch02ContractError("series must be one-dimensional")

    fixed_mode = window is not None
    time_mode = timestamps_ms is not None or lookback_ms is not None
    if fixed_mode == time_mode:
        raise Batch02ContractError(
            "choose exactly one midrank mode: window or timestamps_ms+lookback_ms"
        )

    out = np.full(values.shape[0], np.nan, dtype=np.float64)
    sorted_values: list[float] = []
    queue: deque = deque()
    finite_count = 0

    if fixed_mode:
        if isinstance(window, bool) or not isinstance(window, Integral) or int(window) <= 0:
            raise Batch02ContractError("window must be a positive integer")
        fixed_window = int(window)

        for i, raw in enumerate(values):
            x = float(raw)
            if (
                len(queue) == fixed_window
                and finite_count == fixed_window
                and math.isfinite(x)
            ):
                lo = bisect_left(sorted_values, x)
                hi = bisect_right(sorted_values, x)
                out[i] = (lo + 0.5 * (hi - lo)) / fixed_window

            item: float | None = x if math.isfinite(x) else None
            queue.append(item)
            if item is not None:
                insort_right(sorted_values, item)
                finite_count += 1

            if len(queue) > fixed_window:
                old_item = queue.popleft()
                if old_item is not None:
                    pos = bisect_left(sorted_values, old_item)
                    if pos >= len(sorted_values) or sorted_values[pos] != old_item:
                        raise Batch02ContractError(
                            "rolling midrank window lost deterministic state"
                        )
                    sorted_values.pop(pos)
                    finite_count -= 1
        return out

    if (
        isinstance(lookback_ms, bool)
        or not isinstance(lookback_ms, Integral)
        or int(lookback_ms) <= 0
    ):
        raise Batch02ContractError("lookback_ms must be a positive integer")
    try:
        times = np.asarray(timestamps_ms)
    except (TypeError, ValueError) as exc:
        raise Batch02ContractError("timestamps_ms must be one-dimensional integers") from exc
    if times.ndim != 1 or len(times) != len(values) or times.dtype.kind not in "iu":
        raise Batch02ContractError(
            "timestamps_ms must be a one-dimensional integer array matching series"
        )
    times = times.astype(np.int64)
    if len(times) > 1 and np.any(times[1:] <= times[:-1]):
        raise Batch02ContractError("timestamps_ms must be strictly increasing")

    duration = int(lookback_ms)
    invalid_count = 0
    for i, raw in enumerate(values):
        current_time = int(times[i])
        cutoff = current_time - duration
        while queue and int(queue[0][0]) < cutoff:
            _, old_item = queue.popleft()
            if old_item is None:
                invalid_count -= 1
            else:
                pos = bisect_left(sorted_values, old_item)
                if pos >= len(sorted_values) or sorted_values[pos] != old_item:
                    raise Batch02ContractError(
                        "time-window midrank lost deterministic state"
                    )
                sorted_values.pop(pos)
                finite_count -= 1

        x = float(raw)
        reference_count = len(queue)
        if (
            reference_count > 0
            and invalid_count == 0
            and finite_count == reference_count
            and math.isfinite(x)
        ):
            lo = bisect_left(sorted_values, x)
            hi = bisect_right(sorted_values, x)
            out[i] = (lo + 0.5 * (hi - lo)) / reference_count

        item = x if math.isfinite(x) else None
        queue.append((current_time, item))
        if item is None:
            invalid_count += 1
        else:
            insort_right(sorted_values, item)
            finite_count += 1

    return out
