"""Descriptive interpretation of one shared-context horizon (1h or 4h).

PRODUCT_FIRST_DECISION_V1 §3 row 5 and §3.1 / §3.1b. A pure function over an
already computed `beta.context.market_context` horizon: no I/O, no clock, no
episodes, no delivery decision, no mutation of its inputs and no rendered text.
The renderer owns the Russian copy (`docs/BETA_COPY_CONTRACT_V1.md`); this module
returns semantic states only.

Bands reuse the existing context cut points: "up" = rank >= `context.label_elevated`
(0.80), "down" = rank <= `context.tail_display_max` (0.20), "flat" in between; the
same bands apply to price, OI change and taker delta. «сжатие» = range rank <= 0.20
and OI rank > 0.20. Labels describe what happened; nothing here says what follows,
and the cut points are never tuned against forward outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

INTERPRETATION_VERSION = "BETA_INTERPRETATION_V1"

# Inferred states: the renderer prefixes them with «похоже на …».
SHORT_EXIT = "SHORT_EXIT"                    # похоже на выход шортов
LONG_BUILDUP = "LONG_BUILDUP"                # похоже на рост с новыми лонгами
SHORT_BUILDUP = "SHORT_BUILDUP"              # похоже на снижение с новыми шортами
LONG_EXIT = "LONG_EXIT"                      # похоже на выход лонгов
LONG_WIPEOUT = "LONG_WIPEOUT"                # похоже на вынос лонгов
SHORT_WIPEOUT = "SHORT_WIPEOUT"              # похоже на вынос шортов
# Descriptive states (no cause is claimed).
COMPRESSION = "COMPRESSION"                  # сжатие
COMPRESSION_OI_NA = "COMPRESSION_OI_NA"      # сжатие, OI н/д
NORMAL = "NORMAL"                            # обычное состояние
# Factual fallbacks: taker flow does not confirm the price/OI row.
RISE_OI_DOWN = "RISE_OI_DOWN"                # рост при снижении OI
RISE_OI_UP = "RISE_OI_UP"                    # рост с ростом OI
DROP_OI_UP = "DROP_OI_UP"                    # снижение с ростом OI
DROP_OI_DOWN = "DROP_OI_DOWN"                # снижение при снижении OI
FACTS_ONLY = "FACTS_ONLY"                    # OI from < 2 venues or taker delta missing: facts only
VENUES_DIVERGE = "VENUES_DIVERGE"            # биржи расходятся
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"  # мало истории
DATA_INCOMPLETE = "DATA_INCOMPLETE"          # данные неполные

INFERRED_STATES = frozenset({SHORT_EXIT, LONG_BUILDUP, SHORT_BUILDUP, LONG_EXIT, LONG_WIPEOUT,
                             SHORT_WIPEOUT})
STATES = frozenset(INFERRED_STATES | {COMPRESSION, COMPRESSION_OI_NA, NORMAL, RISE_OI_DOWN, RISE_OI_UP,
                                      DROP_OI_UP, DROP_OI_DOWN, FACTS_ONLY, VENUES_DIVERGE,
                                      INSUFFICIENT_HISTORY, DATA_INCOMPLETE})

UP, DOWN, FLAT = "UP", "DOWN", "FLAT"
MIN_AGREEING_VENUES = 2

PRICE = "price_move_pct_median"
RANGE = "range_width_pct_median"
OI = "oi_change_pct_median"
TAKER = "taker_delta_notional_usd_sum"

# (price band, OI band) -> (label when taker confirms, confirming taker band, factual fallback)
_ROWS = {
    (UP, DOWN): (SHORT_EXIT, UP, RISE_OI_DOWN),
    (UP, UP): (LONG_BUILDUP, UP, RISE_OI_UP),
    (DOWN, UP): (SHORT_BUILDUP, DOWN, DROP_OI_UP),
    (DOWN, DOWN): (LONG_EXIT, DOWN, DROP_OI_DOWN),
}


@dataclass(frozen=True)
class Cuts:
    up: float      # band "up" at rank >= up
    down: float    # band "down" at rank <= down; compression at range rank <= down


def cuts_from_config(cfg) -> Cuts:
    c = cfg.section("context")
    return Cuts(up=float(c["label_elevated"]), down=float(c["tail_display_max"]))


@dataclass(frozen=True)
class Interpretation:
    version: str
    horizon: str
    state: str
    inferred: bool                 # True -> rendered with «похоже на …»
    price: Optional[str]           # UP / DOWN / FLAT, None when not evaluated
    oi: Optional[str]
    taker: Optional[str]
    venues_agreeing: Optional[int]  # venues whose price sign equals the consensus sign
    liquidation_confirmed: bool
    missing: tuple                 # inputs that were unavailable: "price", "range", "oi", "taker"


def _band(rank: float, cuts: Cuts) -> str:
    if rank >= cuts.up:
        return UP
    if rank <= cuts.down:
        return DOWN
    return FLAT


def _sign(x: float) -> int:
    return 0 if x == 0 else (1 if x > 0 else -1)


def interpret(horizon_context: Optional[Mapping[str, Any]], *, horizon: str, cuts: Cuts,
              liquidation_stress_long: bool = False, liquidation_stress_short: bool = False) -> Interpretation:
    """Semantic state of one horizon. `liquidation_stress_long/short` say whether an
    existing LIQUIDATION_STRESS_LONG/SHORT detector episode overlaps the window (the
    caller reads the existing episodes; this function never creates one)."""
    def result(state, *, price=None, oi=None, taker=None, agreeing=None, liq=False, missing=()):
        return Interpretation(version=INTERPRETATION_VERSION, horizon=horizon, state=state,
                              inferred=state in INFERRED_STATES, price=price, oi=oi, taker=taker,
                              venues_agreeing=agreeing, liquidation_confirmed=liq, missing=tuple(missing))

    if not horizon_context:
        return result(DATA_INCOMPLETE, missing=("price", "range", "oi", "taker"))
    pct = horizon_context.get("percentiles") or {}
    value = {m: horizon_context.get(m) for m in (PRICE, RANGE, OI, TAKER)}
    missing = [name for name, m in (("price", PRICE), ("range", RANGE), ("oi", OI), ("taker", TAKER))
               if value[m] is None]
    if value[PRICE] is None or value[RANGE] is None:
        return result(DATA_INCOMPLETE, missing=missing)

    # Venue agreement on the sign of the window's price move (consensus = median).
    venue_moves = [v for v in (horizon_context.get("venue_price_move_pct") or {}).values() if v is not None]
    consensus = _sign(value[PRICE])
    agreeing = sum(1 for v in venue_moves if _sign(v) == consensus)
    if agreeing < MIN_AGREEING_VENUES:
        return result(VENUES_DIVERGE, agreeing=agreeing, missing=missing)

    # Every present value must have a mature rank.
    for m in (PRICE, RANGE, OI, TAKER):
        if value[m] is None:
            continue
        p = pct.get(m) or {}
        if p.get("rank") is None or p.get("tier") != "mature":
            return result(INSUFFICIENT_HISTORY, agreeing=agreeing, missing=missing)

    price = _band(pct[PRICE]["rank"], cuts)
    oi = None if value[OI] is None else _band(pct[OI]["rank"], cuts)
    taker = None if value[TAKER] is None else _band(pct[TAKER]["rank"], cuts)
    bands = dict(price=price, oi=oi, taker=taker, agreeing=agreeing, missing=missing)

    if price in (UP, DOWN):
        if oi is None or taker is None:
            return result(FACTS_ONLY, **bands)
        row = _ROWS.get((price, oi))
        if row is not None:
            label, confirming, fallback = row
            if taker != confirming:
                return result(fallback, **bands)
            if label == LONG_EXIT and liquidation_stress_long:
                return result(LONG_WIPEOUT, liq=True, **bands)
            if label == SHORT_EXIT and liquidation_stress_short:
                return result(SHORT_WIPEOUT, liq=True, **bands)
            return result(label, **bands)

    if pct[RANGE]["rank"] <= cuts.down:
        if oi is None:
            return result(COMPRESSION_OI_NA, **bands)
        if pct[OI]["rank"] > cuts.down:
            return result(COMPRESSION, **bands)
    return result(NORMAL, **bands)
