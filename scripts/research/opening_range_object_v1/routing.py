"""Clock and map routes for a later outcome read. No market labels enter this module.

Difference in significance is not a difference. A cell is separated from UTC_00 only
when the direct contrast clears the frozen scale and its interval excludes 0.
"""

from __future__ import annotations

from . import constants as K

OPENING_WORDING_ALLOWED = False


def interval_excludes_zero(lo: float, hi: float) -> bool:
    return hi < 0.0 or lo > 0.0


def clears(point: float, lo: float, hi: float, scale: float) -> bool:
    return abs(point) >= scale and interval_excludes_zero(lo, hi)


def _adequate(status: str) -> bool:
    return status == "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"


def decide(clock_info: dict, foundation: dict, contrasts: dict, orthogonal: dict) -> dict:
    """`contrasts` are δ_UTC00 − δ_hour for UTC_08, UTC_12, UTC_16.

    `orthogonal` values are {point, lo, hi, scale}. Missing orthogonal estimates
    are not treated as nulls.
    """
    out = {
        "route": "INCONCLUSIVE",
        "opening_wording_allowed": OPENING_WORDING_ALLOWED,
        "hour_adopted": None,
        "orthogonal_candidates": [],
        "object_name": K.OBJECT_NAME,
    }
    if not _adequate(clock_info.get(K.PRIMARY_CELL, "")):
        out["route"] = "INFORMATION_LIMITED"
        return out
    ortho_pass = [
        name for name, est in orthogonal.items()
        if clears(est["point"], est["lo"], est["hi"], est["scale"])
    ]
    out["orthogonal_candidates"] = ortho_pass
    clock_ready = all(_adequate(clock_info.get(cell, "")) for cell in K.CLOCK_CELLS)
    primary = foundation[K.PRIMARY_CELL]
    primary_pass = clears(primary["point"], primary["lo"], primary["hi"], K.PRACTICAL_SCALE)
    if primary_pass and not clock_ready:
        out["route"] = "CLOCK_SPECIFICITY_INFORMATION_LIMITED"
        return out
    if primary_pass:
        separated = {
            cell: clears(contrasts[cell]["point"], contrasts[cell]["lo"], contrasts[cell]["hi"], K.SPECIFICITY_SCALE)
            for cell in ("UTC_08", "UTC_12", "UTC_16")
        }
        passed = {
            cell: clears(foundation[cell]["point"], foundation[cell]["lo"], foundation[cell]["hi"], K.PRACTICAL_SCALE)
            for cell in K.CLOCK_CELLS
        }
        if separated["UTC_08"] and separated["UTC_16"] and separated["UTC_12"]:
            out["route"] = "UTC_DAY_BOUNDARY_RANGE_CANDIDATE"
            return out
        funding_similar = (
            passed["UTC_08"] and passed["UTC_16"]
            and not separated["UTC_08"] and not separated["UTC_16"]
        )
        noon_similar = passed["UTC_12"] and not separated["UTC_12"]
        if funding_similar and noon_similar:
            out["route"] = "GENERIC_FROZEN_HOUR_RANGE_STRUCTURE"
            return out
        if funding_similar:
            out["route"] = "FUNDING_ANCHOR_OR_PERIODIC_RANGE_STRUCTURE"
            return out
        out["route"] = "INCONCLUSIVE"
        return out
    other_clock_pass = any(
        _adequate(clock_info.get(cell, ""))
        and clears(foundation[cell]["point"], foundation[cell]["lo"], foundation[cell]["hi"], K.PRACTICAL_SCALE)
        for cell in ("UTC_08", "UTC_12", "UTC_16")
    )
    if other_clock_pass or not clock_ready:
        out["route"] = "INCONCLUSIVE" if other_clock_pass else "INFORMATION_LIMITED"
        return out
    if ortho_pass:
        out["route"] = "ORTHOGONAL_CANDIDATE_ON_UTC_00"
        return out
    out["route"] = "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"
    return out
