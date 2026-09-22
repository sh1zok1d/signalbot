"""Name-only D13 exclusion lists. Frozen before any return is computed.

Membership is a function of the ticker string and the enumerated USDT set.
No price, volume rank, or return is consulted.
"""

from __future__ import annotations

import hashlib
import json
from typing import Iterable

from scripts.research.discovery_sprint_04 import common as C

# Fiat and dollar-pegged / fiat-pegged bases. Closed name list, not outcome-derived.
STABLE_FIAT_BASES = frozenset(
    {
        "AEUR",
        "ARS",
        "AUD",
        "BIDR",
        "BRL",
        "BUSD",
        "CAD",
        "CHF",
        "DAI",
        "EURI",
        "EUR",
        "EURC",
        "EURS",
        "EURT",
        "FDUSD",
        "FRAX",
        "GBP",
        "GBPT",
        "GUSD",
        "HUSD",
        "IDRT",
        "JPY",
        "KRW",
        "LUSD",
        "MIM",
        "MXN",
        "NGN",
        "NZD",
        "PAX",
        "PLN",
        "PYUSD",
        "RLUSD",
        "RUB",
        "SUSD",
        "TRY",
        "TUSD",
        "UAH",
        "USD",
        "USD1",
        "USDC",
        "USDD",
        "USDE",
        "USDP",
        "USDS",
        "USDT",
        "USDY",
        "UST",
        "USTC",
        "XUSD",
        "ZAR",
    }
)

LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def usdt_base(symbol: str) -> str | None:
    if not symbol.endswith("USDT") or len(symbol) <= 4:
        return None
    return symbol[:-4]


def is_stable_or_fiat(symbol: str) -> bool:
    base = usdt_base(symbol)
    return base is not None and base in STABLE_FIAT_BASES


def leveraged_stripped_base(symbol: str) -> str | None:
    base = usdt_base(symbol)
    if base is None:
        return None
    for suffix in LEVERAGED_SUFFIXES:
        if base.endswith(suffix) and len(base) > len(suffix):
            return base[: -len(suffix)]
    return None


def is_leveraged_token(symbol: str, enumerated: Iterable[str]) -> bool:
    stripped = leveraged_stripped_base(symbol)
    if stripped is None:
        return False
    enumerated_set = set(enumerated)
    return f"{stripped}USDT" in enumerated_set


def exclusion_reason(symbol: str, enumerated: Iterable[str]) -> str | None:
    if is_stable_or_fiat(symbol):
        return "STABLE_OR_FIAT_BASE"
    if is_leveraged_token(symbol, enumerated):
        return "LEVERAGED_TOKEN"
    return None


def excluded_symbols(enumerated: Iterable[str]) -> dict[str, str]:
    symbols = list(enumerated)
    return {sym: reason for sym in symbols if (reason := exclusion_reason(sym, symbols))}


def exclusion_digest(excluded: dict[str, str]) -> str:
    payload = json.dumps(excluded, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def freeze_exclusion_lists(enumerated: Iterable[str]) -> dict[str, object]:
    excluded = excluded_symbols(enumerated)
    stable = sorted(sym for sym, reason in excluded.items() if reason == "STABLE_OR_FIAT_BASE")
    leveraged = sorted(sym for sym, reason in excluded.items() if reason == "LEVERAGED_TOKEN")
    return {
        "STABLE_FIAT_BASES": sorted(STABLE_FIAT_BASES),
        "LEVERAGED_SUFFIXES": list(LEVERAGED_SUFFIXES),
        "STABLE_OR_FIAT_SYMBOLS": stable,
        "LEVERAGED_TOKEN_SYMBOLS": leveraged,
        "EXCLUDED_SYMBOLS": excluded,
        "EXCLUSION_LIST_DIGEST": exclusion_digest(excluded),
        "RULE": (
            "Name-only: exclude USDT symbols whose base is in STABLE_FIAT_BASES, "
            "or whose base ends with UP/DOWN/BULL/BEAR and the stripped base+USDT "
            "exists in the enumerated archive set. No return inspection."
        ),
        "CANONICALIZATION_VERSION": C.D13_CANONICALIZATION_VERSION,
    }
