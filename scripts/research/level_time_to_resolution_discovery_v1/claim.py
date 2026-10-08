"""Candidate rule for the paired unresolved-time difference. Frozen before outcomes."""

from __future__ import annotations

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


def excludes_zero(ci) -> bool:
    if not ci or ci[0] is None or ci[1] is None:
        return False
    return float(ci[0]) > 0.0 or float(ci[1]) < 0.0


def material(delta) -> bool:
    return delta is not None and abs(float(delta)) >= K.PRACTICAL_MIN


def year_stability(full_delta, epochs: list[dict]) -> dict:
    full = _sign(full_delta)
    eligible = [
        item for item in epochs
        if int(item.get("n") or 0) >= K.SLICE_MIN_N and item.get("delta") is not None
    ]
    matched = [item for item in eligible if _sign(item.get("delta")) == full and full != 0]
    n_eligible = len(eligible)
    if full == 0 or n_eligible < 3:
        ok = False
    elif n_eligible >= 5:
        ok = len(matched) >= K.YEAR_SIGN_MIN_OF_FIVE
    elif n_eligible == 4:
        ok = len(matched) >= 3
    else:
        ok = len(matched) == n_eligible
    return {"pass": ok, "n_eligible": n_eligible, "n_matched": len(matched)}


def loyo_stability(full_delta, rows: list[dict]) -> dict:
    full = _sign(full_delta)
    checked = [item for item in rows if int(item.get("n") or 0) >= K.SLICE_MIN_N]
    if full == 0 or len(checked) < 3:
        return {"pass": False, "n_checked": len(checked)}
    ok = all(item.get("delta") is not None and _sign(item.get("delta")) == full for item in checked)
    return {"pass": ok, "n_checked": len(checked)}


def _strong_opposite(left: dict, right: dict) -> bool:
    if int(left.get("n") or 0) < K.SLICE_MIN_N or int(right.get("n") or 0) < K.SLICE_MIN_N:
        return False
    if left.get("delta") is None or right.get("delta") is None:
        return False
    if _sign(left["delta"]) * _sign(right["delta"]) >= 0:
        return False
    return abs(float(left["delta"])) >= K.PRACTICAL_MIN and abs(float(right["delta"])) >= K.PRACTICAL_MIN


def family_stability(rows: list[dict]) -> dict:
    by_name = {item["name"]: item for item in rows}
    day, week = by_name.get("DAY"), by_name.get("WEEK")
    if day is None or week is None:
        return {"pass": True, "strong_opposite": False}
    opposite = _strong_opposite(day, week)
    return {"pass": not opposite, "strong_opposite": opposite}


def side_stability(rows: list[dict]) -> dict:
    by_name = {item["name"]: item for item in rows}
    resistance, support = by_name.get("resistance"), by_name.get("support")
    if resistance is None or support is None:
        return {"pass": True, "strong_opposite": False}
    opposite = _strong_opposite(resistance, support)
    return {"pass": not opposite, "strong_opposite": opposite}


def information_limited(n: int, ci) -> bool:
    if n < K.INFORMATION_MIN_N:
        return True
    if not ci or ci[0] is None or ci[1] is None:
        return True
    return (float(ci[1]) - float(ci[0])) > K.INFORMATION_CI_WIDTH


def candidate_pass(delta, ci, *, years_ok: bool, loyo_ok: bool, family_ok: bool,
                   side_ok: bool, artifact: bool, n: int) -> bool:
    if artifact or n < K.MATCHED_GATE:
        return False
    if not material(delta) or not excludes_zero(ci):
        return False
    return bool(years_ok and loyo_ok and family_ok and side_ok)


def route(*, novelty_ok: bool, gate_pass: bool, candidate: bool, material_effect: bool,
          ci_excludes_0: bool, stable: bool, info_limited: bool) -> str:
    if not novelty_ok:
        return "BLOCKED_REOPENING_TIME_TO_RESOLUTION_CELL"
    if not gate_pass:
        return "INFORMATION_LIMITED"
    if candidate:
        return "LEVEL_RESOLUTION_CLOCK_STRUCTURE_PRESENT"
    if material_effect and ci_excludes_0 and not stable:
        return "STRUCTURE_PRESENT_BUT_UNSTABLE"
    if info_limited:
        return "INFORMATION_LIMITED"
    return "GENERIC_OR_NO_RESOLUTION_CLOCK_DIFFERENCE"
