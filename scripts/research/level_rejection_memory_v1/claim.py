"""Predeclared reading of the primary coefficient. Not a verdict word."""

from __future__ import annotations

from typing import Optional

from . import constants as K


def _excludes_zero(ci) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return ci[1] < 0 or ci[0] > 0


def _sign(x: Optional[float]) -> int:
    if x is None or x == 0:
        return 0
    return 1 if x > 0 else -1


def both_near_zero(coef: Optional[float], ci) -> bool:
    if coef is None or ci is None:
        return False
    return abs(coef) < K.PRACTICAL_SCALE and not _excludes_zero(ci)


def integration_candidate(primary: dict, years: list[dict], control: dict, *,
                          max_year_share: float, max_family_share: float,
                          clusters: int) -> dict:
    """YES only when every predeclared check holds. Otherwise NO.

    `years` are the within-year primary coefficients, one per calendar year in order.
    A year with n < YEAR_MIN_N does not count toward the sign tally.
    """
    coef = primary.get("coef")
    ci = primary.get("ci95")
    scale = coef is not None and abs(coef) >= K.PRACTICAL_SCALE and _excludes_zero(ci)
    eligible = [y for y in years if y.get("n", 0) >= K.YEAR_MIN_N and y.get("coef") is not None]
    same = sum(1 for y in eligible if _sign(y["coef"]) == _sign(coef) and _sign(coef) != 0)
    year_ok = same >= K.YEAR_SIGN_MIN
    c_coef = control.get("coef")
    c_ci = control.get("ci95")
    if c_coef is None or coef is None:
        control_ok = False
    elif c_ci is None:
        control_ok = abs(c_coef) < K.CONTROL_HALF * abs(coef)
    else:
        control_ok = abs(c_coef) < K.CONTROL_HALF * abs(coef) or not _excludes_zero(c_ci)
    share_ok = max_year_share <= K.MAX_YEAR_SHARE and max_family_share <= K.MAX_FAMILY_SHARE
    cluster_ok = clusters >= K.MIN_CLUSTERS
    checks = {
        "abs_coef_at_least_scale_and_ci_excludes_0": scale,
        "year_signs": year_ok,
        "years_eligible": len(eligible),
        "years_same_sign": same,
        "control_not_the_same_pattern": control_ok,
        "year_share_within_cap": max_year_share <= K.MAX_YEAR_SHARE,
        "family_share_within_cap": max_family_share <= K.MAX_FAMILY_SHARE,
        "clusters": cluster_ok,
    }
    candidate = bool(scale and year_ok and control_ok and share_ok and cluster_ok)
    return {"candidate": candidate, "checks": checks}


def l2_allowed(n: int, ci) -> bool:
    return n >= K.L2_MIN_N and ci is not None and ci[0] is not None
