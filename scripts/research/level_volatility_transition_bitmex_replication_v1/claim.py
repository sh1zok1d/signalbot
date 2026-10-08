"""Replication routes. Frozen before any BitMEX transition is read."""

from __future__ import annotations

from scripts.research.level_volatility_transition_discovery_v1.claim import (
    excludes_zero,
    family_stability,
    side_stability,
)
from scripts.research.level_volatility_transition_discovery_v1.claim import _sign

from . import constants as K


def _estimable(item: dict, min_n: int) -> bool:
    return int(item.get("n") or 0) >= min_n and item.get("delta") is not None


def epoch_stability(full_delta, epochs: list[dict]) -> dict:
    full = _sign(full_delta)
    eligible = [item for item in epochs if _estimable(item, K.MIN_EPOCH_PAIRS)]
    limited = [item.get("name") for item in epochs if not _estimable(item, K.MIN_EPOCH_PAIRS)]
    matched = [item for item in eligible if _sign(item.get("delta")) == full and full > 0]
    ok = full > 0 and len(eligible) == len(K.EPOCHS) and len(matched) == len(K.EPOCHS)
    return {
        "pass": ok,
        "n_eligible": len(eligible),
        "n_matched": len(matched),
        "information_limited_epochs": limited,
    }


def loeo_stability(full_delta, loeo: list[dict]) -> dict:
    full = _sign(full_delta)
    checked = [item for item in loeo if _estimable(item, K.MIN_EPOCH_PAIRS)]
    if full <= 0 or len(checked) != len(K.EPOCHS):
        return {"pass": False, "n_checked": len(checked)}
    ok = all(_sign(item.get("delta")) > 0 for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def _contains(ci, value: float) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return float(ci[0]) <= value <= float(ci[1])


def decide(*, pre_gate: bool, delta, ci, ci_withheld: bool, epochs: list[dict],
           families: list[dict], sides: list[dict], loeo: list[dict], loeo_ran: bool,
           artifact: bool) -> dict:
    years = epoch_stability(delta, epochs)
    family = family_stability(families)
    side = side_stability(sides)
    leave = loeo_stability(delta, loeo) if loeo_ran else {"pass": False, "n_checked": 0}
    contains_bar = _contains(ci, K.PRACTICAL_LOG)
    contains_discovery = _contains(ci, K.DISCOVERY_POINT)
    base = {
        "years": years,
        "family": family,
        "side": side,
        "loeo": leave,
        "ci_contains_practical_bar": contains_bar,
        "ci_contains_discovery_point": contains_discovery,
    }
    if not pre_gate or ci_withheld or delta is None:
        return {
            **base,
            "routing": "REPLICATION_INFORMATION_LIMITED",
            "evidence_label": "REPLICATION_INFORMATION_LIMITED",
            "failed": ["information"],
        }
    point = float(delta)
    excludes = excludes_zero(ci)
    positive = point > 0.0
    at_bar = point >= K.PRACTICAL_LOG
    stable = years["pass"] and leave["pass"] and family["pass"] and side["pass"] and not artifact
    if positive and excludes and at_bar and stable:
        routing = "REPLICATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION"
        label = K.LABEL_REPLICATED
        failed = []
    elif positive and excludes and not at_bar:
        routing = "REPLICATION_POSITIVE_BELOW_PRACTICAL_BAR"
        label = routing
        failed = ["practical_bar"]
    elif positive and excludes and at_bar and not stable:
        routing = "REPLICATION_POSITIVE_UNSTABLE"
        label = routing
        failed = []
        if not years["pass"]:
            failed.append("epochs")
        if not leave["pass"]:
            failed.append("loeo")
        if not family["pass"]:
            failed.append("family")
        if not side["pass"]:
            failed.append("side")
        if artifact:
            failed.append("artifact")
    elif point <= 0.0 and excludes:
        routing = "REPLICATION_CONTRADICTS_DISCOVERY"
        label = routing
        failed = ["sign"]
    else:
        routing = "REPLICATION_INCONCLUSIVE"
        label = routing
        failed = ["interval"]
    return {**base, "routing": routing, "evidence_label": label, "failed": failed}
