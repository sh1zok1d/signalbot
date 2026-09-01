"""Canonical integrity contracts for Signalbot Batch02+ runtime code.

This module is the only supported entry point for new Batch02 hypothesis
runners. Frozen/consumed H01-H05 and B2-01 code is intentionally not
rewritten: changing those implementations after outcome access would mutate
historical experimental machinery.

New B2 hypotheses must use:
- verify_batch02_code() for identity-stage exact Git proof without dataset access;
- prepare_batch02_run() only after the explicit development outcome-access gate;
- persist_batch02_result() for immutable JSON evidence;
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

    def __post_init__(self) -> None:
        self.assert_minted()

    def assert_minted(self) -> None:
        if getattr(self, "_run_context_token", None) is not _RUN_CONTEXT_TOKEN:
            raise Batch02ContractError(
                "Batch02RunContext must be created by prepare_batch02_run"
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
            "run_context must be a Batch02RunContext from prepare_batch02_run"
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

    New B2 hypothesis code may use the primitive-only public form
    (dataset_id/snapshot_id/time window/years/gate names). The canonical
    contracts module constructs the internal Harness v1 dataclasses itself, so
    hypothesis code does not need access to internal harness types.

    The legacy typed-object form remains accepted for existing contract tests
    and trusted callers. Mixing typed objects with primitive contract fields is
    rejected to keep the authority boundary unambiguous.
    """
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


def persist_batch02_result(
    path: Path,
    payload: Mapping[str, object],
    *,
    run_context: Batch02RunContext,
) -> str:
    """Persist one provenance-bound Batch02 artifact with a durable lock.

    Provenance is injected from the minted run context; callers cannot provide
    or replace it. The complete destination is deterministically bound to the
    verified repository root plus artifacts/<hypothesis>/<hypothesis+stage>
    so one context cannot mint another hypothesis's artifact or a second
    logical result in a different directory. The Git freeze is reverified
    immediately before the logical artifact is reserved/written.
    """
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
    window: int,
) -> np.ndarray:
    """Strict causal midrank against exactly the preceding window records.

    Contract:
    - output scale is [0, 1];
    - the current record is excluded from its own reference set;
    - no future record can affect an earlier output;
    - no score exists before the full prior window is present;
    - any non-finite value in the prior window makes the score unavailable;
    - a non-finite current value makes the score unavailable;
    - ties use midrank: (count(<x) + 0.5*count(==x)) / window.

    This is the canonical Batch02+ percentile primitive. A frozen hypothesis
    that requires percentile/relative-standing semantics is expected to wire
    those semantics to this function. Source-policy checks reject alternate
    named/library APIs, but arbitrary neutral-name numerical code is not
    claimed to be semantically proven by AST linting.
    """
    if isinstance(window, bool) or not isinstance(window, Integral) or int(window) <= 0:
        raise Batch02ContractError("window must be a positive integer")
    window = int(window)

    try:
        values = np.asarray(series, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise Batch02ContractError(
            "series must be coercible to a one-dimensional float array"
        ) from exc
    if values.ndim != 1:
        raise Batch02ContractError("series must be one-dimensional")

    out = np.full(values.shape[0], np.nan, dtype=np.float64)
    sorted_values: list[float] = []
    queue: deque[float | None] = deque()
    finite_count = 0

    for i, raw in enumerate(values):
        x = float(raw)

        if (
            len(queue) == window
            and finite_count == window
            and math.isfinite(x)
        ):
            lo = bisect_left(sorted_values, x)
            hi = bisect_right(sorted_values, x)
            out[i] = (lo + 0.5 * (hi - lo)) / window

        item: float | None = x if math.isfinite(x) else None
        queue.append(item)
        if item is not None:
            insort_right(sorted_values, item)
            finite_count += 1

        if len(queue) > window:
            old = queue.popleft()
            if old is not None:
                pos = bisect_left(sorted_values, old)
                if pos >= len(sorted_values) or sorted_values[pos] != old:
                    raise Batch02ContractError(
                        "rolling midrank window lost deterministic state"
                    )
                sorted_values.pop(pos)
                finite_count -= 1

    return out
