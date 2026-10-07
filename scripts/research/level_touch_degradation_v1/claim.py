"""Predeclared reading rule. It does not choose a contrast after seeing which one moved.

PRODUCT_INTEGRATION_CANDIDATE is YES only when every check below is true. Otherwise NO.
The claim ceiling stays L2. This module does not emit a verdict word.
"""

from __future__ import annotations

import math
from typing import Optional

from . import constants as K


def _excludes_zero(ci) -> bool:
    if not ci or len(ci) != 2:
        return False
    lo, hi = ci
    if lo is None or hi is None or not math.isfinite(lo) or not math.isfinite(hi):
        return False
    return hi < 0 or lo > 0


def _sign(x: Optional[float]) -> int:
    if x is None or not math.isfinite(x) or x == 0:
        return 0
    return 1 if x > 0 else -1


def integration_candidate(*, d2: Optional[float], d3: Optional[float], ci3, control_d3: Optional[float],
                          control_ci3, year_d3: dict, year_n: dict, max_year_share: Optional[float],
                          max_family_share_touch3: Optional[float], weeks: int) -> dict:
    """year_d3 maps year -> crude Δ(3+−1); year_n maps year -> (n1, n3)."""
    scale = K.PRACTICAL_SCALE
    sign3 = _sign(d3)
    same_sign_2 = _sign(d2) == sign3 and _sign(d2) != 0
    years_ok = 0
    years_used = 0
    for year in K.YEARS:
        n1, n3 = year_n.get(year, (0, 0))
        if n1 < K.YEAR_MIN_ARM or n3 < K.YEAR_MIN_ARM:
            continue
        years_used += 1
        if _sign(year_d3.get(year)) == sign3 and sign3 != 0:
            years_ok += 1
    control_weaker = False
    if d3 is not None and control_d3 is not None and abs(d3) > 0:
        control_weaker = abs(control_d3) < K.CONTROL_HALF * abs(d3) or _excludes_zero(control_ci3) is False
    # "interval includes 0" is the second arm. A missing control interval does not count as includes-0.
    if control_ci3 is None:
        control_weaker = bool(d3 is not None and control_d3 is not None and abs(d3) > 0
                              and abs(control_d3) < K.CONTROL_HALF * abs(d3))
    checks = {
        "abs_d3_at_least_scale_and_ci_excludes_0": bool(
            d3 is not None and abs(d3) >= scale and _excludes_zero(ci3)),
        "d2_same_sign_as_d3": bool(same_sign_2),
        "year_signs": bool(years_ok >= K.YEAR_SIGN_MIN),
        "years_with_both_arms": years_used,
        "years_same_sign": years_ok,
        "control_not_the_same_pattern": bool(control_weaker),
        "year_share_within_cap": bool(max_year_share is not None and max_year_share <= K.MAX_YEAR_SHARE),
        "touch3_family_share_within_cap": bool(
            max_family_share_touch3 is not None and max_family_share_touch3 <= K.MAX_FAMILY_SHARE_TOUCH3),
        "week_clusters": bool(weeks >= K.MIN_WEEKS_READING),
    }
    return {"candidate": all(checks.values()), "checks": checks}


def both_near_zero(d2, ci2, d3, ci3) -> bool:
    """The predeclared 'no practically large difference' reading. Not a verdict label."""
    def _near(d, ci):
        if d is None or ci is None:
            return False
        return abs(d) < K.PRACTICAL_SCALE and not _excludes_zero(ci)
    return bool(_near(d2, ci2) and _near(d3, ci3))


def l2_line_allowed(n_ref: int, n_cmp: int, ci) -> bool:
    return bool(n_ref >= K.YEAR_MIN_ARM and n_cmp >= K.YEAR_MIN_ARM and ci is not None)
