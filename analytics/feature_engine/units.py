"""
Unit-safe notional normalization (pure). BAR_CLOSE approximation.

Per single 1m bar:
    quantity_unit == 'base'      -> notional_usd = quantity * close
    quantity_unit == 'contracts' -> notional_usd = quantity * contract_multiplier * close

Rules:
  * conversion is per-bar, values are summed by the caller (NEVER
    sum(quantity) * last_close);
  * base and contracts are never mixed;
  * contracts without a usable contract_multiplier is FAIL-CLOSED (never 1.0);
  * unknown quantity_unit raises;
  * quantity must be finite and >= 0 (negative rejected, zero allowed);
  * close and multiplier must be finite and > 0; NaN/Infinity rejected.

Reuses the Stage 2 InstrumentMetadata contract from common.instrument_metadata
(no second metadata model, no second OKX mapper).
"""
from __future__ import annotations

import math
from typing import Optional

from common.instrument_metadata import (
    FailClosedError, InstrumentMetadata, is_notional_eligible,
)


class UnitError(ValueError):
    """Invalid unit/quantity/price for notional normalization."""


def _require_quantity(quantity) -> float:
    if not isinstance(quantity, (int, float)) or isinstance(quantity, bool):
        raise UnitError(f"quantity must be a number, got {type(quantity).__name__}")
    q = float(quantity)
    if not math.isfinite(q):
        raise UnitError(f"quantity must be finite, got {quantity!r}")
    if q < 0:
        raise UnitError(f"negative quantity not allowed: {quantity!r}")
    return q


def _require_positive(value, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise UnitError(f"{name} must be a number, got {type(value).__name__}")
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise UnitError(f"{name} must be finite and > 0, got {value!r}")
    return v


def notional_usd_per_bar(quantity, close, quantity_unit: str,
                         contract_multiplier: Optional[float] = None) -> float:
    """Notional USD for one bar's quantity under BAR_CLOSE. Strict/fail-closed."""
    q = _require_quantity(quantity)
    c = _require_positive(close, "close")
    if quantity_unit == "base":
        return q * c
    if quantity_unit == "contracts":
        if contract_multiplier is None:
            raise FailClosedError(
                "contracts quantity has no contract_multiplier — fail closed "
                "(never defaulted to 1.0, never treated as base)")
        m = _require_positive(contract_multiplier, "contract_multiplier")
        return q * m * c
    raise UnitError(f"unknown quantity_unit {quantity_unit!r} (expected 'base'|'contracts')")


def metadata_notional_eligible(metadata: Optional[InstrumentMetadata]) -> bool:
    """True iff `metadata` exists and can produce a comparable USD notional.
    A base instrument is always eligible; a contracts instrument only with a
    usable multiplier; None metadata is never eligible."""
    return metadata is not None and is_notional_eligible(metadata)


def bar_notional_from_metadata(quantity, close,
                               metadata: InstrumentMetadata) -> float:
    """Notional for one bar using the instrument's quantity_unit + multiplier."""
    return notional_usd_per_bar(
        quantity, close, metadata.quantity_unit, metadata.contract_multiplier)
