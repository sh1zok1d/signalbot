"""
Private shared field-validation helpers for the V2 identity/persistence
value objects (`events.py`'s `V2EpisodeEvent`, `provenance.py`'s
`V2EventProvenance`). NOT public API — this module is never imported
outside `analytics/forecasting_v2/`, and nothing here is re-exported by
`analytics/forecasting_v2/__init__.py`.

Exists only because Multi-model Framework PR 3 introduces a second frozen
value object that needs several of the exact same field-shape checks
`V2EpisodeEvent` (PR 2) already enforces: non-blank identifiers, enum
membership, the initial V2 `symbol`/`market_type` scope pin, and the
shared Stage 2 `feature_schema_version`/`calculation_version`/`config_hash`
provenance shapes. Duplicating those checks verbatim in a second module
would let them silently drift apart (e.g. one module's hex-length regex
getting "fixed" without the other); this module is the single place they
are defined, per docs/V2_CORRECTNESS_ACCEPTANCE_CONTRACT.md §3's own
"single source of truth" framing for identity.

Each helper takes the CALLER'S OWN exception class and raises that,
never a shared/generic type — `V2EpisodeEvent` keeps raising
`V2EventInputError`, `V2EventProvenance` keeps raising
`V2ProvenanceError`, and neither has to catch-and-rewrap a foreign
exception type. This mirrors the existing wrap-at-the-call-site pattern
`analytics/forecasting_v2/identity.py` and `events.py` already use for
`common.v2_config.validate_rules_version`'s `V2ConfigError`.

Deliberately NOT imported from `analytics/forecasting/models.py` (V1-owned)
or from `common/v2_config.py` beyond what those callers already import
themselves — this module holds only the field-shape checks that are
identical across the two V2 value objects, nothing V1-specific and nothing
config-loading.

Pure only: no I/O, no clock, no randomness.
"""
from __future__ import annotations

import re
from typing import Any

# ---- initial V2 product scope (V2_PRODUCT_CONTRACT.md §1: "Symbol:
# BTCUSDT... USDT perpetual") — deliberately NOT imported from
# analytics/forecasting/models.py's SUPPORTED_SYMBOL/SUPPORTED_MARKET_TYPE:
# V1's shadow scope and V2's product scope are independently declared and
# must be able to diverge without one module's constant coupling to the
# other's. Re-exported by events.py (and importable directly here by
# provenance.py) so both V2 value objects pin the identical values.
SUPPORTED_SYMBOL = "BTCUSDT"
SUPPORTED_MARKET_TYPE = "perp"

# Shared Stage 2 identity formats (common/versioning.py): calculation_version
# is sha256(...)[:16] hex, config_hash is a full sha256 hex digest. Same
# convention analytics/forecasting/models.py already validates against for
# V1 — re-stated locally (not imported) so V2's own identity validation does
# not depend on a V1-owned module.
HEX16 = re.compile(r"[0-9a-f]{16}")
HEX64 = re.compile(r"[0-9a-f]{64}")


def nonblank(value: Any, name: str, error_cls: type) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error_cls(f"{name} must be a non-empty string")
    return value


def one_of(value: Any, name: str, allowed: tuple, error_cls: type) -> Any:
    if value not in allowed:
        raise error_cls(f"{name} must be one of {allowed}, got {value!r}")
    return value


def validate_symbol(value: Any, error_cls: type) -> str:
    if value != SUPPORTED_SYMBOL:
        raise error_cls(
            f"unsupported symbol {value!r} (V2 initial scope is {SUPPORTED_SYMBOL!r})")
    return value


def validate_market_type(value: Any, error_cls: type) -> str:
    if value != SUPPORTED_MARKET_TYPE:
        raise error_cls(
            f"unsupported market_type {value!r} (V2 initial scope is {SUPPORTED_MARKET_TYPE!r})")
    return value


def validate_feature_schema_version(value: Any, error_cls: type) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise error_cls("feature_schema_version must be an int > 0")
    return value


def validate_calculation_version(value: Any, error_cls: type) -> str:
    if not isinstance(value, str) or not HEX16.fullmatch(value):
        raise error_cls("calculation_version must be exactly 16 lowercase hex chars")
    return value


def validate_config_hash(value: Any, error_cls: type) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise error_cls("config_hash must be exactly 64 lowercase hex chars")
    return value
