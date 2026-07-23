"""Thin Stage 2.1 consensus-feature orchestration pipeline.

Composes exactly the existing consensus input adapter, the pure Level B consensus
core, and exactly one consensus-feature writer call for a single bucket. No
concrete Database import, no reads, no startup/scheduling behavior, and no
exception wrapping — adapter, core, and writer exceptions propagate unchanged.
"""
from __future__ import annotations

from typing import Mapping, Protocol, Sequence

from common.stage2_config import Stage2Config

from .consensus import compute_consensus_features
from .consensus_input_adapter import build_consensus_feature_request
from .consensus_models import ConsensusFeatureVector
from .models import ExchangeFeatureVector


class ConsensusFeatureWriter(Protocol):
    async def upsert_consensus_feature_vectors(
        self,
        rows: Sequence[ConsensusFeatureVector],
    ) -> int:
        ...


async def process_consensus_feature_bucket(
    writer: ConsensusFeatureWriter,
    stage2_config: Stage2Config,
    *,
    exchange_features: Sequence[ExchangeFeatureVector],
    expected_exchanges_by_family: Mapping[str, Sequence[str]],
    exclusion_reasons_by_family: Mapping[str, Mapping[str, str]],
) -> ConsensusFeatureVector:
    """Process exactly one consensus bucket and return the written vector.

    Order is exactly: build request -> compute -> single one-row write -> return
    the same vector. No reads, retries, sleeps, clock, or exception wrapping; if
    the adapter or compute fails the writer is never called, and a writer failure
    propagates unchanged."""
    request = build_consensus_feature_request(
        stage2_config,
        exchange_features=exchange_features,
        expected_exchanges_by_family=expected_exchanges_by_family,
        exclusion_reasons_by_family=exclusion_reasons_by_family,
    )

    vector = compute_consensus_features(request)

    await writer.upsert_consensus_feature_vectors((vector,))

    return vector
