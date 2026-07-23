"""Thin Stage 2.1 consensus-feature orchestration pipeline."""
from __future__ import annotations

from datetime import datetime
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
    symbol: str,
    market_type: str,
    timeframe: str,
    bucket_ts: datetime,
    code_version: str,
) -> ConsensusFeatureVector:
    """Process exactly one consensus bucket and return the written vector."""
    request = build_consensus_feature_request(
        stage2_config,
        exchange_features=exchange_features,
        expected_exchanges_by_family=expected_exchanges_by_family,
        exclusion_reasons_by_family=exclusion_reasons_by_family,
        symbol=symbol,
        market_type=market_type,
        timeframe=timeframe,
        bucket_ts=bucket_ts,
        code_version=code_version,
    )

    vector = compute_consensus_features(request)

    await writer.upsert_consensus_feature_vectors((vector,))

    return vector
