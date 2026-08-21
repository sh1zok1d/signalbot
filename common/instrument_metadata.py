"""
Instrument metadata foundation (decision J): fetch-and-store ctVal/tick with
last-known-good fallback, a mismatch alarm, and fail-closed behavior.

NOT wired to main.py or any live worker in this PR — this is the model + pure
parsers + a mockable fetch wrapper only.

Unit semantics (never guessed, never defaulted):
  * binance / bybit : quantity_unit = 'base'  (no contract multiplier needed)
  * okx             : quantity_unit = 'contracts', contract_multiplier = ctVal
An OKX contracts instrument WITHOUT a usable multiplier is FAIL-CLOSED: it is
ineligible for volume/taker notional consensus (excluded, NOT assumed base).
A missing multiplier never degrades price_structure (percentages from OHLC).

The OKX instrument id comes from the shared common.symbol_mapper — there is no
second, independent OKX mapping here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional

from common.symbol_mapper import to_exchange_symbol

SUPPORTED_EXCHANGES = ("binance", "bybit", "okx")
SUPPORTED_MARKET_TYPES = ("perp",)

# Critical fields whose change between a stored LKG and a refetch raises the
# mismatch alarm (must be deliberately accepted -- storage.db.Database.
# upsert_exchange_instrument's accept_mismatch=True). V2-H2c (tech-lead
# review 4990482334, findings 7/8) first audited the prior claim here that
# this "forks calculation_version": no such mechanism existed anywhere in
# this repository -- that was aspirational only. A first attempt (an
# `accepted_code_version` label recorded alongside the acceptance) was
# then found by tech-lead review 4991738511 to prove only that two STORED
# LABELS differed, never that the live Stage-2 feature-assembly path was
# mechanically prevented from consuming NEW critical metadata under an OLD
# `calculation_version` -- i.e. still not a real fork. The REAL, end-to-end
# mechanism now lives at THREE connected points: (1)
# Database.upsert_exchange_instrument's accept_mismatch=True path requires
# an explicit `target_metadata_revision` strictly greater than the current
# value of the ONE global `stage2_instrument_metadata_state.
# required_revision` row, and atomically bumps it; (2) every live feature
# computation's raw-bundle read
# (storage/stage2_readers.py::read_exchange_feature_raw_bundle) reads that
# SAME global row; (3) analytics/feature_engine/input_adapter.py::
# assemble_exchange_feature_request FAILS CLOSED the instant the resolved
# Stage2Config's OWN `defaults.instrument_metadata_revision` (part of
# config_hash, hence of calculation_version) stops matching it -- so a
# critical acceptance on ANY venue immediately blocks feature persistence
# on EVERY venue/symbol until an operator explicitly updates
# config/stage2.yaml to adopt the new revision, which is what actually
# forks calculation_version. See storage/stage2_schema.sql's
# stage2_instrument_metadata_state table comment for the full mechanism
# and tests/analytics/test_stage2_metadata_revision_fork.py for the
# executable end-to-end proof.
CRITICAL_FIELDS = ("exchange_instrument_id", "quantity_unit",
                   "contract_multiplier", "tick_size")


class InstrumentMetadataError(RuntimeError):
    """Base for instrument-metadata failures."""


class MalformedMetadataError(InstrumentMetadataError):
    """Payload missing required fields or carrying invalid numeric values."""


class MetadataUnavailableError(InstrumentMetadataError):
    """Fetch failed and there is no last-known-good to fall back to."""


class FailClosedError(InstrumentMetadataError):
    """A contracts instrument has no usable contract_multiplier — the venue is
    excluded from notional consensus rather than assumed to be base."""


class MetadataMismatchError(InstrumentMetadataError):
    """A refetched value differs from the stored last-known-good on a critical
    field. Carries old/new so a caller can raise an alarm; the LKG is NOT
    overwritten automatically (deliberate acceptance required)."""

    def __init__(self, old: "InstrumentMetadata", new: "InstrumentMetadata",
                 fields: list[str]):
        self.old = old
        self.new = new
        self.fields = fields
        super().__init__(f"instrument metadata mismatch on {fields} for "
                         f"{new.exchange}/{new.symbol}/{new.market_type}")


@dataclass(frozen=True)
class InstrumentMetadata:
    exchange: str
    symbol: str                      # canonical, e.g. BTCUSDT
    market_type: str
    exchange_instrument_id: str      # venue-native id
    quantity_unit: Optional[str]     # 'base' | 'contracts'
    contract_multiplier: Optional[float]
    tick_size: Optional[float]
    price_precision: Optional[int]
    quantity_precision: Optional[int]
    metadata_source: str             # 'exchange_api' | 'declared_fallback' | 'manual'
    fetched_at: Optional[datetime]
    is_stale: bool
    note: str = ""


# ---- validation helpers ----------------------------------------------------
def _finite_positive(value: Any, field: str, ctx: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise MalformedMetadataError(f"{ctx}: {field}={value!r} is not numeric") from None
    if not math.isfinite(f) or f <= 0:
        raise MalformedMetadataError(f"{ctx}: {field}={value!r} must be finite and > 0")
    return f


def _opt_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---- pure parsers (separately testable; no network) ------------------------
def parse_binance(payload: dict, symbol: str, market_type: str = "perp",
                  *, fetched_at: Optional[datetime] = None) -> InstrumentMetadata:
    """Binance USDT-M futures exchangeInfo payload -> metadata (base unit)."""
    rows = payload.get("symbols") or []
    row = next((r for r in rows if r.get("symbol") == symbol), None)
    if row is None:
        raise MalformedMetadataError(f"binance: symbol {symbol!r} not in exchangeInfo")
    tick = None
    for f in row.get("filters", []):
        if f.get("filterType") == "PRICE_FILTER":
            tick = _finite_positive(f.get("tickSize"), "tickSize", "binance")
            break
    if tick is None:
        raise MalformedMetadataError("binance: no PRICE_FILTER.tickSize")
    return InstrumentMetadata(
        exchange="binance", symbol=symbol, market_type=market_type,
        exchange_instrument_id=symbol,           # binance uses the canonical id
        quantity_unit="base", contract_multiplier=None,
        tick_size=tick,
        price_precision=_opt_int(row.get("pricePrecision")),
        quantity_precision=_opt_int(row.get("quantityPrecision")),
        metadata_source="exchange_api", fetched_at=fetched_at or _now(),
        is_stale=False,
    )


def parse_bybit(payload: dict, symbol: str, market_type: str = "perp",
                *, fetched_at: Optional[datetime] = None) -> InstrumentMetadata:
    """Bybit v5 linear instruments-info payload -> metadata (base unit)."""
    rows = (payload.get("result") or {}).get("list") or []
    row = next((r for r in rows if r.get("symbol") == symbol), None)
    if row is None:
        raise MalformedMetadataError(f"bybit: symbol {symbol!r} not in instruments-info")
    tick = _finite_positive((row.get("priceFilter") or {}).get("tickSize"),
                            "tickSize", "bybit")
    qty_step = (row.get("lotSizeFilter") or {}).get("qtyStep")
    return InstrumentMetadata(
        exchange="bybit", symbol=symbol, market_type=market_type,
        exchange_instrument_id=symbol,
        quantity_unit="base", contract_multiplier=None,
        tick_size=tick,
        price_precision=None,
        quantity_precision=_opt_int(qty_step) if qty_step and str(qty_step).isdigit() else None,
        metadata_source="exchange_api", fetched_at=fetched_at or _now(),
        is_stale=False,
    )


def parse_okx(payload: dict, symbol: str, market_type: str = "perp",
              *, fetched_at: Optional[datetime] = None) -> InstrumentMetadata:
    """OKX public instruments payload -> metadata (contracts unit).

    Resolves the venue instrument id via the SHARED symbol_mapper and requires
    a usable ctVal; a missing/invalid ctVal is FAIL-CLOSED (never defaulted to
    1.0, never treated as base).
    """
    inst_id = to_exchange_symbol("okx", symbol, market_type)
    rows = payload.get("data") or []
    row = next((r for r in rows if r.get("instId") == inst_id), None)
    if row is None:
        raise MalformedMetadataError(f"okx: instId {inst_id!r} not in instruments payload")
    tick = _finite_positive(row.get("tickSz"), "tickSz", "okx")
    ct_val_raw = row.get("ctVal")
    if ct_val_raw is None or str(ct_val_raw) == "":
        raise FailClosedError(
            f"okx {inst_id}: missing ctVal — contracts instrument has no usable "
            f"multiplier, excluded from notional consensus (not assumed base)")
    try:
        multiplier = _finite_positive(ct_val_raw, "ctVal", "okx")
    except MalformedMetadataError as exc:
        raise FailClosedError(f"okx {inst_id}: {exc}") from None
    return InstrumentMetadata(
        exchange="okx", symbol=symbol, market_type=market_type,
        exchange_instrument_id=inst_id,
        quantity_unit="contracts", contract_multiplier=multiplier,
        tick_size=tick,
        price_precision=None, quantity_precision=None,
        metadata_source="exchange_api", fetched_at=fetched_at or _now(),
        is_stale=False,
    )


_PARSERS: dict[str, Callable[..., InstrumentMetadata]] = {
    "binance": parse_binance,
    "bybit": parse_bybit,
    "okx": parse_okx,
}

# Instruments endpoint per exchange (used by the fetch wrapper).
_ENDPOINTS = {
    "binance": ("https://fapi.binance.com/fapi/v1/exchangeInfo", {}),
    "bybit": ("https://api.bybit.com/v5/market/instruments-info",
              {"category": "linear"}),
    "okx": ("https://www.okx.com/api/v5/public/instruments",
            {"instType": "SWAP"}),
}

# (url, params) -> parsed JSON dict. Injected so unit tests never hit the network.
JsonFetcher = Callable[[str, dict], Awaitable[dict]]


def is_notional_eligible(meta: InstrumentMetadata) -> bool:
    """A base-unit instrument is always eligible; a contracts instrument is
    eligible only with a usable (finite, positive) contract_multiplier."""
    if meta.quantity_unit == "base":
        return True
    if meta.quantity_unit == "contracts":
        m = meta.contract_multiplier
        return m is not None and math.isfinite(m) and m > 0
    return False


def _critical_diff(old: InstrumentMetadata, new: InstrumentMetadata) -> list[str]:
    return [f for f in CRITICAL_FIELDS if getattr(old, f) != getattr(new, f)]


async def fetch_instrument_metadata(
    exchange: str,
    symbol: str,
    fetch_json: JsonFetcher,
    *,
    market_type: str = "perp",
    lkg: Optional[InstrumentMetadata] = None,
    fetched_at: Optional[datetime] = None,
) -> InstrumentMetadata:
    """Fetch fresh metadata (outside any hot path).

    * success, no LKG or no critical change -> fresh metadata (is_stale=False)
    * success, critical change vs LKG        -> MetadataMismatchError (LKG kept)
    * network/fetch failure, LKG present     -> LKG returned, is_stale=True
    * network/fetch failure, no LKG          -> MetadataUnavailableError
    * malformed payload                      -> MalformedMetadataError (explicit)
    * OKX contracts w/o usable multiplier    -> FailClosedError (explicit)
    """
    if exchange not in SUPPORTED_EXCHANGES:
        raise InstrumentMetadataError(f"unsupported exchange {exchange!r}")
    if market_type not in SUPPORTED_MARKET_TYPES:
        raise InstrumentMetadataError(f"unsupported market_type {market_type!r}")

    url, base_params = _ENDPOINTS[exchange]
    params = dict(base_params)
    if exchange == "okx":
        params["instId"] = to_exchange_symbol("okx", symbol, market_type)
    else:
        params["symbol"] = symbol

    try:
        payload = await fetch_json(url, params)
    except Exception as exc:  # noqa: BLE001 - network/transport failure
        if lkg is not None:
            return replace(lkg, is_stale=True,
                           note=f"stale last-known-good (refetch failed: {exc})")
        raise MetadataUnavailableError(
            f"{exchange}/{symbol}: fetch failed and no last-known-good ({exc})") from exc

    # Parse errors (malformed / fail-closed) are explicit and are NOT masked by
    # LKG — a changed/broken payload structure needs attention.
    fresh = _PARSERS[exchange](payload, symbol, market_type, fetched_at=fetched_at)

    if lkg is not None:
        diff = _critical_diff(lkg, fresh)
        if diff:
            # Do NOT overwrite the LKG; surface old/new for a deliberate decision.
            raise MetadataMismatchError(old=lkg, new=fresh, fields=diff)
    return fresh
