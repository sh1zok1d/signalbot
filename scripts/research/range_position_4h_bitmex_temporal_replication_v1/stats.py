"""Frozen route. Rank arithmetic is imported from the Bybit successor."""

from __future__ import annotations

from . import constants as K


def _includes_zero(interval: dict) -> bool:
    lo = interval["lo"]
    hi = interval["hi"]
    return lo is not None and hi is not None and lo <= 0.0 <= hi


def _below_zero(interval: dict) -> bool:
    return interval["hi"] is not None and interval["hi"] < 0.0


def _excludes_zero(interval: dict) -> bool:
    lo = interval["lo"]
    hi = interval["hi"]
    return lo is not None and hi is not None and (hi < 0.0 or lo > 0.0)


def assign_route(raw: float | None, raw_ci: dict, primary: float | None, primary_ci: dict) -> str:
    """Design order. A same-sign point whose interval includes 0 is not supported."""
    if (
        raw is None
        or primary is None
        or raw_ci["valid"] < K.MIN_VALID_DRAWS
        or primary_ci["valid"] < K.MIN_VALID_DRAWS
    ):
        return K.ROUTE_UNAVAILABLE
    if raw < 0.0 and primary < 0.0 and _below_zero(primary_ci):
        return K.ROUTE_SUPPORTED
    if raw < 0.0 and _below_zero(raw_ci) and _includes_zero(primary_ci):
        return K.ROUTE_RAW_ONLY
    if raw < 0.0 and primary < 0.0:
        return K.ROUTE_COMPATIBLE
    if raw >= 0.0 or (primary >= 0.0 and _excludes_zero(primary_ci)):
        return K.ROUTE_NOT
    return K.ROUTE_UNAVAILABLE
