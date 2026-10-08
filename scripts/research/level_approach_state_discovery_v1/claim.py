"""Successor rule, routing label and claim ceiling. All cuts were fixed before outcomes."""

from __future__ import annotations

from typing import Optional

from . import constants as K


def _sign(value: Optional[float]) -> int:
    if value is None:
        return 0
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _excludes_zero(ci) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return ci[1] < 0 or ci[0] > 0


def notable(cell: dict) -> bool:
    coef = cell.get("coef")
    return coef is not None and abs(coef) >= K.PRACTICAL_SCALE and _excludes_zero(cell.get("ci95"))


def successor_ok(*, primary: dict, years: list[dict], loyo: list[dict], families: list[dict],
                 control: dict, q: Optional[float], family_share: float) -> bool:
    """A feature-outcome cell is a successor candidate only when every clause holds."""
    coef = primary.get("coef")
    sign = _sign(coef)
    if coef is None or sign == 0 or abs(coef) < K.PRACTICAL_SCALE:
        return False
    if not _excludes_zero(primary.get("ci95")):
        return False
    if q is None or q > K.FDR_Q:
        return False
    eligible = [row for row in years if row.get("n", 0) >= K.YEAR_MIN_N and row.get("coef") is not None]
    same = [row for row in eligible if _sign(row.get("coef")) == sign]
    if len(same) < K.YEAR_SIGN_MIN:
        return False
    if len(loyo) != len(K.YEARS):
        return False
    if any(_sign(row.get("coef")) != sign for row in loyo):
        return False
    if family_share > K.MAX_FAMILY_SHARE:
        return False
    fam_same = [row for row in families if row.get("n", 0) >= K.YEAR_MIN_N and _sign(row.get("coef")) == sign]
    if len(fam_same) < K.FAMILY_SIGN_MIN:
        return False
    control_coef = control.get("coef")
    if control_coef is None:
        return False
    if abs(control_coef) < K.CONTROL_HALF * abs(coef):
        return True
    ci = control.get("ci95")
    if ci is None:
        return False
    return ci[0] <= 0 <= ci[1]


def routing_status(n_candidates: int, primary: list[dict], no_touch: list[dict]) -> str:
    if n_candidates:
        return "DISCOVERY_STRUCTURE_PRESENT"
    if any(notable(cell) for cell in primary):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if any(notable(cell) for cell in no_touch):
        return "REDUNDANT_WITH_KNOWN_STATE"
    return "NO_STABLE_APPROACH_STRUCTURE"


def atlas_state(status: str) -> str:
    if status in ("NO_STABLE_APPROACH_STRUCTURE", "REDUNDANT_WITH_KNOWN_STATE"):
        return "NO_STRUCTURE"
    return "CLOSED_ON_SURFACE"


def claim_level(status: str, n: int) -> str:
    if status == "DISCOVERY_STRUCTURE_PRESENT":
        return "DISCOVERY_ONLY"
    if n >= K.L2_MIN_N:
        return "L2"
    return "not_issued"
