"""Thin Stage 2.1 exchange-feature orchestration pipeline.

Composes exactly one raw reader call, the existing input adapter, the pure
per-exchange feature core, and exactly one exchange-feature writer call for a
single exchange/symbol/market_type/timeframe/bucket. No concrete Database import
or startup/scheduling behavior lives here.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from common.stage2_config import Stage2Config

from .exchange_features import compute_exchange_features
from .input_adapter import RawBundleReader, load_exchange_feature_request
from .models import ExchangeFeatureVector


class ExchangeFeatureWriter(Protocol):
    async def upsert_exchange_feature_vectors(
        self,
        rows: Sequence[ExchangeFeatureVector],
    ) -> int:
        ...


async def process_exchange_feature_bucket(
    reader: RawBundleReader,
    writer: ExchangeFeatureWriter,
    stage2_config: Stage2Config,
    *,
    exchange: str,
    symbol: str,
    market_type: str,
    timeframe: str,
    bucket_ts: datetime,
    code_version: str,
    liquidation_feed_available: bool,
) -> ExchangeFeatureVector:
    """Process exactly one exchange feature bucket and return the written vector."""
    request = await load_exchange_feature_request(
        reader,
        stage2_config,
        exchange=exchange,
        symbol=symbol,
        market_type=market_type,
        timeframe=timeframe,
        bucket_ts=bucket_ts,
        code_version=code_version,
        liquidation_feed_available=liquidation_feed_available,
    )

    vector = compute_exchange_features(request)

    await writer.upsert_exchange_feature_vectors((vector,))

    return vector
