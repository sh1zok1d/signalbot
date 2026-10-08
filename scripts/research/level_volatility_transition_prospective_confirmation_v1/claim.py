"""Routes frozen before any prospective transition exists."""

from __future__ import annotations

from scripts.research.level_volatility_transition_discovery_v1.claim import (
    excludes_zero,
    family_stability,
    side_stability,
)

from . import constants as K


def _sign(value) -> int:
    if value is None:
        return 0
    value = float(value)
    if value > 0.0:
        return 1
    if value < 0.0:
        return -1
    return 0


def epoch_stability(epochs: list[dict]) -> dict:
    eligible = [
        item for item in epochs
        if int(item.get("n") or 0) >= K.EPOCH_MIN_PAIRS and item.get("delta") is not None
    ]
    n = len(eligible)
    if n < 3:
        return {
            "pass": False,
            "status": "TEMPORAL_STABILITY_INFORMATION_LIMITED",
            "n_eligible": n,
        }
    positive = [item for item in eligible if float(item["delta"]) > 0.0]
    opposite = [item for item in eligible if float(item["delta"]) <= 0.0]
    if n == 3:
        ok = len(positive) == 3
    elif n == 4:
        ok = len(positive) >= 3 and all(abs(float(item["delta"])) < K.PRACTICAL_LOG for item in opposite)
    elif n == 5:
        ok = len(positive) >= 4
    else:
        ok = len(positive) >= 5 and n == 6
    return {"pass": ok, "status": "ASSESSED", "n_eligible": n, "n_positive": len(positive)}


def loeo_stability(rows: list[dict]) -> dict:
    checked = [
        item for item in rows
        if int(item.get("n") or 0) >= K.LOEO_MIN_PAIRS and item.get("delta") is not None
    ]
    if not checked:
        return {"pass": False, "n_checked": 0}
    ok = all(_sign(item["delta"]) > 0 for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def ci_contains(ci, value: float) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return float(ci[0]) <= float(value) <= float(ci[1])


def decide(*, stop_met: bool, information_limited: bool, provenance_ok: bool,
           peek: bool, delta, ci, epochs: list[dict], loeo: list[dict],
           families: list[dict], sides: list[dict]) -> dict:
    """One primary route. Peek is not a market result; it blocks every pristine label."""
    if peek:
        return {
            "routing": "PROSPECTIVE_PEEK_CONTAMINATED",
            "pristine": False,
            "evidence_label": None,
            "product_integration_candidate": False,
        }
    if information_limited or not provenance_ok:
        return _limited("frozen information or provenance condition")
    temporal = epoch_stability(epochs)
    if temporal["status"] == "TEMPORAL_STABILITY_INFORMATION_LIMITED":
        return _limited("TEMPORAL_STABILITY_INFORMATION_LIMITED")
    if not stop_met:
        return _limited("frozen N and week floors were not both met")
    point = None if delta is None else float(delta)
    above = point is not None and point >= K.PRACTICAL_LOG
    positive = point is not None and point > 0.0
    nonpositive = point is not None and point <= 0.0
    separated = excludes_zero(ci)
    family = family_stability(families)
    side = side_stability(sides)
    leave = loeo_stability(loeo)
    base = {
        "pristine": True,
        "ci_contains_practical_bar": ci_contains(ci, K.PRACTICAL_LOG),
        "ci_contains_discovery_point": ci_contains(ci, K.DISCOVERY_POINT),
        "product_integration_candidate": False,
        "evidence_label": None,
        "claim_ceiling": K.CLAIM_CEILING,
    }
    if nonpositive and separated:
        base["routing"] = "PROSPECTIVE_CONFIRMATION_CONTRADICTS_HISTORY"
        return base
    if positive and separated and not above:
        base["routing"] = "PROSPECTIVE_POSITIVE_BELOW_PRACTICAL_BAR"
        return base
    if positive and separated and above:
        stable = temporal["pass"] and leave["pass"] and family["pass"] and side["pass"]
        if stable:
            base["routing"] = "PROSPECTIVE_CONFIRMATION_SUPPORTS_LEVEL_VOLATILITY_TRANSITION"
            base["evidence_label"] = K.EVIDENCE_LABEL_ON_PASS
            base["product_integration_candidate"] = True
            return base
        base["routing"] = "PROSPECTIVE_CONFIRMATION_UNSTABLE"
        return base
    base["routing"] = "PROSPECTIVE_CONFIRMATION_INCONCLUSIVE"
    return base


def _limited(reason: str) -> dict:
    return {
        "routing": "PROSPECTIVE_CONFIRMATION_INFORMATION_LIMITED",
        "reason": reason,
        "pristine": True,
        "evidence_label": None,
        "product_integration_candidate": False,
        "claim_ceiling": K.CLAIM_CEILING,
    }
