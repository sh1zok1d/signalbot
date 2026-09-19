"""Independent source definitions. Do not merge OI timing with funding timing."""

from __future__ import annotations

from typing import Any

INSTRUMENT = "BTCUSDT"
MARKET_TYPE = "BINANCE_USD_M_FUTURES"

SOURCE_MARK_PRICE_WS = "BINANCE_UM_BTCUSDT_MARK_PRICE_WS"
SOURCE_PREMIUM_INDEX_REST = "BINANCE_UM_BTCUSDT_PREMIUM_INDEX_REST"
SOURCE_OPEN_INTEREST_REST = "BINANCE_UM_BTCUSDT_OPEN_INTEREST_REST"

DEFAULT_SOURCES: list[dict[str, Any]] = [
    {
        "source_id": SOURCE_MARK_PRICE_WS,
        "family": "mark_price_funding_next_funding",
        "transport": "websocket",
        "endpoint": "wss://fstream.binance.com/ws/btcusdt@markPrice@1s",
        "stream": "btcusdt@markPrice@1s",
        "instrument": INSTRUMENT,
    },
    {
        "source_id": SOURCE_PREMIUM_INDEX_REST,
        "family": "premium_index_basis",
        "transport": "rest",
        "endpoint": "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT",
        "stream": "GET /fapi/v1/premiumIndex",
        "poll_interval_seconds": 5,
        "instrument": INSTRUMENT,
    },
    {
        "source_id": SOURCE_OPEN_INTEREST_REST,
        "family": "open_interest",
        "transport": "rest",
        "endpoint": "https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT",
        "stream": "GET /fapi/v1/openInterest",
        "poll_interval_seconds": 5,
        "instrument": INSTRUMENT,
        "separately_timestamped": True,
        "must_not_merge_clock_with": SOURCE_MARK_PRICE_WS,
    },
]


def default_config(*, root_dir: str = "artifacts/forward_market_observability_v1") -> dict[str, Any]:
    """Config carries no authorization state.

    Collection authorization lives entirely in the external, authenticated
    collection ARM (``collection_authority.py``); nothing in this dict is
    ever read to decide whether ``collect`` may proceed. A prior revision
    hardcoded ``authoritative_collection_authorized = False`` here, but
    nothing consulted it -- the CLI refused unconditionally regardless.
    """
    return {
        "schema": "forward_market_observability_v1_config/1.1.0",
        "instrument": INSTRUMENT,
        "market_type": MARKET_TYPE,
        "venue": "binance",
        "root_dir": root_dir,
        "chunk_max_messages": 100,
        "chunk_max_bytes": 1_048_576,
        "sources": DEFAULT_SOURCES,
        "scientific_outcomes_forbidden": True,
        "m04_fwd_created": False,
        "market_06_created": False,
    }
