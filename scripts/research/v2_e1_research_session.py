"""Research-only coherent read adapter for E1-RUN-001 on the legacy VPS schema.

The frozen Stage-3/4/5 analytics path expects two runtime/storage facilities that
were added after the VPS Stage-2 schema currently materialized its historical
rows:

* publication/coherence state tables; and
* exchange_instrument_history.

Neither is predictive evidence.  This adapter lets the candidate-only E1 replay
use the SAME frozen Stage-3/4/5 readers and detector code without fabricating
those runtime facilities:

* all real feature/percentile/reference-window reads delegate to
  V2CoherentReadSession, preserving its exact identity and no-lookahead guards;
* the caller owns ONE outer REPEATABLE READ, READ ONLY transaction for the whole
  candidate inventory, so every boundary sees one fixed PostgreSQL snapshot;
* historical health is represented as explicit None for every requested pair.
  Current frozen Stage-4/5 code does not consume health; None means unavailable,
  never healthy;
* instrument metadata comes from the current exchange_instruments LKG row ONLY
  when its own fetched_at <= the requested as_of=T.  Otherwise it is unavailable.
  The materialization preflight already established that all three current LKG
  rows were fetched before the E1 materialization start.

This module never imports Stage 6 and never reads future outcome paths.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from storage.v2_coherent_read_session import V2CoherentReadSession


class E1ResearchSessionError(ValueError):
    """Malformed/mismatched research read request; fail closed."""


_CURRENT_INSTRUMENT_SQL = """
SELECT exchange, symbol, market_type, exchange_instrument_id, quantity_unit,
       contract_multiplier, tick_size, price_precision, quantity_precision,
       metadata_source, fetched_at, is_stale, note
FROM exchange_instruments
WHERE exchange = $1 AND symbol = $2 AND market_type = $3
"""


def _utc(value: datetime, name: str) -> datetime:
    if type(value) is not datetime:
        raise E1ResearchSessionError(f"{name} must be a datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        raise E1ResearchSessionError(f"{name} must be timezone-aware")
    try:
        offset = value.utcoffset()
    except Exception as exc:  # pragma: no cover - defensive malformed tzinfo path
        raise E1ResearchSessionError(f"{name}.utcoffset() raised: {exc}") from exc
    if offset != timedelta(0):
        raise E1ResearchSessionError(f"{name} must be UTC, got offset={offset!r}")
    return value


class E1ResearchReadSession:
    """One T-bound research reader over a caller-owned fixed DB snapshot."""

    def __init__(
        self, conn, *, symbol: str, market_type: str, calculation_version: str,
        decision_boundary: datetime,
    ) -> None:
        self._conn = conn
        self._symbol = symbol
        self._market_type = market_type
        self._calculation_version = calculation_version
        self._decision_boundary = _utc(decision_boundary, "decision_boundary")
        # Delegate every ordinary Stage-3/5 read to the real frozen coherent
        # session.  We intentionally do NOT use Database.open_v2_coherent_read_session
        # because the legacy VPS lacks publication-state tables.
        self._delegate = V2CoherentReadSession(
            conn,
            symbol=symbol,
            market_type=market_type,
            calculation_version=calculation_version,
            decision_boundary=decision_boundary,
        )

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def _check_identity(
        self, *, symbol: str, market_type: Optional[str] = None,
        calculation_version: Optional[str] = None,
    ) -> None:
        if symbol != self._symbol:
            raise E1ResearchSessionError(
                f"session symbol={self._symbol!r}, request symbol={symbol!r}")
        if market_type is not None and market_type != self._market_type:
            raise E1ResearchSessionError(
                f"session market_type={self._market_type!r}, request={market_type!r}")
        if calculation_version is not None and calculation_version != self._calculation_version:
            raise E1ResearchSessionError(
                "request calculation_version does not match the research session")

    def _check_not_after_T(self, value: datetime, name: str) -> datetime:
        value = _utc(value, name)
        if value > self._decision_boundary:
            raise E1ResearchSessionError(
                f"{name}={value.isoformat()} is after decision T="
                f"{self._decision_boundary.isoformat()} (lookahead refused)")
        return value

    async def fetch_v2_data_health_at_cutoff(
        self, *, symbol: str, market_type: str, exchanges: Sequence[str],
        metrics: Sequence[str], cutoff_ts: datetime, calculation_version: str,
    ) -> Mapping:
        """Explicit historical unavailability, never a fabricated healthy row."""
        self._check_identity(
            symbol=symbol, market_type=market_type,
            calculation_version=calculation_version)
        self._check_not_after_T(cutoff_ts, "cutoff_ts")
        exs = tuple(exchanges)
        mets = tuple(metrics)
        if not exs or not mets:
            raise E1ResearchSessionError("health exchanges/metrics must be non-empty")
        if any(not isinstance(x, str) or not x.strip() for x in (*exs, *mets)):
            raise E1ResearchSessionError("health exchanges/metrics must be non-empty strings")
        if len(set(exs)) != len(exs) or len(set(mets)) != len(mets):
            raise E1ResearchSessionError("health exchanges/metrics must not contain duplicates")
        return MappingProxyType({(ex, metric): None for ex in exs for metric in mets})

    async def fetch_v2_instrument(
        self, *, exchange: str, symbol: str, market_type: str, as_of: datetime,
    ) -> Optional[Mapping]:
        """Guarded current-LKG fallback for the legacy schema.

        A row observed after T is NOT usable retrospectively and returns None.
        A row observed by T is projected to the history-reader shape with
        effective_from=fetched_at solely for this research adapter.  No DB row
        is inserted or mutated.
        """
        self._check_identity(symbol=symbol, market_type=market_type)
        as_of = self._check_not_after_T(as_of, "as_of")
        row = await self._conn.fetchrow(
            _CURRENT_INSTRUMENT_SQL, exchange, symbol, market_type)
        if row is None:
            return None
        d = dict(row)
        fetched_at = d.get("fetched_at")
        if fetched_at is None:
            return None
        fetched_at = _utc(fetched_at, "instrument.fetched_at")
        if fetched_at > as_of:
            return None
        return MappingProxyType({
            "exchange": d["exchange"],
            "symbol": d["symbol"],
            "market_type": d["market_type"],
            "exchange_instrument_id": d["exchange_instrument_id"],
            "quantity_unit": d["quantity_unit"],
            "contract_multiplier": d["contract_multiplier"],
            "tick_size": d["tick_size"],
            "price_precision": d["price_precision"],
            "quantity_precision": d["quantity_precision"],
            "metadata_source": d["metadata_source"],
            "observed_at": fetched_at,
            "effective_from": fetched_at,
            "effective_until": None,
            "note": d.get("note"),
        })
