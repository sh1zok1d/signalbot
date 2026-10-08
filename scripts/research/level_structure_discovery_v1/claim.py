"""Successor rule and routing. Cuts were fixed before outcomes.

The screened object is Δ = β_real − β_pseudo. A large real slope that also appears at
the rotated price is not a level-specific candidate. The approach unit's 70% DAY cap
is not a clause here.
"""

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


def notable_delta(cell: dict) -> bool:
    coef = cell.get("delta")
    return coef is not None and abs(coef) >= K.PRACTICAL_SCALE and _excludes_zero(cell.get("delta_ci95"))


def notable_real(cell: dict) -> bool:
    coef = cell.get("beta_real")
    return coef is not None and abs(coef) >= K.PRACTICAL_SCALE and _excludes_zero(cell.get("beta_real_ci95"))


def _eligible_same(rows: list[dict], key: str, sign: int) -> tuple[int, int]:
    eligible = [
        row for row in rows
        if row.get("n_real", 0) >= K.YEAR_MIN_N and row.get("n_pseudo", 0) >= K.YEAR_MIN_N and row.get(key) is not None
    ]
    same = [row for row in eligible if _sign(row.get(key)) == sign]
    return len(eligible), len(same)


def successor_ok(*, primary: dict, years: list[dict], loyo: list[dict], families: list[dict],
                 lofo: list[dict], no_touch: dict, q: Optional[float]) -> bool:
    """Every clause has to hold. Low-N family drops are not an automatic failure."""
    delta = primary.get("delta")
    sign = _sign(delta)
    if delta is None or sign == 0 or abs(delta) < K.PRACTICAL_SCALE:
        return False
    if not _excludes_zero(primary.get("delta_ci95")):
        return False
    if q is None or q > K.FDR_Q:
        return False
    real_sign = _sign(primary.get("beta_real"))
    if real_sign == 0:
        return False
    _, real_same = _eligible_same(years, "beta_real", real_sign)
    if real_same < K.YEAR_SIGN_MIN:
        return False
    _, delta_same = _eligible_same(years, "delta", sign)
    if delta_same < K.YEAR_SIGN_MIN:
        return False
    fam_eligible, fam_same = _eligible_same(families, "delta", sign)
    if fam_eligible >= 2 and fam_same < K.FAMILY_SIGN_MIN:
        return False
    if len(loyo) != len(K.YEARS):
        return False
    if any(_sign(row.get("delta")) != sign for row in loyo):
        return False
    for row in lofo:
        if row.get("n_real", 0) < K.LOFO_MIN_N or row.get("n_pseudo", 0) < K.LOFO_MIN_N:
            continue
        if _sign(row.get("delta")) != sign:
            return False
    # Touch-number duplicate: the claim is the touch-adjusted Δ. It fails when dropping the
    # touch dummies produces a large increment of the opposite sign, so the adjusted
    # slope is fighting the known touch-ordinal pattern rather than sitting above it.
    bare = no_touch.get("delta")
    if (bare is not None and abs(bare) >= K.PRACTICAL_SCALE and _excludes_zero(no_touch.get("delta_ci95"))
            and _sign(bare) != sign):
        return False
    return True


def routing_status(n_candidates: int, primary: list[dict], no_touch: list[dict], *, sparse_note: bool) -> str:
    if n_candidates:
        return "LEVEL_SPECIFIC_STRUCTURE_PRESENT"
    if any(notable_delta(cell) for cell in primary):
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if any(notable_real(cell) for cell in primary):
        return "NO_LEVEL_SPECIFIC_STRUCTURE"
    if any(notable_delta(cell) for cell in no_touch):
        return "REDUNDANT_WITH_KNOWN_STATE"
    if sparse_note:
        return "INFORMATION_LIMITED"
    return "NO_LEVEL_SPECIFIC_STRUCTURE"


def atlas_state(status: str) -> str:
    if status in ("NO_LEVEL_SPECIFIC_STRUCTURE", "REDUNDANT_WITH_KNOWN_STATE", "INFORMATION_LIMITED"):
        return "NO_STRUCTURE"
    return "CLOSED_ON_SURFACE"


def claim_level(status: str, n: int) -> str:
    if status == "LEVEL_SPECIFIC_STRUCTURE_PRESENT":
        return "DISCOVERY_ONLY"
    if n >= K.L2_MIN_N:
        return "L2"
    return "not_issued"
