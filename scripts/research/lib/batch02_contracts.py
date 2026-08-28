"""Canonical integrity contracts for Signalbot Batch02+ runtime code.

This module is the only supported entry point for new Batch02 hypothesis
runners. Frozen/consumed H01-H05 and B2-01 code is intentionally not
rewritten: changing those implementations after outcome access would mutate
historical experimental machinery.

New B2 hypotheses must use:
- verify_batch02_code() for identity-stage exact Git proof without dataset access;
- prepare_batch02_run() only after the explicit development outcome-access gate;
- persist_batch02_result() for immutable JSON evidence;
- rolling_midrank_percentile() for the canonical strict prior-window midrank.

Repository regression tests enforce that B2-02+ does not reintroduce the
fail-open Batch01 patterns.
"""
from __future__ import annotations

import math
from bisect import bisect_left, bisect_right, insort_right
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np

from scripts.research.lib.research_harness import (
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


@dataclass(frozen=True)
class Batch02RunContext:
    """Verified code/dataset provenance required before outcome access."""

    code_freeze: VerifiedCodeFreeze
    authorized_dataset: AuthorizedDataset
    run_identity: Mapping[str, object]


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
    identity: DatasetIdentityContract,
    policy: OutcomeAccessPolicy,
    gate_contract: PromotionGateContract,
    hypothesis_id: str,
    stage: str,
    command: Sequence[str],
    seeds: Mapping[str, int],
) -> Batch02RunContext:
    """Authorize dataset bytes and build provenance for an outcome-bearing run.

    This function must be called only after the runner's explicit development
    outcome-access acknowledgement. The supplied code_freeze must already have
    been produced by verify_batch02_code(); authorize_dataset_access() rechecks
    that proof before opening the checksum-bound dataset.

    No fallback SHA, optional manifest path, or caller-supplied provenance label
    is accepted here.
    """
    if outcome_access_acknowledged is not True:
        raise Batch02ContractError(
            "development outcome access requires explicit acknowledgement"
        )
    if not isinstance(code_freeze, VerifiedCodeFreeze):
        raise Batch02ContractError(
            "code_freeze must be a VerifiedCodeFreeze from verify_batch02_code"
        )

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
    return Batch02RunContext(
        code_freeze=code_freeze,
        authorized_dataset=authorized,
        run_identity=run_identity,
    )


def persist_batch02_result(path: Path, payload: Mapping[str, object]) -> str:
    """Persist Batch02 evidence once; existing artifacts are never overwritten."""
    return write_json_new(path, dict(payload))


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

    This is the canonical Batch02+ percentile primitive. Hypothesis-specific
    copies are forbidden for B2-02+.
    """
    if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
        raise Batch02ContractError("window must be a positive integer")

    values = np.asarray(series, dtype=np.float64)
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
