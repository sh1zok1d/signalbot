"""Clock and map routes for a later outcome read. No market labels enter this module.

Amendment A2: a route reads family-wise intervals and Holm p-values. Marginal
intervals may be printed. They do not set a candidate.
"""

from __future__ import annotations

from . import constants as K

OPENING_WORDING_ALLOWED = False
ROUTE_NONFOUNDATION = "NONFOUNDATION_MAP_CANDIDATE_ON_UTC_00"


def interval_excludes_zero(lo: float, hi: float) -> bool:
    return hi < 0.0 or lo > 0.0


def clears_simultaneous(estimate: dict, scale: float) -> bool:
    return abs(estimate["point"]) >= scale and interval_excludes_zero(estimate["sim_lo"], estimate["sim_hi"])


def _adequate(status: str) -> bool:
    return status == "INFORMATION_ADEQUATE_FOR_LATER_OUTCOME"


def nonfoundation_candidates(rows: dict) -> list:
    """Declaration order. No sort by estimate or by p-value."""
    found = []
    for name in K.NONFOUNDATION_ORDER:
        if name not in rows:
            continue
        estimate = rows[name]
        if estimate["holm_p"] < K.FAMILY_ALPHA and abs(estimate["point"]) >= K.NONFOUNDATION_SCALE[name]:
            found.append({"row": name, "role": K.NONFOUNDATION_ROLE[name]})
    return found


def decide(clock_info: dict, foundation: dict, contrasts: dict, nonfoundation: dict) -> dict:
    """`contrasts` are δ_UTC00 − δ_hour. Pass flags use `sim_lo` / `sim_hi`.

    Map rows use `holm_p` from the non-foundation family. A missing map row is
    not a null.
    """
    out = {
        "route": "INCONCLUSIVE",
        "opening_wording_allowed": OPENING_WORDING_ALLOWED,
        "hour_adopted": None,
        "nonfoundation_candidates": [],
        "object_name": K.OBJECT_NAME,
    }
    if not _adequate(clock_info.get(K.PRIMARY_CELL, "")):
        out["route"] = "INFORMATION_LIMITED"
        return out
    out["nonfoundation_candidates"] = nonfoundation_candidates(nonfoundation)
    clock_ready = all(_adequate(clock_info.get(cell, "")) for cell in K.CLOCK_CELLS)
    primary_pass = clears_simultaneous(foundation[K.PRIMARY_CELL], K.PRACTICAL_SCALE)
    if primary_pass and not clock_ready:
        out["route"] = "CLOCK_SPECIFICITY_INFORMATION_LIMITED"
        return out
    if primary_pass:
        separated = {
            cell: clears_simultaneous(contrasts[cell], K.SPECIFICITY_SCALE)
            for cell in ("UTC_08", "UTC_12", "UTC_16")
        }
        passed = {
            cell: clears_simultaneous(foundation[cell], K.PRACTICAL_SCALE)
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
        and clears_simultaneous(foundation[cell], K.PRACTICAL_SCALE)
        for cell in ("UTC_08", "UTC_12", "UTC_16")
    )
    if other_clock_pass or not clock_ready:
        out["route"] = "INCONCLUSIVE" if other_clock_pass else "INFORMATION_LIMITED"
        return out
    if any(name not in nonfoundation for name in K.NONFOUNDATION_ORDER):
        out["route"] = "INFORMATION_LIMITED"
        return out
    if out["nonfoundation_candidates"]:
        out["route"] = ROUTE_NONFOUNDATION
        return out
    out["route"] = "NO_DETECTABLE_FROZEN_HOUR_RANGE_STRUCTURE"
    return out
